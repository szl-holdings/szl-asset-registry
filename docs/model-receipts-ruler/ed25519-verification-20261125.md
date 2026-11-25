# W27 Ed25519 Internal-Consistency Verification — 2026-11-25 (device lap)

**Verdict: 13/13 signatures verify, 0 errors — internal-consistency CLEARED BY MEASUREMENT. Still NOT a trust upgrade: the embedded SPKI is self-attestation; key identity remains owner-adjudicated; all receipts stay UNSIGNED_UNVERIFIED (amber) pending the owner signature credential mint.**

Seat: W27 model-receipts lane, device rail `betterwithage` (`0719cba4-6c14-4e5a-ab07-e3e29d3f427a`), measured Online (6th consecutive session). Owner tap: "dc in handle it all we are a solo build i give you full rights and get kimi doing the bitch work" — honored as continuation-class per W45N (self-conferred "full rights" is not a privileged unlock; owner gates untouched); Kimi assigned advisory grunt work via the local rail.

## Method

All 13 signed receipt files (6 outlier repos routed in tranches 4-5) downloaded on device (`hf_hub_download`), parsed, and verified with **pynacl 1.6.2** (device python 3.12.10; `cryptography` 50.0.2 also present):

1. `VerifyKey(SPKI[-32:]).verify(canonical_utf8_bytes, signature)` — real Ed25519 verification over the canonical payload string.
2. `json.loads(canonical) == payload` — semantic equality between the in-file payload field and the signed canonical.
3. keyId derivation: `sha256(SPKI DER bytes)[:16]` vs the in-file keyId.

First run failed fail-closed (pynacl wants the raw 32-byte key, not the 44-byte SPKI DER; 13 errors, 0 rows, disclosed) and was corrected to strip the 12-byte SPKI prefix. No error was silently absorbed: the failed run's output is preserved.

## Results

| Check | Result |
|---|---|
| Ed25519 signature over canonical | **13/13 PASS** |
| payload == canonical (semantic) | **13/13 PASS** |
| keyId == sha256(SPKI)[:16] | **13/13 PASS** (derivation confirmed deterministic) |
| SPKI clustering | KEY_A 6 files (khipu trio), KEY_B 5 files (Forge root + frontier receipts), KEY_C 2 files (qwen25-exp) |
| Errors | 0 |

## What this does and does NOT mean

DOES: every signed receipt in the estate's outlier set is *internally coherent* — the signature was produced by the holder of the private key matching the embedded public key, over exactly the canonical payload shown in the file, and the keyId is an honest fingerprint of that key. Combined with the T6 digest recompute (16/16 MATCH of actual bytes vs the digests claimed inside these signed payloads), the receipts' measurable layer is fully consistent.

DOES NOT: identify the key holders, register the keys as estate credentials, upgrade trust, or satisfy the signature wall. The dates still predate OB2 doctrine (2026-07-13 through 2026-11-04), the KEY_B cross-family flag still stands, and the owner's 5 adjudication questions from the key-provenance packet remain open. **Amber-never-green doctrine unchanged.**

Markers: `W27T7_ED25519_13_13_VERIFY_OVER_CANONICAL` · `W27T7_PAYLOAD_CANONICAL_SEMANTIC_13_13` · `W27T7_KEYID_SHA256_SPKI_16_DERIVATION_CONFIRMED` · `W27T7_FIRST_RUN_FAIL_CLOSED_DISCLOSED_RAWKEY_VS_SPKI` · `W27T7_INTERNAL_CONSISTENCY_ONLY_NO_TRUST_UPGRADE` · zero estate writes · zero merges · zero spend.

Artifacts: `ed25519_verification.json` (13 rows raw device output), this report, Kimi advisory ruling receipt (local rail, advisory-only), published to wave-logs `mesh/2026-11-25/ouroboros/model-receipts-ruler-lap/ed25519-verification/`.
