# CI Promotion Proposal: receipts-ruler selftest gate — 2026-11-25 (propose-only)

## Status update (revision 2, same day)

The first CI run of this proposal FAILED the repo's actions-security policy: tag-pinned actions
(`actions/checkout@v4`, `actions/setup-python@v5`) are not allowed in szl-holdings — all actions
must be pinned to full-length commit SHAs. This lap corrects the workflow to the estate's own
sanctioned pin pattern (taken verbatim from main's `validate.yml`):

- `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`
- `actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` with `python-version: "3.12"`
- `permissions: contents: read`
- the workflow now also gates its own file (`paths:` includes the workflow yml)

The failure was disclosed, root-caused from the run annotations ("Set up job: actions must be
pinned to a full-length commit SHA"), and repaired with the estate's standing pins — not invented
ones. This is the honest-bar way the estate does CI: fail-closed, measure, fix, re-run.

## What

Add a minimal GitHub Actions workflow (`.github/workflows/receipts-ruler-selftest.yml`) that runs the
estate ruler validator's embedded 6-case selftest on every PR touching `docs/model-receipts-ruler/**`
(and the workflow itself), plus manual dispatch. Stdlib-only validator; no dependencies, no secrets,
read-only contents permission.

## Why

1. The selftest was cleared by measurement on 2026-11-24 (device execution 6/6 PASS, receipt
   `selftest-receipt-20261124.md`) and re-verified on PR#36 commit readbacks. CI promotion gives the
   estate measurement continuity: the fail-closed property gets checked by machine on every future
   edit of the ruler docs.
2. The ruler's honest bar is preserved: a green CI check is NOT a signature and NOT trust. Trust
   stays UNSIGNED_UNVERIFIED (amber) pending the owner signature credential mint (.github#1058).
   This gate annotation shall not be represented as verified-green anywhere.

## Scope and discipline

- Propose-only; adoption owner-gated. Branch stacked on the ruler docs (merged to main via PR#36);
  base retargeted to main.
- Zero writes outside this branch. No guards, no rulesets touched (the blocked signature/review
  rulesets stay authoritative).

Markers: PROPOSE_ONLY_OWNER_GATED; SELFTEST_CLEARED_BY_MEASUREMENT_20261124_6_OF_6;
CI_CHECK_IS_NOT_A_SIGNATURE; ZERO_TRUST_UPGRADE; SHA_PINNED_ACTIONS_ESTATE_POLICY;
FIRST_CI_FAILURE_DISCLOSED_AND_ROOT_CAUSED.
