import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_catalog  # noqa: E402

GENERATED = "2026-11-20"
TAG = "20261120"

AUDIT = [
    {"isArchived": False, "name": "empty-repo", "pushedAt": "2026-11-19T00:00:00Z", "updatedAt": "2026-11-19T00:00:00Z", "visibility": "PUBLIC"},
    {"isArchived": True, "name": "szl-models-b", "pushedAt": "2026-11-19T00:00:00Z", "updatedAt": "2026-11-19T00:00:00Z", "visibility": "PRIVATE"},
    {"isArchived": False, "name": "szl-datasets-override", "pushedAt": "2026-11-19T00:00:00Z", "updatedAt": "2026-11-19T00:00:00Z", "visibility": "PUBLIC"},
    {"isArchived": False, "name": "szl-models-a", "pushedAt": "2026-11-19T00:00:00Z", "updatedAt": "2026-11-19T00:00:00Z", "visibility": "PUBLIC"},
    {"isArchived": False, "name": "szl-spaces-a", "pushedAt": "2026-11-19T00:00:00Z", "updatedAt": "2026-11-19T00:00:00Z", "visibility": "PUBLIC"},
]

ASSETS = [
    {"family": "corpus-benchmark", "id": "SZLHOLDINGS/MODELA", "method": "card", "private": False, "source_repo": "szl-models-a", "type": "models"},
    {"family": "corpus-benchmark", "id": "SZLHOLDINGS/MODELB", "method": "name", "private": True, "source_repo": "szl-models-b", "type": "models"},
    {"family": "marketing-surface", "id": "SZLHOLDINGS/DATA1", "method": "override", "private": False, "source_repo": "szl-datasets-override", "type": "datasets"},
    {"family": "other", "id": "SZLHOLDINGS/SPACE1", "method": "name", "private": False, "source_repo": "szl-spaces-a", "type": "spaces"},
    {"family": "other", "id": "SZLHOLDINGS/UNM1", "method": "unmapped", "private": False, "source_repo": None, "type": "spaces"},
]


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + chr(10), encoding="utf-8")


def make_registry(root, mapped_bump=0):
    root = Path(root)
    write_json(root / "asset_map.json", {
        "generated": GENERATED,
        "coverage": {"total": 5, "mapped": 4 + mapped_bump, "unmapped": 1},
        "stats": {"card": 1, "name": 2, "override": 1, "unmapped": 1},
        "unmapped_family_counts": {"other": 1},
        "assets": ASSETS,
    })
    write_json(root / "data" / "hf_census_20261120.json", {
        "models": [{"id": "SZLHOLDINGS/MODELA", "lastModified": "x", "private": False}, {"id": "SZLHOLDINGS/MODELB", "lastModified": "x", "private": True}],
        "datasets": [{"id": "SZLHOLDINGS/DATA1", "lastModified": "x", "private": False}],
        "spaces": [{"id": "SZLHOLDINGS/SPACE1", "lastModified": "x", "private": False}, {"id": "SZLHOLDINGS/UNM1", "lastModified": "x", "private": False}],
    })
    write_json(root / "data" / "gh_org_audit_20261120.json", AUDIT)
    write_json(root / "data" / "unresolved_assets.json", {
        "generated": GENERATED,
        "policy": "fail-closed fixture",
        "unresolved": [],
    })
    write_json(root / "data" / "asset_map_unmapped_reasons_20261120.json", {
        "_comment": "fixture",
        "_contract": "fixture",
        "class": "fixture",
        "generated_utc": "2026-11-20T00:00:00Z",
        "reasons": {"SZLHOLDINGS/UNM1": {"candidates": {}, "evidence": "fixture", "identity_verified": False, "reason_code": "NO_MATCH"}},
        "sweep_counts": {"ambiguous": 0, "exact": 0, "nomatch": 1, "total": 1},
    })
    write_json(root / "overrides.json", {
        "_comment": "fixture",
        "SZLHOLDINGS/DATA1": "szl-datasets-override",
        "_evidence": {"SZLHOLDINGS/DATA1": "manual override evidence"},
    })
    return root


