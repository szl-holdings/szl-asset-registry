# W27 Tranche-5 Revalidation Report: OTHER_NAMED class (265 repos)

**Date:** 2026-11-25 · **Executor:** W27 model-receipts lap (device rail `betterwithage`, id `0719cba4-6c14-4e5a-ab07-e3e29d3f427a`) · **Mode:** read-only, zero estate writes · **Baseline:** Lap-1 (2026-11-22) `w27_b0_matrix.json` OTHER_NAMED class, pinned per-repo sha + n_files + kw_hits counts · **Live scan:** device `HfApi.repo_info` over all 265 repos (script `w27t5_scan.py`), **265/265 scanned, 0 errors**.

## Method

Per repo: live HEAD sha, sibling-file list, receipt-substring filename scan (`receipt`, `provenance`, `training_report` in lowercase filename). Compared against Lap-1 baseline. Classification transitives ROUTED per ruler doctrine; nothing silently upgraded. All trust claims remain **UNSIGNED_UNVERIFIED** pending the owner signature credential mint (THE unlock).

## Findings

- **Drift:** 258/265 repos drifted HEAD sha since 2026-11-22. 7 unmoved: ChaskaLLM, a11oy-v19-substrate, governed-inference-meter, oac-clinical-transport-health-v1, oac-ops-health-v2, oac-system-health-v1, oac-system-health-v3-candidate. The universal drift shape established in tranches 2-4 continues.
- **Receipt appearance (1):** `szl-scratch-r4-upload-validation` had zero receipt-substring hits at Lap-1 and now carries `results/receipt.json` (+1 file, NEW_RECEIPT_FILE). ROUTE: sibling scratch/upload-validation author; ou30 card-bar candidate observation; UNSIGNED, no trust upgrade; class stays OTHER_NAMED (no `receipts/` directory).
- **Keyword-count growth (4, substring caveat — baseline stored counts only, not filename sets):**
  - A11OY-MINI: 5 hits → 8, +2 files (ADDITION); includes conversion_receipt.json, gguf_gate_receipt.json, hub_put_receipt.json. Observation only.
  - salad-chaski-frontier-4b-op1: 2 → 3, +0 files (RENAME_OR_REPLACE shape): `final/train_receipt.json` + `eval/frontier-v1/receipt.json` now visible. Frontier sibling lane observation.
  - szl-khipu-kernels: 3 → 4, +0 files; growth is Python module names (`receipt_attn.py`, `receipt_agent.py`) — code files, NOT receipt documents. No route needed.
  - szl-triage-qwen3.5-0.8b-lora-study5: 5 → 8, +0 files (REPLACE_RESEED shape): five seed-level `training_receipt-seed-*.json` + `environment-receipt.json` + `publication-receipt.json`. ou30 card-bar candidate observation; UNSIGNED, no trust upgrade.
- **File growth without receipt appearance (4):** khipu-structure-v2-work +7, salad-chaski-calib-v1 +5, salad-chaski-r4-mix1 +1, SZL-Khipu-1.5B-GGUF +2. Zero writes by this lane.
- **Signed-receipt outliers (3, ROUTED):** SZL-Forge-1.5B-ReceiptAgent, SZL-Khipu-1.5B-GGUF, SZL-Khipu-1.5B-abstain each carry root `training_receipt.signed.json` + `eval_receipt.signed.json`. Routed to the same key-provenance adjudication queue opened in tranche-4 (now 6 outlier repos total across T4+T5). Unsigned/unknown-provenance key: **no trust upgrade**, amber-never-green.
- **Removals:** 0. No repo lost receipt-like files.
- **Absence:** Lap-1 zero-hit count for this class was 1 (szl-scratch-r4-upload-validation), which gained a receipt; post-scan zero-hit repos = 0.

## Verdict

**PASS 265/265 at T1-fields-declared, read-only revalidation.** Honest labels intact; separation of counts preserved (drift / appearance / outlier axes reported separately, never merged into one green %).

**Scan program COMPLETE:** with tranche-5, all Lap-1 classes are post-baseline re-fingerprinted: **11 DEEP + 20 SHALLOW + 16 NONE + 107 receipts-dir + 265 OTHER_NAMED = 419/419**.

## Honest gates (device-owed / owner-gated)

1. Binary digest recompute of artifact files remains device-owed (current digests are HF_LFS_METADATA-derived, labeled as such).
2. Signed-outlier key provenance adjudication pending (6 repos).
3. Wave-logs mesh publication debt: none — tranche-5 artifacts published same-day via device `upload_folder`, readback verified from sandbox.
4. Signature credential mint remains THE owner unlock; all receipts remain UNSIGNED_UNVERIFIED.
