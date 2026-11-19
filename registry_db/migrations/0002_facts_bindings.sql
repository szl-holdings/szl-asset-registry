-- 0002_facts_bindings: facts (observed_at + evidence on every fact), own revisions, source bindings, alignment.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS asset_facts (
  asset_id      TEXT NOT NULL REFERENCES assets (asset_id),
  key           TEXT NOT NULL CHECK (length(key) BETWEEN 1 AND 80),
  value_json    TEXT NOT NULL CHECK (json_valid(value_json)),
  observed_at   TEXT NOT NULL,
  evidence_path TEXT NOT NULL CHECK (length(evidence_path) > 0),
  run_id        TEXT NOT NULL REFERENCES ingest_runs (run_id),
  PRIMARY KEY (asset_id, key)
);

CREATE TABLE IF NOT EXISTS asset_fact_history (
  hist_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id       TEXT NOT NULL,
  key            TEXT NOT NULL,
  old_value_json TEXT NOT NULL,
  new_value_json TEXT NOT NULL,
  changed_at     TEXT NOT NULL,
  evidence_path  TEXT NOT NULL,
  run_id         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS asset_fact_history_asset ON asset_fact_history (asset_id, key);

CREATE TRIGGER IF NOT EXISTS asset_facts_history_trg
AFTER UPDATE OF value_json ON asset_facts
WHEN OLD.value_json <> NEW.value_json
BEGIN
  INSERT INTO asset_fact_history (asset_id, key, old_value_json, new_value_json, changed_at, evidence_path, run_id)
  VALUES (NEW.asset_id, NEW.key, OLD.value_json, NEW.value_json, NEW.observed_at, NEW.evidence_path, NEW.run_id);
END;

CREATE TRIGGER IF NOT EXISTS asset_fact_history_append_only_upd BEFORE UPDATE ON asset_fact_history
BEGIN SELECT RAISE(ABORT, 'asset_fact_history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS asset_fact_history_append_only_del BEFORE DELETE ON asset_fact_history
BEGIN SELECT RAISE(ABORT, 'asset_fact_history is append-only'); END;

-- The asset's OWN current revision (what it reports now).
--   github_repo  -> git_sha         revision = default-branch head sha
--   hf_*         -> hf_revision     revision = Hub repo sha
--   pypi_project -> pypi_release    revision = "name==version", digest_sha256 = sdist (else first wheel) sha256
--   cf_worker    -> worker_etag     revision = script id, digest_sha256 = deployed etag
CREATE TABLE IF NOT EXISTS asset_revisions (
  asset_id        TEXT PRIMARY KEY REFERENCES assets (asset_id),
  revision_kind   TEXT NOT NULL CHECK (revision_kind IN ('git_sha','hf_revision','pypi_release','worker_etag','none')),
  revision        TEXT,
  digest_sha256   TEXT CHECK (digest_sha256 IS NULL OR length(digest_sha256) = 64),
  digest_filename TEXT,
  observed_at     TEXT NOT NULL,
  evidence_path   TEXT NOT NULL CHECK (length(evidence_path) > 0),
  run_id          TEXT NOT NULL REFERENCES ingest_runs (run_id)
);

-- Downstream asset -> upstream GitHub source binding. One row per (asset, upstream, kind).
CREATE TABLE IF NOT EXISTS source_bindings (
  asset_id          TEXT NOT NULL REFERENCES assets (asset_id),
  upstream_asset_id TEXT NOT NULL REFERENCES assets (asset_id),
  binding_kind      TEXT NOT NULL CHECK (binding_kind IN ('sync_commit_pin','declared_map','pyproject_in_repo','wrangler_in_repo','reference_only')),
  binding_grade     TEXT NOT NULL CHECK (binding_grade IN ('verified_pin','declared','referenced')),
  pinned_ref        TEXT,
  upstream_head     TEXT,
  pin_comparison    TEXT NOT NULL CHECK (pin_comparison IN ('identical','upstream_ahead','pin_ahead','diverged','not_compared','no_pin')),
  alignment_state   TEXT NOT NULL CHECK (alignment_state IN ('aligned','behind','untraceable','unknown')),
  alignment_reason  TEXT NOT NULL CHECK (length(alignment_reason) > 0),
  observed_at       TEXT NOT NULL,
  evidence_path     TEXT NOT NULL CHECK (length(evidence_path) > 0),
  run_id            TEXT NOT NULL REFERENCES ingest_runs (run_id),
  PRIMARY KEY (asset_id, upstream_asset_id, binding_kind)
);
CREATE INDEX IF NOT EXISTS source_bindings_upstream ON source_bindings (upstream_asset_id);

-- Final per-asset classification (explicit UNKNOWN; never NULL).
CREATE TABLE IF NOT EXISTS asset_alignment (
  asset_id         TEXT PRIMARY KEY REFERENCES assets (asset_id),
  alignment_state  TEXT NOT NULL CHECK (alignment_state IN ('aligned','behind','untraceable','unknown')),
  alignment_reason TEXT NOT NULL CHECK (length(alignment_reason) > 0),
  best_upstream_id TEXT REFERENCES assets (asset_id),
  observed_at      TEXT NOT NULL,
  evidence_path    TEXT NOT NULL CHECK (length(evidence_path) > 0),
  run_id           TEXT NOT NULL REFERENCES ingest_runs (run_id)
);
CREATE INDEX IF NOT EXISTS asset_alignment_state ON asset_alignment (alignment_state);

CREATE TABLE IF NOT EXISTS coverage_reports (
  run_id         TEXT NOT NULL REFERENCES ingest_runs (run_id),
  source         TEXT NOT NULL,
  asset_type     TEXT NOT NULL,
  expected_count INTEGER NOT NULL,
  ingested_count INTEGER NOT NULL,
  missing_count  INTEGER NOT NULL,
  detail_json    TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(detail_json)),
  observed_at    TEXT NOT NULL,
  evidence_path  TEXT NOT NULL CHECK (length(evidence_path) > 0),
  PRIMARY KEY (run_id, source, asset_type)
);
