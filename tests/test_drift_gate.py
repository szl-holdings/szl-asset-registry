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


def make_asset_map():
    return {
        "generated": "2025-01-01T00:00:00Z",
        "stats": {},
        "coverage": {},
        "unmapped_family_counts": {},
        "assets": [
            {
                "id": "asset-ok",
                "type": "model",
                "private": False,
                "source_repo": "org/repo",
                "method": "card",
                "family": "example",
            },
            {
                "id": "asset-unpinned",
                "type": "model",
                "private": False,
                "source_repo": "org/other",
                "method": "name",
                "family": "example",
            },
        ],
    }


def make_pins(asset_id="asset-ok"):
    return {
        "generated": "2025-01-01T00:00:00Z",
        "source": "manual-review",
        "pins": {
            asset_id: {
                "source_repo": "org/repo",
                "revision_sha": "a" * 40,
                "readme_sha256": "b" * 64,
                "evidence_quote": "The model card identifies this asset.",
                "pinned_utc": "2025-01-01T00:00:00Z",
            }
        },
    }


class DriftGateTests(unittest.TestCase):
    def run_gate(self, asset_map=None, pins=None, raw_pins=None):
        if asset_map is None:
            asset_map = make_asset_map()
        if pins is None:
            pins = make_pins()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            map_path = root / "asset_map.json"
            pins_path = root / "source_pins.json"
            map_path.write_text(
                json.dumps(asset_map, sort_keys=True), encoding="utf-8"
            )
            if raw_pins is None:
                pins_path.write_text(
                    json.dumps(pins, sort_keys=True), encoding="utf-8"
                )
            else:
                pins_path.write_text(raw_pins, encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = drift_gate.main(
                    [str(map_path), str(pins_path)]
                )

        raw_verdict = stdout.getvalue()
        verdict = json.loads(raw_verdict)
        self.assertEqual(
            raw_verdict,
            json.dumps(verdict, sort_keys=True, separators=(",", ":"))
            + "\n",
        )
        return exit_code, verdict

    def assert_pin_failure(self, pins, asset_id, field):
        exit_code, verdict = self.run_gate(pins=pins)
        self.assertEqual(exit_code, 1)
        self.assertEqual(verdict["tool"], "drift_gate")
        self.assertEqual(verdict["asset_total"], 2)
        self.assertEqual(verdict["pins_total"], 1)
        self.assertEqual(verdict["pins_valid"], 0)
        self.assertTrue(
            any(
                defect["asset_id"] == asset_id
                and defect["field"] == field
                and defect["reason"]
                for defect in verdict["defects"]
            )
        )
        self.assertEqual(
            verdict["defects"],
            sorted(
                verdict["defects"],
                key=lambda item: (item["asset_id"], item["field"]),
            ),
        )
        return verdict

    def test_pass_with_unpinned_asset(self):
        exit_code, verdict = self.run_gate()
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            set(verdict),
            {
                "tool",
                "generated",
                "asset_total",
                "pins_total",
                "pins_valid",
                "defects",
            },
        )
        self.assertEqual(verdict["tool"], "drift_gate")
        self.assertTrue(verdict["generated"].endswith("Z"))
        self.assertEqual(verdict["asset_total"], 2)
        self.assertEqual(verdict["pins_total"], 1)
        self.assertEqual(verdict["pins_valid"], 1)
        self.assertEqual(verdict["defects"], [])

    def test_fail_bad_hex(self):
        for field, value in (
            ("revision_sha", "g" * 40),
            ("readme_sha256", "z" * 64),
        ):
            with self.subTest(field=field):
                pins = make_pins()
                pins["pins"]["asset-ok"][field] = value
                self.assert_pin_failure(pins, "asset-ok", field)

    def test_fail_head_revision(self):
        pins = make_pins()
        pins["pins"]["asset-ok"]["revision_sha"] = "HEAD"
        verdict = self.assert_pin_failure(
            pins, "asset-ok", "revision_sha"
        )
        self.assertIn("mutable", verdict["defects"][0]["reason"])

    def test_fail_source_mismatch(self):
        pins = make_pins()
        pins["pins"]["asset-ok"]["source_repo"] = "other/repo"
        self.assert_pin_failure(pins, "asset-ok", "source_repo")

    def test_fail_empty_quote(self):
        pins = make_pins()
        pins["pins"]["asset-ok"]["evidence_quote"] = ""
        self.assert_pin_failure(pins, "asset-ok", "evidence_quote")

    def test_fail_unknown_asset_id(self):
        self.assert_pin_failure(
            make_pins(asset_id="unknown-asset"),
            "unknown-asset",
            "asset_id",
        )

    def test_fail_missing_pin_field(self):
        pins = make_pins()
        del pins["pins"]["asset-ok"]["evidence_quote"]
        verdict = self.assert_pin_failure(
            pins, "asset-ok", "evidence_quote"
        )
        self.assertEqual(
            verdict["defects"][0]["reason"], "missing required field"
        )

    def test_fail_malformed_json(self):
        exit_code, verdict = self.run_gate(raw_pins="{")
        self.assertEqual(exit_code, 1)
        self.assertEqual(verdict["pins_valid"], 0)
        self.assertEqual(
            verdict["defects"],
            [
                {
                    "asset_id": "",
                    "field": "source_pins",
                    "reason": "malformed JSON",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
