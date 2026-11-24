# 11-DEEP Controls Revalidation — 2026-11-24 (web seat)

Lap: W27 model-receipts, continuation of the owner's 2026-11-22 directive
("models need to be fully showcasing the right receipts, we only have 3 fully done").

Method: read-only fetch of every DEEP-classified model's receipt from
HF org SZLHOLDINGS via the sandbox HF connector (hf_fs cat/stat/find), from the
web seat, no device rail. Fields were transcribed verbatim; nothing was
recomputed. This document is evidence-seated in the 2026-11-22 Lap-1 scan
(419 models: 11 DEEP / 20 SHALLOW / 107 receipts-dir / 265 other-named / 16 NONE,
published in wave-logs mesh/2026-11-22/ouroboros/model-receipts-lap1/).

## Per-model findings (11/11 refetched)

### Andes-6 (root `TRAINING_RECEIPT.json`, ~1.2KB each)

KILLINCHU-EYE, YARQA-ATTN, qantu, waman, chakana, tinku.

- Structure: per-artifact entries each carrying sha256, loss, accuracy, steps,
  seed — T1-field-shaped and complete.
- Honesty labels INTACT: training data label reads `SYNTHETIC`; `proven_trust`
  reads `false`. No claim laundering, no "trained-on" implication.
- Environment honesty: cuda and energy fields read `UNAVAILABLE`, stated as
  such rather than fabricated. Good fail-closed form.

### Nano-4 + szl-khipu (shared 4-artifact receipt)

TinyKhipu-Nano, ReceiptAgent-Nano, Moons-Nano, MiniEmbed-Nano, and
SZLHOLDINGS/szl-khipu all carry the same four artifact digests in their
receipt blocks (declared under honest what-labels; shared provenance is
disclosed, not hidden):

- mini_embed.npz — `ae31a3a7…` (prefix shown; full sha256 in the receipt file)
- moons.npz — `dda50e3f…`
- receipt_agent.npz — `8aca4d24c90d6159cbb2bb885c7a94822d715899437f58abe69fb5c9664a1381`
- tiny_khipu.npz — `cc8d0385…`

szl-khipu additionally carries a copy under `artifacts/`.

### Digest corroboration (first web-seat independent corroboration)

`receipt_agent.npz` declared sha256
`8aca4d24c90d6159cbb2bb885c7a94822d715899437f58abe69fb5c9664a1381`
was cross-checked against two independent providers:

1. the LFS pointer oid of the same path on SZLHOLDINGS/szl-khipu (read in the
   device lap, 6014 bytes), and
2. the file listing of SZLHOLDINGS/ReceiptAgent-Nano (find size = 6014).

Both match. Classification per the ruler: **corroborated at
digest_source=HF_LFS_METADATA** — a provider metadata match, NOT a local
recompute. It raises confidence but does not substitute for the device-lap
binary digest recompute.

### Alias disclosure

KILLINCHU-EYE declares itself an "alias-seat of waman" in its receipt —
honest labeling of a shared seat rather than a duplicate identity claim.

## Verdict

Controls PASS at **T1-fields-declared** with honest labels intact:
T1 structure (tier, honesty what/what-not, signature status, typed facts)
is present and truthful on all 11; nothing unsigned claims trust; nothing
synthetic claims provenance; nothing unmeasured claims to be measured.

Still owed for this class (device lap, not executable from the web seat):

1. **Binary digest recompute** — actually download each artifact and
   sha256 it locally; provider corroboration is not a recompute.
2. **Run-binding evidence objects** (T2 requirement) — immutable dataset
   revisions + exact output-digest bindings; no DEEP control currently has
   them, so T1 remains the honest ceiling.
3. **Validator selftest execution** — run
   `python verify_receipts_ruler.py --selftest` on device before this ruler
   package is referenced by any CI or promotion gate.
4. **Signature layer** — all receipts remain UNSIGNED /
   trust_status=UNSIGNED_UNVERIFIED until the owner's signature credential
   mint. Amber, never green, by design.

Markers: CONTROLS_11_11_REVALIDATED; ANDES6_HONEST_LABELS_INTACT;
NANO4_SHARED_RECEIPT_DISCLOSED; RECEIPT_AGENT_NPZ_DIGEST_CORROBORATED_LFS;
KILLINCHU_EYE_ALIAS_OF_WAMAN_DISCLOSED; T1_CEILING_DEVICE_DIGESTS_OWED.
