# Validator selftest receipt — 2026-11-24 (device execution)

Device: owner desktop betterwithage (0719cba4-6c14-4e5a-ab07-e3e29d3f427a),
via Desktop Commander from the web seat. Fetch: raw.githubusercontent.com
szl-holdings/szl-asset-registry branch receipts-ruler-20261124,
docs/model-receipts-ruler/verify_receipts_ruler.py. Executed:
`python verify_receipts_ruler.py --selftest`, PowerShell, one shot.

## stdout (verbatim)

```
VALID_T1 defects=0 OK
BAD_GREENWASH defects=1 OK
BAD_UNTYPED_FACT defects=1 OK
BAD_T2_NO_EVIDENCE defects=1 OK
BAD_PROVIDER_DIGEST_LABEL defects=1 OK
BAD_UNKNOWN_NO_REASON defects=1 OK
SELFTEST PASS
```

6/6 cases matched expectations (VALID_T1 clean, all 5 defect cases caught).
Exit-marker probe printed after the run; SELFTEST PASS line is the binding
receipt. Advisory ruling W27T2 (kimi-estate-ops local, same date): the pass
CLEARs the ruler's in-file selftest gate; removal of the in-file note is
authorized ONLY as this follow-up commit carrying this receipt
(w27t2-kimi-ruling-receipt.md, Q2 HOLD-with-scope honored here).

Class: execution receipt, first-class evidence. Execution environment is the
owner device, not CI; the device stdout above is the authoritative capture.
