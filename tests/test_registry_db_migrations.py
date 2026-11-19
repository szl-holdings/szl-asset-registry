import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os, shutil, sqlite3, tempfile, unittest
from registry_db import migrate

class MigrationGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self.db = os.path.join(self.tmp, "r.db")
    def tearDown(self): shutil.rmtree(self.tmp)
    def mig_copy(self):
        d = os.path.join(self.tmp, "migs"); shutil.copytree(migrate.MIG_DIR, d); return d

    def test_from_zero_replay_applies_all_in_order_and_is_idempotent(self):
        files = migrate.load_files()
        self.assertEqual(migrate.apply(self.db), len(files))
        self.assertEqual(migrate.apply(self.db), len(files))          # re-run is a no-op
        c = sqlite3.connect(self.db)
        self.assertEqual([r[0] for r in c.execute("SELECT id FROM registry_migrations ORDER BY id")], list(range(1, len(files) + 1)))
        for t in ("assets", "asset_facts", "asset_revisions", "source_bindings", "asset_alignment", "receipts", "proposals", "ingest_runs", "coverage_reports", "candidate_refs"):
            self.assertTrue(c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (t,)).fetchone(), t)

    def test_skipped_lower_migration_is_refused_not_silently_skipped(self):
        # F1/F2 shape: id 3 recorded as applied while id 2 never ran.
        migrate.apply(self.db)
        c = sqlite3.connect(self.db); c.execute("DELETE FROM registry_migrations WHERE id = 2"); c.commit(); c.close()
        with self.assertRaisesRegex(migrate.MigrationError, "not a contiguous prefix"):
            migrate.apply(self.db)

    def test_edited_applied_migration_is_refused(self):
        migrate.apply(self.db)
        d = self.mig_copy(); p = os.path.join(d, "0002_facts_bindings.sql")
        open(p, "a").write("\n-- sneaky edit\n")
        files = migrate.load_files(d); open(os.path.join(d, "MANIFEST.sha256"), "w").write(migrate.manifest_text(files))   # even with a regenerated manifest
        with self.assertRaisesRegex(migrate.MigrationError, "checksum mismatch"):
            migrate.apply(self.db, mig_dir=d)

    def test_manifest_mismatch_refused(self):
        d = self.mig_copy(); open(os.path.join(d, "0003_receipts_proposals.sql"), "a").write("\n-- x\n")
        with self.assertRaisesRegex(migrate.MigrationError, "MANIFEST"):
            migrate.apply(self.db, mig_dir=d)

    def test_gap_in_file_ids_refused(self):
        d = self.mig_copy(); os.remove(os.path.join(d, "0002_facts_bindings.sql"))
        with self.assertRaisesRegex(migrate.MigrationError, "contiguous"):
            migrate.load_files(d)

    def test_failed_migration_rolls_back_and_leaves_journal_unchanged(self):
        d = self.mig_copy()
        open(os.path.join(d, "0004_bad.sql"), "w").write("CREATE TABLE ok_t (a INTEGER);\nINSERT INTO nonexistent_table VALUES (1);\n")
        open(os.path.join(d, "MANIFEST.sha256"), "w").write(migrate.manifest_text(migrate.load_files(d)))
        with self.assertRaises(sqlite3.Error):
            migrate.apply(self.db, mig_dir=d)
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("SELECT MAX(id) FROM registry_migrations").fetchone()[0], 3)
        self.assertIsNone(c.execute("SELECT 1 FROM sqlite_master WHERE name='ok_t'").fetchone())

    def test_sql_is_d1_portable(self):
        # D1 has no sha256() SQL function and no ATTACH/VACUUM; hashes are computed in Python.
        for f in migrate.load_files():
            low = "\n".join(l.split("--")[0] for l in f["sql"].lower().splitlines())
            for bad in ("sha256(", "attach ", "vacuum", "load_extension"):
                self.assertNotIn(bad, low, f["name"])

if __name__ == "__main__":
    unittest.main()
