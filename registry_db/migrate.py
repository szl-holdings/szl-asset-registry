"""Guarded migration runner (stdlib only).

Guards (these exist because drizzle 0.45 silently skipped out-of-order migrations, audit F1/F2):
  1. file ids must be contiguous 1..N, unique, named NNNN_name.sql
  2. MANIFEST.sha256 must list exactly those files with matching sha256 (edited file => refuse)
  3. the journal (registry_migrations) must be an exact PREFIX 1..k of the files with matching
     name+sha256 -- an unapplied lower id with a higher id applied is an error, never skipped
  4. each migration + its journal row run in ONE transaction; a failure leaves k unchanged
CLI: python -m registry_db.migrate {apply|verify|manifest} --db PATH
"""
import argparse, hashlib, os, re, sqlite3, sys, datetime

MIG_DIR = os.path.join(os.path.dirname(__file__), "migrations")
NAME_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

class MigrationError(Exception):
    pass

def sha256_bytes(b): return hashlib.sha256(b).hexdigest()

def load_files(mig_dir=MIG_DIR):
    files = []
    for fn in sorted(os.listdir(mig_dir)):
        if fn.endswith(".sql"):
            m = NAME_RE.match(fn)
            if not m: raise MigrationError(f"bad migration filename: {fn}")
            with open(os.path.join(mig_dir, fn), "rb") as fh: raw = fh.read()
            files.append({"id": int(m.group(1)), "name": fn, "sha256": sha256_bytes(raw), "sql": raw.decode()})
    ids = [f["id"] for f in files]
    if not ids: raise MigrationError("no migrations found")
    if ids != list(range(1, len(ids) + 1)):
        raise MigrationError(f"migration ids must be contiguous from 0001; got {ids}")
    return files

def manifest_text(files):
    return "".join(f"{f['sha256']}  {f['name']}\n" for f in files)

def check_manifest(files, mig_dir=MIG_DIR):
    p = os.path.join(mig_dir, "MANIFEST.sha256")
    if not os.path.exists(p): raise MigrationError("MANIFEST.sha256 missing")
    with open(p) as fh: on_disk = fh.read()
    if on_disk != manifest_text(files):
        raise MigrationError("MANIFEST.sha256 does not match migration files (edited or added file without regenerating manifest)")

def journal_rows(conn):
    has = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='registry_migrations'").fetchone()
    if not has: return []
    return conn.execute("SELECT id, name, sha256 FROM registry_migrations ORDER BY id").fetchall()

def verify(conn, files):
    """Returns number of applied migrations k; raises on any divergence."""
    rows = journal_rows(conn)
    ids = [r[0] for r in rows]
    if ids != list(range(1, len(ids) + 1)):
        raise MigrationError(f"journal is not a contiguous prefix: applied ids {ids} (skipped or out-of-order migration)")
    if len(rows) > len(files):
        raise MigrationError(f"journal has {len(rows)} entries but only {len(files)} migration files")
    for (i, name, sha), f in zip(rows, files):
        if name != f["name"]: raise MigrationError(f"journal id {i} is {name!r} but file is {f['name']!r}")
        if sha != f["sha256"]: raise MigrationError(f"checksum mismatch for {name}: applied file was edited after apply")
    return len(rows)

def apply(db_path, mig_dir=MIG_DIR, now=None):
    files = load_files(mig_dir); check_manifest(files, mig_dir)
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        # Foreign keys are off while applying: 0004 rebuilds tables to replace CHECK
        # constraints, and SQLite ignores PRAGMA foreign_keys changes inside a transaction.
        conn.execute("PRAGMA foreign_keys = OFF")
        k = verify(conn, files)
        for f in files[k:]:
            ts = now or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                conn.execute("BEGIN IMMEDIATE")
                for stmt in split_sql(f["sql"]): conn.execute(stmt)
                conn.execute("INSERT INTO registry_migrations (id, name, sha256, applied_at) VALUES (?,?,?,?)", (f["id"], f["name"], f["sha256"], ts))
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction: conn.execute("ROLLBACK")
                raise
        conn.execute("PRAGMA foreign_keys = ON")
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise MigrationError(f"foreign key check failed after apply: {violations[:5]}")
        return verify(conn, files)
    finally:
        conn.close()

def split_sql(sql):
    """Split on ';' respecting CREATE TRIGGER ... BEGIN ... END; blocks."""
    out, buf, depth = [], [], 0
    for line in sql.splitlines():
        s = line.strip()
        if s.startswith("--") and not buf: continue
        buf.append(line)
        up = s.upper()
        if re.match(r"^CREATE\s+TRIGGER", up) or (buf and "CREATE TRIGGER" in " ".join(buf[:3]).upper()):
            pass
        if up.startswith("BEGIN") or up == "BEGIN;" or re.search(r"\bBEGIN$", up): depth += 1
        if depth and (up == "END;" or up.endswith(" END;")): depth -= 1
        if depth == 0 and s.endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt: out.append(stmt)
            buf = []
    if "".join(buf).strip(): out.append("\n".join(buf).strip())
    return out

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["apply", "verify", "manifest"])
    ap.add_argument("--db")
    a = ap.parse_args(argv)
    files = load_files()
    if a.cmd == "manifest":
        with open(os.path.join(MIG_DIR, "MANIFEST.sha256"), "w") as fh: fh.write(manifest_text(files))
        print("manifest written"); return 0
    check_manifest(files)
    if a.cmd == "apply":
        print("applied through", apply(a.db)); return 0
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    print("verified; applied", verify(conn, files), "of", len(files)); return 0

if __name__ == "__main__":
    try: sys.exit(main())
    except MigrationError as e:
        print("MIGRATION GUARD FAILED:", e, file=sys.stderr); sys.exit(2)
