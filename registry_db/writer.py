"""The single writer for proposals (the only code path besides loader that opens the DB read-write)."""
import glob, json, os, sqlite3
from . import receipts

def _conn(path):
    c = sqlite3.connect(path, isolation_level=None); c.execute("PRAGMA foreign_keys = ON"); return c

def apply_outbox(db_path, outbox_dir, actor="ingest:registry_db.writer"):
    c = _conn(db_path); filed = []
    try:
        for p in sorted(glob.glob(os.path.join(outbox_dir, "*.json"))):
            b = json.load(open(p))
            if c.execute("SELECT 1 FROM proposals WHERE proposal_id=?", (b["proposal_id"],)).fetchone(): continue
            c.execute("BEGIN IMMEDIATE")
            try:
                seq = receipts.append(c, actor=b["actor"], actor_kind="agent", action="proposal.create", target=b["asset_id"], reason=b["reason"], at=b["at"],
                                      payload={"proposal_id": b["proposal_id"], "change_kind": b["change_kind"], "proposed": b["proposed"], "filed_by": actor})
                c.execute("INSERT INTO proposals (proposal_id, asset_id, change_kind, proposed_json, status, proposer, created_receipt_seq) VALUES (?,?,?,?, 'pending', ?, ?)",
                          (b["proposal_id"], b["asset_id"], b["change_kind"], json.dumps(b["proposed"], sort_keys=True), b["actor"], seq))
                c.execute("COMMIT"); filed.append(b["proposal_id"])
            except Exception:
                if c.in_transaction: c.execute("ROLLBACK")
                raise
        return filed
    finally: c.close()

def decide(db_path, proposal_id, *, accept, decider, reason, at=None):
    """Human/ingest decision. Always a receipt. Accepted set_fact/set_binding become 'agent.*' facts (ingest never deletes agent.* keys)."""
    c = _conn(db_path)
    try:
        row = c.execute("SELECT asset_id, change_kind, proposed_json, status FROM proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
        if not row: raise ValueError("unknown proposal")
        if row[3] != "pending": raise ValueError(f"proposal already {row[3]}")
        c.execute("BEGIN IMMEDIATE")
        try:
            seq = receipts.append(c, actor=decider, actor_kind="human", action="proposal.accept" if accept else "proposal.reject", target=row[0], reason=reason, at=at,
                                  payload={"proposal_id": proposal_id, "change_kind": row[1]})
            c.execute("UPDATE proposals SET status=?, decided_receipt_seq=? WHERE proposal_id=?", ("accepted" if accept else "rejected", seq, proposal_id))
            if accept and row[1] in ("set_fact", "set_binding"):
                prop = json.loads(row[2]); key = prop["key"] if row[1] == "set_fact" else "agent.binding_hint"
                val = prop.get("value") if row[1] == "set_fact" else prop
                run = c.execute("SELECT run_id FROM assets WHERE asset_id=?", (row[0],)).fetchone()[0]
                c.execute("""INSERT INTO asset_facts (asset_id, key, value_json, observed_at, evidence_path, run_id) VALUES (?,?,?,?,?,?)
                             ON CONFLICT(asset_id,key) DO UPDATE SET value_json=excluded.value_json, observed_at=excluded.observed_at, evidence_path=excluded.evidence_path""",
                          (row[0], key, json.dumps(val, sort_keys=True), at or receipts.utcnow(), f"proposal:{proposal_id}", run))
            c.execute("COMMIT"); return seq
        except Exception:
            if c.in_transaction: c.execute("ROLLBACK")
            raise
    finally: c.close()

def delete_asset(db_path, asset_id, *, approver, reason, at=None):
    """Hard delete is possible ONLY immediately after an asset.delete receipt for that exact asset (DB trigger enforces)."""
    c = _conn(db_path)
    try:
        c.execute("BEGIN IMMEDIATE")
        try:
            receipts.append(c, actor=approver, actor_kind="human", action="asset.delete", target=asset_id, reason=reason, at=at, payload={"asset_id": asset_id})
            for t in ("asset_facts", "asset_revisions", "source_bindings", "asset_alignment", "proposals"):
                c.execute(f"DELETE FROM {t} WHERE asset_id=?", (asset_id,))
            c.execute("DELETE FROM source_bindings WHERE upstream_asset_id=?", (asset_id,))
            c.execute("UPDATE asset_alignment SET best_upstream_id=NULL WHERE best_upstream_id=?", (asset_id,))
            c.execute("DELETE FROM candidate_refs WHERE from_asset_id=?", (asset_id,))
            c.execute("DELETE FROM assets WHERE asset_id=?", (asset_id,))
            c.execute("COMMIT")
        except Exception:
            if c.in_transaction: c.execute("ROLLBACK")
            raise
    finally: c.close()
