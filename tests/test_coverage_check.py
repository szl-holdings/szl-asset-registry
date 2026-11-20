import copy
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

import coverage_check  # noqa: E402

REAL_ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "asset_map": "asset_map.json",
    "census": "data/hf_census_20261120.json",
    "audit": "data/gh_org_audit_20261120.json",
    "unresolved": "data/unresolved_assets.json",
    "reasons": "data/asset_map_unmapped_reasons_20261120.json",
    "overrides": "overrides.json",
}
REAL_OK = all((REAL_ROOT / rel).is_file() for rel in FILES.values())


def make_registry(root):
    root = Path(root)
    (root / "data").mkdir(parents=True)
    census = {
        "models": [
            {"id": "SZLHOLDINGS/MODELA", "lastModified": "2026-11-19T00:00:00.000Z", "private": False},
            {"id": "SZLHOLDINGS/MODELB", "lastModified": "2026-11-19T00:00:00.000Z", "private": True},
        ],
        "datasets": [
            {"id": "SZLHOLDINGS/DATA1", "lastModified": "2026-11-19T00:00:00.000Z", "private": False},
        ],
        "spaces": [
            {"id": "SZLHOLDINGS/SPACE1", "lastModified": "2026-11-19T00:00:00.000Z", "private": False},
        ],
    }
    assets = [
        {"family": "corpus-benchmark", "id": "SZLHOLDINGS/MODELA", "method": "card", "private": False, "source_repo": "szl-models-a", "type": "models"},
        {"family": "corpus-benchmark", "id": "SZLHOLDINGS/MODELB", "method": "name", "private": True, "source_repo": "szl-models-b", "type": "models"},
        {"family": "marketing-surface", "id": "SZLHOLDINGS/DATA1", "method": "override", "private": False, "source_repo": "szl-datasets-override", "type": "datasets"},
        {"family": "other", "id": "SZLHOLDINGS/SPACE1", "method": "name", "private": False, "source_repo": "szl-spaces-a", "type": "spaces"},
    ]
    asset_map = {
        "assets": assets,
        "coverage": {"total": 4, "mapped": 4, "unmapped": 0},
        "generated": "2026-11-20",
        "stats": {"card": 1, "name": 2, "override": 1, "unmapped": 0},
        "unmapped_family_counts": {},
    }
    audit = [
        {
            "isArchived": False,
            "name": name,
            "pushedAt": "2026-11-19T00:00:00.000Z",
            "updatedAt": "2026-11-19T00:00:00.000Z",
            "visibility": "PRIVATE" if name == "szl-models-b" else "PUBLIC",
        }
        for name in ("szl-models-a", "szl-models-b", "szl-datasets-override", "szl-spaces-a")
    ]
    unresolved = {
        "generated": "2026-11-20",
        "policy": "fail-closed: every unmapped asset must carry a reason",
        "unresolved": [],
    }
    reasons = {
        "_comment": "fixture",
        "_contract": "fixture",
        "class": "fixture",
        "generated_utc": "2026-11-20T00:00:00.000Z",
        "reasons": {},
        "sweep_counts": {},
    }
    overrides = {
        "_comment": "fixture",
        "SZLHOLDINGS/DATA1": "szl-datasets-override",
        "_evidence": {"SZLHOLDINGS/DATA1": "manual override evidence"},
    }
    payload = {
        "asset_map": asset_map,
        "census": census,
        "audit": audit,
        "unresolved": unresolved,
        "reasons": reasons,
        "overrides": overrides,
    }
    for key, relpath in FILES.items():
        (root / relpath).write_text(json.dumps(payload[key], indent=2), encoding="utf-8")
    return root


