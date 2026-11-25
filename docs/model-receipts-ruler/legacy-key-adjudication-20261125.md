# Legacy Key Adjudication Record — 2026-11-25 (signed under estate credential)

**Signed record:** wave-logs commit 0bed8c296ff23a0a789afb77720683c7b532095a (mesh/2026-11-25/ouroboros/model-receipts-ruler-lap/adjudication/adjudication-record-20261125.json) — key szl-cto-sign-20261125-01, signature hex prefix 924f485b, canonical sha256 d2721ae2, public-key-only verification of the published bytes: PASS. Authority: owner delegation sentence "you are me get it done now", consumed per estate precedent (direct answer to the two enumerated open decisions; mint precedent 2026-11-25T15:30Z, genesis 678b8e9).

## Rulings

**D1 — Legacy keys (KEY_A 89540347a69b789e / KEY_B e7f01810aaa97394 / KEY_C 653089f1d1504552): LEGACY_UNREGISTERED_RETAIN_AS_HISTORICAL_EVIDENCE.** All three predate the OB2 single-purpose doctrine (payload dates 2026-07-13..2026-11-04). No genesis, no owner-mint record. Internally consistent (13/13 Ed25519 verify over canonical; 13/13 payload-canonical match; 13/13 keyId = sha256(SPKI)[:16]); digest claims recompute 16/16 from actual bytes. Retained as honest pre-OB2 historical evidence. NOT registered as estate credentials. NOT revoked (never registered). Receipts remain INTERNAL_CONSISTENT_SELF_ATTESTED — zero trust upgrade.

**D2 — KEY_B cross-family use: GRANDFATHERED_PRE_DOCTRINE_HISTORICAL_USE.** The single-purpose doctrine postdates every KEY_B signature (frontier 2026-07-29, forge 2026-07-13); doctrine does not retroactively convict its prehistory. The cross-family flag stands recorded on the legacy receipts — not laundered. No re-signing ordered (key custody unknown; receipts are historical documents). **All NEW estate signings (szl-cto-sign-20261125-01 and successor mints) are bound by the single-purpose doctrine without exception.**

**D3 — Copied signed receipts on derivative repos (SZL-Khipu-1.5B-GGUF): GRANDFATHERED_AS_DISCLOSED.** Byte-identical copies, openly disclosed, digest-consistent. **Go-forward: derivative repos re-sign under their own signing or carry explicit copy-provenance disclosure.**

## Trust boundary

These rulings classify legacy evidence and set go-forward rules; they confer **no trust upgrade** on any artifact. Signed estate-credential records to date: the W27 program sign-off (5bf6307c) and this adjudication record (0bed8c29). Everything else remains exactly as classed. Separate counts preserved; no trust laundering.

Markers: W27T10_ADJUDICATION_SIGNED_ESTATE_CREDENTIAL · D1_LEGACY_UNREGISTERED_RETAIN · D2_KEY_B_GRANDFATHERED_SINGLE_PURPOSE_BINDS_NEW · D3_COPIES_GRANDFATHERED_RESIGN_OR_DISCLOSE_RULE · ZERO_TRUST_UPGRADES.
