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


if __name__ == "__main__":
    unittest.main()