import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "drift_gate.py"
SPEC = importlib.util.spec_from_file_location("drift_gate", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {TOOL_PATH}")
drift_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drift_gate)

REAL_MAP = REPO_ROOT / "asset_map.json"
REAL_PINS = REPO_ROOT / "data" / "source_pins.json"
A40 = "a" * 40
B64 = "b" * 64


def make_asset_map():
    """Seven assets including a legal cross-type twin pair sharing one id.

    Identity model mirrors the real map: twin ids collide only across
    Hub types, never within (id, type).
    """
    return {
        "generated": "2026-01-01T00:00:00Z",
        "stats": {},
        "coverage": {},
        "unmapped_family_counts": {},
        "assets": [
            {"id": "org/asset-ok", "type": "models", "private": False,
             "source_repo": "org/ok-repo", "method": "name", "family": "example"},
            {"id": "org/asset-unpinned", "type": "models", "private": False,
             "source_repo": "org/other-repo", "method": "name", "family": "example"},
            {"id": "org/twin", "type": "models", "private": False,
             "source_repo": "org/twin-models", "method": "card", "family": "example"},
            {"id": "org/twin", "type": "datasets", "private": False,
             "source_repo": "org/twin-datasets", "method": "name", "family": "example"},
            {"id": "org/asset-card", "type": "datasets", "private": False,
             "source_repo": "org/cardrepo", "method": "card", "family": "example"},
            {"id": "org/asset-override", "type": "models", "private": False,
             "source_repo": "org/ovrepo", "method": "override", "family": "example"},
            {"id": "org/asset-unmapped", "type": "spaces", "private": False,
             "source_repo": None, "method": "unmapped", "family": "example"},
        ],
    }


def pin(source_repo):
    return {
        "source_repo": source_repo,
        "revision_sha": A40,
        "readme_sha256": B64,
        "evidence_quote": "measured at fetch time",
        "pinned_utc": "2026-01-01T00:00:00Z",
    }


