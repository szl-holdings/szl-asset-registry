# Source-shadow byte readback — source-only review

This contract compares the **exact bytes** of the legacy `asset_map.json`
with the untrusted, unsigned `receipts/source-binding-shadow-20261120.json`.
It never imports model code or contacts a provider. A successful comparison
is only `BYTE_BOUND_SHADOW_ONLY`, not producing-source attestation, training,
evaluation, deployment, certification, or publication.

## Observed negative control (2026-11-20)

At the reviewed source-head of PR #15, the checked-in map SHA-256 was
`a4ae0c9bf02f21f91680191ce588fde7c4a7fd70dc42bd6b40c090ab72e4ea75`,
while the checked-in shadow claimed source SHA-256
`7893238dbe74ae15ea80b06af3ee930347702549c31080cc6b94275c0cf9e4d6`.
The verifier MUST return `HOLD/SOURCE_MAP_BYTE_DIGEST_MISMATCH`.
The hashes are checksums, not signatures; even a self-consistent rewritten
source and shadow can be forged.

## Workflow

Run the offline unit tests with `python -m unittest discover -s tests` in an
isolated checkout of the approved source. The existing source owner must
independently establish the correct input commit, regenerate the shadow from
that exact input if appropriate, review changed bytes, and bind a trusted
signature separately. Do **not** edit or regenerate the historic shadow
from this stacked review, mutate the asset map, change model visibility,
rename repositories, or claim training completed. Missing private models
are handled only in an owner-controlled private observation.

Cross-plane joins need exact immutable provider revisions, distinct
source-producer attestations, and data/model rights before they can be
used as release or training evidence.
