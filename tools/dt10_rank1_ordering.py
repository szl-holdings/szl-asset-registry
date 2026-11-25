#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""szl-asset-registry: DT10 rank-1 license-remediation ordering tool.

Implements the deterministic candidate ordering ratified in the Kimi DT10
backlog (DT10-DATASET-BACKLOG-20261124, workstream rank 1:
license_metadata_remediation) with the estate's published stable ordering
(downloads desc, likes desc, id asc, disclosed) and fail-closed exclusions.

Laws enforced:
  - fail closed: any census row with a missing/unknown license_state aborts
    the whole run (no silent partial candidate list, no inferred licenses)
  - eligibility gate: candidates must be NO_LICENSE with readme_present
    true; everything else is excluded with a recorded reason
  - the tool NEVER writes to Hugging Face and NEVER asserts licenses;
    the emitted packet is propose-only and requires the owner gate plus a
    per-candidate license_evidence_receipt before any apply
  - ordering is total: (downloads desc, likes desc, id asc) with id as the
    final tiebreaker, so reruns on an identical census are byte-reproducible

Usage:
  python tools/dt10_rank1_ordering.py --census data/hf_dataset_census_leg-lap2_20261124.json \
      --out data/dt10_rank1_packet_20261124.json [--pilot 5]
"""
import argparse
import json
import sys

ORDERING_RULE = "downloads_all_time desc, likes desc, id asc (final tiebreaker id asc; disclosed)"


class FailClosed(Exception):
    pass


def load_census(path):
    with open(path, encoding="utf-8") as f:
        census = json.load(f)
    datasets = census.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise FailClosed("census has no datasets array")
    return census, datasets


def order_key(row):
    return (-int(row.get("downloads_all_time", 0)),
            -int(row.get("likes", 0)),
            str(row.get("id", "")).lower())


def build_packet(census, pilot_n):
    candidates, exclusions = [], []
    for row in census["datasets"]:
        rid = row.get("id")
        lic = row.get("license_state")
        if lic not in ("LICENSED", "NO_LICENSE"):
            raise FailClosed("unmeasured license_state for %s; abort (no inferred licenses)" % rid)
        if lic == "NO_LICENSE":
            if row.get("readme_present") is not True:
                exclusions.append({"id": rid, "reason": "NO_LICENSE_BUT_NO_README_SURFACE",
                                   "rule": "sha or cardData incomplete (DT10 fail-closed gate)"})
            else:
                candidates.append({
                    "id": rid,
                    "downloads_all_time": int(row.get("downloads_all_time", 0)),
                    "likes": int(row.get("likes", 0)),
                    "evidence_required": [
                        "authoritative upstream license evidence (named source repo/file + verbatim license text)",
                        "source_sha_recheck at apply time",
                        "license_evidence_receipt",
                        "owner_gate_receipt before any apply",
                    ],
                })
        else:
            exclusions.append({"id": rid, "reason": "LICENSE_PRESENT", "rule": "not in rank-1 cohort"})
    candidates.sort(key=order_key)
    exclusions.sort(key=order_key)
    return {
        "schema": "szl.dt10_rank1_packet/v1",
        "generated_from_census": "data/hf_dataset_census_leg-lap2_20261124.json",
        "ordering_rule": ORDERING_RULE,
        "workstream": "license_metadata_remediation (DT10 rank 1)",
        "fail_closed_note": "no inferred licenses; unmeasured rows abort; apply requires owner gate",
        "candidate_count": len(candidates),
        "pilot_top": candidates[:pilot_n],
        "candidates_all": candidates,
        "exclusion_count": len(exclusions),
        "exclusions_all": exclusions,
        "owner_gate": "PROPOSE_ONLY",
        "expected_receipts_owed_at_apply": [
            "license_evidence_receipt (per candidate)",
            "owner_gate_receipt (one owner sentence naming the cohort and the apply)",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pilot", type=int, default=5)
    args = ap.parse_args()
    try:
        census, datasets = load_census(args.census)
        packet = build_packet(census, args.pilot)
    except FailClosed as e:
        print("FAIL_CLOSED: %s" % e, file=sys.stderr)
        return 2
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(packet, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("OK candidates=%d pilot=%d exclusions=%d"
          % (packet["candidate_count"], len(packet["pilot_top"]), packet["exclusion_count"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
