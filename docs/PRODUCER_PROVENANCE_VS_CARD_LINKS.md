# Producer provenance is not card-link coverage

Status: **SOURCE ONLY / EVIDENCE HOLD** (2026-11-20).

The existing historical `asset_map.json` has 666 assets, 648 non-null
`source_repo` links, and 18 unmapped. Exactly 491 links point to
`estate-cards` (428 from `card`, 63 from `override`). This is a
README/SVG card weaver, so a link to it cannot prove it produced model
weights, training data, or Space application source. A majority of links
in a card is not proof of producer identity.

This change adds a separate, versioned **offline audit** instead of silently
changing historical `source_repo` and breaking downstream clients. Its
`producer_repo` is NULL and `producer_verified` is FALSE until separately
reviewed evidence exists. A documented generator citation can label
`card_generator_repo`, never the producer.

Run from the repository root, no network or credentials:

```bash
python tools/audit_producer_provenance.py --audit-only
python -m unittest discover -s tests -p 'test_producer_provenance.py' -v
```

The audit records SHA-256 of both exact input JSON byte strings in its output and rejects unknown or malformed evidence IDs. Ambiguous cross-type IDs never inherit a type-unspecified card-generator citation.

Optionally write a **new unsigned** local snapshot via
`--out /new/audit.json`; existing files cannot be overwritten.
`legacy_link_coverage` means links, not verified producer mappings.
`producer_verified_total=0` means this audit has **no independently
attested producers**, not that all legacy links are incorrect or that
all the underlying models are untrained.

Before a future reviewed migration to verified producer mappings, require
immutable GitHub producing source and commit, specific HF asset revision,
actual model training/weight hashes where applicable, license and consent,
independent eval, reviewer evidence, negative controls and exact runtime
binding. Preserve ambiguous/unmapped classifications until proven. This
source-only code does not authorize HF uploads, training, model promotion,
Cloudflare writes, or merges.

Tracks existing source-owner issues #13 and #14; no duplicate issue.
