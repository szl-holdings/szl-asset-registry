#!/usr/bin/env python3
"""Offline evidence-grade audit of legacy Hugging Face -> GitHub mappings.

A README link or a similar name is a discovery hint, NOT verified producer
provenance. The v1 asset_map.json contains no independently verified,
revision-bound source/weight attestation. Never promote hints to proof.
No network access, secrets, Hub writes, or mutation of the input registry.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "szl.source-binding-shadow/v1"
METHODS = {"name", "card", "override", "unmapped"}
TYPES = {"models", "datasets", "spaces"}


class AuditError(ValueError):
    """Fail closed on malformed or contradictory registry input."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise AuditError(f"DUPLICATE_JSON_KEY:{key}")
        obj[key] = value
    return obj


def read_json_strict(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError("INVALID_JSON") from exc
    if type(data) is not dict:
        raise AuditError("ROOT_NOT_OBJECT")
    return data


def classify(asset: dict[str, Any]) -> str:
    method, repo = asset.get("method"), asset.get("source_repo")
    if method == "unmapped":
        return "NO_SOURCE_HINT"
    if method == "card" and repo == "estate-cards":
        return "SHOWCASE_LINK_NOT_PRODUCER_PROOF"
    if method == "card":
        return "CARD_LINK_NOT_PRODUCER_PROOF"
    if method == "name":
        return "NAME_SIMILARITY_NOT_PRODUCER_PROOF"
    return "OVERRIDE_WITHOUT_VERIFIED_ATTESTATION"


def audit_map(doc: dict[str, Any], source_sha256: str) -> dict[str, Any]:
    rows = doc.get("assets")
    if type(rows) is not list:
        raise AuditError("ASSETS_NOT_ARRAY")
    seen: set[tuple[str, str]] = set()
    reasons: Counter[str] = Counter()
    methods: Counter[str] = Counter()
    details: list[dict[str, str | None]] = []
    for asset in rows:
        if type(asset) is not dict:
            raise AuditError("ASSET_NOT_OBJECT")
        kind, rid = asset.get("type"), asset.get("id")
        method, repo = asset.get("method"), asset.get("source_repo")
        if kind not in TYPES or type(rid) is not str or not rid.startswith("SZLHOLDINGS/"):
            raise AuditError("INVALID_ASSET_ID_OR_TYPE")
        if (kind, rid) in seen:
            raise AuditError(f"DUPLICATE_ASSET:{kind}:{rid}")
        seen.add((kind, rid))
        if method not in METHODS:
            raise AuditError(f"UNKNOWN_MAPPING_METHOD:{rid}")
        if method == "unmapped":
            if repo is not None:
                raise AuditError(f"UNMAPPED_HAS_REPO:{rid}")
        elif type(repo) is not str or not repo:
            raise AuditError(f"MAPPED_HINT_MISSING_REPO:{rid}")
        # A map field cannot self-certify source provenance.
        if ("producer_verified" in asset and asset["producer_verified"] is not False) or asset.get("source_binding_status") not in (None, "UNVERIFIED", "UNKNOWN"):
            raise AuditError(f"UNSUPPORTED_PRODUCER_PROOF_CLAIM:{rid}")
        reason = classify(asset)
        methods[method] += 1
        reasons[reason] += 1
        details.append({
            "id": rid, "type": kind, "legacy_method": method,
            "legacy_source_hint": repo,
            "producer_proof_state": "NOT_ESTABLISHED",
            "reason": reason,
        })
    coverage, stats = doc.get("coverage"), doc.get("stats")
    if type(coverage) is not dict or type(stats) is not dict:
        raise AuditError("MISSING_COVERAGE_OR_STATS")
    if any(type(coverage.get(key)) is not int for key in ("total", "mapped", "unmapped")) or any(type(stats.get(m)) is not int for m in METHODS):
        raise AuditError("INVALID_COUNT_TYPE")
    if coverage.get("total") != len(rows) or coverage.get("unmapped") != methods["unmapped"]:
        raise AuditError("INCONSISTENT_COVERAGE")
    if coverage.get("mapped") != len(rows) - methods["unmapped"]:
        raise AuditError("INCONSISTENT_MAPPED_HINT_COUNT")
    if any(stats.get(m) != methods[m] for m in METHODS):
        raise AuditError("INCONSISTENT_METHOD_STATS")
    return {
        "schema": SCHEMA,
        "receipt_signature": "UNSIGNED_LOCAL",
        "source_map_sha256": source_sha256,
        "semantics": "source hints are NOT verified producing-source attestations",
        "coverage": {
            "total": len(rows),
            "legacy_mapped_hints": len(rows) - methods["unmapped"],
            "unmapped_without_hint": methods["unmapped"],
            "producer_proven_by_input": 0,
            "showcase_link_hints": reasons["SHOWCASE_LINK_NOT_PRODUCER_PROOF"],
        },
        "method_counts": dict(sorted(methods.items())),
        "reason_counts": dict(sorted(reasons.items())),
        "assets": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("asset_map.json"))
    parser.add_argument("--output", type=Path, help="Exclusive-create JSON audit receipt (no overwrite)")
    args = parser.parse_args()
    raw = args.input.read_bytes()
    result = audit_map(read_json_strict(raw), hashlib.sha256(raw).hexdigest())
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps({
        "schema": result["schema"],
        "source_map_sha256": result["source_map_sha256"],
        "coverage": result["coverage"],
        "reason_counts": result["reason_counts"],
        "receipt_file": str(args.output) if args.output else None,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
