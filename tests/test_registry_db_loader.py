import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import copy, hashlib, json, os, shutil, sqlite3, tempfile, unittest
from registry_db import loader, receipts, migrate, api, writer
from registry_db_fixtures import write_raw, H1, H2
import ingest_snapshot_helper as helper

def dump(db):
    c = sqlite3.connect(db)
    return "\n".join(c.iterdump())

class LoaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self.raw = os.path.join(self.tmp, "raw"); write_raw(self.raw)
        self.snap = helper.build(self.raw, self.tmp); self.db = os.path.join(self.tmp, "r.db")
    def tearDown(self): shutil.rmtree(self.tmp)
    def q(self, sql, *a): return sqlite3.connect(self.db).execute(sql, a).fetchall()

    def test_snapshot_is_deterministic(self):
        s2 = helper.build(self.raw, self.tmp)
        self.assertEqual(self.snap["meta"]["snapshot_sha256"], s2["meta"]["snapshot_sha256"])

    def test_from_zero_load_and_alignment_classification(self):
        r = loader.load(self.db, self.snap); self.assertEqual(r["status"], "complete")
        st = dict(self.q("SELECT asset_id, alignment_state FROM asset_alignment"))
        self.assertEqual(st["github_repo:szl-holdings/core"], "aligned")                         # authority
        self.assertEqual(st["hf_space:SZLHOLDINGS/core-space"], "behind")                        # sync pin H1 is an ancestor of head H2 (compare=ahead)
        self.assertEqual(st["hf_model:SZLHOLDINGS/no-source"], "untraceable")                    # built artifact, no binding
        self.assertEqual(st["hf_model:SZLHOLDINGS/declared-model"], "unknown")                   # asset-map declaration only
        self.assertEqual(st["hf_model:SZLHOLDINGS/orphan-ref"], "unknown")                       # text reference only
        self.assertEqual(st["pypi_project:pypi/szl-core"], "unknown")                            # declared via pyproject, no provenance
        self.assertEqual(st["cf_worker:cloudflare/core-worker"], "unknown")                      # wrangler declares source repo
        self.assertEqual(st["cf_worker:cloudflare/stray-worker"], "untraceable")                 # no source
        self.assertTrue(all(s in ("aligned", "behind", "untraceable", "unknown") for s in st.values()))
        self.assertEqual(len(st), len(self.snap["assets"]))

    def test_sync_pin_equal_to_head_is_aligned(self):
        write_raw(self.raw, hf_pin=H2, repo_head=H2); snap = helper.build(self.raw, self.tmp)
        loader.load(self.db, snap)
        self.assertEqual(self.q("SELECT alignment_state FROM asset_alignment WHERE asset_id='hf_space:SZLHOLDINGS/core-space'")[0][0], "aligned")

    def test_pin_not_found_upstream_is_untraceable(self):
        write_raw(self.raw, with_compare=False)
        import json as j; p = os.path.join(self.raw, "github", "compare.json")
        j.dump({"pairs": {f"core@{H1}...{H2}": {"status": "not_found"}}}, open(p, "w")); snap = helper.build(self.raw, self.tmp)
        loader.load(self.db, snap)
        self.assertEqual(self.q("SELECT alignment_state FROM asset_alignment WHERE asset_id='hf_space:SZLHOLDINGS/core-space'")[0][0], "untraceable")

    def test_every_fact_and_binding_has_observed_at_and_evidence(self):
        loader.load(self.db, self.snap)
        for t in ("assets", "asset_facts", "asset_revisions", "source_bindings", "asset_alignment", "candidate_refs"):
            self.assertEqual(self.q(f"SELECT COUNT(*) FROM {t} WHERE observed_at IS NULL OR observed_at='' OR evidence_path IS NULL OR evidence_path=''" if t != "assets" else "SELECT COUNT(*) FROM assets WHERE observed_at='' OR evidence_path=''")[0][0], 0, t)

    def test_source_binding_columns_per_asset_kind(self):
        loader.load(self.db, self.snap)
        rev = dict((r[0], r[1:]) for r in self.q("SELECT asset_id, revision_kind, revision, digest_sha256, digest_filename FROM asset_revisions"))
        self.assertEqual(rev["github_repo:szl-holdings/core"][:2], ("git_sha", H2))
        self.assertEqual(rev["hf_space:SZLHOLDINGS/core-space"][:2], ("hf_revision", "d" * 40))
        self.assertEqual(rev["pypi_project:pypi/szl-core"], ("pypi_release", "szl-core==0.2.0", "e" * 64, "szl_core-0.2.0.tar.gz"))   # name==version + sha256 (sdist preferred)
        self.assertEqual(rev["cf_worker:cloudflare/core-worker"][0], "worker_etag"); self.assertEqual(rev["cf_worker:cloudflare/core-worker"][2], "0" * 64)

    def test_private_repo_content_is_not_scanned_or_copied(self):
        loader.load(self.db, self.snap)
        f = dict(self.q("SELECT key, value_json FROM asset_facts WHERE asset_id='github_repo:szl-holdings/secret'"))
        self.assertEqual(json.loads(f["content_scanned"]), False); self.assertNotIn("description", f)

    def test_reingest_same_snapshot_is_a_noop(self):
        loader.load(self.db, self.snap); before = dump(self.db)
        r = loader.load(self.db, self.snap); self.assertEqual(r["status"], "already_ingested")
        self.assertEqual(dump(self.db), before)

    def test_reingest_with_new_observation_and_identical_values_adds_no_history(self):
        loader.load(self.db, self.snap)
        s2 = copy.deepcopy(self.snap)
        for a in s2["assets"]: a["observed_at"] = "2026-11-20T00:00:00Z"
        s2["meta"]["observed"]["github"] = "2026-11-20T00:00:00Z"; s2["meta"].pop("snapshot_sha256")
        r = loader.load(self.db, s2)
        self.assertEqual(r["status"], "complete"); self.assertEqual(r["stats"]["facts_changed"], 0)
        self.assertEqual(self.q("SELECT COUNT(*) FROM asset_fact_history")[0][0], 0)
        self.assertEqual(self.q("SELECT COUNT(*) FROM assets")[0][0], len(self.snap["assets"]))          # no duplicates
        self.assertEqual(self.q("SELECT observed_at FROM assets WHERE asset_id='github_repo:szl-holdings/core'")[0][0], "2026-11-20T00:00:00Z")
        self.assertTrue(receipts.verify_chain(sqlite3.connect(self.db))["ok"])

    def test_changed_fact_is_recorded_in_history_and_absent_asset_is_not_deleted(self):
        loader.load(self.db, self.snap)
        s2 = copy.deepcopy(self.snap); s2["meta"].pop("snapshot_sha256")
        core = next(a for a in s2["assets"] if a["asset_id"] == "github_repo:szl-holdings/core"); core["facts"]["open_prs"] = 99
        s2["assets"] = [a for a in s2["assets"] if a["asset_id"] != "hf_model:SZLHOLDINGS/no-source"]
        s2["bindings"] = [b for b in s2["bindings"] if b["asset_id"] != "hf_model:SZLHOLDINGS/no-source"]
        r = loader.load(self.db, s2); self.assertEqual(r["stats"]["assets_absent"], 1)
        h = self.q("SELECT old_value_json, new_value_json FROM asset_fact_history WHERE asset_id='github_repo:szl-holdings/core' AND key='open_prs'")
        self.assertEqual(h, [("1", "99")])
        self.assertEqual(self.q("SELECT lifecycle FROM assets WHERE asset_id='hf_model:SZLHOLDINGS/no-source'")[0][0], "absent")
        self.assertEqual(self.q("SELECT COUNT(*) FROM receipts WHERE action='ingest.run'")[0][0], 2)

    def test_load_is_atomic_on_failure(self):
        bad = copy.deepcopy(self.snap); bad["meta"].pop("snapshot_sha256")
        bad["bindings"].append({"asset_id": "hf_model:SZLHOLDINGS/no-source", "upstream_asset_id": "github_repo:szl-holdings/does-not-exist", "kind": "declared_map", "grade": "declared", "pinned_ref": None,
                                "upstream_head": None, "compare_status": None, "observed_at": "t", "evidence_path": "x"})
        with self.assertRaises(sqlite3.IntegrityError): loader.load(self.db, bad)
        self.assertEqual(self.q("SELECT COUNT(*) FROM assets")[0][0], 0); self.assertEqual(self.q("SELECT COUNT(*) FROM ingest_runs")[0][0], 0)

    def test_tampered_snapshot_hash_rejected(self):
        bad = copy.deepcopy(self.snap); bad["assets"][0]["name"] = "evil"
        with self.assertRaisesRegex(ValueError, "does not match"): loader.load(self.db, bad)

    def test_coverage_report_expected_vs_ingested(self):
        loader.load(self.db, self.snap)
        rows = {r[0]: r[1:] for r in self.q("SELECT source||':'||asset_type, expected_count, ingested_count, missing_count FROM coverage_reports")}
        self.assertEqual(rows["github:github_repo"], (2, 2, 0)); self.assertEqual(rows["hf:hf_model"], (3, 3, 0))
        self.assertEqual(rows["pypi:pypi_project"][0:2], (2, 1))      # 1 candidate is 404 on PyPI -> reported missing, not dropped

class ProposalFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); raw = os.path.join(self.tmp, "raw"); write_raw(raw)
        self.db = os.path.join(self.tmp, "r.db"); loader.load(self.db, helper.build(raw, self.tmp)); self.ob = os.path.join(self.tmp, "outbox")
    def tearDown(self): shutil.rmtree(self.tmp)

    def test_propose_writes_outbox_only_then_writer_files_under_receipt_then_human_decides(self):
        ro = api.connect_ro(self.db); h0 = hashlib.sha256(open(self.db, "rb").read()).hexdigest()
        p = api.propose_update(self.ob, ro, actor="agent:chakana", asset_id="hf_model:SZLHOLDINGS/no-source", change_kind="set_fact",
                               proposed={"key": "agent.source_repo", "value": "szl-forge"}, reason="card says authored in szl-forge")
        self.assertEqual(hashlib.sha256(open(self.db, "rb").read()).hexdigest(), h0)               # DB untouched by the API path
        self.assertEqual(writer.apply_outbox(self.db, self.ob), [p["proposal_id"]])
        self.assertEqual(writer.apply_outbox(self.db, self.ob), [])                                # idempotent
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("SELECT status FROM proposals").fetchone()[0], "pending")
        writer.decide(self.db, p["proposal_id"], accept=True, decider="human:stephen", reason="reviewed evidence")
        self.assertEqual(c.execute("SELECT value_json, evidence_path FROM asset_facts WHERE key='agent.source_repo'").fetchone(), ('"szl-forge"', f"proposal:{p['proposal_id']}"))
        self.assertEqual([r[0] for r in c.execute("SELECT action FROM receipts ORDER BY seq")], ["ingest.run", "proposal.create", "proposal.accept"])
        self.assertTrue(receipts.verify_chain(c)["ok"])
        with self.assertRaisesRegex(ValueError, "already"): writer.decide(self.db, p["proposal_id"], accept=False, decider="h", reason="r")

    def test_agent_facts_survive_next_ingest(self):
        ro = api.connect_ro(self.db)
        p = api.propose_update(self.ob, ro, actor="agent:a", asset_id="hf_model:SZLHOLDINGS/no-source", change_kind="set_fact", proposed={"key": "agent.note", "value": 1}, reason="r")
        writer.apply_outbox(self.db, self.ob); writer.decide(self.db, p["proposal_id"], accept=True, decider="human:s", reason="ok")
        raw = os.path.join(self.tmp, "raw2"); write_raw(raw, hf_pin="3" * 40); snap = helper.build(raw, self.tmp)
        self.assertEqual(loader.load(self.db, snap)["status"], "complete")
        self.assertEqual(sqlite3.connect(self.db).execute("SELECT COUNT(*) FROM asset_facts WHERE key='agent.note'").fetchone()[0], 1)

    def test_invalid_proposals_rejected(self):
        ro = api.connect_ro(self.db)
        for kw in ({"change_kind": "delete"}, {"asset_id": "nope:x"}, {"reason": " "}, {"change_kind": "set_fact", "proposed": {"key": "head_sha", "value": "x"}}):
            args = dict(actor="agent:a", asset_id="hf_model:SZLHOLDINGS/no-source", change_kind="set_binding", proposed={}, reason="r"); args.update(kw)
            with self.assertRaises(ValueError): api.propose_update(self.ob, ro, **args)

if __name__ == "__main__":
    unittest.main()
