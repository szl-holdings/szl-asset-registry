# W27 Kimi Advisory Ruling Receipt — Tranche-7 (2026-11-25)

**Rail:** local `ollama kimi-estate-ops` on device `betterwithage` · **Nonce echo: MET** (`W27T7-KIMI-20261125` returned verbatim after the think block, breaking the two-lap unmet streak — still disclosed since the rail's echo reliability is historically unreliable) · **Standing: ADVISORY ONLY.** Kimi rules on nothing owner-gated; key registration, KEY_B cross-family ruling, copied-receipt sanctioning, and the signature mint stay owner-gated.

**Context given:** the fully measured T6+T7 record (3 keys, 13 signed receipts, 13/13 Ed25519 verify over canonical, 13/13 payload-canonical semantic match, keyId = sha256(SPKI)[:16], digest recompute 16/16 match, all payload dates pre-OB2, amber-never-green doctrine).

## Ruling (verbatim from the rail, think block omitted)

```
W27T7-KIMI-20261125
Q1: HOLD (Legacy keys pre-OB2, not registered estate credentials)
Q2: HOLD-PENDING (Legacy key usage may violate OB2 doctrine but requires OB2-era validation)
Q3: HOLD-PENDING (No action needed; device-verified but owner minting required)
Q4: HOLD (In-payload claims are UNVERIFIED at ruler level)
Q5: GO (Propose ruler-level amendment for internal consistency checks)

**Top 3 grunt work tasks:**
1. Audit legacy key registration status (Q1)
2. Validate KEY_B's cross-family usage against OB2-era single-purpose doctrine (Q2)
3. Draft ruler-level amendment for internal consistency verification (Q5)
```

## Execution disposition (this lane)

- Q1/Q2/Q3/Q4: **HOLD/HOLD-PENDING honored** — no trust upgrade, no registration claim, no sanctioning, claims annotated UNVERIFIED.
- Q5: **GO executed this lap** — ruler-level amendment draft added to the PR#36 docs series (`ruler-amendment-internal-consistency-20261125.md`), propose-only.
- Kimi grunt tasks 1-2 are owner-gated by nature (registration audit/mint); task 3 delivered.

Process disclosure: two failed ollama invocation patterns disclosed (cmd-wrap process killed at timeout producing spinner-only output; PowerShell-detach pattern from T2 used successfully, output 75.9KB raw, ANSI/braille spinner scrubbed with an exact-state cleaner script). Raw output preserved on device.

Markers: `W27T7_KIMI_NONCE_ECHO_MET` · `W27T7_KIMI_RULING_HOLD_HOLDP_HOLDP_HOLD_GO` · `W27T7_ADVISORY_ONLY_NO_VERDICTS` · `W27T7_Q5_GO_EXECUTED_AMENDMENT_DRAFTED`.
