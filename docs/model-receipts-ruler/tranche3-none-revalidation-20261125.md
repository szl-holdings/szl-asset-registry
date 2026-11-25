# 16-NONE Tranche-3 Revalidation — 2026-11-25 (device lap)

Lap: W27 model-receipts, ruler tranche order step 4 (All-419 freeze -> 11 DEEP
-> 20 SHALLOW -> **16 NONE** -> 107 receipts-dir -> 265 other-named).
Input: Lap-1 T0 absence markers (wave-logs mesh/2026-11-22/ouroboros/
model-receipts-lap1/w27_t0_absence_markers.json, n=16).

Method (read-only): device-executed HF API pass on owner desktop
(w27t3_none_check.py, huggingface_hub org-authenticated, covers the private
repos the sandbox connector cannot reach): pinned revision sha, visibility,
file count, and receipt-like filename scan for all 16; compared against the
Lap-1 pinned markers (tranche3_absence_table.tsv, tranche3_none_revalidation.json).

## Findings

1. **16/16 repos alive and re-fingerprinted; 16/16 REV-DRIFTED** since the
   11-22 Lap-1 pin (100% drift in this class; these are the estate's live
   Salad/frontier artifacts, actively managed by sibling lanes).
2. **13/16 absence markers CONFIRMED**: no receipt-like content exists yet
   (salad-ring-v1, v1b, serve-gemma1, serve-llama1, serve-mistral1,
   ouro-l12, l15, l16, l17, l18, l13b, chaski-preflight, khipu-scholar-4b-v2).
   These stay T0 CLASSIFIED_INCOMPLETE, honestly closed, exactly as the ruler
   requires: absence is recorded, never rounded up to a fake receipt.
3. **3/16 HONEST CLASS TRANSITIONS** (receipt-like content appeared AFTER the
   11-22 markers, published by sibling lanes; detected live, zero fabrication):
   - **salad-flagship55-v1** (public, 495 files now): receipts/salad-flagship55-v1-heldout/
     {result.json, heldout_eval.py} + holo/receipt-chain-3d-v1.svg — the sibling
     P2D/frontier flagship heldout evidence chain. Class NONE -> receipts-dir.
   - **salad-governed-distill-27b-qlora-r1** (private, 53 files):
     training_report.json at root. Class NONE -> SHALLOW-family (training_report
     carrier). No-stomp: sibling distill lane owns this lineage's adjudication.
   - **salad-ring-ouro-l13** (public, 3 files): receipts/observation-v1.json.
     Class NONE -> receipts-dir.
4. Zero writes by this lap anywhere; the three transitions are routed, not
   acted on: each moves to its new tranche queue for normal processing rather
   than being silently reclassified.

## Verdict

Tranche-3 revalidation COMPLETE at the read-only level: 16/16 re-fingerprinted,
13/16 absence confirmed, 3/16 live class transitions detected and routed,
16/16 revision drift measured. Updated totals for the ruler scoreboard:
NONE-class count is now 13 (was 16); receipts-dir class grows by 2; SHALLOW
family grows by 1. All UNSIGNED_UNVERIFIED (amber); T0 stays the honest state
for the 13; no claim laundering of the 3 transitions.

Markers: TRANCHE3_16_16_REVREVALIDATED; ABSENCE_CONFIRMED_13_OF_16;
CLASS_TRANSITIONS_3_HONEST_ROUTED; REVISION_DRIFT_16_OF_16;
FOOTPRINT_495_FLAGSHIP55_HELDOUT_CHAIN_DETECTED; ZERO_WRITES.
