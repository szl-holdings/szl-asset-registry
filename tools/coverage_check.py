"""Independent fail-closed coverage check for the szl-asset-registry estate.

Every aggregate published in asset_map.json is re-derived from row-level
snapshot data; any drift is reported as a stable violation code.  Standard
library only, no network, no clock reads: identical inputs always produce
byte-identical stdout.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

SCHEMA = "szl.coverage/v1"

VALID_TYPES = frozenset({"models", "datasets", "spaces"})
VALID_METHODS = frozenset({"name", "card", "override", "unmapped"})
MAPPED_METHODS = frozenset({"name", "card", "override"})
VALID_FAMILIES = frozenset({
    "candidate-eval-20261104",
    "corpus-benchmark",
    "laptop-lora-training",
    "marketing-surface",
    "other",
    "run-artifact-store",
})
CENSUS_KINDS = ("models", "datasets", "spaces")
ID_PREFIX = "SZLHOLDINGS/"

# Documented escape hatch for mapped rows whose source_repo is intentionally
# absent from the GitHub org audit.  Empty by policy: every mapped row's
# source_repo must appear in data/gh_org_audit_20261120.json (COV013).
SOURCE_REPO_EXEMPT = frozenset()

ASSET_MAP_RELPATH = "asset_map.json"
CENSUS_RELPATH = "data/hf_census_20261120.json"
AUDIT_RELPATH = "data/gh_org_audit_20261120.json"
UNRESOLVED_RELPATH = "data/unresolved_assets.json"
REASONS_RELPATH = "data/asset_map_unmapped_reasons_20261120.json"
OVERRIDES_RELPATH = "overrides.json"


class InputError(Exception):
    """A snapshot file is missing, unreadable, unparseable, or mis-shaped."""


def _default_read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _require(condition, relpath, problem):
    if not condition:
        raise InputError(relpath + ": " + problem)


def _load_json(root, relpath, read_text):
    path = root / relpath
    try:
        text = read_text(path)
    except Exception as exc:
        raise InputError(relpath + ": missing or unreadable: " + str(exc)) from exc
    try:
        return json.loads(text)
    except (TypeError, ValueError) as exc:
        raise InputError(relpath + ": invalid JSON: " + str(exc)) from exc


def _validate_asset_map(data, relpath):
    _require(isinstance(data, dict), relpath, "top level must be an object")
    for key in ("assets", "coverage", "generated", "stats", "unmapped_family_counts"):
        _require(key in data, relpath, "missing key " + repr(key))
    _require(isinstance(data["assets"], list), relpath, "assets must be a list")
    _require(isinstance(data["coverage"], dict), relpath, "coverage must be an object")
    _require(isinstance(data["generated"], str), relpath, "generated must be a string")
    _require(isinstance(data["stats"], dict), relpath, "stats must be an object")
    _require(isinstance(data["unmapped_family_counts"], dict), relpath, "unmapped_family_counts must be an object")


def _validate_census(data, relpath):
    _require(isinstance(data, dict), relpath, "top level must be an object")
    _require(set(data.keys()) == set(CENSUS_KINDS), relpath, "must have exactly the keys models, datasets, spaces")
    for kind in CENSUS_KINDS:
        rows = data[kind]
        _require(isinstance(rows, list), relpath, kind + " must be a list")
        for index, row in enumerate(rows):
            where = kind + "[" + str(index) + "]"
            _require(isinstance(row, dict), relpath, where + " must be an object")
            _require(isinstance(row.get("id"), str) and row.get("id") != "", relpath, where + ".id must be a nonempty string")
            _require(isinstance(row.get("lastModified"), str), relpath, where + ".lastModified must be a string")
            _require(isinstance(row.get("private"), bool), relpath, where + ".private must be a bool")


def _validate_audit(data, relpath):
    _require(isinstance(data, list), relpath, "top level must be a list")
    for index, row in enumerate(data):
        where = "[" + str(index) + "]"
        _require(isinstance(row, dict), relpath, where + " must be an object")
        _require(isinstance(row.get("isArchived"), bool), relpath, where + ".isArchived must be a bool")
        _require(isinstance(row.get("name"), str) and row.get("name") != "", relpath, where + ".name must be a nonempty string")
        _require(isinstance(row.get("pushedAt"), str), relpath, where + ".pushedAt must be a string")
        _require(isinstance(row.get("updatedAt"), str), relpath, where + ".updatedAt must be a string")
        _require(row.get("visibility") in ("PUBLIC", "PRIVATE"), relpath, where + ".visibility must be PUBLIC or PRIVATE")


def _validate_unresolved(data, relpath):
    _require(isinstance(data, dict), relpath, "top level must be an object")
    for key in ("generated", "policy", "unresolved"):
        _require(key in data, relpath, "missing key " + repr(key))
    _require(isinstance(data["generated"], str), relpath, "generated must be a string")
    _require(isinstance(data["policy"], str), relpath, "policy must be a string")
    _require(isinstance(data["unresolved"], list), relpath, "unresolved must be a list")


def _validate_reasons(data, relpath):
    _require(isinstance(data, dict), relpath, "top level must be an object")
    for key in ("_comment", "_contract", "class", "generated_utc", "reasons", "sweep_counts"):
        _require(key in data, relpath, "missing key " + repr(key))
    for key in ("_comment", "_contract", "class", "generated_utc"):
        _require(isinstance(data[key], str), relpath, key + " must be a string")
    _require(isinstance(data["reasons"], dict), relpath, "reasons must be an object")
    _require(isinstance(data["sweep_counts"], dict), relpath, "sweep_counts must be an object")


def _validate_overrides(data, relpath):
    _require(isinstance(data, dict), relpath, "top level must be an object")
    for key, value in data.items():
        if key.startswith("_"):
            if key == "_comment":
                _require(isinstance(value, str), relpath, "_comment must be a string")
            elif key == "_evidence":
                _require(isinstance(value, dict), relpath, "_evidence must be an object")
                for asset_id, evidence in value.items():
                    _require(isinstance(asset_id, str) and isinstance(evidence, str), relpath, "_evidence entries must map string asset ids to string evidence")
            # Any other underscore key is tolerated at load time; COV010 flags it.
        else:
            _require(isinstance(value, str) and value != "", relpath, "override " + repr(key) + " must be a nonempty string source repo")


def load_snapshots(registry_root, read_text=None):
    """Load and structurally validate all six snapshots.

    Returns a dict with keys asset_map, census, audit, unresolved, reasons,
    overrides.  Any missing, unreadable, unparseable, or wrongly shaped file
    raises InputError naming the file and the problem.
    """
    root = Path(registry_root)
    if read_text is None:
        read_text = _default_read_text
    specs = (
        ("asset_map", ASSET_MAP_RELPATH, _validate_asset_map),
        ("census", CENSUS_RELPATH, _validate_census),
        ("audit", AUDIT_RELPATH, _validate_audit),
        ("unresolved", UNRESOLVED_RELPATH, _validate_unresolved),
        ("reasons", REASONS_RELPATH, _validate_reasons),
        ("overrides", OVERRIDES_RELPATH, _validate_overrides),
    )
    snapshots = {}
    for name, relpath, validate in specs:
        data = _load_json(root, relpath, read_text)
        validate(data, relpath)
        snapshots[name] = data
    return snapshots


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def collect_violations(registry_root, snapshots=None):
    """Recompute every aggregate and return the sorted list of violations."""
    if snapshots is None:
        snapshots = load_snapshots(registry_root)
    violations = []
    asset_map = snapshots["asset_map"]
    assets = asset_map["assets"]
    census = snapshots["census"]
    audit = snapshots["audit"]
    unresolved_records = snapshots["unresolved"]["unresolved"]
    reasons = snapshots["reasons"]["reasons"]
    overrides = snapshots["overrides"]

    rows = []
    for index, row in enumerate(assets):
        if isinstance(row, dict):
            rows.append(row)
        else:
            violations.append("COV004_ROW_FIELD_INVALID row_index=" + str(index))

    # COV002: coverage block must equal row-level recomputation.
    coverage = asset_map["coverage"]
    total = len(assets)
    mapped = sum(1 for row in rows if row.get("method") in MAPPED_METHODS)
    unmapped = sum(1 for row in rows if row.get("method") == "unmapped")
    for field, recomputed in (("total", total), ("mapped", mapped), ("unmapped", unmapped)):
        claimed = coverage.get(field)
        if not _is_int(claimed) or claimed != recomputed:
            violations.append("COV002_COVERAGE_COUNT_MISMATCH " + field + " coverage=" + repr(claimed) + " recomputed=" + str(recomputed))

    # COV003: census id multiset must equal the asset rows of each type.
    for kind in CENSUS_KINDS:
        census_ids = [row["id"] for row in census[kind]]
        asset_ids = [row.get("id") for row in rows if row.get("type") == kind and isinstance(row.get("id"), str)]
        census_counts = Counter(census_ids)
        asset_counts = Counter(asset_ids)
        if census_counts != asset_counts:
            parts = [kind, "census=" + str(len(census_ids)), "rows=" + str(len(asset_ids))]
            only_census = sorted(set(census_ids) - set(asset_ids))
            only_assets = sorted(set(asset_ids) - set(census_ids))
            if only_census:
                parts.append("census_only=" + ",".join(only_census[:5]))
            if only_assets:
                parts.append("asset_only=" + ",".join(only_assets[:5]))
            violations.append("COV003_CENSUS_ROW_MISMATCH " + " ".join(parts))

    # COV004: row-level field contract; at most one violation per row, id context.
    for row in rows:
        asset_id = row.get("id")
        context = asset_id if isinstance(asset_id, str) else repr(asset_id)
        bad = False
        if not (isinstance(asset_id, str) and asset_id.startswith(ID_PREFIX) and asset_id.count("/") == 1 and len(asset_id) > len(ID_PREFIX)):
            bad = True
        elif row.get("type") not in VALID_TYPES:
            bad = True
        elif row.get("method") not in VALID_METHODS:
            bad = True
        elif row.get("family") not in VALID_FAMILIES:
            bad = True
        elif not isinstance(row.get("private"), bool):
            bad = True
        elif row.get("method") == "unmapped":
            bad = row.get("source_repo") is not None
        else:
            source_repo = row.get("source_repo")
            bad = not (isinstance(source_repo, str) and source_repo != "")
        if bad:
            violations.append("COV004_ROW_FIELD_INVALID " + context)

    # COV005: duplicate asset identity keys. Asset identity is (type, id):
    # the same id may legitimately exist as distinct HF kinds (model and
    # dataset and space); only a repeated (type, id) pair is a duplicate.
    key_counts = Counter(
        (row.get("type"), row.get("id"))
        for row in rows
        if isinstance(row.get("id"), str) and isinstance(row.get("type"), str)
    )
    for (asset_type, asset_id), count in sorted(key_counts.items()):
        if count > 1:
            violations.append(
                "COV005_DUPLICATE_ASSET_ID "
                + asset_type
                + "/"
                + asset_id
            )


    # COV006: stats block must equal per-method recomputation.
    stats = asset_map["stats"]
    recomputed_stats = {
        "card": sum(1 for row in rows if row.get("method") == "card"),
        "name": sum(1 for row in rows if row.get("method") == "name"),
        "override": sum(1 for row in rows if row.get("method") == "override"),
        "unmapped": sum(1 for row in rows if row.get("method") == "unmapped"),
    }
    for key in sorted(set(stats.keys()) | set(recomputed_stats.keys())):
        if key not in recomputed_stats:
            violations.append("COV006_STATS_MISMATCH " + key + " unexpected_key stats=" + repr(stats.get(key)))
            continue
        claimed = stats.get(key)
        if not _is_int(claimed) or claimed != recomputed_stats[key]:
            violations.append("COV006_STATS_MISMATCH " + key + " stats=" + repr(claimed) + " recomputed=" + str(recomputed_stats[key]))

    # COV007: unmapped_family_counts must equal per-family unmapped counts.
    claimed_families = asset_map["unmapped_family_counts"]
    family_counts = Counter(
        row.get("family") for row in rows
        if row.get("method") == "unmapped" and isinstance(row.get("family"), str)
    )
    for family in sorted(set(claimed_families.keys()) | set(family_counts.keys())):
        recomputed = family_counts.get(family, 0)
        if family not in claimed_families:
            violations.append("COV007_FAMILY_COUNT_MISMATCH " + str(family) + " map=absent recomputed=" + str(recomputed))
            continue
        claimed = claimed_families[family]
        if not _is_int(claimed) or claimed != recomputed:
            violations.append("COV007_FAMILY_COUNT_MISMATCH " + str(family) + " map=" + repr(claimed) + " recomputed=" + str(recomputed))

    asset_ids = {asset_id for (_asset_kind, asset_id) in key_counts}
    unmapped_ids = set(
        row.get("id") for row in rows
        if row.get("method") == "unmapped" and isinstance(row.get("id"), str)
    )

    # COV008: unresolved records must sit inside the unmapped asset ids.
    seen_unresolved = Counter()
    for record in unresolved_records:
        record_id = record.get("id") if isinstance(record, dict) else None
        if not isinstance(record_id, str):
            continue  # malformed shape is COV012's job
        seen_unresolved[record_id] += 1
        if record_id not in asset_ids:
            violations.append("COV008_UNRESOLVED_NOT_IN_UNMAPPED " + record_id + " absent_from_assets")
        elif record_id not in unmapped_ids:
            violations.append("COV008_UNRESOLVED_NOT_IN_UNMAPPED " + record_id + " not_unmapped")
    for record_id, count in seen_unresolved.items():
        if count > 1:
            violations.append("COV008_UNRESOLVED_NOT_IN_UNMAPPED " + record_id + " repeated=" + str(count))

    # COV009: every unmapped asset id needs a nonempty reason_code.
    for asset_id in sorted(unmapped_ids):
        entry = reasons.get(asset_id)
        reason_code = entry.get("reason_code") if isinstance(entry, dict) else None
        if not isinstance(reason_code, str) or reason_code == "":
            violations.append("COV009_UNMAPPED_REASON_MISSING " + asset_id)

    # COV010: overrides.json must agree with override asset rows, both ways.
    rows_by_id = {}
    for row in rows:
        row_id = row.get("id")
        if isinstance(row_id, str) and row_id not in rows_by_id:
            rows_by_id[row_id] = row
    override_entries = {key: value for key, value in overrides.items() if not key.startswith("_")}
    for key in sorted(override_entries.keys()):
        row = rows_by_id.get(key)
        if row is None:
            violations.append("COV010_OVERRIDE_CONTRACT " + key + " missing_asset_row")
        elif row.get("method") != "override":
            violations.append("COV010_OVERRIDE_CONTRACT " + key + " method=" + repr(row.get("method")))
        elif row.get("source_repo") != override_entries[key]:
            violations.append("COV010_OVERRIDE_CONTRACT " + key + " source_repo=" + repr(row.get("source_repo")) + " overrides=" + repr(override_entries[key]))
    for row in rows:
        if row.get("method") == "override":
            row_id = row.get("id")
            if not isinstance(row_id, str):
                continue
            if row_id not in override_entries:
                violations.append("COV010_OVERRIDE_CONTRACT " + row_id + " missing_override_entry")
            elif override_entries[row_id] != row.get("source_repo"):
                violations.append("COV010_OVERRIDE_CONTRACT " + row_id + " source_repo_mismatch")
    for key in sorted(overrides.keys()):
        if key.startswith("_") and key not in ("_comment", "_evidence"):
            violations.append("COV010_OVERRIDE_CONTRACT underscore_key=" + key)

    # COV011: every overrides.json entry needs a nonempty _evidence entry.
    evidence = overrides.get("_evidence")
    if not isinstance(evidence, dict):
        evidence = {}
    for key in sorted(override_entries.keys()):
        item = evidence.get(key)
        if not isinstance(item, str) or item == "":
            violations.append("COV011_OVERRIDE_EVIDENCE_MISSING " + key)

    # COV012: unresolved record shape, one violation per bad record.
    for index, record in enumerate(unresolved_records):
        if not isinstance(record, dict):
            violations.append("COV012_UNRESOLVED_RECORD_INVALID index=" + str(index))
            continue
        record_id = record.get("id")
        context = record_id if isinstance(record_id, str) and record_id != "" else "index=" + str(index)
        shape_ok = True
        for field in ("id", "type", "reason"):
            value = record.get(field)
            if not isinstance(value, str) or value == "":
                shape_ok = False
        for field in ("quotes", "urls"):
            value = record.get(field)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                shape_ok = False
        if not shape_ok:
            violations.append("COV012_UNRESOLVED_RECORD_INVALID " + context)

    # COV013: mapped rows' source_repo must appear in the org audit.
    audit_names = set(row["name"] for row in audit)
    for row in rows:
        if row.get("method") in MAPPED_METHODS:
            source_repo = row.get("source_repo")
            if (
                isinstance(source_repo, str)
                and source_repo not in audit_names
                and source_repo not in SOURCE_REPO_EXEMPT
            ):
                row_id = row.get("id") if isinstance(row.get("id"), str) else "unknown"
                violations.append("COV013_SOURCE_REPO_NOT_IN_AUDIT " + row_id + " repo=" + source_repo)

    return sorted(violations)


def _error_payload(message):
    return {"schema": SCHEMA, "clean": False, "error": message, "violations": []}


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) > 1:
        print(json.dumps(_error_payload("usage: coverage_check.py [REGISTRY_ROOT]")))
        return 2
    root = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent
    try:
        snapshots = load_snapshots(root)
        violations = collect_violations(root, snapshots)
    except InputError as exc:
        print(json.dumps(_error_payload(str(exc))))
        return 2
    except Exception as exc:
        print(json.dumps(_error_payload("internal error: " + type(exc).__name__ + ": " + str(exc))))
        return 2

    assets = snapshots["asset_map"]["assets"]
    rows = [row for row in assets if isinstance(row, dict)]
    unresolved_records = snapshots["unresolved"]["unresolved"]
    reasons = snapshots["reasons"]["reasons"]
    unmapped_ids = set(
        row.get("id") for row in rows
        if row.get("method") == "unmapped" and isinstance(row.get("id"), str)
    )
    inside = 0
    for record in unresolved_records:
        if isinstance(record, dict) and record.get("id") in unmapped_ids:
            inside += 1
    without_reason = 0
    for asset_id in unmapped_ids:
        entry = reasons.get(asset_id)
        reason_code = entry.get("reason_code") if isinstance(entry, dict) else None
        if not isinstance(reason_code, str) or reason_code == "":
            without_reason += 1
    payload = {
        "schema": SCHEMA,
        "clean": len(violations) == 0,
        "violations": violations,
        "counts": {
            "total": len(assets),
            "mapped": sum(1 for row in rows if row.get("method") in MAPPED_METHODS),
            "unmapped": sum(1 for row in rows if row.get("method") == "unmapped"),
            "unresolved": len(unresolved_records),
            "override_mapped": sum(1 for row in rows if row.get("method") == "override"),
            "audit_repos": len(snapshots["audit"]),
            "reasons": len(reasons),
        },
        "reconciliation": {
            "unresolved_inside_unmapped": inside,
            "unresolved_outside": len(unresolved_records) - inside,
            "unmapped_without_reason": without_reason,
        },
    }
    print(json.dumps(payload))
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
