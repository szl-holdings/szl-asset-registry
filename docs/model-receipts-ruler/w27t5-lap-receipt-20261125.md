# W27 Lap Receipt — Tranche-5 OTHER_NAMED (2026-11-25)

**Markers:** `W27T5_265_265_REVALIDATED_0_ERRORS` · `W27T5_DRIFT_258_OF_265` · `W27T5_UNMOVED_7_LISTED` · `W27T5_NEW_RECEIPT_1_SZL_SCRATCH_R4` · `W27T5_KW_GROWTH_4_SUBSTRING_CAVEAT` · `W27T5_SIGNED_OUTLIERS_3_ROUTED_KEY_PROVENANCE` · `W27_SCAN_PROGRAM_COMPLETE_419_OF_419` · `W27T5_READ_ONLY_ZERO_ESTATE_WRITES`

**Lane:** W27 model-receipts (owner directive: "models fully showcasing the right receipts, we only have 3 fully done")
**Seat:** device rail `betterwithage` (`0719cba4-6c14-4e5a-ab07-e3e29d3f427a`), measured Online at every lap of this session contra the platform's stale offline notes.
**Session line:** 2026-11-25, owner tap "execute keep piusign use dc" honored as continuation-class per doctrine (bare/typo EXECUTE-taps are not unlocks; W45N ruling). If the tap intended a signature action, the standing gate stands: credential mint is owner-gated and was not attempted.

## Executed (this lap)

1. Baseline extraction: Lap-1 `w27_b0_matrix.json` OTHER_NAMED class → 265 repos with pinned sha/n_files/kw_hits → `lap1_on_baseline.json` (LAP1_ON_BASELINE_WRITTEN 265).
2. Live scan: `w27t5_scan.py` over all 265 repos via `HfApi.repo_info`; **265 rows, 0 errors** (markers W27T5_SCAN_START/END).
3. Comparison vs baseline: 258/265 drift; 7 unmoved (listed); 1 true receipt-appearance (`szl-scratch-r4-upload-validation` `results/receipt.json`) ROUTED; 4 kw-count growth events with substring caveat (A11OY-MINI ADDITION; salad-chaski-frontier-4b-op1, szl-khipu-kernels, szl-triage-qwen3.5-0.8b-lora-study5 zero-file-growth shapes); 4 file-growth-without-receipt events; 3 signed-receipt outliers (SZL-Forge-1.5B-ReceiptAgent, SZL-Khipu-1.5B-GGUF, SZL-Khipu-1.5B-abstain) ROUTED to key-provenance adjudication (joins tranche-4's 3); 0 removals; post-scan absence-zero = 0.
4. Artifacts: `tranche5_transition_table.json`, `tranche5-revalidation-20261125.md`, `w27t5_scan_live.json` (= device `scan_live.json`), `lap1_on_baseline.json` all staged; wave-logs publication via device `upload_folder` to `mesh/2026-11-25/ouroboros/model-receipts-ruler-lap/` with sandbox hf_fs independent readback (commit hash recorded below once returned).
5. PR#36 follow-up commit: tranche-4 + tranche-5 reports pushed to branch `receipts-ruler-20261124`, propose-only, PR stays draft, no merge.

## Verdict

**PASS 265/265 at T1-fields-declared; honest labels intact; zero estate writes.** Scan program COMPLETE: 419/419 Lap-1-classified repos re-fingerprinted across tranches 1-5.

## Honest gates

- All trust still UNSIGNED_UNVERIFIED; owner signature credential mint = THE unlock; not attempted.
- Binary digest recompute device-owed; digests remain HF_LFS_METADATA-labeled.
- 6 signed-outlier repos pending key-provenance adjudication (3 from T4 + 3 from T5).
- Device scratches disclosed: `C:\Users\Public\w27t5_baseline.py`, `w27t5_scan.py`, `w27t5_baseline_out.txt`, `w27t5_scan_out.txt`, `w27t5_push\` (no secrets, all benign).