class DriftGateTests(unittest.TestCase):
    """Consult v480 test vectors (Kimi e3f63149..., Mistral c12bd881...)."""

    def run_gate(self, asset_map=None, pins=None, raw_pins=None,
                 pins_absent=False, pin_transform=None):
        if asset_map is None:
            asset_map = make_asset_map()
        if pins is None:
            pins = self.base_pins_doc()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            map_path = root / "asset_map.json"
            pins_path = root / "source_pins.json"
            map_path.write_text(
                json.dumps(asset_map, sort_keys=True), encoding="utf-8"
            )
            if raw_pins is None:
                if pin_transform is not None:
                    pin_transform(pins)
                pins_path.write_text(
                    json.dumps(pins, sort_keys=True), encoding="utf-8"
                )
            else:
                pins_path.write_text(raw_pins, encoding="utf-8")
            if pins_absent:
                pins_path.unlink()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = drift_gate.main([str(map_path), str(pins_path)])

        raw_verdict = stdout.getvalue()
        verdict = json.loads(raw_verdict)
        self.assertEqual(
            raw_verdict,
            json.dumps(verdict, sort_keys=True, separators=(",", ":")) + "\n",
        )
        self.assertEqual(verdict["tool"], "drift_gate")
        for defect in verdict["defects"]:
            self.assertIsInstance(defect["asset_id"], str)
            self.assertIsInstance(defect["field"], str)
            self.assertIsInstance(defect["reason"], str)
        self.assertEqual(
            verdict["defects"],
            sorted(
                verdict["defects"],
                key=lambda item: (
                    item["asset_id"],
                    item["field"],
                    drift_gate.REASON_RANK.get(
                        item["reason"], len(drift_gate.REASON_RANK)
                    ),
                ),
            ),
        )
        return exit_code, verdict

    def base_pins_doc(self):
        return {
            "generated": "2026-01-01T00:00:00Z",
            "pins_seed_batch": 1,
            "pins": {"models/org/asset-ok": pin("org/ok-repo")},
            "backlog": [
                {"key": "models/org/asset-unpinned", "reason": "no_hub_readme"},
                {"key": "models/org/twin", "reason": "card_method_deferred"},
                {"key": "datasets/org/twin", "reason": "no_hub_readme"},
                {"key": "datasets/org/asset-card", "reason": "card_method_deferred"},
                {"key": "models/org/asset-override", "reason": "override_method_deferred"},
                {"key": "spaces/org/asset-unmapped", "reason": "unmapped_method_deferred"},
            ],
            "backlog_total": 6,
        }

    def assert_has_defect(self, verdict, asset_id, field, reason):
        self.assertTrue(
            any(
                defect["asset_id"] == asset_id
                and defect["field"] == field
                and defect["reason"] == reason
                for defect in verdict["defects"]
            ),
            f"expected defect {asset_id}/{field}/{reason} in "
            f"{verdict['defects']}",
        )

    # ---------------------------------------------------------- accounting

    def test_base_accounting_pass(self):
        exit_code, verdict = self.run_gate()
        self.assertEqual(exit_code, 0)
        self.assertEqual(verdict["asset_total"], 7)
        self.assertEqual(verdict["pins_total"], 1)
        self.assertEqual(verdict["pins_valid"], 1)
        self.assertEqual(verdict["backlog_total"], 6)
        self.assertEqual(verdict["pins_seed_batch"], 1)
        self.assertEqual(verdict["defects"], [])

    def test_missing_backlog_entry(self):
        def drop_asset_unpinned(pins):
            pins["backlog"] = [
                item for item in pins["backlog"]
                if item["key"] != "models/org/asset-unpinned"
            ]
        exit_code, verdict = self.run_gate(pin_transform=drop_asset_unpinned)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "models/org/asset-unpinned", "backlog",
            "missing_backlog_entry",
        )

    def test_backlog_key_invalid(self):
        def corrupt(pins):
            for item in pins["backlog"]:
                if item["key"] == "models/org/asset-unpinned":
                    item["key"] = "not-a-composite-key"
        exit_code, verdict = self.run_gate(pin_transform=corrupt)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "not-a-composite-key", "backlog", "backlog_key_invalid",
        )

    def test_backlog_asset_unknown(self):
        def corrupt(pins):
            for item in pins["backlog"]:
                if item["key"] == "models/org/asset-unpinned":
                    item["key"] = "models/org/ghost"
        exit_code, verdict = self.run_gate(pin_transform=corrupt)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "models/org/ghost", "backlog", "backlog_asset_unknown",
        )

    def test_backlog_reason_invalid(self):
        def corrupt(pins):
            for item in pins["backlog"]:
                if item["key"] == "models/org/asset-unpinned":
                    item["reason"] = "because-i-say-so"
        exit_code, verdict = self.run_gate(pin_transform=corrupt)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "models/org/asset-unpinned", "backlog",
            "backlog_reason_invalid",
        )

    def test_backlog_entry_conflicts_pin(self):
        def conflict(pins):
            pins["backlog"].append(
                {"key": "models/org/asset-ok", "reason": "card_method_deferred"}
            )
        exit_code, verdict = self.run_gate(pin_transform=conflict)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "models/org/asset-ok", "backlog",
            "backlog_entry_conflicts_pin",
        )

    # ------------------------------------------------------------ keying

    def test_all_type_prefixes_parse(self):
        def add(pins):
            pins["pins"]["datasets/org/asset-card"] = pin("org/cardrepo")
            pins["backlog"] = [
                item for item in pins["backlog"]
                if item["key"] != "datasets/org/asset-card"
            ]
        exit_code, verdict = self.run_gate(pin_transform=add)
        self.assertEqual(exit_code, 0)
        self.assertEqual(verdict["pins_valid"], 2)

    def test_bare_id_key_rejected(self):
        def add(pins):
            pins["pins"].pop("models/org/asset-ok")
            pins["pins"]["org/asset-ok"] = pin("org/ok-repo")
        exit_code, verdict = self.run_gate(pin_transform=add)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "org/asset-ok", "asset_id", "pin_key_bare_id",
        )
        # the failed pin leaves a missing accounting entry, fail-closed
        self.assert_has_defect(
            verdict, "models/org/asset-ok", "backlog", "missing_backlog_entry",
        )

    def test_bad_type_prefix(self):
        for bad in ("model/org/asset-ok", "Models/org/asset-ok",
                    "modelsx/org/asset-ok"):
            with self.subTest(bad=bad):
                def add(pins, bad=bad):
                    key = pins["pins"].pop("models/org/asset-ok")
                    pins["pins"][bad] = key
                exit_code, verdict = self.run_gate(pin_transform=add)
                self.assertEqual(exit_code, 1)
                self.assert_has_defect(
                    verdict, bad, "asset_id", "pin_key_type_prefix_invalid",
                )

    def test_bad_depth_and_segments(self):
        for bad in ("models/a/b/c", "models//org", "models/org/",
                    "models/org/asset-ok\n", "asset-ok",
                    "models/örjan/asset-ok"):
            with self.subTest(bad=repr(bad)):
                def add(pins, bad=bad):
                    key = pins["pins"].pop("models/org/asset-ok")
                    pins["pins"][bad] = key
                exit_code, verdict = self.run_gate(pin_transform=add)
                self.assertEqual(exit_code, 1)
                self.assert_has_defect(
                    verdict, bad, "asset_id", "composite_pin_key_malformed",
                )

    # -------------------------------------------------------- resolution

    def test_wrong_twin_mismatch_sibling_stays_valid(self):
        def add(pins):
            pins["pins"]["datasets/org/twin"] = pin("org/twin-models")
            for item in list(pins["backlog"]):
                if item["key"] == "datasets/org/twin":
                    pins["backlog"].remove(item)
        exit_code, verdict = self.run_gate(pin_transform=add)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "datasets/org/twin", "source_repo", "source_repo_mismatch",
        )
        # the models twin must stay defect-free and properly accounted
        # through its own backlog entry: indexing is per (id, type),
        # never by bare id
        self.assertFalse(
            any("models/org/twin" in str(defect) for defect in verdict["defects"])
        )

    def test_dual_twins_both_pinnable(self):
        def add(pins):
            pins["pins"]["models/org/twin"] = pin("org/twin-models")
            pins["pins"]["datasets/org/twin"] = pin("org/twin-datasets")
            pins["backlog"] = [
                item for item in pins["backlog"]
                if item["key"] not in ("models/org/twin", "datasets/org/twin")
            ]
        exit_code, verdict = self.run_gate(pin_transform=add)
        self.assertEqual(exit_code, 0)
        self.assertEqual(verdict["pins_total"], 3)
        self.assertEqual(verdict["pins_valid"], 3)
        self.assertEqual(verdict["defects"], [])

    def test_unknown_asset(self):
        def add(pins):
            key = pins["pins"].pop("models/org/asset-ok")
            pins["pins"]["models/org/ghost"] = key
        exit_code, verdict = self.run_gate(pin_transform=add)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "models/org/ghost", "asset_id", "pin_asset_unknown",
        )

    def test_unmapped_method_asset_pin(self):
        def add(pins):
            pins["pins"]["spaces/org/asset-unmapped"] = pin("org/whatever")
            pins["backlog"] = [
                item for item in pins["backlog"]
                if item["key"] != "spaces/org/asset-unmapped"
            ]
        exit_code, verdict = self.run_gate(pin_transform=add)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "spaces/org/asset-unmapped", "asset_id",
            "pin_asset_unmapped_method",
        )

    def test_other_method_asset_pin(self):
        asset_map = make_asset_map()
        asset_map["assets"][6]["method"] = "weird-method"
        def add(pins):
            pins["pins"]["spaces/org/asset-unmapped"] = pin("org/whatever")
            pins["backlog"] = [
                item for item in pins["backlog"]
                if item["key"] != "spaces/org/asset-unmapped"
            ]
        exit_code, verdict = self.run_gate(
            asset_map=asset_map, pin_transform=add
        )
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "spaces/org/asset-unmapped", "asset_id",
            "pin_asset_unmapped",
        )

    # ------------------------------------------------------- entry shape

    def test_pin_not_object(self):
        def add(pins):
            pins["pins"]["models/org/asset-ok"] = "not-an-object"
        exit_code, verdict = self.run_gate(pin_transform=add)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "models/org/asset-ok", "pin", "pin_not_object",
        )

    def test_duplicate_pin_key_in_file(self):
        first = json.dumps(pin("org/ok-repo"), sort_keys=True)
        second = json.dumps(pin("org/ok-repo"), sort_keys=True)
        raw = (
            '{"generated":"2026-01-01T00:00:00Z","pins":{'
            f'"models/org/asset-ok":{first},"models/org/asset-ok":{second}'
            '},"backlog":['
            '{"key":"models/org/asset-unpinned","reason":"no_hub_readme"},'
            '{"key":"models/org/twin","reason":"card_method_deferred"},'
            '{"key":"datasets/org/twin","reason":"no_hub_readme"},'
            '{"key":"datasets/org/asset-card","reason":"card_method_deferred"},'
            '{"key":"models/org/asset-override","reason":"override_method_deferred"},'
            '{"key":"spaces/org/asset-unmapped","reason":"unmapped_method_deferred"}'
            '],"backlog_total":6}'
        )
        exit_code, verdict = self.run_gate(raw_pins=raw)
        self.assertEqual(exit_code, 1)
        self.assertTrue(
            any(
                defect["reason"] == "duplicate_pin_key"
                for defect in verdict["defects"]
            )
        )

    def test_pins_not_object(self):
        def add(pins):
            pins["pins"] = "not-an-object"
        exit_code, verdict = self.run_gate(pin_transform=add)
        self.assertEqual(exit_code, 2)

    # ----------------------------------------------------- JSON/file edge

    def test_nan_constant_rejected(self):
        exit_code, verdict = self.run_gate(
            raw_pins='{"pins": {"models/org/asset-ok": NaN}}'
        )
        self.assertEqual(exit_code, 2)
        self.assertEqual(verdict["pins_total"], 0)

    def test_infinity_constant_rejected(self):
        exit_code, verdict = self.run_gate(
            raw_pins='{"pins": {"models/org/asset-ok": Infinity}}'
        )
        self.assertEqual(exit_code, 2)

    def test_malformed_json(self):
        exit_code, verdict = self.run_gate(raw_pins="{")
        self.assertEqual(exit_code, 2)
        self.assertEqual(
            verdict["defects"][0]["field"], "source_pins"
        )

    def test_oversize_input(self):
        exit_code, verdict = self.run_gate(
            raw_pins='{"padding":"' + "x" * (5 * 1024 * 1024) + '"}'
        )
        self.assertEqual(exit_code, 2)

    def test_deep_nesting_input_error(self):
        exit_code, verdict = self.run_gate(
            raw_pins="[" * 5000 + "]" * 5000
        )
        self.assertEqual(exit_code, 2)

    # -------------------------------------------------------------- map

    def test_map_duplicate_identity(self):
        asset_map = make_asset_map()
        asset_map["assets"].append(dict(asset_map["assets"][0]))
        exit_code, verdict = self.run_gate(asset_map=asset_map)
        self.assertEqual(exit_code, 1)
        self.assertIn(
            "duplicate_id_type_pair",
            [defect["reason"] for defect in verdict["defects"]],
        )

    def test_map_structural_error(self):
        asset_map = make_asset_map()
        asset_map["assets"][0]["type"] = "bogus"
        exit_code, verdict = self.run_gate(asset_map=asset_map)
        self.assertEqual(exit_code, 2)

    # ------------------------------------------------------------ fields

    def test_field_missing_required(self):
        def add(pins):
            del pins["pins"]["models/org/asset-ok"]["evidence_quote"]
        exit_code, verdict = self.run_gate(pin_transform=add)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "models/org/asset-ok", "evidence_quote",
            "missing_required_field",
        )

    def test_field_revision_sha(self):
        for value, reason in (
            ("g" * 40, "revision_sha_invalid"),
            ("a" * 39, "revision_sha_invalid"),
            ("a" * 41, "revision_sha_invalid"),
            ("A" * 40, "revision_sha_invalid"),
            ("HEAD", "revision_sha_mutable_ref"),
            ("main", "revision_sha_mutable_ref"),
            ("master", "revision_sha_mutable_ref"),
        ):
            with self.subTest(value=value):
                def add(pins, value=value):
                    pins["pins"]["models/org/asset-ok"]["revision_sha"] = value
                exit_code, verdict = self.run_gate(pin_transform=add)
                self.assertEqual(exit_code, 1)
                self.assert_has_defect(
                    verdict, "models/org/asset-ok", "revision_sha", reason,
                )

    def test_field_readme_sha(self):
        for length in (63, 65):
            with self.subTest(length=length):
                def add(pins, length=length):
                    pins["pins"]["models/org/asset-ok"]["readme_sha256"] = "z" * length
                exit_code, verdict = self.run_gate(pin_transform=add)
                self.assertEqual(exit_code, 1)
                self.assert_has_defect(
                    verdict, "models/org/asset-ok", "readme_sha256",
                    "readme_sha256_invalid",
                )

    def test_field_evidence_quote(self):
        for value in ("", "   ", "\n"):
            with self.subTest(value=repr(value)):
                def add(pins, value=value):
                    pins["pins"]["models/org/asset-ok"]["evidence_quote"] = value
                exit_code, verdict = self.run_gate(pin_transform=add)
                self.assertEqual(exit_code, 1)
                self.assert_has_defect(
                    verdict, "models/org/asset-ok", "evidence_quote",
                    "evidence_quote_empty",
                )

    def test_field_pinned_utc(self):
        for value in ("yesterday", "2026-01-01 00:00:00Z",
                      "2026-01-01T00:00:00+01:00"):
            with self.subTest(value=value):
                def add(pins, value=value):
                    pins["pins"]["models/org/asset-ok"]["pinned_utc"] = value
                exit_code, verdict = self.run_gate(pin_transform=add)
                self.assertEqual(exit_code, 1)
                self.assert_has_defect(
                    verdict, "models/org/asset-ok", "pinned_utc",
                    "pinned_utc_invalid",
                )

    def test_field_source_repo_mismatch(self):
        def add(pins):
            pins["pins"]["models/org/asset-ok"]["source_repo"] = "org/not-it"
        exit_code, verdict = self.run_gate(pin_transform=add)
        self.assertEqual(exit_code, 1)
        self.assert_has_defect(
            verdict, "models/org/asset-ok", "source_repo", "source_repo_mismatch",
        )

    # ------------------------------------------------------- exit states

    def test_absent_pins_file_green_zero_pin_verdict(self):
        exit_code, verdict = self.run_gate(pins_absent=True)
        self.assertEqual(exit_code, 0)
        self.assertEqual(verdict["asset_total"], 7)
        self.assertEqual(verdict["pins_total"], 0)
        self.assertEqual(verdict["pins_valid"], 0)
        self.assertEqual(verdict["backlog_total"], 0)
        self.assertEqual(verdict["backlog"], [])
        self.assertEqual(verdict["defects"], [])

    def test_empty_pins_full_accounting_defects(self):
        exit_code, verdict = self.run_gate(
            pins={"generated": "2026-01-01T00:00:00Z", "pins": {},
                  "backlog": [], "backlog_total": 0}
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(
            sorted(
                defect["asset_id"] for defect in verdict["defects"]
            ),
            sorted(
                f"{asset['type']}/{asset['id']}"
                for asset in make_asset_map()["assets"]
            ),
        )

    def test_verdict_deterministic(self):
        first = self.run_gate()
        second = self.run_gate()
        self.assertEqual(first[1]["defects"], second[1]["defects"])
        self.assertEqual(first[1]["backlog"], second[1]["backlog"])
        self.assertEqual(first[1]["pins_valid"], second[1]["pins_valid"])

    # ------------------------------------------------- real map vectors

    def test_real_map_and_seed_green(self):
        if not REAL_PINS.exists():
            self.skipTest("real seed not present yet")
        exit_code, verdict = self.run_gate_real()
        self.assertEqual(exit_code, 0)
        self.assertEqual(verdict["asset_total"], 666)
        self.assertEqual(verdict["pins_total"], 42)
        self.assertEqual(verdict["pins_valid"], 42)
        self.assertEqual(verdict["backlog_total"], 624)
        self.assertEqual(verdict["defects"], [])

    def test_real_map_all_six_twin_keys_pinnable(self):
        """Kimi vector 16: all three real twin pairs pin independently."""
        if not REAL_PINS.exists():
            self.skipTest("real seed not present yet")
        assets = json.loads(REAL_MAP.read_text(encoding="utf-8"))["assets"]
        by_identity = {
            (asset["type"], asset["id"]): asset for asset in assets
        }
        doc = json.loads(REAL_PINS.read_text(encoding="utf-8"))
        twin_keys = [
            "models/SZLHOLDINGS/SZLHOLDINGS",
            "datasets/SZLHOLDINGS/SZLHOLDINGS",
            "models/SZLHOLDINGS/szl-khipu",
            "spaces/SZLHOLDINGS/szl-khipu",
            "datasets/SZLHOLDINGS/governed-agent-bench",
            "spaces/SZLHOLDINGS/governed-agent-bench",
        ]
        for key in twin_keys:
            type_prefix, asset_id = key.split("/", 1)
            asset = by_identity[(type_prefix, asset_id)]
            self.assertIn(asset["method"], {"name", "card", "override"})
            doc["pins"][key] = {
                "source_repo": asset["source_repo"],
                "revision_sha": A40,
                "readme_sha256": B64,
                "evidence_quote": "measured at fetch time",
                "pinned_utc": "2026-01-01T00:00:00Z",
            }
            doc["backlog"] = [
                item for item in doc["backlog"] if item["key"] != key
            ]
            doc["backlog_total"] = len(doc["backlog"])
        exit_code, verdict = self.run_gate_real(doc)
        self.assertEqual(exit_code, 0)
        for key in twin_keys:
            self.assertIn(key, doc["pins"])
        expected_total = len(doc["pins"])
        self.assertEqual(verdict["pins_total"], expected_total)
        self.assertEqual(verdict["pins_valid"], expected_total)
        self.assertEqual(verdict["defects"], [])

    def run_gate_real(self, doc=None):
        if doc is None:
            doc = json.loads(REAL_PINS.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            pins_path = Path(directory) / "source_pins.json"
            pins_path.write_text(
                json.dumps(doc, sort_keys=True), encoding="utf-8"
            )
            return drift_gate.evaluate(REAL_MAP, pins_path)


if __name__ == "__main__":
    unittest.main()
