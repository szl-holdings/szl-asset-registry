# szl-asset-registry

Canonical machine-readable map of every Hugging Face asset in the SZLHOLDINGS org to the GitHub repository that codes and produces it ("GitHub is source" doctrine).

## Status (generated 2026-11-14)

- 351 HF assets censused (191 models, 94 datasets, 66 spaces)
- 222 mapped to a source repo with evidence (57 by repo-name match, 165 by GitHub links found in the asset's own Hub card)
- 129 UNMAPPED — declared honestly, never guessed, bucketed by family below

## Method (fail-closed)

1. Name match: normalized asset name == normalized repo name (with version-suffix stripping).
2. Card evidence: the asset's own README.md on the Hub is fetched and scanned for github.com/szl-holdings/ links; a link to an existing repo is accepted.
3. Otherwise the asset is recorded UNMAPPED with a family tag. No mapping is ever fabricated.

## Unmapped gap ledger (129)

| Family | Count | Meaning |
| --- | --- | --- |
| other | 60 | assorted models/spaces needing individual study |
| candidate-eval-20261104 | 26 | enterprise candidate evaluation outputs (Nov 4 run) |
| laptop-lora-training | 20 | LoRA adapters trained on the estate laptop |
| corpus-benchmark | 12 | corpus/benchmark datasets |
| run-artifact-store | 7 | run/eval artifact stores |
| marketing-surface | 4 | marketing surfaces |

Closing each bucket means either mapping it to the producing repo once that repo exists, or creating the missing source repo. Buckets are the build queue for the alignment loop.

## Files

- `asset_map.json` — the map (generated, committed; regenerate with tools/build_asset_map.py)
- `tools/build_asset_map.py` — generator (takes org_audit.json + hf_census.json as inputs)
- `tools/validate.py` — CI validator (schema + count consistency)

## Regenerate

```bash
python tools/build_asset_map.py --audit org_audit.json --census hf_census.json --out asset_map.json
```

Then commit. CI validates on every push.

## Doctrine

- Fail-closed honesty: UNMAPPED stays UNMAPPED until evidence exists.
- Receipts chain canonical: mappings carry the method that produced them.
- This registry is metadata only; it never duplicates asset content.
