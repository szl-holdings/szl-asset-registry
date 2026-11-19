-- 0001_core: migration journal, ingest runs, assets, candidate references.
-- D1 (SQLite) compatible: no sha256() in SQL; hashes are computed by the Python writer.
-- Migration guard: registry_migrations is the journal (id, name, sha256). The runner and
-- registry_db/migrate.py (apply|verify) refuse gaps, reordering, edited files, or an unapplied lower id.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS registry_migrations (
  id         INTEGER PRIMARY KEY CHECK (id >= 1),
  name       TEXT    NOT NULL UNIQUE,
  sha256     TEXT    NOT NULL CHECK (length(sha256) = 64),
  applied_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  run_id          TEXT PRIMARY KEY,
  source          TEXT NOT NULL CHECK (source IN ('github','hf','pypi','cloudflare','all')),
  started_at      TEXT NOT NULL,
  finished_at     TEXT,
  snapshot_sha256 TEXT NOT NULL CHECK (length(snapshot_sha256) = 64),
  snapshot_path   TEXT,
  tool_version    TEXT NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('running','complete','partial','failed')),
  counts_json     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(counts_json)),
  coverage_json   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(coverage_json))
);

-- One row per observed asset. asset_id is a stable natural key: "<asset_type>:<namespace>/<name>".
CREATE TABLE IF NOT EXISTS assets (
  asset_id      TEXT PRIMARY KEY,
  asset_type    TEXT NOT NULL CHECK (asset_type IN (
                  'github_repo','hf_model','hf_dataset','hf_space','hf_kernel','hf_bucket','hf_collection',
                  'pypi_project',
                  'cf_worker','cf_d1','cf_r2','cf_kv','cf_tunnel','cf_zone','cf_dns_record','cf_route',
                  'cf_access_app','cf_worker_domain')),
  namespace     TEXT NOT NULL,
  name          TEXT NOT NULL,
  external_id   TEXT,
  visibility    TEXT NOT NULL CHECK (visibility IN ('public','private','internal','unknown')),
  lifecycle     TEXT NOT NULL DEFAULT 'present' CHECK (lifecycle IN ('present','absent')),
  first_seen_at TEXT NOT NULL,
  last_seen_at  TEXT NOT NULL,
  observed_at   TEXT NOT NULL,
  evidence_path TEXT NOT NULL CHECK (length(evidence_path) > 0),
  run_id        TEXT NOT NULL REFERENCES ingest_runs (run_id),
  UNIQUE (asset_type, namespace, name)
);
CREATE INDEX IF NOT EXISTS assets_type ON assets (asset_type);
CREATE INDEX IF NOT EXISTS assets_external ON assets (asset_type, external_id);

-- Raw references found in README/config/workflow text: candidates only (a reference is evidence, not proof).
CREATE TABLE IF NOT EXISTS candidate_refs (
  ref_key       TEXT PRIMARY KEY,                -- sha256(repo|kind|target_type|target_id|evidence_path)
  from_asset_id TEXT NOT NULL REFERENCES assets (asset_id),
  kind          TEXT NOT NULL CHECK (kind IN ('hf','pypi','cloudflare')),
  target_type   TEXT NOT NULL,
  target_id     TEXT NOT NULL,
  evidence_path TEXT NOT NULL CHECK (length(evidence_path) > 0),
  snippet       TEXT,
  observed_at   TEXT NOT NULL,
  run_id        TEXT NOT NULL REFERENCES ingest_runs (run_id)
);
CREATE INDEX IF NOT EXISTS candidate_refs_target ON candidate_refs (kind, target_type, target_id);
