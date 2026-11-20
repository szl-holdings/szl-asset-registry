# szl-asset-registry

Machine-readable **legacy source-hint** map for Hugging Face assets in the SZLHOLDINGS org. A matching repo name, shared README URL, or curated override is discovery metadata; it does **not** independently establish the GitHub checkout that produced an asset's model weights, dataset, or deployed Space. Source binding requires independently verified immutable revisions and artifact digests.

## Status (generated 2026-11-20, evidence sweep lap 2)

- 666 HF assets censused (414 models, 173 datasets, 79 spaces; includes private)
- 648 legacy source **hints** (66 by name heuristic, 513 by card URL, 69 by curated override), not 648 independently producer-attested mappings
- 18 UNMAPPED - declared honestly, never guessed; queue with reasons in data/unresolved_assets.json
- 2026-11-20 evidence sweep: 73 backlog assets re-audited against their README cards; 63 case-cards carry an explicit canonical generator URL (github.com/szl-holdings/estate-cards weaver v0.1.0) and were mapped via evidence-cited overrides; 10 remain fail-closed (no unique canonical source URL).

## Source-binding evidence qualification (2026-11-20)

The checked-in v1 map reports a plausible source-repo hint for 648 of 666 assets but carries no verified producer-source checkout and model/dataset artifact digest pair. The reproducible, network-free audit in `tools/source_binding_audit.py` classified **428 card-link hints to `estate-cards`** as `SHOWCASE_LINK_NOT_PRODUCER_PROOF`; it can identify those links without assuming the showcase repo trained 428 models. **Producer bindings proven by this input: 0** (missing proof fields, not proof no training occurred). The audit SHA-256-binds its input, rejects duplicate asset identities and unsupported self-asserted verification, and publishes no tokens. This is an honesty overlay; changing a source hint into an authenticated producer link requires a separately reviewed, asset-specific attestation and migration.

```bash
python tools/source_binding_audit.py --input asset_map.json --output source-binding-shadow-20261120.json
```

The output is exclusive-create and should be retained with the source map commit. `coverage.mapped` is a historical count of hints, not a release gate, trained-model count, or operational-source-bound count.

## Legacy mapping heuristic (not producer provenance)

1. Name match: normalized asset name == normalized repo name (with version-suffix stripping).
2. Card evidence: the asset's own README.md on the Hub is fetched and scanned for github.com/szl-holdings/ links; a link to an existing repo is accepted.
3. Otherwise the asset is recorded UNMAPPED with a family tag. This prevents unsupported hint generation; it does not certify a found link as the actual producer.

## Historical unmapped gap ledger (129 before the November 20 evidence sweeps)

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