class BuildCatalogTest(unittest.TestCase):
    def scenario(self, mapped_bump=0):
        reg_tmp = tempfile.TemporaryDirectory()
        out_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(reg_tmp.cleanup)
        self.addCleanup(out_tmp.cleanup)
        root = make_registry(Path(reg_tmp.name), mapped_bump=mapped_bump)
        out = Path(out_tmp.name)
        return root, out

    def run_main(self, root, out):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = build_catalog.main([str(root), "--output-dir", str(out)])
        return rc, json.loads(buf.getvalue().strip())

    def paths(self, out):
        return out / ("repo_catalog_" + TAG + ".json"), out / ("repo_catalog_" + TAG + ".md")

    def test_clean_build(self):
        root, out = self.scenario()
        rc, payload = self.run_main(root, out)
        self.assertEqual(rc, 0)
        self.assertEqual(payload["schema"], "szl.catalog/v1")
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["repo_count"], len(AUDIT))
        json_path, md_path = self.paths(out)
        self.assertTrue(json_path.is_file() and md_path.is_file())
        rows = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), len(AUDIT))
        self.assertEqual([r["github_name"] for r in rows], sorted(e["name"] for e in AUDIT))
        md = md_path.read_text(encoding="utf-8")
        self.assertTrue(md.startswith("| repository | visibility | archived | mapped | unmapped | status |"))
        for entry in AUDIT:
            self.assertIn(entry["name"], md)
        self.assertTrue(md.endswith(chr(10)) and not md.endswith(chr(10) + chr(10)))

    def test_gate_blocks(self):
        root, out = self.scenario(mapped_bump=1)
        rc, payload = self.run_main(root, out)
        self.assertEqual(rc, 1)
        self.assertTrue(payload.get("catalog_refused"))
        written = list(out.glob("repo_catalog_*")) if out.exists() else []
        self.assertEqual(written, [])

    def test_identical_bytes(self):
        root, out = self.scenario()
        self.assertEqual(self.run_main(root, out)[0], 0)
        json_path, md_path = self.paths(out)
        first_json = json_path.read_bytes()
        first_md = md_path.read_bytes()
        self.assertEqual(self.run_main(root, out)[0], 0)
        self.assertEqual(json_path.read_bytes(), first_json)
        self.assertEqual(md_path.read_bytes(), first_md)

    def test_digest_rule(self):
        root, out = self.scenario()
        self.assertEqual(self.run_main(root, out)[0], 0)
        json_path, _ = self.paths(out)
        rows = json.loads(json_path.read_text(encoding="utf-8"))
        stripped = [{k: v for k, v in r.items() if k != "catalog_snapshot_sha256"} for r in rows]
        blob = json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        expected = hashlib.sha256(blob).hexdigest()
        self.assertEqual(len({r["catalog_snapshot_sha256"] for r in rows}), 1)
        for row in rows:
            self.assertEqual(row["catalog_snapshot_sha256"], expected)

    def test_no_clock(self):
        root, out = self.scenario()
        self.assertEqual(self.run_main(root, out)[0], 0)
        json_path, _ = self.paths(out)
        rows = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertTrue(all(r["generated_at_from_snapshot"] == GENERATED for r in rows))

    def test_unmapped_not_counted(self):
        root, out = self.scenario()
        self.assertEqual(self.run_main(root, out)[0], 0)
        json_path, _ = self.paths(out)
        rows = {r["github_name"]: r for r in json.loads(json_path.read_text(encoding="utf-8"))}
        empty = rows["empty-repo"]
        self.assertEqual(empty["registry_coverage_status"], "none")
        self.assertEqual(empty["mapped_asset_count"], 0)
        self.assertEqual(empty["unmapped_asset_count"], 0)
        self.assertEqual(empty["registry_mapping_ids_json"], "[]")
        gamma = rows["szl-datasets-override"]
        self.assertEqual(gamma["registry_coverage_status"], "full")
        self.assertEqual(json.loads(gamma["registry_mapping_ids_json"]), ["SZLHOLDINGS/DATA1"])
        self.assertEqual(gamma["mapped_asset_count"], 1)


if __name__ == "__main__":
    unittest.main()
