"""Append-only, hash-chained receipts (pattern reused from szl-safe-stack safe-qa-service ledger.py:
canonical JSON, sha256, previous_hash, GENESIS)."""
import hashlib, json, uuid, datetime

GENESIS = "0" * 64

def canonical(entry: dict) -> bytes:
    body = {k: entry[k] for k in ("seq", "receipt_id", "prev_hash", "actor", "actor_kind", "action", "target", "reason", "payload", "at")}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

def entry_hash(entry: dict) -> str:
    return hashlib.sha256(canonical(entry)).hexdigest()

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def append(conn, *, actor, actor_kind, action, target, reason, payload=None, at=None, receipt_id=None):
    """Append one receipt inside the caller's transaction. Returns seq."""
    if not reason or not reason.strip(): raise ValueError("reason is required")
    row = conn.execute("SELECT seq, entry_hash FROM receipts ORDER BY seq DESC LIMIT 1").fetchone()
    seq, prev = (row[0] + 1, row[1]) if row else (1, GENESIS)
    e = {"seq": seq, "receipt_id": receipt_id or str(uuid.uuid4()), "prev_hash": prev, "actor": actor, "actor_kind": actor_kind,
         "action": action, "target": target, "reason": reason, "payload": payload if payload is not None else {}, "at": at or utcnow()}
    h = entry_hash(e)
    conn.execute("INSERT INTO receipts (seq, receipt_id, prev_hash, entry_hash, actor, actor_kind, action, target, reason, payload_json, at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (seq, e["receipt_id"], prev, h, actor, actor_kind, action, target, reason, json.dumps(e["payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=True), e["at"]))
    return seq

def verify_chain(conn):
    """Recompute every hash. Returns {ok, count, head, error}."""
    prev = GENESIS; n = 0
    for r in conn.execute("SELECT seq, receipt_id, prev_hash, entry_hash, actor, actor_kind, action, target, reason, payload_json, at FROM receipts ORDER BY seq"):
        n += 1
        seq, rid, ph, eh, actor, ak, act, tgt, reason, pj, at = r
        if seq != n: return {"ok": False, "count": n, "head": prev, "error": f"seq gap at {seq} (expected {n})"}
        if ph != prev: return {"ok": False, "count": n, "head": prev, "error": f"prev_hash mismatch at seq {seq}"}
        e = {"seq": seq, "receipt_id": rid, "prev_hash": ph, "actor": actor, "actor_kind": ak, "action": act, "target": tgt, "reason": reason, "payload": json.loads(pj), "at": at}
        if entry_hash(e) != eh: return {"ok": False, "count": n, "head": prev, "error": f"entry_hash mismatch at seq {seq} (row content altered)"}
        prev = eh
    return {"ok": True, "count": n, "head": prev, "error": None}
