"""Load a snapshot into the registry SQLite/D1-schema database (the single writer).

* idempotent: run_id = first 16 hex of the snapshot sha256; re-loading the same snapshot is a no-op
* upserts keyed on stable ids (assets.asset_id, (asset_id,key) facts, ...); unchanged facts only bump observed_at
* changed facts are captured by the history trigger; vanished assets become lifecycle='absent' (never deleted)
* one transaction; one 'ingest.run' receipt per run
No network. No remote writes: the target is a local SQLite file.
"""
import hashlib, json, sqlite3, sys
from . import migrate, receipts, alignment, __version__

def canon(v): return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def snapshot_hash(snap):
    s = {k: v for k, v in snap.items()}
    s["meta"] = {k: v for k, v in snap["meta"].items() if k != "snapshot_sha256"}
    return hashlib.sha256(canon(s).encode()).hexdigest()

def load(db_path, snapshot, *, actor="ingest:registry_db.loader", reason=None, snapshot_path=None, now=None):
    sha = snapshot["meta"].get("snapshot_sha256") or snapshot_hash(snapshot)
    if snapshot["meta"].get("snapshot_sha256") and snapshot_hash(snapshot) != sha:
        raise ValueError("snapshot sha256 does not match content")
    migrate.apply(db_path)
    run_id = sha[:16]
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        if conn.execute("SELECT 1 FROM ingest_runs WHERE run_id=?", (run_id,)).fetchone():
            return {"run_id": run_id, "status": "already_ingested", "changed": False}
        started = receipts.utcnow() if now is None else now
        conn.execute("BEGIN IMMEDIATE")
        obs_max = max([v for v in snapshot["meta"]["observed"].values() if v] or [started])
        conn.execute("INSERT INTO ingest_runs (run_id, source, started_at, snapshot_sha256, snapshot_path, tool_version, status) VALUES (?,?,?,?,?,?,?)",
                     (run_id, "all", started, sha, snapshot_path, __version__, "running"))
        stats = {"assets_new": 0, "assets_updated": 0, "assets_absent": 0, "assets_coverage_gap": 0, "facts_changed": 0}
        seen = set()
        types_in_snapshot = {a["asset_type"] for a in snapshot["assets"]}
        coverage_by_type = {c["asset_type"]: c for c in snapshot.get("coverage") or []}
        for a in snapshot["assets"]:
            seen.add(a["asset_id"])
            old = conn.execute("SELECT 1 FROM assets WHERE asset_id=?", (a["asset_id"],)).fetchone()
            life = alignment.norm_lifecycle(a.get("lifecycle") or "PRESENT")
            vis = alignment.norm_visibility(a["visibility"])
            conn.execute("""INSERT INTO assets (asset_id, asset_type, namespace, name, external_id, visibility, lifecycle, first_seen_at, last_seen_at, observed_at, evidence_path, run_id)
                            VALUES (?,?,?,?,?,?,?, ?,?,?,?,?)
                            ON CONFLICT(asset_id) DO UPDATE SET external_id=excluded.external_id, visibility=excluded.visibility, lifecycle=excluded.lifecycle,
                              last_seen_at=excluded.last_seen_at, observed_at=excluded.observed_at, evidence_path=excluded.evidence_path, run_id=excluded.run_id""",
                         (a["asset_id"], a["asset_type"], a["namespace"], a["name"], a["external_id"], vis, life, a["observed_at"], a["observed_at"], a["observed_at"], a["evidence_path"], run_id))
            stats["assets_updated" if old else "assets_new"] += 1
            for k, v in a["facts"].items():
                before = conn.total_changes
                conn.execute("""INSERT INTO asset_facts (asset_id, key, value_json, observed_at, evidence_path, run_id) VALUES (?,?,?,?,?,?)
                                ON CONFLICT(asset_id, key) DO UPDATE SET value_json=excluded.value_json, observed_at=excluded.observed_at, evidence_path=excluded.evidence_path, run_id=excluded.run_id""",
                             (a["asset_id"], k, canon(v), a["observed_at"], a["evidence_path"], run_id))
            for (stale,) in conn.execute("SELECT key FROM asset_facts WHERE asset_id=?", (a["asset_id"],)).fetchall():
                if stale not in a["facts"] and not stale.startswith("agent."):
                    oldv = conn.execute("SELECT value_json FROM asset_facts WHERE asset_id=? AND key=?", (a["asset_id"], stale)).fetchone()[0]
                    conn.execute("INSERT INTO asset_fact_history (asset_id, key, old_value_json, new_value_json, changed_at, evidence_path, run_id) VALUES (?,?,?,?,?,?,?)",
                                 (a["asset_id"], stale, oldv, "null", a["observed_at"], a["evidence_path"], run_id))
                    conn.execute("DELETE FROM asset_facts WHERE asset_id=? AND key=?", (a["asset_id"], stale))
            r = a["revision"]
            conn.execute("""INSERT INTO asset_revisions (asset_id, revision_kind, revision, digest_sha256, digest_filename, observed_at, evidence_path, run_id) VALUES (?,?,?,?,?,?,?,?)
                            ON CONFLICT(asset_id) DO UPDATE SET revision_kind=excluded.revision_kind, revision=excluded.revision, digest_sha256=excluded.digest_sha256, digest_filename=excluded.digest_filename,
                              observed_at=excluded.observed_at, evidence_path=excluded.evidence_path, run_id=excluded.run_id""",
                         (a["asset_id"], r["kind"], r["revision"], r["digest_sha256"], r["digest_filename"], a["observed_at"], a["evidence_path"], run_id))
        # assets of a covered type that vanished: ABSENT only after an authoritative listing (fix #3).
        # Visibility is last-observed (ruling: ABSENT rows carry Nov 19 / prior visibility, never a default).
        # Alignment of an ABSENT asset is UNKNOWN (ruling (a)); a COVERAGE_GAP is also not comparable as missing.
        for (aid, atype) in conn.execute("SELECT asset_id, asset_type FROM assets WHERE lifecycle IN ('PRESENT','COVERAGE_GAP','present')").fetchall():
            if atype in types_in_snapshot and aid not in seen:
                life = alignment.vanished_lifecycle(atype, coverage_by_type)
                conn.execute("UPDATE assets SET lifecycle=?, observed_at=?, run_id=? WHERE asset_id=?", (life, obs_max, run_id, aid))
                if life == "ABSENT":
                    stats["assets_absent"] += 1
                    a_reason = "ABSENT: no current revision; last known from prior observation"
                    a_state = "UNKNOWN"
                else:
                    stats["assets_coverage_gap"] += 1
                    a_reason = "COVERAGE_GAP: listing was not authoritative; not marked ABSENT"
                    a_state = "UNKNOWN"
                conn.execute("""INSERT INTO asset_alignment (asset_id, alignment_state, alignment_reason, best_upstream_id, observed_at, evidence_path, run_id) VALUES (?,?,?,?,?,?,?)
                                ON CONFLICT(asset_id) DO UPDATE SET alignment_state=excluded.alignment_state, alignment_reason=excluded.alignment_reason, best_upstream_id=excluded.best_upstream_id,
                                  observed_at=excluded.observed_at, evidence_path=excluded.evidence_path, run_id=excluded.run_id""",
                             (aid, a_state, a_reason, None, obs_max, "ingest:vanished", run_id))
        # bindings + classification
        conn.execute("DELETE FROM source_bindings")      # derived table: rebuilt from the snapshot each run
        by_asset = {}
        for b in snapshot["bindings"]:
            pin = b["pinned_ref"]
            cmpv = "no_pin" if not pin else None
            cs = b.get("compare_status")
            if pin and b["kind"] == "pyproject_in_repo":
                cmpv = alignment.compare_versions(pin, (cs or "version:").split("version:")[-1])
            elif pin and cs is not None:
                cmpv = alignment.comparison_from_compare_status(cs) if cs != "not_found" else "not_compared"
            elif pin:
                cmpv = "not_compared"
            pin_found = not (cs == "not_found")
            state, reason = alignment.classify_binding(b["grade"], pin if b["kind"] != "pyproject_in_repo" else None, b["upstream_head"], cmpv, pin_found)
            if b["kind"] == "pyproject_in_repo":
                state, reason = "UNKNOWN", f"declared via pyproject name in repo; version pin {pin} vs PyPI latest: {cmpv}"
            pin_digests = b.get("pin_asset_digests")
            pin_digests_json = canon(pin_digests) if pin_digests is not None else None
            conn.execute("""INSERT INTO source_bindings (asset_id, upstream_asset_id, binding_kind, binding_grade, pinned_ref, upstream_head, pin_comparison, alignment_state, alignment_reason, observed_at, evidence_path, run_id, pin_repository, pin_revision, pin_asset_digests, pin_target)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (b["asset_id"], b["upstream_asset_id"], b["kind"], b["grade"], pin, b["upstream_head"], cmpv, state, reason, b["observed_at"], b["evidence_path"], run_id,
                          b.get("pin_repository"), b.get("pin_revision") or pin, pin_digests_json, b.get("pin_target")))
            by_asset.setdefault(b["asset_id"], []).append({"grade": b["grade"], "alignment_state": state, "alignment_reason": reason, "upstream_asset_id": b["upstream_asset_id"]})
        counts = {}
        for a in snapshot["assets"]:
            state, reason, best = alignment.classify_asset(a["asset_type"], by_asset.get(a["asset_id"], []), lifecycle=alignment.norm_lifecycle(a.get("lifecycle") or "PRESENT"))
            conn.execute("""INSERT INTO asset_alignment (asset_id, alignment_state, alignment_reason, best_upstream_id, observed_at, evidence_path, run_id) VALUES (?,?,?,?,?,?,?)
                            ON CONFLICT(asset_id) DO UPDATE SET alignment_state=excluded.alignment_state, alignment_reason=excluded.alignment_reason, best_upstream_id=excluded.best_upstream_id,
                              observed_at=excluded.observed_at, evidence_path=excluded.evidence_path, run_id=excluded.run_id""",
                         (a["asset_id"], state, reason, best, a["observed_at"], a["evidence_path"], run_id))
            counts[state] = counts.get(state, 0) + 1
        # candidate refs (derived; rebuilt)
        conn.execute("DELETE FROM candidate_refs")
        for c in snapshot["candidate_refs"]:
            key = hashlib.sha256("|".join([c["from_asset_id"], c["kind"], c["target_type"], c["target_id"], c["evidence_path"]]).encode()).hexdigest()
            conn.execute("INSERT OR IGNORE INTO candidate_refs (ref_key, from_asset_id, kind, target_type, target_id, evidence_path, snippet, observed_at, run_id) VALUES (?,?,?,?,?,?,?,?,?)",
                         (key, c["from_asset_id"], c["kind"], c["target_type"], c["target_id"], c["evidence_path"], c["snippet"], c["observed_at"], run_id))
        for c in snapshot["coverage"]:
            conn.execute("""INSERT INTO coverage_reports (run_id, source, asset_type, expected_count, ingested_count, missing_count, detail_json, observed_at, evidence_path) VALUES (?,?,?,?,?,?,?,?,?)""",
                         (run_id, c["source"], c["asset_type"], c["expected"], c["ingested"], c["missing"], canon(c["detail"]), snapshot["meta"]["observed"].get(c["source"]) or obs_max, c["evidence"]))
        stats["facts_changed"] = conn.execute("SELECT COUNT(*) FROM asset_fact_history WHERE run_id=?", (run_id,)).fetchone()[0]
        total_cov = {"expected": sum(c["expected"] for c in snapshot["coverage"]), "ingested": sum(c["ingested"] for c in snapshot["coverage"]), "missing": sum(c["missing"] for c in snapshot["coverage"])}
        seq = receipts.append(conn, actor=actor, actor_kind="ingest", action="ingest.run", target=run_id, at=started,
                              reason=reason or "scheduled/manual read-only ingest of GitHub, HF, PyPI, Cloudflare metadata snapshot",
                              payload={"snapshot_sha256": sha, "alignment_counts": counts, "stats": stats, "coverage": total_cov, "assets": len(snapshot["assets"])})
        conn.execute("UPDATE ingest_runs SET status='complete', finished_at=?, counts_json=?, coverage_json=? WHERE run_id=?", (started, canon({**stats, "alignment": counts, "assets": len(snapshot["assets"])}), canon(total_cov), run_id))
        conn.execute("COMMIT")
        return {"run_id": run_id, "status": "complete", "changed": True, "receipt_seq": seq, "alignment_counts": counts, "stats": stats}
    except Exception:
        if conn.in_transaction: conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    snap = json.load(open(sys.argv[2])); print(json.dumps(load(sys.argv[1], snap, snapshot_path=sys.argv[2]), indent=1))
