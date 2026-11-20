"""Offline regression tests for source-claim honesty; network-free."""
import hashlib
import json
import unittest

from tools.source_binding_audit import AuditError, audit_map, read_json_strict


def fixture(rows):
    counts = {m: sum(r["method"] == m for r in rows)
              for m in ("name", "card", "override", "unmapped")}
    return {
        "assets": rows,
        "stats": counts,
        "coverage": {"total": len(rows),
                     "mapped": len(rows) - counts["unmapped"],
                     "unmapped": counts["unmapped"]},
    }


def row(name, method, repo, kind="models"):
    return {"id": "SZLHOLDINGS/" + name, "type": kind,
            "method": method, "source_repo": repo}


class SourceBindingAuditTests(unittest.TestCase):
    def test_common_showcase_link_is_not_producer_proof(self):
        doc = fixture([row("MiniEmbed-Nano", "card", "estate-cards"),
                       row("WILLAY", "card", "estate-cards")])
        result = audit_map(doc, "a" * 64)
        self.assertEqual(result["coverage"]["showcase_link_hints"], 2)
        self.assertEqual(result["coverage"]["producer_proven_by_input"], 0)
        self.assertTrue(all(a["producer_proof_state"] == "NOT_ESTABLISHED"
                            for a in result["assets"]))

    def test_fuzzy_and_suffix_name_matches_do_not_establish_proof(self):
        doc = fixture([row("szl-canvas-r4", "name", "szl-canvas"),
                       row("szl-canvas-extra", "name", "szl-canvas")])
        result = audit_map(doc, "b" * 64)
        self.assertEqual(result["reason_counts"]["NAME_SIMILARITY_NOT_PRODUCER_PROOF"], 2)

    def test_override_is_still_not_cryptographic_proof(self):
        r = audit_map(fixture([row("x", "override", "szl-gpu-bridge")]), "c" * 64)
        self.assertEqual(r["coverage"]["producer_proven_by_input"], 0)

    def test_unmapped_remains_unmapped(self):
        r = audit_map(fixture([row("x", "unmapped", None)]), "d" * 64)
        self.assertEqual(r["coverage"]["unmapped_without_hint"], 1)

    def test_duplicate_asset_identity_denied(self):
        doc = fixture([row("x", "name", "x"), row("x", "card", "x")])
        with self.assertRaisesRegex(AuditError, "DUPLICATE_ASSET"):
            audit_map(doc, "e" * 64)

    def test_map_cannot_self_assert_provenance(self):
        asset = row("x", "card", "estate-cards")
        asset["producer_verified"] = True
        with self.assertRaisesRegex(AuditError, "UNSUPPORTED_PRODUCER_PROOF"):
            audit_map(fixture([asset]), "f" * 64)

    def test_reconcile_coverage_and_method_totals(self):
        doc = fixture([row("x", "card", "estate-cards")])
        doc["coverage"]["mapped"] = 0
        with self.assertRaisesRegex(AuditError, "INCONSISTENT"):
            audit_map(doc, "0" * 64)

    def test_bool_as_count_is_rejected(self):
        doc = fixture([row("x", "card", "estate-cards")])
        doc["coverage"]["mapped"] = True
        with self.assertRaisesRegex(AuditError, "INVALID_COUNT_TYPE"):
            audit_map(doc, "0" * 64)

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(AuditError, "DUPLICATE_JSON_KEY"):
            read_json_strict(b'{"coverage":{},"coverage":{}}')

    def test_digest_is_input_bound(self):
        raw = json.dumps(fixture([row("x", "unmapped", None)])).encode()
        digest = hashlib.sha256(raw).hexdigest()
        r = audit_map(read_json_strict(raw), digest)
        self.assertEqual(r["source_map_sha256"], digest)


if __name__ == "__main__":
    unittest.main()
