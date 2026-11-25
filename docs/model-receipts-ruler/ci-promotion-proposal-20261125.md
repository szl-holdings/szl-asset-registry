# CI Promotion Proposal: receipts-ruler selftest gate — 2026-11-25 (PROPOSE-ONLY, DRAFT)

## What

Add a minimal GitHub Actions workflow (`.github/workflows/receipts-ruler-selftest.yml`) that runs the
estate ruler validator's embedded 6-case selftest on every PR touching `docs/model-receipts-ruler/**`,
plus manual dispatch. Stdlib-only validator; no dependencies, no secrets, no network.

## Why

1. The selftest was cleared by measurement on 2026-11-24 (device execution 6/6 PASS, receipt
   `selftest-receipt-20261124.md`, in-file honest note cleared by Kimi W27T2 Q2 ruling) and verified
   again on PR#36 commit 5d59944e readbacks. CI promotion gives the estate *measurement continuity*
   so the fail-closed property is checked on every future edit of the ruler docs, by machine.
2. The ruler's own honest bar is preserved: a green CI check is **NOT** a signature and **NOT** trust.
   Trust stays UNSIGNED_UNVERIFIED (amber) pending the owner signature credential mint (.github#1058).
   This gate annotation shall not be represented as verified-green anywhere.

## Scope and discipline

- Propose-only, DRAFT, owner-gated merge. This branch is cut from `receipts-ruler-20261124` (PR#36)
  so the validator exists for the workflow; merge only AFTER (or together with) PR#36, or rebase
  onto main once PR#36 lands.
- Zero writes outside this branch. No guards, no rulesets touched (owner-physics: the 9 BLOCKED
  signature/review rulesets stay authoritative).
- If the owner prefers, an alternative is adding the same selftest step to an existing lint workflow
  instead of a new one; this PR is the minimal additive proposal.

Markers: PROPOSE_ONLY_DRAFT_OWNER_GATED; SELFTEST_CLEARED_BY_MEASUREMENT_20261124_6_OF_6;
CI_CHECK_IS_NOT_A_SIGNATURE; ZERO_TRUST_UPGRADE.
