# What is reused, and why (read-only study, 2026-11-19)
| Piece (repo @ sha) | Reused | Why |
|---|---|---|
| a11oy `gdw_workspace.py` (`proof_outbox`, `effect_outbox`, @ 35151026) | the **outbox** idea: an effect is first recorded (`PENDING`), a single worker exports it; `payload_sha256`, `idempotency_key`, `status` | `registry_propose_update` writes only to an outbox; the single writer files it. Same one-writer rule. Not copied: a11oy's lease/CAS machinery (this DB has no concurrent writers). |
| a11oy `docs/adr/ADR-0001-a11oy-state-store.md` | immutable snapshot + verify-before-trust restore; "live DB on a FUSE volume is unsafe" | informs the restore drill (backup → restore into a new file → verify) and why the registry is a small local-disk SQLite/D1, not a bucket-mounted file |
| szl-safe-stack `safe-qa-service/.../ledger.py` | canonical-JSON + `previous_hash` + GENESIS + `verify_chain` | the receipt chain uses the identical pattern, stdlib only, SQLite instead of Postgres |
| agents-studio `hosted/edge/` (`schema.sql`, `migrations/0002..0004`, `wrangler.toml`) | D1 conventions: additive idempotent `CREATE ... IF NOT EXISTS`, `migrations_dir`, `[[d1_databases]]` binding, `CHECK` constraints, no secrets in wrangler.toml | same D1 idiom. Not reused: the database itself (F17: `0004` unapplied; base schema not journaled) — hence a separate D1 |
| hatun-mcp `hatun_mcp/server_http.py` (`read`/`write`/`admin` scope bindings) | the **scope split** (a read scope cannot call privileged tools) | MCP surface exposes read tools plus a proposal tool; no write/delete tool |
| platform (`DATA-MODEL.md`, `API-CATALOGUE.md`) | naming/contract reference only (≈500-table Replit-era model, now retired) | nothing copied; the registry is deliberately small |
| szl-holdings/szl-asset-registry `asset_map.json`, `tools/build_asset_map.py` | **declared** HF → GitHub mapping input and the host repo | continuity with the existing fail-closed map |
| szl-db-audit F1/F2 (drizzle silent skips), F17 | migration guard design and the own-D1 decision | see DESIGN §2, §4 |
