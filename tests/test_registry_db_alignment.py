import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import unittest
from registry_db import alignment as A

class AlignmentFixtures(unittest.TestCase):
    H = "a" * 40; P = "b" * 40
    def test_verified_pin_equal_head_is_aligned(self):
        self.assertEqual(A.classify_binding("verified_pin", self.H, self.H, "identical")[0], "ALIGNED")
    def test_verified_pin_ancestor_is_behind(self):
        self.assertEqual(A.classify_binding("verified_pin", self.P, self.H, "upstream_ahead")[0], "BEHIND")
    def test_verified_pin_ahead_or_diverged_is_drifted(self):
        for c in ("pin_ahead", "diverged"):
            self.assertEqual(A.classify_binding("verified_pin", self.P, self.H, c)[0], "DRIFTED", c)
    def test_verified_pin_not_compared_is_unknown(self):
        self.assertEqual(A.classify_binding("verified_pin", self.P, self.H, "not_compared")[0], "UNKNOWN")
    def test_pin_missing_upstream_is_untraceable(self):
        self.assertEqual(A.classify_binding("verified_pin", self.P, self.H, "not_compared", pin_found=False)[0], "UNTRACEABLE")
    def test_declared_and_referenced_never_claim_alignment(self):
        for g in ("declared", "referenced"):
            for cmp_ in ("identical", "upstream_ahead", "no_pin"):
                st, reason = A.classify_binding(g, self.P if cmp_ != "no_pin" else None, self.H, cmp_)
                self.assertEqual(st, "UNKNOWN"); self.assertTrue(reason)
    def test_asset_without_binding(self):
        self.assertEqual(A.classify_asset("hf_model", [])[0], "UNTRACEABLE")
        self.assertEqual(A.classify_asset("pypi_project", [])[0], "UNTRACEABLE")
        self.assertEqual(A.classify_asset("cf_worker", [])[0], "UNTRACEABLE")
        for t in ("hf_bucket", "hf_collection", "cf_zone", "cf_dns_record", "cf_d1", "cf_tunnel"):
            self.assertEqual(A.classify_asset(t, [])[0], "UNKNOWN", t)
    def test_github_repo_is_authority(self):
        self.assertEqual(A.classify_asset("github_repo", [])[0], "ALIGNED")
    def test_best_binding_prefers_grade_then_state(self):
        b = [{"grade": "declared", "alignment_state": "UNKNOWN", "alignment_reason": "d", "upstream_asset_id": "x"},
             {"grade": "verified_pin", "alignment_state": "BEHIND", "alignment_reason": "v", "upstream_asset_id": "y"},
             {"grade": "referenced", "alignment_state": "UNKNOWN", "alignment_reason": "r", "upstream_asset_id": "z"}]
        self.assertEqual(A.classify_asset("hf_space", b), ("BEHIND", "v", "y"))
    def test_state_is_never_null(self):
        for g in ("verified_pin", "declared", "referenced", "bogus"):
            self.assertIn(A.classify_binding(g, None, None, "no_pin")[0], ("aligned", "behind", "untraceable", "UNKNOWN"))
    def test_compare_status_mapping(self):
        self.assertEqual([A.comparison_from_compare_status(s) for s in ("identical", "ahead", "behind", "diverged", "weird")],
                         ["identical", "upstream_ahead", "pin_ahead", "diverged", "not_compared"])
    def test_version_compare(self):
        self.assertEqual(A.compare_versions("0.1.0", "0.1.0"), "identical")
        self.assertEqual(A.compare_versions("0.1.0", "0.2.0"), "upstream_ahead")
        self.assertEqual(A.compare_versions("0.3.0", "0.2.0"), "pin_ahead")
        self.assertEqual(A.compare_versions("garbage", "0.2.0"), "not_compared")


    def test_absent_asset_is_unknown_even_with_bindings(self):
        b = [{"grade": "verified_pin", "alignment_state": "BEHIND", "alignment_reason": "v", "upstream_asset_id": "y"}]
        self.assertEqual(A.classify_asset("hf_model", b, lifecycle="ABSENT")[0], "UNKNOWN")
        self.assertEqual(A.classify_asset("hf_model", [], lifecycle="ABSENT")[0], "UNKNOWN")
    def test_pages_project_without_binding_is_untraceable(self):
        self.assertEqual(A.classify_asset("cf_pages_project", [])[0], "UNTRACEABLE")
    def test_pep503_normalize(self):
        self.assertEqual(A.pep503_name("SZL_Core.Name"), "szl-core-name")
    def test_visibility_unknown_uppercase(self):
        self.assertEqual(A.norm_visibility("unknown"), "UNKNOWN")
        self.assertEqual(A.norm_visibility(None), "UNKNOWN")
        self.assertEqual(A.norm_visibility("public"), "public")
        self.assertEqual(A.norm_visibility("private"), "private")

if __name__ == "__main__":
    unittest.main()
