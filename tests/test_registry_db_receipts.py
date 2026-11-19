import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os, shutil, sqlite3, tempfile, unittest
from registry_db import migrate, receipts, loader, writer
from registry_db_fixtures import write_raw

def fresh():
    tmp = tempfile.mkdtemp(); db = os.path.join(tmp, "r.db"); migrate.apply(db); return tmp, db

class ReceiptChainTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = fresh(); self.c = sqlite3.connect(self.db, isolation_level=None)
        for i in range(3):
            receipts.append(self.c, actor="agent:x", actor_kind="agent", action="proposal.create", target=f"t{i}", reason=f"why {i}", payload={"i": i}, at=f"2026-11-19T12:00:0{i}Z")
    def tearDown(self): self.c.close(); shutil.rmtree(self.tmp)

    def test_chain_verifies(self):
        r = receipts.verify_chain(self.c); self.assertTrue(r["ok"]); self.assertEqual(r["count"], 3)
        self.assertEqual(self.c.execute("SELECT prev_hash FROM receipts WHERE seq=1").fetchone()[0], receipts.GENESIS)

    def test_reason_required(self):
        with self.assertRaises(ValueError): receipts.append(self.c, actor="a", actor_kind="agent", action="proposal.create", target="t", reason=" ")

    def test_update_and_delete_blocked_by_triggers(self):
        with self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"): self.c.execute("UPDATE receipts SET reason='x' WHERE seq=2")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"): self.c.execute("DELETE FROM receipts WHERE seq=3")

    def test_forged_insert_rejected_structurally(self):
        row = self.c.execute("SELECT entry_hash FROM receipts WHERE seq=3").fetchone()[0]
        ins = "INSERT INTO receipts (seq, receipt_id, prev_hash, entry_hash, actor, actor_kind, action, target, reason, payload_json, at) VALUES (?,?,?,?,?,?,?,?,?,?,?)"
        with self.assertRaisesRegex(sqlite3.DatabaseError, "seq must be"):      # gap
            self.c.execute(ins, (9, "r9", row, "9" * 64, "a", "agent", "proposal.create", "t", "r", "{}", "t"))
        with self.assertRaisesRegex(sqlite3.DatabaseError, "prev_hash"):        # fork
            self.c.execute(ins, (4, "r4", "0" * 64, "8" * 64, "a", "agent", "proposal.create", "t", "r", "{}", "t"))

    def test_verifier_detects_tampering_even_if_triggers_are_dropped(self):
        self.c.execute("DROP TRIGGER receipts_no_update")
        self.c.execute("UPDATE receipts SET reason='rewritten history' WHERE seq=2")
        r = receipts.verify_chain(self.c); self.assertFalse(r["ok"]); self.assertIn("seq 2", r["error"])

    def test_verifier_detects_relinked_chain(self):
        self.c.execute("DROP TRIGGER receipts_no_update")
        self.c.execute("UPDATE receipts SET prev_hash=? WHERE seq=3", ("7" * 64,))
        r = receipts.verify_chain(self.c); self.assertFalse(r["ok"])

class DeleteGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); raw = os.path.join(self.tmp, "raw"); write_raw(raw)
        import registry_db_fixtures, ingest_snapshot_helper
        self.db = os.path.join(self.tmp, "r.db"); loader.load(self.db, ingest_snapshot_helper.build(raw, self.tmp))
    def tearDown(self): shutil.rmtree(self.tmp)

    def test_asset_cannot_be_deleted_without_a_receipt(self):
        c = sqlite3.connect(self.db, isolation_level=None); c.execute("PRAGMA foreign_keys=ON")
        c.execute("DELETE FROM asset_facts WHERE asset_id='hf_model:SZLHOLDINGS/no-source'"); c.execute("DELETE FROM asset_revisions WHERE asset_id='hf_model:SZLHOLDINGS/no-source'")
        c.execute("DELETE FROM asset_alignment WHERE asset_id='hf_model:SZLHOLDINGS/no-source'")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "delete requires"): c.execute("DELETE FROM assets WHERE asset_id='hf_model:SZLHOLDINGS/no-source'")

    def test_delete_with_receipt_works_and_chain_stays_valid(self):
        n = lambda: sqlite3.connect(self.db).execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        before = n()
        writer.delete_asset(self.db, "hf_model:SZLHOLDINGS/no-source", approver="human:stephen", reason="test: retired asset", at="2026-11-19T13:00:00Z")
        self.assertEqual(n(), before - 1)
        c = sqlite3.connect(self.db); self.assertTrue(receipts.verify_chain(c)["ok"])
        self.assertEqual(c.execute("SELECT action, target FROM receipts ORDER BY seq DESC LIMIT 1").fetchone(), ("asset.delete", "hf_model:SZLHOLDINGS/no-source"))

    def test_receipt_for_a_different_asset_does_not_unlock_delete(self):
        c = sqlite3.connect(self.db, isolation_level=None); c.execute("PRAGMA foreign_keys=ON")
        receipts.append(c, actor="human:x", actor_kind="human", action="asset.delete", target="hf_model:SZLHOLDINGS/orphan-ref", reason="r")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "delete requires"): c.execute("DELETE FROM assets WHERE asset_id='hf_model:SZLHOLDINGS/no-source'")

if __name__ == "__main__":
    unittest.main()
