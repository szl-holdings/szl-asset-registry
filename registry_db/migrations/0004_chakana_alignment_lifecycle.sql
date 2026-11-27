-- 0004_chakana_alignment_lifecycle (additive; 0001-0003 files are not edited).
-- Chakana fixes 1-3 + schema delta for Yachay:
--   * asset_type gains cf_pages_project
--   * lifecycle PRESENT | ABSENT | COVERAGE_GAP  (present/absent rows are migrated)
--   * visibility keeps public|private|internal; only the unknown token becomes UNKNOWN
--   * alignment_state ALIGNED | BEHIND | DRIFTED | UNTRACEABLE | UNKNOWN
--   * source_bindings gains binding_kind source_binding_json and pin_* columns
--     (pin_repository, pin_revision, pin_asset_digests, pin_target) from szl-source-binding.json
-- Existing 0001 column names are unchanged. Table rebuilds replace CHECK constraints
-- (SQLite cannot ALTER a CHECK). The migration runner turns foreign_keys OFF around this
-- file because a CHECK rebuild drops and recreates the tables.
--
-- Values already stored lowercase are copied upward. Empty databases (just 0001-0003) copy 0 rows.

DROP VIEW IF EXISTS v_alignment_counts;
DROP VIEW IF EXISTS v_asset_overview;
DROP TRIGGER IF EXISTS assets_delete_requires_receipt;

CREATE TABLE assets_0004 (
  asset_id      TEXT PRIMARY KEY,
  asset_type    TEXT NOT NULL CHECK (asset_type IN (
                  'github_repo','hf_model','hf_dataset','hf_space','hf_kernel','hf_bucket','hf_collection',
                  'pypi_project',
                  'cf_worker','cf_d1','cf_r2','cf_kv','cf_tunnel','cf_zone','cf_dns_record','cf_route',
                  'cf_access_app','cf_worker_domain','cf_pages_project')),
  namespace     TEXT NOT NULL,
  name          TEXT NOT NULL,
  external_id   TEXT,
  visibility    TEXT NOT NULL CHECK (visibility IN ('public','private','internal','UNKNOWN')),
  lifecycle     TEXT NOT NULL DEFAULT 'PRESENT' CHECK (lifecycle IN ('PRESENT','ABSENT','COVERAGE_GAP')),
  first_seen_at TEXT NOT NULL,
  last_seen_at  TEXT NOT NULL,
  observed_at   TEXT NOT NULL,
  evidence_path TEXT NOT NULL CHECK (length(evidence_path) > 0),
  run_id        TEXT NOT NULL REFERENCES ingest_runs (run_id),
  UNIQUE (asset_type, namespace, name)
);
INSERT INTO assets_0004 (asset_id, asset_type, namespace, name, external_id, visibility, lifecycle, first_seen_at, last_seen_at, observed_at, evidence_path, run_id)
SELECT asset_id, asset_type, namespace, name, external_id,
       CASE WHEN lower(visibility) = 'unknown' THEN 'UNKNOWN' ELSE visibility END,
       CASE lower(lifecycle)
         WHEN 'present' THEN 'PRESENT'
         WHEN 'absent' THEN 'ABSENT'
         WHEN 'coverage_gap' THEN 'COVERAGE_GAP'
         ELSE lifecycle
       END,
       first_seen_at, last_seen_at, observed_at, evidence_path, run_id
FROM assets;
DROP TABLE assets;
ALTER TABLE assets_0004 RENAME TO assets;
CREATE INDEX IF NOT EXISTS assets_type ON assets (asset_type);
CREATE INDEX IF NOT EXISTS assets_external ON assets (asset_type, external_id);