def mutate(root, key, fn):
    path = root / FILES[key]
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class CoverageCheckTest(unittest.TestCase):
    def fresh(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return make_registry(Path(tmp.name))

    def captured_main(self, root):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = coverage_check.main([str(root)])
        return rc, json.loads(buf.getvalue().strip())

    def assert_code(self, root, code):
        violations = coverage_check.collect_violations(root)
        self.assertTrue(
            any(v == code or v.startswith(code + " ") for v in violations),
            (code, violations),
        )
        rc, _ = self.captured_main(root)
        self.assertEqual(rc, 1)

    def test_clean_registry(self):
        root = self.fresh()
        self.assertEqual(coverage_check.collect_violations(root), [])
        rc, payload = self.captured_main(root)
        self.assertEqual(rc, 0)
        self.assertEqual(payload["schema"], "szl.coverage/v1")
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["violations"], [])
        self.assertEqual(payload["counts"]["total"], 4)
        self.assertEqual(payload["counts"]["mapped"], 4)
        self.assertEqual(payload["counts"]["unmapped"], 0)

    @unittest.skipUnless(REAL_OK, "real registry snapshots not present")
    def test_real_registry(self):
        self.assertEqual(coverage_check.collect_violations(REAL_ROOT), [])
        asset_map = json.loads((REAL_ROOT / FILES["asset_map"]).read_text(encoding="utf-8"))
        self.assertEqual(asset_map["coverage"], {"total": 666, "mapped": 648, "unmapped": 18})
        methods = [row["method"] for row in asset_map["assets"]]
        self.assertEqual(len(methods), 666)
        self.assertEqual(sum(1 for m in methods if m in ("name", "card", "override")), 648)
        self.assertEqual(sum(1 for m in methods if m == "unmapped"), 18)
        unresolved = json.loads((REAL_ROOT / FILES["unresolved"]).read_text(encoding="utf-8"))
        self.assertEqual(len(unresolved["unresolved"]), 10)
        rc, payload = self.captured_main(REAL_ROOT)
        self.assertEqual(rc, 0)
        self.assertEqual(payload["reconciliation"]["unresolved_inside_unmapped"], 10)
        self.assertEqual(payload["reconciliation"]["unmapped_without_reason"], 0)

    def test_cov002_coverage_count_mismatch(self):
        root = self.fresh()
        mutate(root, "asset_map", lambda m: m["coverage"].update(total=5))
        self.assert_code(root, "COV002_COVERAGE_COUNT_MISMATCH")

    def test_cov003_census_row_mismatch(self):
        root = self.fresh()
        mutate(root, "census", lambda c: c["models"].pop())
        self.assert_code(root, "COV003_CENSUS_ROW_MISMATCH")

    def test_cov004_row_field_invalid(self):
        root = self.fresh()
        mutate(root, "asset_map", lambda m: m["assets"][0].update(private="no"))
        self.assert_code(root, "COV004_ROW_FIELD_INVALID")

    def test_cov005_duplicate_asset_key(self):
        root = self.fresh()
        mutate(root, "asset_map", lambda m: m["assets"].append(copy.deepcopy(m["assets"][0])))
        self.assert_code(root, "COV005_DUPLICATE_ASSET_ID")

    def test_cov006_stats_mismatch(self):
        root = self.fresh()
        mutate(root, "asset_map", lambda m: m["stats"].update(card=99))
        self.assert_code(root, "COV006_STATS_MISMATCH")

    def test_cov007_family_count_mismatch(self):
        root = self.fresh()
        mutate(root, "asset_map", lambda m: m.update(unmapped_family_counts={"other": 1}))
        self.assert_code(root, "COV007_FAMILY_COUNT_MISMATCH")

    def test_cov008_unresolved_not_in_unmapped(self):
        root = self.fresh()
        record = {"id": "SZLHOLDINGS/MODELA", "quotes": ["quote"], "reason": "mapped row", "type": "models", "urls": []}
        mutate(root, "unresolved", lambda u: u["unresolved"].append(record))
        self.assert_code(root, "COV008_UNRESOLVED_NOT_IN_UNMAPPED")

    def test_cov009_unmapped_reason_missing(self):
        root = self.fresh()
        row = {"family": "other", "id": "SZLHOLDINGS/UNMAPPED1", "method": "unmapped", "private": True, "source_repo": None, "type": "models"}
        mutate(root, "asset_map", lambda m: m["assets"].append(row))
        self.assert_code(root, "COV009_UNMAPPED_REASON_MISSING")

    def test_cov010_override_contract(self):
        root = self.fresh()
        mutate(root, "overrides", lambda o: o.update({"SZLHOLDINGS/DATA1": "szl-wrong-repo"}))
        self.assert_code(root, "COV010_OVERRIDE_CONTRACT")

    def test_cov011_override_evidence_missing(self):
        root = self.fresh()
        mutate(root, "overrides", lambda o: o.update(_evidence={}))
        self.assert_code(root, "COV011_OVERRIDE_EVIDENCE_MISSING")

    def test_cov013_source_repo_not_in_audit(self):
        root = self.fresh()
        mutate(root, "audit", lambda a: a.pop(0))
        self.assert_code(root, "COV013_SOURCE_REPO_NOT_IN_AUDIT")

    def test_input_error_missing_file(self):
        root = self.fresh()
        (root / FILES["census"]).unlink()
        rc, payload = self.captured_main(root)
        self.assertEqual(rc, 2)
        self.assertFalse(payload["clean"])
        self.assertEqual(payload["violations"], [])
        self.assertIn("hf_census_20261120.json", payload["error"])

    def test_input_error_malformed(self):
        root = self.fresh()
        (root / FILES["census"]).write_bytes(b"{oops")
        rc, payload = self.captured_main(root)
        self.assertEqual(rc, 2)
        self.assertFalse(payload["clean"])
        self.assertIn("invalid JSON", payload["error"])

    def test_determinism(self):
        root = self.fresh()
        first = coverage_check.collect_violations(root)
        self.assertEqual(first, coverage_check.collect_violations(root))
        mutate(root, "asset_map", lambda m: m["coverage"].update(total=99))
        mutated_a = coverage_check.collect_violations(root)
        mutated_b = coverage_check.collect_violations(root)
        self.assertEqual(mutated_a, mutated_b)
        self.assertTrue(mutated_a)


if __name__ == "__main__":
    unittest.main()
