#!/usr/bin/env python3
"""Offline byte-bound comparison of a legacy HF asset map with its shadow receipt.

This checks a self-consistent pair of *untrusted* source documents.
It does NOT authenticate source authors, producing code, weights, signatures,
licenses, model evaluations, release authority, or any provider operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

SCHEMA = "szl.source-binding-shadow/v1"
METHODS = {"card", "name", "override", "unmapped"}
TYPES = {"models", "datasets", "spaces"}
MAP_KEYS = {"assets", "coverage", "generated", "stats", "unmapped_family_counts"}
MAP_ROW_KEYS = {"id", "type", "private", "source_repo", "method", "family"}
SHADOW_KEYS = {
    "assets",
    "coverage",
    "method_counts",
    "reason_counts",
    "receipt_signature",
    "schema",
    "semantics",
    "source_map_sha256",
}
SHADOW_ROW_KEYS = {
    "id",
    "type",
    "legacy_method",
    "legacy_source_hint",
    "producer_proof_state",
    "reason",
}
SHADOW_COVERAGE_KEYS = {
    "total",
    "legacy_mapped_hints",
    "unmapped_without_hint",
    "producer_proven_by_input",
    "showcase_link_hints",
}


class ShadowHold(ValueError):
    """Untrusted or inconsistent source-shadow evidence."""


def _unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ShadowHold("DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def _nonfinite(value):
    raise ShadowHold("NONFINITE_JSON")


def _read(raw: bytes):
    if type(raw) is not bytes or len(raw) > 4_000_000:
        raise ShadowHold("INPUT_TYPE_OR_BYTES_CAP")
    try:
        doc = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique,
            parse_constant=_nonfinite,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ShadowHold("MALFORMED_JSON") from exc
    if type(doc) is not dict:
        raise ShadowHold("ROOT_NOT_OBJECT")
    return doc


def _exact_keys(row, allowed, required):
    if type(row) is not dict:
        raise ShadowHold("ROW_NOT_OBJECT")
    if not required.issubset(row) or set(row) - allowed:
        raise ShadowHold("UNREVIEWED_FIELDS_OR_MISSING_REQUIRED")


def _int(actual, expected, code):
    if type(actual) is not int or actual != expected:
        raise ShadowHold(code)


def _reason(method, source_repo):
    if method == "unmapped":
        return "NO_SOURCE_HINT"
    if method == "card" and source_repo == "estate-cards":
        return "SHOWCASE_LINK_NOT_PRODUCER_PROOF"
    if method == "card":
        return "CARD_LINK_NOT_PRODUCER_PROOF"
    if method == "name":
        return "NAME_SIMILARITY_NOT_PRODUCER_PROOF"
    return "OVERRIDE_WITHOUT_VERIFIED_ATTESTATION"


def verify_source_shadow(map_bytes: bytes, shadow_bytes: bytes) -> dict:
    original = _read(map_bytes)
    shadow = _read(shadow_bytes)
    _exact_keys(original, MAP_KEYS, {"assets", "coverage", "stats"})
    _exact_keys(shadow, SHADOW_KEYS, SHADOW_KEYS)
    digest = hashlib.sha256(map_bytes).hexdigest()
    if (
        type(shadow["source_map_sha256"]) is not str
        or shadow["source_map_sha256"] != digest
    ):
        raise ShadowHold("SOURCE_MAP_BYTE_DIGEST_MISMATCH")
    if shadow["schema"] != SCHEMA:
        raise ShadowHold("SHADOW_SCHEMA_UNSUPPORTED")
    if shadow["receipt_signature"] != "UNSIGNED_LOCAL":
        raise ShadowHold("UNSUPPORTED_SIGNATURE_ASSERTION")
    if (
        shadow["semantics"]
        != "source hints are NOT verified producing-source attestations"
    ):
        raise ShadowHold("UNREVIEWED_SEMANTICS")
    originals, claims = original["assets"], shadow["assets"]
    if type(originals) is not list or type(claims) is not list:
        raise ShadowHold("ASSET_ARRAY_MISSING")
    if len(originals) != len(claims):
        raise ShadowHold("SHADOW_POPULATION_MISMATCH")

    seen, methods, reasons = set(), Counter(), Counter()
    for source, claim in zip(originals, claims, strict=True):
        _exact_keys(
            source,
            MAP_ROW_KEYS,
            {"id", "type", "private", "source_repo", "method", "family"},
        )
        _exact_keys(claim, SHADOW_ROW_KEYS, SHADOW_ROW_KEYS)
        identity = (source["type"], source["id"])
        if (
            source["type"] not in TYPES
            or type(source["id"]) is not str
            or not source["id"].startswith("SZLHOLDINGS/")
            or type(source["private"]) is not bool
            or source["method"] not in METHODS
            or type(source["family"]) is not str
        ):
            raise ShadowHold("INVALID_SOURCE_ID_OR_METADATA")
        if identity in seen:
            raise ShadowHold("DUPLICATE_ASSET_ID")
        seen.add(identity)
        if source["method"] == "unmapped":
            if source["source_repo"] is not None:
                raise ShadowHold("UNMAPPED_HAS_SOURCE_HINT")
        elif type(source["source_repo"]) is not str or not source["source_repo"]:
            raise ShadowHold("SOURCE_HINT_INVALID")
        if (
            claim["type"] != source["type"]
            or claim["id"] != source["id"]
            or claim["legacy_method"] != source["method"]
            or claim["legacy_source_hint"] != source["source_repo"]
        ):
            raise ShadowHold("SHADOW_ASSET_CONTENT_MISMATCH")
        if claim["producer_proof_state"] != "NOT_ESTABLISHED":
            raise ShadowHold("UNATTESTED_PRODUCER_PROMOTION")
        expected_reason = _reason(source["method"], source["source_repo"])
        if claim["reason"] != expected_reason:
            raise ShadowHold("SHADOW_REASON_CONFLICT")
        methods[source["method"]] += 1
        reasons[expected_reason] += 1

    cov, stats, cover = original["coverage"], original["stats"], shadow["coverage"]
    _exact_keys(cov, {"total", "mapped", "unmapped"}, {"total", "mapped", "unmapped"})
    _exact_keys(stats, METHODS, METHODS)
    _exact_keys(cover, SHADOW_COVERAGE_KEYS, SHADOW_COVERAGE_KEYS)
    _int(cov["total"], len(originals), "SOURCE_TOTAL_CONFLICT")
    _int(cov["mapped"], len(originals) - methods["unmapped"], "SOURCE_MAPPED_CONFLICT")
    _int(cov["unmapped"], methods["unmapped"], "SOURCE_UNMAPPED_CONFLICT")
    for key in METHODS:
        _int(stats[key], methods[key], "SOURCE_METHOD_CONFLICT")
    _int(cover["total"], len(originals), "SHADOW_TOTAL_CONFLICT")
    _int(cover["legacy_mapped_hints"], cov["mapped"], "SHADOW_MAPPED_CONFLICT")
    _int(cover["unmapped_without_hint"], cov["unmapped"], "SHADOW_UNMAPPED_CONFLICT")
    _int(cover["producer_proven_by_input"], 0, "SELF_ATTESTED_PRODUCER_COUNT")
    _int(
        cover["showcase_link_hints"],
        reasons["SHOWCASE_LINK_NOT_PRODUCER_PROOF"],
        "SHADOW_SHOWCASE_COUNT_CONFLICT",
    )
    for label, actual, expected in (
        ("SHADOW_METHOD_COUNTER_CONFLICT", shadow["method_counts"], methods),
        ("SHADOW_REASON_COUNTER_CONFLICT", shadow["reason_counts"], reasons),
    ):
        if type(actual) is not dict or set(actual) != set(expected):
            raise ShadowHold(label)
        if any(
            type(actual[k]) is not int or actual[k] != v for k, v in expected.items()
        ):
            raise ShadowHold(label)
    return {
        "state": "BYTE_BOUND_SHADOW_ONLY",
        "source_map_sha256": digest,
        "rows": len(originals),
        "legacy_mapped_hints": cov["mapped"],
        "producer_verified": False,
        "signature_verified": False,
        "training_verified": False,
        "quality_verified": False,
        "runtime_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--shadow", type=Path, required=True)
    args = parser.parse_args()
    try:
        answer = verify_source_shadow(args.map.read_bytes(), args.shadow.read_bytes())
    except (OSError, ShadowHold) as exc:
        code = str(exc) if isinstance(exc, ShadowHold) else "SOURCE_READ_UNAVAILABLE"
        print(json.dumps({"state": "HOLD", "reason": code}, sort_keys=True))
        return 78
    print(json.dumps(answer, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
