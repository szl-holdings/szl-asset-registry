# PROPOSED RULER AMENDMENT: internal-consistency verification — 2026-11-25 (draft, propose-only)

**Status: DRAFT AMENDMENT to RULER.md v1.0, cut per Kimi advisory ruling W27T7 Q5 (GO). Propose-only. Adoption is owner-gated; the ruler council process owns acceptance. Not merged anywhere.**

## Amendment text (proposed insertion into the ruler's done-gate / evidence-graph section)

> **Internal-consistency checks (machine, required for any receipt bearing signature fields).** A receipt that carries `signatureBase64` / `publicKeySpkiBase64` / `canonical` / `keyId` fields MUST have all four machine-checkable, and the checks MUST be reported as a separate count on the scoreboard, never merged into completion or trust percentages:
>
> 1. **SIGVERIFY:** the signature verifies against the embedded public key over the canonical payload bytes (Ed25519 or as-declared).
> 2. **CANONICAL-MATCH:** the in-file payload is semantically equal to the signed canonical (`json.loads(canonical) == payload`).
> 3. **KEYID-DERIVATION:** the declared keyId equals the declared derivation of the embedded key material (observed estate convention: `sha256(SPKI DER)[:16]`).
>
> Passing all three yields the classification **INTERNAL_CONSISTENT, self-attested** — which is NOT trust. Internal consistency is orthogonal to the trust axis and confers zero trust points; an embedded public key proves possession of the matching private key, nothing more. Failure yields **INTERNAL_INCONSISTENT (red)** regardless of other axes. In-payload self-claims (e.g. `signatureChainValid: true`) MUST be annotated as CLAIM_UNVERIFIED at the ruler level until verified against external key provenance.

## Evidence basis (measured, this estate, 2026-11-24/25)

- 6 outlier repos, 13 signed receipts, 3 Ed25519 keys: **13/13 SIGVERIFY, 13/13 CANONICAL-MATCH, 13/13 KEYID-DERIVATION PASS** (device pynacl 1.6.2; fail-closed first run disclosed: raw-32-byte-key vs SPKI-DER error, corrected, preserved).
- Binary digest recompute vs signed payload digests: **16/16 MATCH** (actual downloaded bytes).
- All payload dates predate OB2 doctrine → the amendment deliberately does NOT upgrade these receipts' trust; it only codifies the machine checkable layer and keeps it separate-count honest.

## Scoreboard note (separate counts doctrine)

If adopted, the estate scoreboard gains independent counters: `internal_consistent_receipts`, `digest_recompute_verified_files`, alongside (never inside) the existing trust and completion counts. No single green % may combine them.

Markers: `AMENDMENT_PROPOSE_ONLY_OWNER_GATED` · `SEPARATE_COUNTS_PRESERVED` · `INTERNAL_CONSISTENT_IS_NOT_TRUST` · `W27T7_Q5_GO_EXECUTED`.
