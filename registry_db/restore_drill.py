"""Restore drill (local, executable): backup -> restore into a NEW file -> prove equivalence.
Checks: PRAGMA integrity_check + foreign_key_check, migration journal verifies, receipt chain verifies and
head hash equals the source head, and a per-table content digest matches the source.
The remote equivalent (documented in DESIGN.md, NOT executed here): `wrangler d1 export` to a SQL file,
import into a *new* D1 database name, run this same verification against the export. Never restore over production."""
import hashlib, json, os, sqlite3, sys
from . import migrate, receipts

TABLES = ["registry_migrations", "ingest_runs", "assets", "candidate_refs", "asset_facts", "asset_fact_history", "asset_revisions", "source_bindings", "asset_alignment",
          "coverage_reports", "receipts", "proposals"]

def table_digest(conn, t):
    h = hashlib.sha256()
    for row in conn.execute(f"SELECT * FROM {t} ORDER BY 1, 2" if t in ("asset_facts", "source_bindings") else f"SELECT * FROM {t} ORDER BY 1"):
        h.update(json.dumps(row, default=str, sort_keys=True).encode() + b"\n")
    return h.hexdigest()

def fingerprint(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return {"tables": {t: {"rows": c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], "sha256": table_digest(c, t)} for t in TABLES},
                "receipt_chain": receipts.verify_chain(c), "integrity": c.execute("PRAGMA integrity_check").fetchone()[0], "fk_violations": len(c.execute("PRAGMA foreign_key_check").fetchall()),
                "migrations_applied": migrate.verify(c, migrate.load_files())}
    finally: c.close()

def backup(src, dst):
    if os.path.exists(dst): raise FileExistsError(dst)
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True); d = sqlite3.connect(dst)
    try: s.backup(d)
    finally: d.close(); s.close()
    return fingerprint(dst)

def restore_and_verify(backup_path, restore_path, expected):
    if os.path.exists(restore_path): raise FileExistsError(restore_path)
    s = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True); d = sqlite3.connect(restore_path)
    try: s.backup(d)
    finally: d.close(); s.close()
    got = fingerprint(restore_path); problems = []
    if got["integrity"] != "ok": problems.append("integrity_check failed")
    if got["fk_violations"]: problems.append("foreign key violations")
    if not got["receipt_chain"]["ok"]: problems.append("receipt chain broken")
    if got["receipt_chain"]["head"] != expected["receipt_chain"]["head"]: problems.append("receipt head differs from source")
    if got["tables"] != expected["tables"]: problems.append("table digests differ: " + ",".join(t for t in TABLES if got["tables"][t] != expected["tables"][t]))
    return {"ok": not problems, "problems": problems, "fingerprint": got}

if __name__ == "__main__":
    src, workdir = sys.argv[1], sys.argv[2]; os.makedirs(workdir, exist_ok=True)
    exp = backup(src, os.path.join(workdir, "backup.db"))
    r = restore_and_verify(os.path.join(workdir, "backup.db"), os.path.join(workdir, "restored.db"), exp)
    print(json.dumps({"ok": r["ok"], "problems": r["problems"], "rows": {t: v["rows"] for t, v in r["fingerprint"]["tables"].items()}, "receipt_head": r["fingerprint"]["receipt_chain"]["head"]}, indent=1)); sys.exit(0 if r["ok"] else 1)
