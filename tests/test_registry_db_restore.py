import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os, shutil, sqlite3, tempfile, unittest
from registry_db import loader, restore_drill, receipts
from registry_db_fixtures import write_raw
import ingest_snapshot_helper as helper

class RestoreDrillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); raw = os.path.join(self.tmp, "raw"); write_raw(raw)
        self.db = os.path.join(self.tmp, "r.db"); loader.load(self.db, helper.build(raw, self.tmp))
    def tearDown(self): shutil.rmtree(self.tmp)

    def test_backup_restore_roundtrip_is_equivalent(self):
        exp = restore_drill.backup(self.db, os.path.join(self.tmp, "b.db"))
        r = restore_drill.restore_and_verify(os.path.join(self.tmp, "b.db"), os.path.join(self.tmp, "rest.db"), exp)
        self.assertTrue(r["ok"], r["problems"]); self.assertTrue(r["fingerprint"]["receipt_chain"]["ok"])
        self.assertEqual(r["fingerprint"]["tables"]["assets"]["rows"], sqlite3.connect(self.db).execute("SELECT COUNT(*) FROM assets").fetchone()[0])

    def test_drill_detects_a_corrupted_backup(self):
        exp = restore_drill.backup(self.db, os.path.join(self.tmp, "b.db"))
        c = sqlite3.connect(os.path.join(self.tmp, "b.db")); c.execute("DROP TRIGGER receipts_no_update"); c.execute("UPDATE receipts SET reason='altered' WHERE seq=1"); c.commit(); c.close()
        r = restore_drill.restore_and_verify(os.path.join(self.tmp, "b.db"), os.path.join(self.tmp, "rest.db"), exp)
        self.assertFalse(r["ok"]); self.assertTrue(any("receipt chain" in p or "digests" in p for p in r["problems"]))

    def test_refuses_to_overwrite_existing_target(self):
        open(os.path.join(self.tmp, "x.db"), "w").close()
        with self.assertRaises(FileExistsError): restore_drill.backup(self.db, os.path.join(self.tmp, "x.db"))

if __name__ == "__main__":
    unittest.main()
