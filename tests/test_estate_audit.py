import copy
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import estate_audit  # noqa: E402

SHA = "a" * 40


def valid_manifest():
    return {
        "metadata": {
            "repo_name": "repo",
            "last_audit_date": "2026-06-01",
            "loop_level": 1,
        },
        "estate_context": {
            "purpose_domain": "testing",
            "baseline_commit": SHA,
            "leader_profiles": [
                {"name": "n", "url": "https://x", "checked_date": "2026-05-01"}
            ],
        },
        "evidence_index": {
            "publications": [
                {"id": "DOI:10.1/x", "link": "https://x", "applicability": "a"}
            ],
            "gap_register": [],
            "prioritized_changes": [],
        },
        "execution_trace": {},
    }


class TestEstateAudit(unittest.TestCase):
    def test_valid_passes(self):
        self.assertEqual(estate_audit.verdict(valid_manifest()),
                         {"defects": [], "defect_count": 0, "ok": True})

    def test_missing_required(self):
        m = valid_manifest()
        del m["metadata"]["repo_name"]
        del m["estate_context"]
        v = estate_audit.verdict(m)
        self.assertFalse(v["ok"])
        self.assertIn("metadata.repo_name:missing-or-not-str", v["defects"])
        self.assertIn("estate_context:missing-or-not-object", v["defects"])

    def test_loop_level_range(self):
        for bad in (0, 11, "2", True):
            m = valid_manifest()
            m["metadata"]["loop_level"] = bad
            self.assertIn("metadata.loop_level:missing-or-out-of-range",
                          estate_audit.verdict(m)["defects"])

    def test_bad_date(self):
        m = valid_manifest()
        m["metadata"]["last_audit_date"] = "2026-13-40"
        self.assertIn("metadata.last_audit_date:missing-or-bad-iso-date",
                      estate_audit.verdict(m)["defects"])

    def test_short_sha(self):
        m = valid_manifest()
        m["estate_context"]["baseline_commit"] = "abc123"
        self.assertIn("estate_context.baseline_commit:missing-or-not-40hex",
                      estate_audit.verdict(m)["defects"])

    def test_loop1_no_url_passes(self):
        m = valid_manifest()
        m["execution_trace"] = {}
        self.assertTrue(estate_audit.verdict(m)["ok"])

    def test_loop2_no_url_fails(self):
        m = valid_manifest()
        m["metadata"]["loop_level"] = 2
        self.assertIn("execution_trace.upgrade_pr_url:required-at-loop>=2",
                      estate_audit.verdict(m)["defects"])

    def test_bad_pub_id_prefix(self):
        m = valid_manifest()
        m["evidence_index"]["publications"][0]["id"] = "ISBN:123"
        self.assertIn("evidence_index.publications[0].id:bad-prefix",
                      estate_audit.verdict(m)["defects"])

    def test_stdout_roundtrip_determinism(self):
        tool = str(Path(__file__).resolve().parent.parent / "tools" / "estate_audit.py")
        m = valid_manifest()
        m["metadata"]["loop_level"] = 2  # force one defect
        payload = json.dumps(m).encode()
        outs = []
        for _ in range(2):
            r = subprocess.run([sys.executable, tool], input=payload,
                               capture_output=True)
            self.assertEqual(r.returncode, 1)
            outs.append(r.stdout)
        self.assertEqual(outs[0], outs[1])
        v = json.loads(outs[0])
        self.assertEqual(v, estate_audit.verdict(m))
        self.assertEqual(v["defects"], sorted(v["defects"]))
        raw = outs[0].decode().strip()
        self.assertEqual(raw, json.dumps(v, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    unittest.main()
