#!/usr/bin/env python3
"""Contract tests for fail-closed, read-only HF model hygiene census."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "audit_model_hygiene",
    Path(__file__).resolve().parents[1] / "tools" / "audit_model_hygiene.py",
)
hygiene = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hygiene)


def model(name, files, tags=None, task=None):
    return {
        "id": "SZLHOLDINGS/" + name,
        "sha": "abc",
        "siblings": [{"rfilename": f} for f in files],
        "tags": tags or [],
        "pipeline_tag": task,
    }


class HygieneTest(unittest.TestCase):
    def report(self, *objects):
        return hygiene.audit(list(objects), observed_at="2026-11-19T14:30:00Z")

    def test_software_model_is_not_a_trained_checkpoint(self):
        result = self.report(model("szl-kernels", ["README.md", "kernel.py"], ["software"]))
        self.assertEqual(result["counts"]["no_recognized_tensor_weight_file"], 1)
        self.assertEqual(result["counts"]["explicit_software_or_fixture"], 1)
        self.assertFalse(result["models"][0]["training_verified"])

    def test_adapter_variant_is_not_production_approved(self):
        result = self.report(model("willay-laptop-lora", ["adapter_model.safetensors", "README.md"]))
        self.assertEqual(result["counts"]["laptop_lora_variants"], 1)
        self.assertEqual(result["models"][0]["weight_file_count"], 1)
        self.assertFalse(result["models"][0]["promotion_authorized"])

    def test_empty_candidate_is_not_counted_as_trained(self):
        result = self.report(model("khipu-abstain-r3-candidate", ["README.md"], task="text-generation"))
        self.assertEqual(result["counts"]["candidate_or_research_only"], 1)
        self.assertEqual(result["counts"]["text_generation_label_without_recognized_tensor_weights"], 1)

    def test_receipt_filename_does_not_certify_training(self):
        result = self.report(model("receiptagent-v2-trained", [
            "README.md", "adapter_model.safetensors", "receipts/eval_battery.json"
        ]))
        row = result["models"][0]
        self.assertEqual(len(row["receipt_or_eval_json_names"]), 1)
        self.assertFalse(row["training_verified"])
        self.assertFalse(row["quality_verified"])

    def test_nontensor_model_does_not_get_spam_verdict(self):
        row = self.report(model("yachay-nano", ["model/weights.json", "README.md"]))["models"][0]
        self.assertIn("NO_RECOGNIZED_TENSOR_WEIGHT_FILE", row["flags"])
        self.assertNotIn("EXPLICIT_SOFTWARE_OR_FIXTURE_IN_MODEL_NAMESPACE", row["flags"])

    def test_card_and_license_observation_is_not_release_qualification(self):
        observed = self.report(model("public", [
            "README.md", "model.safetensors", "receipts/eval.json",
        ], ["license:apache-2.0", "text-generation"], task="text-generation"))
        row = observed["models"][0]
        self.assertTrue(row["model_card_readme_present"])
        self.assertTrue(row["license_metadata_present_not_rights_verified"])
        self.assertEqual(observed["counts"]["model_card_readme_missing"], 0)
        self.assertEqual(observed["counts"]["license_metadata_not_observed"], 0)
        self.assertFalse(row["training_verified"])
        self.assertFalse(row["quality_verified"])
        self.assertFalse(row["promotion_authorized"])

    def test_missing_readme_and_license_are_distinct_fail_closed_metadata(self):
        observed = self.report(model("missing", [
            "README.txt", "adapter_model.safetensors",
        ], ["license:unknown"], task="text-generation"))
        row = observed["models"][0]
        self.assertIn("MODEL_CARD_README_MISSING", row["flags"])
        self.assertIn("LICENSE_METADATA_NOT_OBSERVED", row["flags"])
        self.assertFalse(row["model_card_readme_present"])
        self.assertFalse(row["license_metadata_present_not_rights_verified"])
        self.assertEqual(observed["counts"]["model_card_readme_missing"], 1)
        self.assertEqual(observed["counts"]["license_metadata_not_observed"], 1)

    def test_license_other_is_observed_but_never_certified(self):
        row = self.report(model("custom-licensed", [
            "README.md", "weights.gguf",
        ], ["license:other"]))["models"][0]
        self.assertTrue(row["license_metadata_present_not_rights_verified"])
        self.assertFalse(row["promotion_authorized"])


    def test_duplicate_and_wrong_org_rejected(self):
        item = model("x", ["README.md"])
        with self.assertRaises(ValueError):
            self.report(item, item)
        with self.assertRaises(ValueError):
            self.report({"id": "Other/x", "siblings": []})

    def test_missing_or_duplicate_inventory_rejected(self):
        with self.assertRaises(ValueError):
            self.report({"id": "SZLHOLDINGS/x"})
        with self.assertRaises(ValueError):
            self.report(model("x", ["README.md", "README.md"]))

    def test_boundary_prevents_claiming_complete_at_cap(self):
        items = [model("repo-" + str(n), []) for n in range(hygiene.MAX_MODELS)]
        with self.assertRaises(ValueError):
            self.report(*items)

    def test_order_deterministic(self):
        names = [row["repo"] for row in self.report(model("z", []), model("a", []))["models"]]
        self.assertEqual(names, ["SZLHOLDINGS/a", "SZLHOLDINGS/z"])


class LineageScopeTests(unittest.TestCase):
    """Metadata mapping is never proof of a producing or served model."""

    @staticmethod
    def report(*rows):
        scope_path = Path(__file__).resolve().parents[1] / "tools" / "lineage_boundaries.py"
        spec = importlib.util.spec_from_file_location("szl_lineage_boundaries", scope_path)
        scope = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scope)
        doc = {
            "coverage": {
                "total": len(rows),
                "mapped": sum(row["method"] != "unmapped" for row in rows),
                "unmapped": sum(row["method"] == "unmapped" for row in rows),
            },
            "assets": list(rows),
        }
        return scope, doc

    @staticmethod
    def asset(name, method, repo):
        return {
            "id": "SZLHOLDINGS/" + name, "type": "models",
            "method": method, "source_repo": repo,
        }

    def test_card_issuer_is_not_model_source(self):
        scope, doc = self.report(
            self.asset("khipu", "card", "estate-cards"),
            self.asset("real", "name", "szl-khipu"),
            self.asset("no-match", "unmapped", None),
        )
        out = scope.assess(doc)
        self.assertEqual(out["card_generator_only"], 1)
        self.assertEqual(out["reference_scopes"]["NAME_REFERENCE_ONLY"], 1)
        self.assertEqual(out["source_producer_verified"], 0)
        self.assertEqual(out["evaluation_verified"], 0)
        self.assertEqual(out["release_admission"], "HOLD_INDEPENDENT_SOURCE_EVAL_AND_RUNTIME_PROOF")

    def test_curated_override_is_not_signed_provenance(self):
        scope, doc = self.report(self.asset("x", "override", "szl-khipu"))
        out = scope.assess(doc)
        self.assertEqual(out["reference_scopes"]["CURATED_REFERENCE_ONLY"], 1)
        self.assertEqual(out["promotion_authorized"], 0)

    def test_injected_producer_success_rejected(self):
        row = self.asset("x", "card", "estate-cards")
        row["producer_verified"] = True
        scope, doc = self.report(row)
        with self.assertRaisesRegex(scope.ScopeError, "UNATTESTED_VERIFICATION_CLAIM"):
            scope.assess(doc)

    def test_duplicate_and_wrong_org_rejected(self):
        row = self.asset("x", "name", "szl-khipu")
        scope, doc = self.report(row, row)
        with self.assertRaisesRegex(scope.ScopeError, "DUPLICATE_ASSET"):
            scope.assess(doc)
        scope, doc = self.report(self.asset("x", "name", "szl-khipu"))
        doc["assets"][0]["id"] = "outside-org/x"
        with self.assertRaisesRegex(scope.ScopeError, "IDENTITY_INVALID"):
            scope.assess(doc)

    def test_unmapped_and_denominators_fail_closed(self):
        scope, doc = self.report(self.asset("x", "unmapped", "estate-cards"))
        with self.assertRaisesRegex(scope.ScopeError, "UNMAPPED_SOURCE_CONTRADICTION"):
            scope.assess(doc)
        scope, doc = self.report(self.asset("x", "unmapped", None))
        doc["coverage"]["mapped"] = 1
        with self.assertRaisesRegex(scope.ScopeError, "COVERAGE_DENOMINATOR_INVALID"):
            scope.assess(doc)

if __name__ == "__main__":
    unittest.main()