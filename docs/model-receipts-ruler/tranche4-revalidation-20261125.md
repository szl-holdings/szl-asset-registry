# 107 receipts-dir Tranche-4 Revalidation — 2026-11-25 (device lap)

Lap: W27 model-receipts, ruler tranche order step 5 (All-419 freeze -> 11 DEEP
-> 20 SHALLOW -> 16 NONE -> **107 receipts-dir** -> 265 other-named).
Seat context: owner verbatim "execuyte you are teh cto dc in" honored as
continuation-class (W45N doctrine) with the device rail measured ONLINE
(list_devices cantouch 52s; 4 clean device executions this lap).
Input: Lap-1 B0 matrix class RECEIPTS_DIR (107 repos, w27_b0_matrix.json,
re-parsed on device from the wave-logs original).

Method (read-only): single device pass (w27t4_scan.py, HfApi org-auth) over
all 107 repos: pinned revision, file count, receipt-like filename scan;
compared against the Lap-1 baseline sha + counts extracted the same way
(w27t4_baseline.py). Full matrix: tranche4_drift_matrix.json;
raw scan: tranche4_scan_live.json; baseline: lap1_rd_baseline.json.

## Findings

1. **107/107 alive and re-fingerprinted, ZERO scan errors.**
2. **106/107 REV-DRIFTED** since the 11-22 Lap-1 pin. The single unmoved repo:
   **khipu-r3**. Across the whole ruler program so far the drift pattern is:
   11-DEEP class stable-ish, 18/20 SHALLOW, 16/16 NONE, 106/107 receipts-dir —
   the estate's live repos move almost entirely on a 2-day timescale, so the
   ruler's fingerprint-at-execution-time rule is now proven at every tranche.
3. **15/107 grew file counts** since Lap-1 (e.g. SZL-Khipu-1.5B 43->45,
   szl-training-scripts 19->24, the szl-receiptagent family tree +2 each,
   SZL-Nemotron/SZL-Reasoning/SZL-FreeEnergy estate v1/DPO pairs +2 each).
   The burst-like +2 pattern in the v1/DPO families suggests a common
   publish campaign by a sibling lane (receipts + card assets), not
   investigated further read-only; flagged for that lane's own receipt work.
4. **3/107 carry .signed. receipt files** (signature-evidence outliers):
   - SZL-Khipu-1.5B: eval_receipt.signed.json + training_receipt.signed.json
   - szl-receiptagent-qwen35-0.8b-v2: receipts/{eval,training,publication}_
     receipt.signed.json (+ salvaged-merge/merge_receipt.json)
   - szl-receiptagent-qwen25-1.5b-experimental-20261104: same pattern
   Honest classification: SIGNATURE_EVIDENCE_PRESENT, KEY_PROVENANCE_
   UNADJUDICATED_THIS_LAP. These predate the estate's signature-era doctrine
   (eval receipt dated 2026-11-05 inside one). THIS lane continues producing
   UNSIGNED_UNVERIFIED (amber) receipts; the three signed outliers are ROUTED
   to a signature-provenance adjudication item (key identity, signing time,
   whether the p2d OB2 single-purpose key or a legacy convention produced
   them). No trust upgrade claimed or implied.
5. No repo lost receipt-like files; no class regression detected
   (zero receipts-dir repos now empty).

## Verdict

Tranche-4 revalidation COMPLETE at the read-only level: 107/107 re-fingerprinted,
106/107 drift measured, 15 growth events tabulated, 3 signature-evidence
outliers routed for provenance adjudication, 0 scan errors. Next ruler step:
the 265 other-named tranche (largest, batched). All counts remain
UNSIGNED_UNVERIFIED (amber) from this lane.

Markers: TRANCHE4_107_107_REVREVALIDATED; REVISION_DRIFT_106_OF_107;
KHIPU_R3_SOLO_UNMOVED; FILE_GROWTH_15_TABULATED;
SIGNATURE_EVIDENCE_3_ROUTED_KEY_PROVENANCE_UNADJUDICATED;
ZERO_SCAN_ERRORS; ZERO_MERGES_ZERO_COMPUTE.
