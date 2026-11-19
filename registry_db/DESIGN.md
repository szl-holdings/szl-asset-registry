# SZL asset registry — design (v0.1, local candidate)

Status: **proposal + locally tested code. Not deployed. No remote D1 database exists for it.**
Owner: Qullqa (database). Architecture review: Chakana. Approval needed before any remote create/migrate/write.

## 1. Purpose
One registry that ties every asset in the estate to its source and says how sure we are:
GitHub org `szl-holdings` repos, Hugging Face org `SZLHOLDINGS` (models, datasets, Spaces, kernels, buckets, collections),
PyPI projects, and Cloudflare surfaces (Workers, D1, R2, KV, tunnels, zones, DNS, routes, Access apps).
Each asset has a **source binding** and an **alignment state** with `observed_at` and an **evidence path** on every fact.
GitHub is the code authority (SZL fleet mandate); everything else is reconciled against it.

## 2. Where it lives: its own D1 database `szl-asset-registry` (Chakana's decision; recommended here too)
| | shared `szl-agents-studio-store` | own `szl-asset-registry` (chosen) |
|---|---|---|
| Blast radius | studio Worker could write estate provenance | only the ingest holds a write binding; API/MCP get a read-only binding |
| Migration integrity | inherits F17 (studio store is missing `0004_snowflake_dispatch_hold.sql`; its base schema has no journal row) | clean, journaled, checksummed chain from `0001` |
| Lifecycle | studio release cadence | bulk re-ingest + receipted reads; restore windows independent |
| Studio needs data | cross-DB join | read through the registry API only (no cross-database joins) |
Creating the D1 database and any remote migration need Stephen's separate yes. Nothing here creates one.

## 3. Schema (SQLite = D1; `registry_db/migrations/`)
`0001_core` journal `registry_migrations`, `ingest_runs`, `assets`, `candidate_refs`
`0002_facts_bindings` `asset_facts` (+ append-only `asset_fact_history` via trigger), `asset_revisions`, `source_bindings`, `asset_alignment`, `coverage_reports`
`0003_receipts_proposals` hash-chained `receipts`, `proposals`, delete guard, views

**Stable ids.** `asset_id = "<asset_type>:<namespace>/<name>"` (`github_repo:szl-holdings/a11oy`, `hf_space:SZLHOLDINGS/killinchu`,
`pypi_project:pypi/szl-guardrail-receipt`, `cf_worker:cloudflare/szl-alert-relay`). `external_id` keeps the provider id (GitHub databaseId, HF `_id`, CF uuid) so a rename is detectable.
Upserts are `INSERT ... ON CONFLICT DO UPDATE` on those keys; re-ingesting the same snapshot is a no-op.

**Source binding per asset (own revision, `asset_revisions`):**
| asset | revision_kind | revision | digest |
|---|---|---|---|
| GitHub repo | `git_sha` | default-branch head sha (GraphQL, cross-checked with `git ls-remote`) | — |
| HF repo | `hf_revision` | Hub repo sha | — |
| PyPI project | `pypi_release` | `name==version` | sha256 of the sdist (else first wheel) + filename |
| Cloudflare Worker | `worker_etag` | script id | deployed etag |

**Downstream → upstream binding (`source_bindings`)**, one row per (asset, upstream repo, kind), with a *grade*:
- `verified_pin`: HF sync/publish commit title `szl-holdings/<repo>@<40-hex>` (machine-written by the publisher)
- `declared`: card text pin, `asset_map.json` (this repo), pyproject name in a repo, wrangler `name`/`database_name` in a repo
- `referenced`: a repo's text mentions the asset
`pin_comparison` (identical / upstream_ahead / pin_ahead / diverged / not_compared / no_pin) comes from the GitHub compare API (`pin...head`).

**Alignment (`asset_alignment`, never NULL; `UNKNOWN` is explicit)** — strict on purpose:
| situation | state |
|---|---|
| GitHub repo | `aligned` (authority) |
| verified pin == head | `aligned` |
| verified pin is an ancestor of head | `behind` |
| verified pin ahead / diverged / not compared | `unknown` |
| verified pin sha not found upstream | `untraceable` |
| only declared / referenced evidence | `unknown` (reason records what was compared) |
| built artifact (HF model/dataset/space/kernel, PyPI, Worker) with no binding at all | `untraceable` |
| bucket, collection, zone, DNS, route, D1, R2, KV, tunnel, Access app | `unknown` ("no source build by design") |
Only a machine-verifiable pin can yield `aligned`/`behind`. A card claiming a source does not.

**Facts** (`asset_facts`, PK asset+key): `value_json`, `observed_at`, `evidence_path` (a path into the evidence bundle, e.g.
`github/repo_details.json#repos.a11oy`), `run_id`. A changed value writes `asset_fact_history` (trigger). Agent-supplied facts live under `agent.*` and are never removed by ingest.

## 4. Migration guard (F1/F2: "out-of-order migrations silently skipped")
`registry_db/migrate.py`: ids contiguous from 0001; `MANIFEST.sha256` must match every file; the journal must be an **exact prefix** `1..k`
with matching name + sha256 (an applied id with an unapplied lower id is an error, never skipped; an edited applied file is an error);
each migration + its journal row run in one transaction. `python -m registry_db.migrate verify --db X` is read-only.
For D1, `wrangler d1 migrations apply` records its own `d1_migrations`; the same `verify` logic is run against an `export` before and after (see §8). No drizzle.

