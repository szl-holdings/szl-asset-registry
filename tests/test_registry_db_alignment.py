import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import unittest
from registry_db import alignment as A

class AlignmentFixtures(unittest.TestCase):
    H = "a" * 40; P = "b" * 40
    def test_verified_pin_equal_head_is_aligned(self):
        self.assertEqual(A.classify_binding("verified_pin", self.H, self.H, "identical")[0], "aligned")
    def test_verified_pin_ancestor_is_behind(self):
        self.assertEqual(A.classify_binding("verified_pin", self.P, self.H, "upstream_ahead")[0], "behind")
    def test_verified_pin_ahead_or_diverged_is_unknown_not_aligned(self):
        for c in ("pin_ahead", "diverged", "not_compared"):
            self.assertEqual(A.classify_binding("verified_pin", self.P, self.H, c)[0], "unknown", c)
    def test_pin_missing_upstream_is_untraceable(self):
        self.assertEqual(A.classify_binding("verified_pin", self.P, self.H, "not_compared", pin_found=False)[0], "untraceable")
    def test_declared_and_referenced_never_claim_alignment(self):
        for g in ("declared", "referenced"):
            for cmp_ in ("identical", "upstream_ahead", "no_pin"):
                st, reason = A.classify_binding(g, self.P if cmp_ != "no_pin" else None, self.H, cmp_)
                self.assertEqual(st, "unknown"); self.assertTrue(reason)
    def test_asset_without_binding(self):
        self.assertEqual(A.classify_asset("hf_model", [])[0], "untraceable")
        self.assertEqual(A.classify_asset("pypi_project", [])[0], "untraceable")
        self.assertEqual(A.classify_asset("cf_worker", [])[0], "untraceable")
        for t in ("hf_bucket", "hf_collection", "cf_zone", "cf_dns_record", "cf_d1", "cf_tunnel"):
            self.assertEqual(A.classify_asset(t, [])[0], "unknown", t)
    def test_github_repo_is_authority(self):
        self.assertEqual(A.classify_asset("github_repo", [])[0], "aligned")
    def test_best_binding_prefers_grade_then_state(self):
        b = [{"grade": "declared", "alignment_state": "unknown", "alignment_reason": "d", "upstream_asset_id": "x"},
             {"grade": "verified_pin", "alignment_state": "behind", "alignment_reason": "v", "upstream_asset_id": "y"},
             {"grade": "referenced", "alignment_state": "unknown", "alignment_reason": "r", "upstream_asset_id": "z"}]
        self.assertEqual(A.classify_asset("hf_space", b), ("behind", "v", "y"))
    def test_state_is_never_null(self):
        for g in ("verified_pin", "declared", "referenced", "bogus"):
            self.assertIn(A.classify_binding(g, None, None, "no_pin")[0], ("aligned", "behind", "untraceable", "unknown"))
    def test_compare_status_mapping(self):
        self.assertEqual([A.comparison_from_compare_status(s) for s in ("identical", "ahead", "behind", "diverged", "weird")],
                         ["identical", "upstream_ahead", "pin_ahead", "diverged", "not_compared"])
    def test_version_compare(self):
        self.assertEqual(A.compare_versions("0.1.0", "0.1.0"), "identical")
        self.assertEqual(A.compare_versions("0.1.0", "0.2.0"), "upstream_ahead")
        self.assertEqual(A.compare_versions("0.3.0", "0.2.0"), "pin_ahead")
        self.assertEqual(A.compare_versions("garbage", "0.2.0"), "not_compared")

if __name__ == "__main__":
    unittest.main()
