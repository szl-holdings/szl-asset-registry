# szl-asset-registry

Machine-readable registry of Hugging Face asset-to-GitHub **references** ("GitHub is source" doctrine). A README hyperlink or asset-name match does not prove which repository produced model weights, training data, model evaluations, or a deployed runtime.

## Status (generated 2026-11-20, evidence sweep lap 2)

- 666 HF assets censused (414 models, 173 datasets, 79 spaces; includes private)
- 648 assets have a GitHub **reference** (66 by repo-name match, 513 by GitHub link/card reference, 69 by curated override), not 648 verified model producers
- 18 UNMAPPED in the committed 666-asset snapshot; never guess. Some newer or private Hub assets may not yet be in this historical snapshot.
- **491 references point to `estate-cards`, a card/documentation generator — NOT verified training/inference source.** The source producer, checkpoint hashes, evaluation, and deployment evidence remain independently gated. The additive `tools/lineage_boundaries.py` validator enforces the distinction.
- 2026-11-20 evidence sweep: 73 backlog assets re-audited against their README cards; 63 case-cards carry an explicit canonical generator URL (github.com/szl-holdings/estate-cards weaver v0.1.0) and were mapped via evidence-cited overrides; 10 remain fail-closed (no unique canonical source URL).

## Method (fail-closed)

1. Name match: normalized asset name == normalized repo name (with version-suffix stripping).
2. Card evidence: the asset's own README.md on the Hub is fetched and scanned for github.com/szl-holdings/ links; a link to an existing repo is accepted.
3. Otherwise the asset is recorded UNMAPPED with a family tag. No mapping is ever fabricated.

## Unmapped gap ledger: 18 current, 129 historical

Current committed `asset_map.json` lists 17 `other` and one `run-artifact-store` unmapped asset. The 129-row family breakdown below is a **historical earlier snapshot**, not the present denominator. It must not be added to the 18 or quoted as current evidence.

| Family | Count | Meaning |
| --- | --- | --- |
| other | 60 | assorted models/spaces needing individual study |
| candidate-eval-20261104 | 26 | enterprise candidate evaluation outputs (Nov 4 run) |
| laptop-lora-training | 20 | LoRA adapters trained on the estate laptop |
| corpus-benchmark | 12 | corpus/benchmark datasets |
| run-artifact-store | 7 | run/eval artifact stores |
| marketing-surface | 4 | marketing surfaces |

Closing a bucket requires independent code/data lineage, an exact source revision, and governed runtime readback. Creating another repository or adding a card-weaver hyperlink is **not** by itself proof of source ownership or release readiness.

## Files

- `asset_map.json` — the map (generated, committed; regenerate with tools/build_asset_map.py)
- `tools/build_asset_map.py` — generator (takes org_audit.json + hf_census.json as inputs)
- `tools/validate.py` — CI validator (schema + count consistency)

## Regenerate

```bash
python tools/build_asset_map.py --audit org_audit.json --census hf_census.json --out asset_map.json
```

Then commit. CI validates on every push.

## Public model namespace hygiene — November 19, 2026

The [frozen 184-row public model triage snapshot](data/hf_public_model_hygiene_20261119.json) preserves observed Hub commit SHA, weight-file count, flags and receipt-file count for every listed repository. This snapshot is not a release list.

A read-only, timestamped public Hub model census is available with:
`python tools/audit_model_hygiene.py --live --output hf-model-hygiene-$(date -u +%Y%m%dT%H%M%SZ).json`.
For offline replay, pass `--snapshot <public-full-models-response.json>` instead of `--live`.
The output path is exclusive-create; the tool never changes Hub repository content or visibility.

At **2026-11-19T14:46:49Z**, the independent public API read returned **184 models**.
Of these, **41 lacked recognized tensor-weight filenames**, **nine were explicitly tagged software,
kernel or fixture without such files**, **20 were laptop-LoRA variants**, and **69 had candidate/research
markers**. These classifications overlap; none is an automatic deletion order or an assertion that
a non-tensor statistical model is untrained. Private/inaccessible coverage is unavailable.

**Card metadata census, additive only.** The same source-owned read-only
tool now flags missing standard `README.md` model cards and missing declared
`license:` Hub tags separately from checkpoint/adapter hygiene. It records
`model_card_readme_present` and
`license_metadata_present_not_rights_verified` as observations—not claims that
a card is accurate, a license grants training rights, or a model has passed
quality/release gates. Offline tests check both missing and present metadata.
Use a fresh `--live` observation before acting on historical snapshots;
never mass-delete or auto-publish cards from filename heuristics alone.

**Critical distinction:** model names ending in `-trained`, checkpoint-looking filenames,
eval JSON, and repository-bound battery receipts do **not** establish independently verified
training, exact checkpoint identity, released quality, or runtime admission. The tool forces
`training_verified=false`, `quality_verified=false` and `promotion_authorized=false`
until an external governed, weight-hash-bound train/eval/readback process supplies evidence.
Do not auto-delete, rename, change visibility, retrain, or publish from this census.

## Doctrine

- Fail-closed honesty: UNMAPPED stays UNMAPPED until evidence exists.
- Receipts chain canonical: mappings carry the method that produced them.
- This registry is metadata only; it never duplicates asset content.