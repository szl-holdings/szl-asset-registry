#!/usr/bin/env python3
"""Fail-closed invariants v2 (2026-11-20): unmapped coverage honest, reason codes disciplined.

Contract change vs v1, reviewer-visible: reasons entries are RETAINED historical
sweep receipts. PR#12 mapped 63 of the original sweep population, so v1 invariants
(reasons == unmapped exactly, all NO_MATCH, count 73) expired and would require
deleting receipt evidence to stay green. v2 keeps receipts and enforces:
unmapped-covered, real-asset-keys, code/cardinality discipline, recomputed counts.

Exit 0 only if every invariant holds. No network. Run: python tools/test_unmapped_reasons.py
"""
import io, json, os, sys
from collections import Counter

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
all_ids = set(a["id"] for a in am["assets"])
check("T1_coverage_math", am["coverage"]["mapped"] + am["coverage"]["unmapped"] == am["coverage"]["total"] == len(am["assets"]))
check("T2_unmapped_have_null_repo", all(a["source_repo"] is None for a in am["assets"] if a["method"] == "unmapped"))
check("T3_mapped_have_repo", all(a["source_repo"] for a in am["assets"] if a["method"] != "unmapped"))
check("T4_unmapped_covered_by_reasons", set(unmapped) <= set(rs["reasons"]))
check("T5_reasons_are_real_assets", set(rs["reasons"]) <= all_ids)
check("T6_code_cardinality_discipline", all(
    (v["reason_code"] == "NO_MATCH" and len(v["candidates"]) == 0)
    or (v["reason_code"] == "EXACT" and len(v["candidates"]) == 1)
    or (v["reason_code"] == "AMBIGUOUS" and len(v["candidates"]) >= 2)
    for v in rs["reasons"].values()))
check("T7_identity_never_verified", all(v["identity_verified"] is False for v in rs["reasons"].values()))
check("T8_evidence_present", all(str(v.get("evidence", "")).strip() for v in rs["reasons"].values()))
cnt = Counter(v["reason_code"] for v in rs["reasons"].values())
sc = rs["sweep_counts"]
check("T9_sweep_counts_recomputed",
    sc["total"] == len(rs["reasons"])
    and cnt.get("NO_MATCH", 0) == sc["nomatch"]
    and cnt.get("EXACT", 0) == sc["exact"]
    and cnt.get("AMBIGUOUS", 0) == sc["ambiguous"]
    and sum(sc[k] for k in ("nomatch", "exact", "ambiguous")) == sc["total"]
    and sw["counts"]["total"] == 73 and sw["counts"]["exact"] == 0)
check("T10_candidate_repos_wellformed", all(
    isinstance(repo, str) and repo.startswith("szl-holdings/") and repo.count("/") == 1
    for v in rs["reasons"].values()
    for repo in v["candidates"]))

print("RESULT=" + ("PASS" if not fails else "FAIL:" + str(fails)))
sys.exit(0 if not fails else 1)
