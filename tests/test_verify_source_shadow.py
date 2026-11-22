"""Offline synthetic controls for SZL asset-map shadow readback (no provider calls)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.verify_source_shadow import ShadowHold, verify_source_shadow


def encode(obj):
    return json.dumps(obj, sort_keys=True).encode("utf-8")


def fixture():
    entries = [
        {
            "id": "SZLHOLDINGS/synthetic-a",
            "type": "models",
            "private": False,
            "method": "card",
            "source_repo": "estate-cards",
            "family": "other",
        }
    ]
    source = {
        "generated": "synthetic",
        "assets": entries,
        "stats": {"card": 1, "name": 0, "override": 0, "unmapped": 0},
        "coverage": {"total": 1, "mapped": 1, "unmapped": 0},
        "unmapped_family_counts": {},
    }
    raw = encode(source)
    shadow = {
        "schema": "szl.source-binding-shadow/v1",
        "receipt_signature": "UNSIGNED_LOCAL",
        "source_map_sha256": hashlib.sha256(raw).hexdigest(),
        "semantics": "source hints are NOT verified producing-source attestations",
        "coverage": {
            "total": 1,
            "legacy_mapped_hints": 1,
            "unmapped_without_hint": 0,
            "producer_proven_by_input": 0,
            "showcase_link_hints": 1,
        },
        "method_counts": {"card": 1},
        "reason_counts": {"SHOWCASE_LINK_NOT_PRODUCER_PROOF": 1},
        "assets": [
            {
                "id": "SZLHOLDINGS/synthetic-a",
                "type": "models",
                "legacy_method": "card",
                "legacy_source_hint": "estate-cards",
                "producer_proof_state": "NOT_ESTABLISHED",
                "reason": "SHOWCASE_LINK_NOT_PRODUCER_PROOF",
            }
        ],
    }
    return raw, shadow


class ShadowReadbackTests(unittest.TestCase):
    def test_exact_byte_bound_shadow_stays_unqualified(self):
        raw, shadow = fixture()
        result = verify_source_shadow(raw, encode(shadow))
        self.assertEqual(result["state"], "BYTE_BOUND_SHADOW_ONLY")
        for field in (
            "producer_verified",
            "signature_verified",
            "training_verified",
            "quality_verified",
            "runtime_verified",
        ):
            self.assertIs(result[field], False)

    def test_whitespace_byte_change_refuses(self):
        raw, shadow = fixture()
        with self.assertRaisesRegex(ShadowHold, "SOURCE_MAP_BYTE_DIGEST_MISMATCH"):
            verify_source_shadow(raw + b" ", encode(shadow))

    def test_replaced_asset_id_refuses(self):
        raw, shadow = fixture()
        shadow["assets"][0]["id"] = "SZLHOLDINGS/synthetic-b"
        with self.assertRaisesRegex(ShadowHold, "SHADOW_ASSET_CONTENT"):
            verify_source_shadow(raw, encode(shadow))

    def test_reordered_or_extra_source_refuses_hash(self):
        raw, shadow = fixture()
        source = json.loads(raw)
        source["assets"].append(source["assets"][0].copy())
        with self.assertRaisesRegex(ShadowHold, "SOURCE_MAP_BYTE"):
            verify_source_shadow(encode(source), encode(shadow))

    def test_duplicate_asset_id_refuses_even_with_matching_hash(self):
        raw, shadow = fixture()
        source = json.loads(raw)
        source["assets"].append(source["assets"][0].copy())
        source["coverage"]["total"] = 2
        source["coverage"]["mapped"] = 2
        source["stats"]["card"] = 2
        shadow["assets"].append(shadow["assets"][0].copy())
        shadow["coverage"]["total"] = 2
        shadow["coverage"]["legacy_mapped_hints"] = 2
        shadow["method_counts"]["card"] = 2
        shadow["reason_counts"]["SHOWCASE_LINK_NOT_PRODUCER_PROOF"] = 2
        shadow["coverage"]["showcase_link_hints"] = 2
        new_raw = encode(source)
        shadow["source_map_sha256"] = hashlib.sha256(new_raw).hexdigest()
        with self.assertRaisesRegex(ShadowHold, "DUPLICATE_ASSET_ID"):
            verify_source_shadow(new_raw, encode(shadow))

    def test_claimed_source_proof_refuses(self):
        raw, shadow = fixture()
        shadow["assets"][0]["producer_proof_state"] = "SOURCE_BOUND"
        with self.assertRaisesRegex(ShadowHold, "UNATTESTED_PRODUCER"):
            verify_source_shadow(raw, encode(shadow))

    def test_extra_source_provenance_field_refuses(self):
        raw, shadow = fixture()
        src = json.loads(raw)
        src["assets"][0]["producer_verified"] = True
        changed = encode(src)
        shadow["source_map_sha256"] = hashlib.sha256(changed).hexdigest()
        with self.assertRaisesRegex(ShadowHold, "UNREVIEWED_FIELDS"):
            verify_source_shadow(changed, encode(shadow))

    def test_shadow_fake_signature_refuses(self):
        raw, shadow = fixture()
        shadow["receipt_signature"] = "VERIFIED_SIGNATURE"
        with self.assertRaisesRegex(ShadowHold, "UNSUPPORTED_SIGNATURE"):
            verify_source_shadow(raw, encode(shadow))

    def test_shadow_extra_auth_field_refuses(self):
        raw, shadow = fixture()
        shadow["assets"][0]["production_ready"] = True
        with self.assertRaisesRegex(ShadowHold, "UNREVIEWED_FIELDS"):
            verify_source_shadow(raw, encode(shadow))

    def test_duplicate_nested_json_key_refuses(self):
        raw, _ = fixture()
        with self.assertRaisesRegex(ShadowHold, "DUPLICATE_JSON_KEY"):
            verify_source_shadow(raw, b'{"schema":1,"schema":2}')

    def test_nan_refuses(self):
        raw, shadow = fixture()
        bad = encode(shadow).replace(
            b'"showcase_link_hints": 1', b'"showcase_link_hints": NaN'
        )
        with self.assertRaisesRegex(ShadowHold, "NONFINITE_JSON"):
            verify_source_shadow(raw, bad)

    def test_bool_as_integer_refuses(self):
        raw, shadow = fixture()
        shadow["coverage"]["producer_proven_by_input"] = False
        with self.assertRaisesRegex(ShadowHold, "SELF_ATTESTED_PRODUCER_COUNT"):
            verify_source_shadow(raw, encode(shadow))

    def test_inconsistent_counts_refuses(self):
        raw, shadow = fixture()
        shadow["coverage"]["legacy_mapped_hints"] = 2
        with self.assertRaisesRegex(ShadowHold, "SHADOW_MAPPED_CONFLICT"):
            verify_source_shadow(raw, encode(shadow))

    def test_reason_tamper_refuses(self):
        raw, shadow = fixture()
        shadow["assets"][0]["reason"] = "SOURCE_BOUND"
        with self.assertRaisesRegex(ShadowHold, "SHADOW_REASON_CONFLICT"):
            verify_source_shadow(raw, encode(shadow))

    def test_bool_as_shadow_method_count_refuses(self):
        raw, shadow = fixture()
        shadow["method_counts"]["card"] = True
        with self.assertRaisesRegex(ShadowHold, "SHADOW_METHOD_COUNTER_CONFLICT"):
            verify_source_shadow(raw, encode(shadow))

    def test_bool_as_shadow_reason_count_refuses(self):
        raw, shadow = fixture()
        shadow["reason_counts"]["SHOWCASE_LINK_NOT_PRODUCER_PROOF"] = True
        with self.assertRaisesRegex(ShadowHold, "SHADOW_REASON_COUNTER_CONFLICT"):
            verify_source_shadow(raw, encode(shadow))

    def test_self_consistent_forgery_not_authenticated(self):
        raw, shadow = fixture()
        src = json.loads(raw)
        src["assets"][0]["source_repo"] = "other-repo"
        forged_map = encode(src)
        shadow["source_map_sha256"] = hashlib.sha256(forged_map).hexdigest()
        shadow["assets"][0]["legacy_source_hint"] = "other-repo"
        shadow["assets"][0]["reason"] = "CARD_LINK_NOT_PRODUCER_PROOF"
        shadow["reason_counts"] = {"CARD_LINK_NOT_PRODUCER_PROOF": 1}
        shadow["coverage"]["showcase_link_hints"] = 0
        result = verify_source_shadow(forged_map, encode(shadow))
        self.assertFalse(result["producer_verified"])
        self.assertEqual(result["state"], "BYTE_BOUND_SHADOW_ONLY")


    def test_non_scalar_source_type_and_method_hold_instead_of_crashing(self):
        for field in ("type", "method"):
            for value in ([], {}):
                with self.subTest(field=field, value=value):
                    raw, shadow = fixture()
                    source = json.loads(raw)
                    source["assets"][0][field] = value
                    altered = encode(source)
                    shadow["source_map_sha256"] = hashlib.sha256(altered).hexdigest()
                    with self.assertRaisesRegex(ShadowHold, "INVALID_SOURCE_ID_OR_METADATA"):
                        verify_source_shadow(altered, encode(shadow))

    def test_missing_canonical_map_root_fields_hold(self):
        for field in ("generated", "unmapped_family_counts"):
            with self.subTest(field=field):
                raw, shadow = fixture()
                source = json.loads(raw)
                del source[field]
                altered = encode(source)
                shadow["source_map_sha256"] = hashlib.sha256(altered).hexdigest()
                with self.assertRaisesRegex(ShadowHold, "UNREVIEWED_FIELDS_OR_MISSING_REQUIRED"):
                    verify_source_shadow(altered, encode(shadow))

    def test_noncanonical_asset_family_holds(self):
        for family in ("unlisted-family", "", "LAPTOP-LORA-TRAINING"):
            with self.subTest(family=family):
                raw, shadow = fixture()
                source = json.loads(raw)
                source["assets"][0]["family"] = family
                altered = encode(source)
                shadow["source_map_sha256"] = hashlib.sha256(altered).hexdigest()
                with self.assertRaisesRegex(ShadowHold, "INVALID_SOURCE_ID_OR_METADATA"):
                    verify_source_shadow(altered, encode(shadow))


    def test_cli_malformed_type_emits_structured_hold(self):
        raw, shadow = fixture()
        source = json.loads(raw)
        source["assets"][0]["type"] = []
        altered = encode(source)
        shadow["source_map_sha256"] = hashlib.sha256(altered).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "map.json").write_bytes(altered)
            (directory / "shadow.json").write_bytes(encode(shadow))
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "tools/verify_source_shadow.py"),
                    "--map", str(directory / "map.json"),
                    "--shadow", str(directory / "shadow.json"),
                ],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {"state": "HOLD", "reason": "INVALID_SOURCE_ID_OR_METADATA"},
        )
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
