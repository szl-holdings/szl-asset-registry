# W27 Key-Provenance Adjudication Packet — 2026-11-25 (prep, read-only)

**Status: PREP ONLY. No verdicts. No trust upgrade. Adjudication is owner-gated.**
Scope: the 6 signed-receipt outlier repos routed in tranches 4-5. Method: authenticated sandbox HF reads + device rail (`betterwithage`). All 13 signed receipt files feteched, parsed, and tabulated; full digests recomputed from actual downloaded bytes on device.

## The three keys

| Nickname | keyId | SPKI (Ed25519) | Signed receipts | Payload dates |
|---|---|---|---|---|
| KEY_A Khipu-BrainNavigator | `89540347a69b789e` | `…k3N3ZehTp+jwgSEm9Qvl+bn3fKTAsGlyP96WT2EF1A0=` | 6 (SZL-Khipu-1.5B ×2, -GGUF ×2, -abstain ×2) | 2026-07-14 (+2026-09-08 abstain) |
| KEY_B Frontier+Forge CROSS-FAMILY | `e7f01810aaa97394` | `…0hrzlPL52zi3yA9Wj1uKL1CJMr12dTwKeIXYfJCg3a8=` | 5 (qwen35-0.8b-v2 receipts/ ×3, SZL-Forge-1.5B root ×2) | 2026-07-13, 2026-07-29 |
| KEY_C Forge-experimental | `653089f1d1504552` | `…pfLrWxjBNsLEvqpnO2Qgj8Yl0CHqaRe5VNkmEC/n0H0=` | 2 (qwen25-experimental receipts/ ×2) | 2026-11-04 |

## Key measurements (receipt-level)

1. **SZL-Khipu-1.5B and SZL-Khipu-1.5B-GGUF carry byte-identical signed receipts** (same signatureBase64 `Ob30FniG…` / `K7RyjcWz…`): copied signed files on a derivative repo. The `-abstain` sibling has its own distinct signatures under the same key (2026-09-08, adapter `bd5a1a92…` vs `fceba8b3…`).
2. **KEY_B spans two receipt families**: it signs the frontier-family receipts (`szl-frontier-*`, qwen35-0.8b-v2) *and* the forge-family root receipts (SZL-Forge-1.5B). Cross-family single key — flagged against the single-purpose-key doctrine.
3. **qwen25-experimental is forge-family** (schemaFingerprint `68b41b9f…`, identical dataset digests to Forge-root) **but signed by KEY_C**, not KEY_B.
4. **Correction of the tranche-4 report:** `receipts/publication_receipt.signed.json` does NOT exist in szl-receiptagent-qwen25-1.5b-experimental-20261104 (HF_FS_NOT_FOUND). Total signed receipt files across the 6 repos: **13, not 14**.
5. **Every payload date predates the Nov-2026 OB2 signature-era doctrine** (Jul 13, Jul 14, Jul 29, Sep 8, Nov 4). These keys are not the OB2 mint (which postdates them); most likely a pre-OB2 legacy convention. This is the owner's call, not this lane's.
6. In-payload claims observed, NOT verified: `evidence.signatureChainValid=true`, `autonomyEligible=false`, state `MEASURED_HF_READBACK_VERIFIED`, `keyId` self-declarations.

## Binary digest recompute (device-owed gate, CLEARED BY MEASUREMENT for this set)

Device downloaded the **actual bytes** of every digest-target file present in the 6 repos and recomputed sha256 against the values claimed inside the SIGNED payloads: **16/16 MATCH, 0 MISMATCH** (15 further targets are NOT_IN_REPO — external dataset references, honestly absent). Largest verified file 43,079 B (`train.jsonl` on Khipu-abstain). Honest label: **the signatures cover these bytes** (digest matches the signed claim). Still NOT a trust upgrade: an embedded public key is self-attestation; key identity is unadjudicated; this lane's receipts remain UNSIGNED_UNVERIFIED amber.

## Owner adjudication questions

1. Are KEY_A/B/C registered estate signing credentials or an unregistered legacy convention? (If unregistered: retain-as-legacy-evidence vs revamp under the OB2 single-purpose family, .github#1058.)
2. Does KEY_B's cross-family use violate the single-purpose-key doctrine?
3. Is copying byte-identical signed receipts to derivative repos (Khipu-GGUF) a sanctioned pattern going forward?
4. Should in-payload self-claims (`signatureChainValid=true`) be ruler-annotated as UNVERIFIED until crypto-verified?
5. Ed25519 internal-consistency verification (sig vs embedded SPKI vs canonical) is now fully feasible — all fields are in-file. Not executed this lap; propose as the next device step or owner-side check.

## Artifacts

`key_provenance_dossier.json` (machine dossier, includes SPKI, sig prefixes, dates, claims), `digest_recompute.json` (31 rows, raw device output). Published to wave-logs `mesh/2026-11-25/ouroboros/model-receipts-ruler-lap/key-provenance/`; PR#36 follow-up commit carries this packet into `docs/model-receipts-ruler/`.

Markers: `W27T6_13_SIGNED_RECEIPTS_DOSSIERED_3_KEYS` · `W27T6_DIGEST_RECOMPUTE_16_MATCH_0_MISMATCH_DEVICE_MEASURED` · `W27T6_CROSS_FAMILY_KEY_FLAGGED` · `W27T6_COPIED_SIGNED_RECEIPTS_DISCLOSED` · `W27T6_T4_COUNT_CORRECTION_13_NOT_14` · `W27T6_ALL_SIG_DATES_PREDATE_OB2_DOCTRINE` · `W27T6_PREP_ONLY_NO_VERDICTS_OWNER_GATED` · zero estate writes.
