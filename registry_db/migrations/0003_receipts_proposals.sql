-- 0003_receipts_proposals: append-only hash-chained receipts, proposals, delete guard, views.
-- SQL enforces chain STRUCTURE (contiguous seq, prev_hash == previous entry_hash, no update/delete);
-- the Python verifier recomputes every entry_hash (D1 has no sha256()).
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS receipts (
  seq          INTEGER PRIMARY KEY CHECK (seq >= 1),
  receipt_id   TEXT NOT NULL UNIQUE,
  prev_hash    TEXT NOT NULL CHECK (length(prev_hash) = 64),
  entry_hash   TEXT NOT NULL UNIQUE CHECK (length(entry_hash) = 64),
  actor        TEXT NOT NULL CHECK (length(actor) > 0),
  actor_kind   TEXT NOT NULL CHECK (actor_kind IN ('ingest','agent','human')),
  action       TEXT NOT NULL CHECK (action IN ('ingest.run','proposal.create','proposal.accept','proposal.reject','asset.tombstone','asset.delete','chain.verify')),
  target       TEXT NOT NULL,
  reason       TEXT NOT NULL CHECK (length(reason) > 0),
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
  at           TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS receipts_chain_insert BEFORE INSERT ON receipts
BEGIN
  SELECT RAISE(ABORT, 'receipts: seq must be previous seq + 1')
    WHERE NEW.seq <> COALESCE((SELECT MAX(seq) FROM receipts), 0) + 1;
  SELECT RAISE(ABORT, 'receipts: prev_hash must equal previous entry_hash (genesis = 64 zeros)')
    WHERE NEW.prev_hash <> COALESCE((SELECT entry_hash FROM receipts ORDER BY seq DESC LIMIT 1), '0000000000000000000000000000000000000000000000000000000000000000');
END;
CREATE TRIGGER IF NOT EXISTS receipts_no_update BEFORE UPDATE ON receipts
BEGIN SELECT RAISE(ABORT, 'receipts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS receipts_no_delete BEFORE DELETE ON receipts
BEGIN SELECT RAISE(ABORT, 'receipts are append-only'); END;

-- Agents never write assets directly. They file proposals (through the single writer); a human/ingest
-- decision is itself a receipt. A proposal row always points at the receipts that created/decided it.
CREATE TABLE IF NOT EXISTS proposals (
  proposal_id         TEXT PRIMARY KEY,
  asset_id            TEXT NOT NULL REFERENCES assets (asset_id),
  change_kind         TEXT NOT NULL CHECK (change_kind IN ('set_binding','set_fact','mark_absent','request_delete')),
  proposed_json       TEXT NOT NULL CHECK (json_valid(proposed_json)),
  status              TEXT NOT NULL CHECK (status IN ('pending','accepted','rejected')),
  proposer            TEXT NOT NULL,
  created_receipt_seq INTEGER NOT NULL REFERENCES receipts (seq),
  decided_receipt_seq INTEGER REFERENCES receipts (seq),
  CHECK ((status = 'pending' AND decided_receipt_seq IS NULL) OR (status <> 'pending' AND decided_receipt_seq IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS proposals_status ON proposals (status);

-- Never delete an asset without a receipt: the newest receipt must be an asset.delete for exactly this asset.
CREATE TRIGGER IF NOT EXISTS assets_delete_requires_receipt BEFORE DELETE ON assets
BEGIN
  SELECT RAISE(ABORT, 'assets: delete requires newest receipt = asset.delete for this asset')
    WHERE NOT EXISTS (SELECT 1 FROM receipts r
                      WHERE r.seq = (SELECT MAX(seq) FROM receipts)
                        AND r.action = 'asset.delete' AND r.target = OLD.asset_id);
END;

CREATE VIEW IF NOT EXISTS v_asset_overview AS
SELECT a.asset_id, a.asset_type, a.namespace, a.name, a.visibility, a.lifecycle,
       r.revision_kind, r.revision, r.digest_sha256,
       l.alignment_state, l.alignment_reason, l.best_upstream_id,
       a.observed_at, a.evidence_path
FROM assets a
LEFT JOIN asset_revisions r ON r.asset_id = a.asset_id
LEFT JOIN asset_alignment l ON l.asset_id = a.asset_id;

CREATE VIEW IF NOT EXISTS v_alignment_counts AS
SELECT a.asset_type, COALESCE(l.alignment_state, 'unknown') AS alignment_state, COUNT(*) AS n
FROM assets a LEFT JOIN asset_alignment l ON l.asset_id = a.asset_id
WHERE a.lifecycle = 'present'
GROUP BY 1, 2;