CREATE TABLE source_bindings_0004 (
  asset_id          TEXT NOT NULL REFERENCES assets (asset_id),
  upstream_asset_id TEXT NOT NULL REFERENCES assets (asset_id),
  binding_kind      TEXT NOT NULL CHECK (binding_kind IN ('sync_commit_pin','declared_map','pyproject_in_repo','wrangler_in_repo','reference_only','source_binding_json','pep740_attestation')),
  binding_grade     TEXT NOT NULL CHECK (binding_grade IN ('verified_pin','declared','referenced')),
  pinned_ref        TEXT,
  upstream_head     TEXT,
  pin_comparison    TEXT NOT NULL CHECK (pin_comparison IN ('identical','upstream_ahead','pin_ahead','diverged','not_compared','no_pin')),
  alignment_state   TEXT NOT NULL CHECK (alignment_state IN ('ALIGNED','BEHIND','DRIFTED','UNTRACEABLE','UNKNOWN')),
  alignment_reason  TEXT NOT NULL CHECK (length(alignment_reason) > 0),
  observed_at       TEXT NOT NULL,
  evidence_path     TEXT NOT NULL CHECK (length(evidence_path) > 0),
  run_id            TEXT NOT NULL REFERENCES ingest_runs (run_id),
  pin_repository    TEXT,
  pin_revision      TEXT,
  pin_asset_digests TEXT CHECK (pin_asset_digests IS NULL OR json_valid(pin_asset_digests)),
  pin_target        TEXT,
  PRIMARY KEY (asset_id, upstream_asset_id, binding_kind)
);
INSERT INTO source_bindings_0004 (
  asset_id, upstream_asset_id, binding_kind, binding_grade, pinned_ref, upstream_head, pin_comparison,
  alignment_state, alignment_reason, observed_at, evidence_path, run_id,
  pin_repository, pin_revision, pin_asset_digests, pin_target)
SELECT asset_id, upstream_asset_id, binding_kind, binding_grade, pinned_ref, upstream_head, pin_comparison,
       CASE upper(alignment_state)
         WHEN 'ALIGNED' THEN 'ALIGNED'
         WHEN 'BEHIND' THEN 'BEHIND'
         WHEN 'DRIFTED' THEN 'DRIFTED'
         WHEN 'UNTRACEABLE' THEN 'UNTRACEABLE'
         ELSE 'UNKNOWN'
       END,
       alignment_reason, observed_at, evidence_path, run_id,
       NULL, NULL, NULL, NULL
FROM source_bindings;
DROP TABLE source_bindings;
ALTER TABLE source_bindings_0004 RENAME TO source_bindings;
CREATE INDEX IF NOT EXISTS source_bindings_upstream ON source_bindings (upstream_asset_id);

CREATE TABLE asset_alignment_0004 (
  asset_id         TEXT PRIMARY KEY REFERENCES assets (asset_id),
  alignment_state  TEXT NOT NULL CHECK (alignment_state IN ('ALIGNED','BEHIND','DRIFTED','UNTRACEABLE','UNKNOWN')),
  alignment_reason TEXT NOT NULL CHECK (length(alignment_reason) > 0),
  best_upstream_id TEXT REFERENCES assets (asset_id),
  observed_at      TEXT NOT NULL,
  evidence_path    TEXT NOT NULL CHECK (length(evidence_path) > 0),
  run_id           TEXT NOT NULL REFERENCES ingest_runs (run_id)
);
INSERT INTO asset_alignment_0004 (asset_id, alignment_state, alignment_reason, best_upstream_id, observed_at, evidence_path, run_id)
SELECT asset_id,
       CASE upper(alignment_state)
         WHEN 'ALIGNED' THEN 'ALIGNED'
         WHEN 'BEHIND' THEN 'BEHIND'
         WHEN 'DRIFTED' THEN 'DRIFTED'
         WHEN 'UNTRACEABLE' THEN 'UNTRACEABLE'
         ELSE 'UNKNOWN'
       END,
       alignment_reason, best_upstream_id, observed_at, evidence_path, run_id
FROM asset_alignment;
DROP TABLE asset_alignment;
ALTER TABLE asset_alignment_0004 RENAME TO asset_alignment;
CREATE INDEX IF NOT EXISTS asset_alignment_state ON asset_alignment (alignment_state);

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
SELECT a.asset_type, COALESCE(l.alignment_state, 'UNKNOWN') AS alignment_state, COUNT(*) AS n
FROM assets a LEFT JOIN asset_alignment l ON l.asset_id = a.asset_id
WHERE a.lifecycle = 'PRESENT'
GROUP BY 1, 2;
