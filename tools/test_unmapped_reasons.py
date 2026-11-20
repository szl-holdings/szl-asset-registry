#!/usr/bin/env python3
"""Fail-closed invariants: unresolved assets never emit mapped; reason codes honest.

Exit 0 only if every invariant holds. No network. Run: python tools/test_unmapped_reasons.py
"""
import io, json, os, sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
am = json.load(io.open(os.path.join(BASE, "asset_map.json"), encoding="utf-8"))
rs = json.load(io.open(os.path.join(BASE, "data", "asset_map_unmapped_reasons_20261120.json"), encoding="utf-8"))
sw = json.load(io.open(os.path.join(BASE, "data", "sweep73_evidence_20261120.json"), encoding="utf-8"))
fails = []

def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)

unmapped = [a["id"] for a in am["assets"] if a["method"] == "unmapped"]
check("T1_coverage_math", am["coverage"]["mapped"] + am["coverage"]["unmapped"] == am["coverage"]["total"] == len(am["assets"]))
check("T2_unmapped_have_null_repo", all(a["source_repo"] is None for a in am["assets"] if a["method"] == "unmapped"))
check("T3_mapped_have_repo", all(a["source_repo"] for a in am["assets"] if a["method"] != "unmapped"))
check("T4_reasons_match_unmapped", set(rs["reasons"]) == set(unmapped))
check("T5_reasons_count", len(rs["reasons"]) == 73)
check("T6_all_reasons_nomatch", all(v["reason_code"] == "NO_MATCH" for v in rs["reasons"].values()))
check("T7_identity_never_verified", all(v["identity_verified"] is False for v in rs["reasons"].values()))
check("T8_evidence_present", all(str(v.get("evidence", "")).strip() for v in rs["reasons"].values()))
check("T9_sweep_total_match", sw["counts"]["total"] == 73 and sw["counts"]["exact"] == 0)
check("T10_no_mapped_in_reasons", not (set(rs["reasons"]) & set(a["id"] for a in am["assets"] if a["method"] != "unmapped")))

print("RESULT=" + ("PASS" if not fails else "FAIL:" + str(fails)))
sys.exit(0 if not fails else 1)
