"""Build the deterministic SZL repo catalog from registry snapshots.

Offline, fail-closed estate-registry catalog builder. Python 3.12, stdlib
only. No network access and no clock reads anywhere: every timestamp in the
output originates from snapshot data (``asset_map["generated"]``).

Self-digest rule
----------------
``catalog_snapshot_sha256`` (identical in every row) is the SHA-256 hex
digest of the canonical serialization of the full rows list WITH the
``catalog_snapshot_sha256`` key removed from every row.
``source_census_sha256`` is the SHA-256 hex digest of the canonical
serialization of the raw audit list (the whole top-level list from the
``gh_org_audit_*.json`` snapshot).

Canonical serialization
-----------------------
``json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)``
encoded as UTF-8. Identical inputs therefore produce byte-identical output
files.

Fail-closed gate
----------------
The catalog files are emitted ONLY when
``coverage_check.collect_violations(registry_root)`` returns an empty list.
On any violation nothing is written and the CLI exits 1. The coverage gate
itself lives in the sibling ``coverage_check`` module and is imported here,
never reimplemented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import coverage_check  # noqa: E402  sibling gate module (imported, not reimplemented)

ORG_IDENTITY = "szl-holdings"  # fixed org identity constant (documented)
SCHEMA_ID = "szl.catalog/v1"
SCHEMA_VERSION = "1"  # schema_version is always the string "1"
REPO_CATALOG_GEN = "repo_catalog_{GEN}"


def _canonical(obj) -> bytes:
    """Canonical deterministic serialization: sorted keys, compact, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _snapshot_tag(generated: str) -> str:
    """Compact snapshot tag for filenames: 2026-11-20 -> 20261120."""
    return generated.replace(":", "-").replace("-", "")


def build_rows(snapshots: dict) -> list[dict]:
    """Build one catalog row per audit entry, sorted by github_name."""
    asset_map = snapshots["asset_map"]
    audit = snapshots["audit"]
    generated = str(asset_map["generated"])

    by_repo: dict[str, list[str]] = {}
    for asset in asset_map["assets"]:
        source_repo = asset.get("source_repo")
        if source_repo is None:
            continue  # unmapped rows never carry source_repo
        by_repo.setdefault(str(source_repo), []).append(str(asset["id"]))
    for ids in by_repo.values():
        ids.sort()

    source_census_sha256 = _sha256_hex(_canonical(audit))

    rows: list[dict] = []
    for entry in audit:
        name = str(entry["name"])
        ids = by_repo.get(name, [])
        rows.append({
            "schema_version": SCHEMA_VERSION,
            "catalog_snapshot_sha256": "",  # placeholder; self-digest filled below
            "repository_id": name,
            "github_owner": ORG_IDENTITY,
            "github_name": name,
            "full_name": ORG_IDENTITY + "/" + name,
            "default_branch": "",  # not derivable offline
            "census_revision_or_head_sha": "",  # not derivable offline
            "visibility": str(entry["visibility"]).lower(),
            "archived": bool(entry["isArchived"]),
            "is_fork": "",  # unknown offline; never guess
            "description": "",
            "primary_language": "",
            "topics_json": json.dumps([], separators=(",", ":")),
            "registry_mapping_ids_json": json.dumps(ids, separators=(",", ":"), ensure_ascii=False),
            "mapped_asset_count": len(ids),
            "unmapped_asset_count": 0,
            "registry_coverage_status": "full" if ids else "none",
            "attestation_run_id": "",  # digest pin pending; never fabricate
            "source_census_sha256": source_census_sha256,
            "generated_at_from_snapshot": generated,
        })
    rows.sort(key=lambda row: row["github_name"])

    stripped = [
        {key: value for key, value in row.items() if key != "catalog_snapshot_sha256"}
        for row in rows
    ]
    catalog_snapshot_sha256 = _sha256_hex(_canonical(stripped))
    for row in rows:
        row["catalog_snapshot_sha256"] = catalog_snapshot_sha256
    return rows


def _md_cell(value) -> str:
    return str(value).replace("|", "\\|")


def _render_markdown(rows: list[dict]) -> str:
    """Pipe table derived only from the written JSON rows."""
    lines = [
        "| repository | visibility | archived | mapped | unmapped | status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in sorted(rows, key=lambda r: r["github_name"]):
        archived = "true" if row["archived"] else "false"
        lines.append(
            "| {} | {} | {} | {} | {} | {} |".format(
                _md_cell(row["github_name"]),
                _md_cell(row["visibility"]),
                archived,
                row["mapped_asset_count"],
                row["unmapped_asset_count"],
                _md_cell(row["registry_coverage_status"]),
            )
        )
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_catalog.py",
        description="Build the deterministic SZL repo catalog; writes only when the coverage gate is clean.",
    )
    parser.add_argument("registry_root", nargs="?", default=".", help="Registry root (default: current directory).")
    parser.add_argument("--output-dir", default=None, help="Output dir for catalog files (default: REGISTRY_ROOT/data).")
    args = parser.parse_args(argv)

    registry_root = Path(args.registry_root)
    output_dir = Path(args.output_dir) if args.output_dir is not None else registry_root / "data"

    try:
        violations = coverage_check.collect_violations(registry_root)
    except coverage_check.InputError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2

    if violations:
        # Fail-closed: coverage gate not clean -> emit no catalog files at all.
        print(json.dumps({"violations": list(violations), "catalog_refused": True}, sort_keys=True))
        return 1

    try:
        snapshots = coverage_check.load_snapshots(registry_root)
    except coverage_check.InputError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2

    rows = build_rows(snapshots)
    catalog_snapshot_sha256 = rows[0]["catalog_snapshot_sha256"] if rows else _sha256_hex(_canonical([]))

    tag = _snapshot_tag(str(snapshots["asset_map"]["generated"]))
    json_name = REPO_CATALOG_GEN.format(GEN=tag) + ".json"
    md_name = REPO_CATALOG_GEN.format(GEN=tag) + ".md"

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / json_name
    md_path = output_dir / md_name

    json_path.write_bytes(_canonical(rows) + b"\n")
    written_rows = json.loads(json_path.read_bytes().decode("utf-8"))  # md derives ONLY from the written JSON
    md_path.write_bytes(_render_markdown(written_rows).encode("utf-8"))

    def _rel(path: Path) -> str:
        return os.path.relpath(str(path), str(registry_root))

    print(json.dumps({
        "schema": SCHEMA_ID,
        "clean": True,
        "repo_count": len(rows),
        "json_path": _rel(json_path),
        "md_path": _rel(md_path),
        "catalog_snapshot_sha256": catalog_snapshot_sha256,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
