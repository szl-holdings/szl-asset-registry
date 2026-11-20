# szl-asset-registry

Machine-readable **legacy source-hint** map for Hugging Face assets in the SZLHOLDINGS org. A matching repo name, shared README URL, or curated override is discovery metadata; it does **not** independently establish the GitHub checkout that produced an asset's model weights, dataset, or deployed Space. Source binding requires independently verified immutable revisions and artifact digests; the separate [producer-evidence audit](docs/PRODUCER_PROVENANCE_VS_CARD_LINKS.md) preserves that distinction before any production claim.

## Status (generated 2026-11-20, evidence sweep lap 2)

- 666 HF assets censused (414 models, 173 datasets, 79 spaces; includes private)
- 648 legacy source **hints** (66 by name heuristic, 513 by card URL, 69 by curated override), not 648 independently producer-attested mappings. Of these, 491 point to the \`estate-cards\` card generator and require producer-specific review.
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

## Historical unmapped gap ledger (129 before the November 20 evidence sweeps; superseded by the 18-row current unmapped count)

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
- `tools/audit_producer_provenance.py` — offline fail-closed audit of producer evidence versus legacy link coverage; does not mutate `asset_map.json`

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
## Durable source pins (drift gate v2)

`tools/drift_gate.py` is an offline gate that binds every mapped asset to a
pinned GitHub source and a measured Hub README hash.

**Identity model.** Hub identity is `(id, type)`; the real map contains legal
cross-type twins (same id, different type), so pin keys are composite with the
exact grammar `^(models|datasets|spaces)/[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$`
(one type prefix, one owner/name id). A bare-id pins file cannot even hold both
twins (JSON key collision), so composite keys are structural, not stylistic.

**Accounting.** Every asset must appear exactly once: as a pin, or as a
declared backlog entry with one of the reason tokens `no_hub_readme`,
`card_method_deferred`, `override_method_deferred`, `unmapped_method_deferred`,
`source_moved_during_measurement`. An asset that is neither pinned nor in the
backlog is a `missing_backlog_entry` defect. An absent pins file is a reported
unseeded state (green zero-pin verdict), never a reason to skip the gate in CI.

**Defect tokens** (machine-stable, byte-stable output): `composite_pin_key_malformed`,
`pin_key_type_prefix_invalid`, `pin_key_bare_id`, `pin_asset_unknown`,
`pin_asset_unmapped`, `pin_asset_unmapped_method`, `duplicate_pin_key`,
`pin_not_object`, `missing_required_field`, `source_repo_mismatch`,
`revision_sha_mutable_ref`, `revision_sha_invalid`, `readme_sha256_invalid`,
`evidence_quote_empty`, `pinned_utc_invalid`, `backlog_key_invalid`,
`backlog_asset_unknown`, `backlog_reason_invalid`, `backlog_entry_conflicts_pin`,
`missing_backlog_entry`, `duplicate_id_type_pair`.

**Pin fields.** `source_repo` (equal to the map row), `revision_sha` (40 lowercase
hex; mutable refs such as HEAD/main/master rejected), `readme_sha256` (64 hex
over the Hub README.md bytes), `evidence_quote` (non-empty), `pinned_utc`
(UTC, `...Z`). The seeder measures everything live and verifies after read: a
source that moved during measurement defers to `source_moved_during_measurement`,
never a mixed pin.

**Exit codes.** 0 = valid (or unseeded), 1 = defects, 2 = input error
(unreadable, malformed JSON, non-standard constants, duplicate asset_map keys,
oversized input, excessive nesting). Verdicts are single-line sorted JSON on
stdout with full backlog accounting.

Design consults are recorded in wave-logs (Kimi v480 `e3f63149...`,
Mistral v480 `c12bd881...`).
