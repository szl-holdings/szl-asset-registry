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
        self.assertEqual(st["github_repo:szl-holdings/core"], "ALIGNED")                         # authority
        self.assertEqual(st["hf_space:SZLHOLDINGS/core-space"], "BEHIND")                        # sync pin H1 is an ancestor of head H2 (compare=ahead)
        self.assertEqual(st["hf_model:SZLHOLDINGS/no-source"], "UNTRACEABLE")                    # built artifact, no binding
        self.assertEqual(st["hf_model:SZLHOLDINGS/declared-model"], "UNKNOWN")                   # asset-map declaration only
        self.assertEqual(st["hf_model:SZLHOLDINGS/orphan-ref"], "UNKNOWN")                       # text reference only
        self.assertEqual(st["pypi_project:pypi/szl-core"], "BEHIND")                            # declared via pyproject, no provenance
        self.assertEqual(st["cf_worker:cloudflare/core-worker"], "UNKNOWN")                      # wrangler declares source repo
        self.assertEqual(st["cf_worker:cloudflare/stray-worker"], "UNTRACEABLE")                 # no source
        self.assertTrue(all(s in ("ALIGNED", "BEHIND", "DRIFTED", "UNTRACEABLE", "UNKNOWN") for s in st.values()))
        self.assertEqual(len(st), len(self.snap["assets"]))

    def test_sync_pin_equal_to_head_is_aligned(self):
        write_raw(self.raw, hf_pin=H2, repo_head=H2); snap = helper.build(self.raw, self.tmp)
        loader.load(self.db, snap)
        self.assertEqual(self.q("SELECT alignment_state FROM asset_alignment WHERE asset_id='hf_space:SZLHOLDINGS/core-space'")[0][0], "ALIGNED")

    def test_pin_not_found_upstream_is_untraceable(self):
        write_raw(self.raw, with_compare=False)
        import json as j; p = os.path.join(self.raw, "github", "compare.json")
        j.dump({"pairs": {f"core@{H1}...{H2}": {"status": "not_found"}}}, open(p, "w")); snap = helper.build(self.raw, self.tmp)
        loader.load(self.db, snap)
        self.assertEqual(self.q("SELECT alignment_state FROM asset_alignment WHERE asset_id='hf_space:SZLHOLDINGS/core-space'")[0][0], "UNTRACEABLE")

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
        self.assertEqual(rev["cf_worker:cloudflare/core-worker"], ("worker_etag", "0" * 64, "0" * 64, "deployed-etag"))

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
        self.assertEqual(self.q("SELECT lifecycle FROM assets WHERE asset_id='hf_model:SZLHOLDINGS/no-source'")[0][0], "ABSENT")
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


    def test_source_binding_json_pin_columns_and_pages_project(self):
        loader.load(self.db, self.snap)
        rows = self.q("SELECT binding_kind, binding_grade, pin_repository, pin_revision, pin_target FROM source_bindings WHERE asset_id='hf_space:SZLHOLDINGS/core-space' AND binding_kind='source_binding_json'")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "source_binding_json")
        self.assertEqual(rows[0][1], "verified_pin")
        self.assertEqual(rows[0][2], "szl-holdings/core")
        self.assertEqual(rows[0][4], "SZLHOLDINGS/core-space")
        self.assertEqual(self.q("SELECT asset_type, name FROM assets WHERE asset_id='cf_pages_project:cloudflare/szl-portal'")[0], ("cf_pages_project", "szl-portal"))
        # pages has no source binding -> UNTRACEABLE
        self.assertEqual(self.q("SELECT alignment_state FROM asset_alignment WHERE asset_id='cf_pages_project:cloudflare/szl-portal'")[0][0], "UNTRACEABLE")

    def test_worker_external_id_is_script_tag(self):
        loader.load(self.db, self.snap)
        self.assertEqual(self.q("SELECT external_id, visibility FROM assets WHERE asset_id='cf_worker:cloudflare/core-worker'")[0], ("tag-core-worker", "UNKNOWN"))

    def test_pypi_external_id_is_pep503_and_pep740_binding(self):
        loader.load(self.db, self.snap)
        self.assertEqual(self.q("SELECT external_id FROM assets WHERE asset_id='pypi_project:pypi/szl-core'")[0][0], "szl-core")
        kind, grade, state = self.q("SELECT binding_kind, binding_grade, alignment_state FROM source_bindings WHERE asset_id='pypi_project:pypi/szl-core' AND binding_kind='pep740_attestation'")[0]
        self.assertEqual((kind, grade, state), ("pep740_attestation", "verified_pin", "BEHIND"))

    def test_vanished_asset_keeps_visibility_and_unknown_alignment(self):
        loader.load(self.db, self.snap)
        vis = self.q("SELECT visibility FROM assets WHERE asset_id='hf_model:SZLHOLDINGS/no-source'")[0][0]
        s2 = __import__("copy").deepcopy(self.snap); s2["meta"].pop("snapshot_sha256")
        s2["assets"] = [a for a in s2["assets"] if a["asset_id"] != "hf_model:SZLHOLDINGS/no-source"]
        s2["bindings"] = [b for b in s2["bindings"] if b["asset_id"] != "hf_model:SZLHOLDINGS/no-source"]
        loader.load(self.db, s2)
        row = self.q("SELECT visibility, lifecycle FROM assets WHERE asset_id='hf_model:SZLHOLDINGS/no-source'")[0]
        self.assertEqual(row, (vis, "ABSENT"))
        self.assertEqual(self.q("SELECT alignment_state FROM asset_alignment WHERE asset_id='hf_model:SZLHOLDINGS/no-source'")[0][0], "UNKNOWN")

    def test_coverage_gap_when_listing_is_not_authoritative(self):
        loader.load(self.db, self.snap)
        s2 = __import__("copy").deepcopy(self.snap); s2["meta"].pop("snapshot_sha256")
        s2["assets"] = [a for a in s2["assets"] if a["asset_id"] != "hf_model:SZLHOLDINGS/no-source"]
        s2["bindings"] = [b for b in s2["bindings"] if b["asset_id"] != "hf_model:SZLHOLDINGS/no-source"]
        for c in s2["coverage"]:
            if c["asset_type"] == "hf_model":
                c["listing_authoritative"] = False
                c["ingested"] = 2
                c.setdefault("detail", {})["listing_authoritative"] = False
        r = loader.load(self.db, s2)
        self.assertEqual(r["stats"]["assets_coverage_gap"], 1)
        self.assertEqual(self.q("SELECT lifecycle FROM assets WHERE asset_id='hf_model:SZLHOLDINGS/no-source'")[0][0], "COVERAGE_GAP")

    def test_off_org_pypi_is_coverage_gap(self):
        import json as j
        inv = j.load(open(os.path.join(self.raw, "pypi/pypi_inventory.json")))
        inv["projects"]["szl-off"] = {"exists": True, "name": "szl-off", "latest": "0.1.0", "n_releases": 1, "versions": ["0.1.0"],
            "summary": "s", "project_urls": {"Source": "https://github.com/szl-holdings/core"}, "org_linked": False,
            "observed_at": "2026-11-19T12:00:00Z", "files": [{"filename": "szl_off-0.1.0.tar.gz", "sha256": "c" * 64, "upload_time": "2026-11-19T12:00:00Z"}]}
        j.dump(inv, open(os.path.join(self.raw, "pypi/pypi_inventory.json"), "w"))
        # declare via pyproject so it is admitted
        refs = j.load(open(os.path.join(self.raw, "github/candidate_bindings.json")))
        refs["refs"].append({"repo": "core", "kind": "pypi", "target_type": "project", "target_id": "szl-off",
                             "evidence_path": "core:pyproject.toml#project.name", "snippet": "name=szl-off version=0.1.0"})
        j.dump(refs, open(os.path.join(self.raw, "github/candidate_bindings.json"), "w"))
        snap = helper.build(self.raw, self.tmp)
        loader.load(self.db, snap)
        life, vis, own = self.q("SELECT lifecycle, visibility, (SELECT value_json FROM asset_facts WHERE asset_id='pypi_project:pypi/szl-off' AND key='ownership') FROM assets WHERE asset_id='pypi_project:pypi/szl-off'")[0]
        self.assertEqual(life, "COVERAGE_GAP")
        self.assertEqual(json.loads(own), "UNKNOWN")

    def test_absent_row_from_gone_probe_keeps_nov19_visibility(self):
        import json as j
        obs = "2026-11-19T12:00:00Z"
        j.dump({"observed_at": "2026-11-27T02:07:11Z", "probes": {"model:SZLHOLDINGS/gone-pub": {"http": 404}, "model:SZLHOLDINGS/gone-priv": {"http": 404}}},
               open(os.path.join(self.raw, "hf/gone_probes.json"), "w"))
        j.dump({"kinds": {"model": {"items": [
            {"id": "SZLHOLDINGS/gone-pub", "sha": "e" * 40, "private": False, "lastModified": obs, "_id": "id-pub"},
            {"id": "SZLHOLDINGS/gone-priv", "sha": "f" * 40, "private": True, "lastModified": obs, "_id": "id-priv"},
        ]}}}, open(os.path.join(self.raw, "hf/nov19_hf_inventory.json"), "w"))
        snap = helper.build(self.raw, self.tmp)
        loader.load(self.db, snap)
        rows = dict(self.q("SELECT name, visibility||':'||lifecycle||':'||(SELECT alignment_state FROM asset_alignment WHERE asset_id=assets.asset_id) FROM assets WHERE name IN ('gone-pub','gone-priv')"))
        self.assertEqual(rows["gone-pub"], "public:ABSENT:UNKNOWN")
        self.assertEqual(rows["gone-priv"], "private:ABSENT:UNKNOWN")

    def test_excluded_third_party_pypi_not_ingested(self):
        import json as j
        inv = j.load(open(os.path.join(self.raw, "pypi/pypi_inventory.json")))
        for n in ("anatomy", "ollm", "the-grid"):
            inv["projects"][n] = {"exists": True, "name": n, "latest": "1.0.0", "n_releases": 1, "versions": ["1.0.0"],
                "org_linked": False, "observed_at": "2026-11-19T12:00:00Z", "files": []}
        j.dump(inv, open(os.path.join(self.raw, "pypi/pypi_inventory.json"), "w"))
        snap = helper.build(self.raw, self.tmp)
        loader.load(self.db, snap)
        self.assertEqual(self.q("SELECT COUNT(*) FROM assets WHERE name IN ('anatomy','ollm','the-grid')")[0][0], 0)

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
