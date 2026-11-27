"""Read API (read-only SQLite connection) + proposal filing (outbox file; never writes the database).
Only the single writer (registry_db.writer / loader) holds a write handle -- same split as the planned D1
bindings: read binding for API/MCP, write binding for ingest only."""
import hashlib, json, os, sqlite3, datetime
from . import receipts

CHANGE_KINDS = ("set_binding", "set_fact", "mark_absent", "request_delete")

def connect_ro(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c

def _rows(cur): return [dict(r) for r in cur.fetchall()]

def query_assets(conn, asset_type=None, alignment_state=None, visibility=None, name_like=None, lifecycle="PRESENT", limit=100, offset=0):
    limit = max(1, min(int(limit), 500)); offset = max(0, int(offset))
    where, args = [], []
    for col, v in (("asset_type", asset_type), ("alignment_state", alignment_state), ("visibility", visibility), ("lifecycle", lifecycle)):
        if v: where.append(f"{col} = ?"); args.append(v)
    if name_like: where.append("name LIKE ? ESCAPE '\\'"); args.append("%" + name_like.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    sql = "SELECT asset_id, asset_type, name, visibility, lifecycle, revision_kind, revision, alignment_state, alignment_reason, best_upstream_id, observed_at, evidence_path FROM v_asset_overview"
    if where: sql += " WHERE " + " AND ".join(where)
    total = conn.execute("SELECT COUNT(*) FROM v_asset_overview" + (" WHERE " + " AND ".join(where) if where else ""), args).fetchone()[0]
    sql += " ORDER BY asset_id LIMIT ? OFFSET ?"
    return {"total": total, "limit": limit, "offset": offset, "items": _rows(conn.execute(sql, args + [limit, offset]))}

def get_asset(conn, asset_id):
    a = conn.execute("SELECT * FROM v_asset_overview WHERE asset_id = ?", (asset_id,)).fetchone()
    if not a: return None
    facts = {r["key"]: {"value": json.loads(r["value_json"]), "observed_at": r["observed_at"], "evidence_path": r["evidence_path"]} for r in conn.execute("SELECT * FROM asset_facts WHERE asset_id = ?", (asset_id,))}
    return {"asset": dict(a), "facts": facts,
            "bindings": _rows(conn.execute("SELECT * FROM source_bindings WHERE asset_id = ? ORDER BY binding_grade, binding_kind", (asset_id,))),
            "history": _rows(conn.execute("SELECT * FROM asset_fact_history WHERE asset_id = ? ORDER BY hist_id DESC LIMIT 50", (asset_id,))),
            "proposals": _rows(conn.execute("SELECT proposal_id, change_kind, status, proposer FROM proposals WHERE asset_id = ?", (asset_id,)))}

def alignment_summary(conn):
    out = {}
    for r in conn.execute("SELECT asset_type, alignment_state, SUM(n) n FROM v_alignment_counts GROUP BY 1,2"):
        out.setdefault(r["asset_type"], {})[r["alignment_state"]] = r["n"]
    return out

def coverage(conn):
    run = conn.execute("SELECT run_id FROM ingest_runs ORDER BY started_at DESC, rowid DESC LIMIT 1").fetchone()
    if not run: return {"run_id": None, "rows": []}
    return {"run_id": run["run_id"], "rows": _rows(conn.execute("SELECT source, asset_type, expected_count, ingested_count, missing_count, observed_at, evidence_path FROM coverage_reports WHERE run_id = ? ORDER BY source, asset_type", (run["run_id"],)))}

def verify_receipts(conn): return receipts.verify_chain(conn)

def list_receipts(conn, limit=50):
    return _rows(conn.execute("SELECT seq, receipt_id, entry_hash, actor, actor_kind, action, target, reason, at FROM receipts ORDER BY seq DESC LIMIT ?", (max(1, min(int(limit), 200)),)))

def propose_update(outbox_dir, conn, *, actor, asset_id, change_kind, proposed, reason, at=None):
    """Validate + write a proposal file to the outbox. No database write; the writer files it under a receipt."""
    if change_kind not in CHANGE_KINDS: raise ValueError(f"change_kind must be one of {CHANGE_KINDS}")
    if not actor or not reason or not reason.strip(): raise ValueError("actor and reason are required")
    if not conn.execute("SELECT 1 FROM assets WHERE asset_id = ?", (asset_id,)).fetchone(): raise ValueError(f"unknown asset_id {asset_id}")
    if change_kind == "set_fact" and not str(proposed.get("key", "")).startswith("agent."): raise ValueError("set_fact keys must start with 'agent.'")
    body = {"actor": actor, "asset_id": asset_id, "change_kind": change_kind, "proposed": proposed, "reason": reason, "at": at or receipts.utcnow()}
    pid = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    body["proposal_id"] = pid
    os.makedirs(outbox_dir, exist_ok=True)
    path = os.path.join(outbox_dir, f"{pid}.json")
    if not os.path.exists(path):
        tmp = path + ".tmp"; json.dump(body, open(tmp, "w"), sort_keys=True, indent=1); os.replace(tmp, path)
    return {"proposal_id": pid, "status": "queued_in_outbox", "path": path}
