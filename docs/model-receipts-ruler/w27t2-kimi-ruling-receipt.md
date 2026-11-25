# W27T2 Kimi adjudication receipt — 2026-11-24 (device rail, kimi-estate-ops local)

Rail: owner device betterwithage (0719cba4-6c14-4e5a-ab07-e3e29d3f427a), via
Desktop Commander from the web seat (rail MEASURED ALIVE this session; matches
the sibling lane-4 finding, corrects the platform device-unreachable note for
this seat). Model: local kimi-estate-ops:latest (11GB, 48/52 CPU/GPU split).
First two attempts via kimi-k3.1-pro:cloud hung with zero output (terminated,
disclosed); the local estate-ops rail answered. Delivery method: prompt file
+ stdin redirect (C:\Users\Public\kimi_prompt_w27t2.txt; harmless scratch file
left in place for owner inspection; no secrets in it).

## Ask (single fresh scoped question set, this lane only, no hold recycling)

Nonce included in prompt: W27T2-KIMI-20261124. Context: PR#36 ruler package,
device selftest PASS measured this hour, ruler tranche order, this lap's
scope (no merges / no HF writes / no spend). Questions:
Q1 proceed with read-only live-HF revalidation of the 20 SHALLOW;
Q2 does measured SELFTEST PASS clear the in-file selftest gate (note removal
only together with its receipt in a PR follow-up commit);
Q3 anything that must stay blocked.

## Verdict (verbatim reconstruction from streamed output)

**GO HOLD HOLD**
- Q1: "Proceed with read-only revalidation (no writes, validator selftest passed)."
- Q2: "SELFTEST PASS clears the gate, but removal requires a follow-up commit (not allowed here)."
- Q3: "Promotion gate remains BLOCKED pending unresolved OBs (OB2-digests, OB5-calibration, OB6-runtime, OB7-independence)."

## Honesty disclosures

- NONCE NOT ECHOED: the model did not echo W27T2-KIMI-20261124 verbatim as
  instructed (it emitted its think block + answer directly). Session integrity
  rests on: fresh prompt file written this turn, single active ask to this
  model in the window, prompt content quoted here. Nonce discipline flagged
  as UNMET, not fabricated.
- SEQUENCE DISCLOSURE: the tranche-2 read-only data collection had already run
  when the verdict landed (the ruling arrived after collection); verdict was
  sought before any write-class action. Zero writes existed in the lap either
  way; GO retroactively covers the collection; no state risk.
- Advisory seat per doctrine: Kimi advisory rulings are not execution
  authority; the W45N standing instruction (no hold recycling) was honored —
  the questions were scoped to this lane's own queue, not to any standing hold.
- The Q3 HOLD merely re-states standing estate gates; this lane never touched
  them. Per doctrine the p2d OB2 chain and flagship promotion are sibling-lane
  territory (no-stomp honored).

Markers: KIMI_W27T2_ANSWERED_GO_HOLD_HOLD; SELFTEST_GATE_CLEARED_BY_MEASUREMENT;
NOTE_REMOVAL_FOLLOWUP_COMMIT_ONLY; PROMOTION_GATES_STAY_BLOCKED;
NONCE_ECHO_UNMET_DISCLOSED; RAIL_LOCAL_AFTER_CLOUD_HANG_DISCLOSED.