## 5. Receipts (who / when / why, append-only, hash-chained)
`receipts(seq, receipt_id, prev_hash, entry_hash, actor, actor_kind, action, target, reason, payload_json, at)`.
`entry_hash = sha256(canonical JSON of the entry incl. prev_hash)` (pattern from szl-safe-stack `ledger.py`). SQL triggers enforce
contiguous `seq`, `prev_hash == previous entry_hash` (genesis = 64 zeros), no UPDATE, no DELETE. D1 has no `sha256()`, so the Python verifier recomputes every hash
(`registry_db.receipts.verify_chain`) and catches tampering even if triggers were dropped. **What a receipt proves:** order and non-alteration of recorded entries since genesis.
**What it does not prove:** that the claim was true, or who held the key (no signature yet; signing needs Stephen's approval per the mandate).

Actions: `ingest.run`, `proposal.create|accept|reject`, `asset.tombstone`, `asset.delete`, `chain.verify`.
**Never delete without a receipt:** `DELETE FROM assets` aborts unless the newest receipt is `asset.delete` for exactly that asset (trigger). Normal disappearance = `lifecycle='absent'`.

## 6. Read API and MCP (read-only binding)
`registry_db/api.py` (read-only SQLite handle) and `registry_db/mcp_server.py` (JSON-RPC over stdio, stdlib):
`registry_query`, `registry_get_asset`, `registry_alignment_summary`, `registry_coverage`, `registry_verify_receipts`, `registry_list_receipts`, `registry_propose_update`.
No delete tool. `registry_propose_update` validates (actor, reason, known asset, `set_fact` keys must start with `agent.`) and writes a file to an **outbox** — it never touches the database.
The single writer (`registry_db/writer.py`) files it as a proposal under a `proposal.create` receipt; a human decision (`accept`/`reject`) is another receipt.
In Cloudflare terms: API/MCP Worker = read binding; ingest Worker/job = the only write binding; the outbox becomes a Queue or R2 prefix. (Port is not built.)

## 7. Ingest (`registry_db/ingest/`, pure Python, stdlib only)
Read-only, paced (`INGEST_MIN_INTERVAL`, default 0.25s; PyPI 1s), honours 429 / `Retry-After` / `x-ratelimit-reset`, resumable checkpoints, metadata only (no clones, weights or data).
`gh_enumerate` (REST `type=all` + GraphQL `totalCount` + `gh repo list`) → `gh_detail` (GraphQL batches + `git ls-remote`) → `gh_tree` (recursive tree names) → `gh_refs` (candidate bindings with `repo:path#Lnn` evidence)
→ `hf_ingest` (models/datasets/spaces/kernels/buckets/collections vs org overview counts) → `hf_commits` (sync pins from commit titles) → `hf_cards` (card-declared pins; only `(repo,sha,line)` kept)
→ `pypi_ingest` → `cf_ingest` (GET only; endpoints the token cannot read are recorded as gaps) → `gh_compare` → `build_snapshot` (deterministic JSON, sha256 = idempotency key) → `loader` (one transaction).
Private repos: metadata and file *names* only; file contents are read for public repos only and never copied into the snapshot.
PyPI note: `pypi.org/robots.txt` disallows `/pypi/*/json` for crawlers and the HTML pages sit behind a bot challenge (not bypassed). The job issues a bounded list of single-project JSON API lookups (names from our own repos, ≈170 requests at 1/s). It can be turned off; discovery by maintainer page is not possible without that challenge.
Secrets: tokens are read from the environment (`GITHUB_TOKEN`, `HF_TOKEN_SZL`/`HF_TOKEN`, `CF_API_TOKEN_SZL`/`CLOUDFLARE_API_TOKEN`) and never written to disk or logs; the snapshot contains no credentials.

## 8. Restore drill (defined before anything goes remote) — `registry_db/restore_drill.py`
Local, executable, tested: backup (SQLite online backup) → restore into a **new** file → `integrity_check`, `foreign_key_check`, migration `verify`, receipt chain verifies and **head hash equals the source head**, per-table row count + content digest equal.
Remote runbook (**not executed**; each step needs approval): (1) `wrangler d1 export szl-asset-registry --remote --output x.sql` (read) ; (2) import into a **new, differently named** D1 database; (3) run the same verification against it; (4) record the result as a `chain.verify` receipt; (5) D1 Time Travel (`wrangler d1 time-travel info`) is the point-in-time fallback — retention window must be read back from the account, not assumed. Never restore over the production database. RPO/RTO are UNKNOWN until measured.

## 9. Host repo for the code
`szl-holdings/szl-asset-registry` (existing, public, Apache-2.0, Python, default branch `main`): it already holds the file-based predecessor — `asset_map.json` (HF asset → GitHub source repo, fail-closed) and `tools/build_asset_map.py`. The registry is the database form of the same contract and consumes `asset_map.json` as a `declared` input.
Not `agents-studio` (private-turned-public product repo with an unrelated D1), not `a11oy`/`platform` (product/runtime repos). The PR adds only a new `registry_db/` package and `tests/test_registry_db_*.py`; it adds no workflow, secret or deploy path and changes no existing file. A new repo is not needed.

## 10. Known limits (v0.1)
- Alignment of PyPI/Workers is `unknown` for lack of provenance: PyPI JSON gives no commit pin; Worker deployments report an etag, not a git sha. Closing this needs publisher attestations (PEP 740) / `SOURCE_REVISION` vars read back — a future ingest source.
- HF README card pins are claims at write time; they are `declared`, never `aligned`.
- Facts removed upstream are deleted from `asset_facts` with a history row (except `agent.*`).
- `source_bindings` and `candidate_refs` are derived and rebuilt each run; accepted agent proposals persist as `agent.*` facts, not as bindings.
- GitHub audit-log events are first page only (100 newest `repo.*`). Org repo visibility history beyond that is not complete.
- No signature on receipts; no deployed Worker; no scheduler. Not operational.
