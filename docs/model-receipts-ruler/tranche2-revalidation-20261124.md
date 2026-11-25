# 20-SHALLOW Tranche-2 Revalidation — 2026-11-24 (web + device lap)

Lap: W27 model-receipts, ruler tranche order step 3 (All-419 freeze -> 11 DEEP
-> **20 SHALLOW** -> 16 NONE -> 107 receipts-dir -> 265 other-named).
Input: Lap-1 T1 candidates (wave-logs mesh/2026-11-22/ouroboros/
model-receipts-lap1/w27_t1_candidates_shallow20.json).

Method (read-only, zero writes, zero spend):
1. Live HF ls of all 20 repos (root fingerprint, all 20 alive and readable).
2. Live HF cat of all 20 root receipts (TRAINING_RECEIPT.json /
   training_receipt.json / merge_receipt.json / training_report.json), staged
   verbatim in tranche2_receipts_live.jsonl (78KB).
3. Device-executed HF API metadata pass (owner desktop, Python +
   huggingface_hub, script w27t2_lfs_meta.py): pinned revision sha + LFS
   provider sha256 for every LFS file in all 20 repos
   (tranche2_lfs_meta.json).
4. Corroboration matrix: Lap-1 declared digests vs live provider LFS digests
   (tranche2_corrob_matrix.json).

## Finding 1: REVISION DRIFT IS THE DOMINANT FACT

18 of 20 repos drifted off their Lap-1 pinned revisions in the ~2 days since
the 11-22 scan (only brain-navigator-r2 and chakana-r1-candidate are still at
their Lap-1 revisions). Several are actively trained (chaski family,
WILLAY/Estate lanes). Consequence, now MEASURED, not assumed: every
publication receipt must pin and fingerprint the revision at execution time;
a receipt older than the live repo is a statement about history, not about the
published bytes. This is exactly the ruler's revision-anchor rule.

## Finding 2: digest corroboration (provider metadata class)

- 11 digests CORROBORATED_LFS: Lap-1 declared sha256 == live provider LFS
  sha256 (szl-kernels vectors.npz; WILLAY adapter_model.safetensors + willay.npz;
  chaski adapter_model.safetensors + chaski.npz; chaski-5050 both; chaski-r2
  both; brain-navigator-r2 adapter; chaski-r4 adapter).
- 4 MISMATCH, all the path adapter-unsloth/adapter_model.safetensors on
  WILLAY / chaski / chaski-5050 / chaski-r2, all four repos REV-DRIFTED since
  Lap-1: classified DRIFT_CLASS (live artifact legitimately changed after the
  Lap-1 pin; the Lap-1 receipt remains a true statement about its pinned
  revision; NOT a defect, NOT a laundering event). Republishing these four
  needs a fresh T1 at the new revision.
- 8 artifacts Lap-1 could not hash (budget cap) NOW HAVE live provider
  digests (digest_source=HF_LFS_METADATA, locally_recomputed=false), e.g.
  WILLAY model.safetensors aa15071b..., chaski model-...-00001, KHIPU-R2
  model.safetensors 498f3f52..., completing most PARTIAL inventories at the
  metadata level.

## Finding 3: honesty labels

- The 10 asset-family repos (governed-norm, lambda-gate, kernels, blocked,
  govsign, provctl, nemo, invariants, ouroboros, formulas) carry a long-form
  honesty string: "Every number above is MEASURED by this run..." plus
  disclosed SYNTHETIC / surrogate statements. Honest, but the honesty field is
  a free STRING, not the ruler's structured what/what_not — they are
  T1-compatible once fields are re-typed; no dishonesty found.
- The process-family repos (KHIPU-R2, WILLAY, chaski family, brain-navigator,
  chakana, a11oy-code, Yachay-Nano) have legacy receipts without a ruler
  honesty block: claims preserved verbatim, promoted=false (anti-laundering),
  re-adjudication owed per-model before any README publication.
- chaski-r2 carries BOTH training_receipt.json and training_receipt.local.json
  (disclosed dual), flagged for the adjudication queue.

## Verdict

Tranche-2 revalidation COMPLETE at the read-only level:
20/20 repos alive + re-fingerprinted, 20/20 root receipts re-fetched,
11 digests provider-corroborated, 4 drift-class mismatches honestly classified,
8 previously-unhashed artifacts now carry provider digests, 18/20 revision-drift
measured. All counts remain UNSIGNED_UNVERIFIED (amber); local digest recompute
still owed for anything beyond provider metadata; T1 remains the ceiling.

Device lap deliverable in hand: the PR#36 validator selftest ran ON DEVICE
(6/6 cases, SELFTEST PASS), clearing the ruler's in-file selftest gate for
removal in a PR follow-up together with this receipt.

Markers: TRANCHE2_20_20_REVREVALIDATED; REVISION_DRIFT_18_OF_20_MEASURED;
DIGESTS_CORROBORATED_LFS_11; DRIFT_CLASS_MISMATCH_4_HONEST; LFS_META_8_NEW;
HONESTY_STRINGS_LEGACY_PRESERVED; SELFTEST_DEVICE_EXECUTED_6_OF_6_PASS;
ZERO_MERGES_ZERO_COMPUTE.

## Kimi advisory verdict (post-collection)

W27T2 ask over the device kimi-estate-ops rail ruled **GO HOLD HOLD**: Q1 GO
for this read-only revalidation (retroactively covers the already-run
collection; no writes existed); Q2 HOLD, the in-file selftest note clears by
measurement but its removal must be a PR#36 follow-up commit, not done in this
lap; Q3 HOLD, promotion gates stay blocked pending the sibling OB items
(OB2-digests, OB5-calibration, OB6-runtime, OB7-independence). Full receipt:
w27t2-kimi-ruling-receipt.md. Nonce echo unmet, disclosed.
