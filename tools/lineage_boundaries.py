# SPDX-License-Identifier: Apache-2.0
"""Honest mapping scopes: a card-weaver link is not weight/training provenance.

This module is metadata-only. It never reads a Hub token, accesses a private
artifact, executes remote files or authorizes publication.
"""

from __future__ import annotations

from collections import Counter
import re

KINDS = frozenset({"models", "datasets", "spaces"})
METHODS = frozenset({"name", "card", "override", "unmapped"})
ALLOWED_SCOPE = {
    "unmapped": "SOURCE_UNMAPPED",
    "name": "NAME_REFERENCE_ONLY",
    "card": "CARD_LINK_REFERENCE_ONLY",
    "override": "CURATED_REFERENCE_ONLY",
}
NAME = re.compile(r"^SZLHOLDINGS/[^/\s]+$")
REPO = re.compile(r"^[A-Za-z0-9._-]{1,200}$")


class ScopeError(ValueError):
    """Reject non-evidenced metadata without revealing asset payloads."""


def assess(document: dict) -> dict:
    """Produce *aggregate* scoped claims; never emit private Hub asset names."""
    if not isinstance(document, dict):
        raise ScopeError("MAP_INVALID")
    rows = document.get("assets")
    coverage = document.get("coverage")
    if not isinstance(rows, list) or not isinstance(coverage, dict):
        raise ScopeError("MAP_INVALID")
    seen: set[tuple[str, str]] = set()
    counts: Counter[str] = Counter()
    method_counts: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row, dict):
            raise ScopeError("ASSET_INVALID")
        ident, kind = row.get("id"), row.get("type")
        method, source = row.get("method"), row.get("source_repo")
        if not isinstance(ident, str) or not NAME.fullmatch(ident) or kind not in KINDS:
            raise ScopeError("IDENTITY_INVALID")
        key = (kind, ident)
        if key in seen:
            raise ScopeError("DUPLICATE_ASSET")
        seen.add(key)
        if method not in METHODS:
            raise ScopeError("METHOD_INVALID")
        if any(row.get(flag) is True for flag in (
            "training_verified", "quality_verified", "promotion_authorized",
            "producer_verified", "source_verified", "runtime_verified",
        )):
            raise ScopeError("UNATTESTED_VERIFICATION_CLAIM")
        if method == "unmapped":
            if source is not None:
                raise ScopeError("UNMAPPED_SOURCE_CONTRADICTION")
            scope = ALLOWED_SCOPE[method]
        else:
            if (not isinstance(source, str) or source in (".", "..")
                    or not REPO.fullmatch(source)):
                raise ScopeError("SOURCE_REFERENCE_INVALID")
            # The documented card-issuer project weaves README/card assets.
            # No training code, data lineage or runtime identity follows
            # from an asset linking to this repository.
            if source == "estate-cards":
                scope = "CARD_PRESENTATION_ONLY"
            else:
                scope = ALLOWED_SCOPE[method]
        method_counts[method] += 1
        counts[scope] += 1
    mapped = len(rows) - method_counts["unmapped"]
    if (coverage.get("total") != len(rows)
            or coverage.get("mapped") != mapped
            or coverage.get("unmapped") != method_counts["unmapped"]):
        raise ScopeError("COVERAGE_DENOMINATOR_INVALID")
    return {
        "schema": "szl.hf-map-lineage-boundaries/v1",
        "source_map_rows": len(rows),
        "reference_mapped": mapped,
        "unmapped": method_counts["unmapped"],
        "method_counts": dict(sorted(method_counts.items())),
        "reference_scopes": dict(sorted(counts.items())),
        "card_generator_only": counts["CARD_PRESENTATION_ONLY"],
        "source_producer_verified": 0,
        "evaluation_verified": 0,
        "promotion_authorized": 0,
        "claim_boundary": "GITHUB_REFERENCE_MAP_NOT_TRAINING_DATA_MODEL_OR_RELEASE_PROVENANCE",
        "release_admission": "HOLD_INDEPENDENT_SOURCE_EVAL_AND_RUNTIME_PROOF",
    }
