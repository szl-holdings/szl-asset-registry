import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

VERIFIER = Path(__file__).resolve().parents[1] / 'tools' / 'verify_receipt.py'
TEMPLATE = b'szl-stub-catalog-fixed-v1' + bytes([10])
MUTATED = TEMPLATE + b'mutated' + bytes([10])
STUB = '''import pathlib
import sys
TEMPLATE = b'szl-stub-catalog-fixed-v1' + bytes([10])
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.')
data = root / 'data'
data.mkdir(parents=True, exist_ok=True)
(data / 'repo_catalog_99999999.json').write_bytes(TEMPLATE)
'''
COVERAGE = 'raise SystemExit(0)' + chr(10)


def write(root, rel, data):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode()
    path.write_bytes(data)


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


class VerifyReceiptTests(unittest.TestCase):
    def run_verifier(self, root):
        proc = subprocess.run([sys.executable, str(VERIFIER), str(root)], capture_output=True, text=True)
        self.assertEqual(proc.stdout.count(chr(10)), 1, msg=proc.stderr)
        verdict = json.loads(proc.stdout)
        return proc.returncode, verdict, proc.stdout

    def make_root(self, tmp, catalog=TEMPLATE, two_catalogs=False, receipt=None, receipts=True):
        root = Path(tmp)
        write(root, 'tools/build_catalog.py', STUB)
        write(root, 'tools/coverage_check.py', COVERAGE)
        write(root, 'data/repo_catalog_99999999.json', catalog)
        if two_catalogs:
            write(root, 'data/repo_catalog_88888888.json', catalog)
        git(root, 'init', '-q')
        git(root, 'config', 'user.email', 'ci@example.invalid')
        git(root, 'config', 'user.name', 'CI')
        git(root, 'add', '-A')
        git(root, 'commit', '-q', '-m', 'seed')
        rev = git(root, 'rev-parse', 'HEAD')
        digest = hashlib.sha256(catalog).hexdigest()
        if receipt is None:
            receipt = {'schema': 'szl.release-evidence/v1', 'source_revision': rev, 'artifact_sha256': digest}
        if receipts:
            write(root, 'receipts/registry_catalog_r1.json', json.dumps(receipt, separators=(',', ':')))
        return str(root), rev, digest

    def test_happy_path_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, rev, digest = self.make_root(tmp)
            code, verdict, out = self.run_verifier(root)
            self.assertEqual(code, 0)
            self.assertIn('VERIFIED', out)
            self.assertEqual(verdict['status'], 'VERIFIED')
            self.assertEqual(verdict['receipts_verified'], 1)
            self.assertEqual(verdict['reasons'], [])
            self.assertFalse(verdict['publication_authorized'])

    def test_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrong = hashlib.sha256(b'different-constant-bytes' + bytes([10])).hexdigest()
            root, rev, digest = self.make_root(tmp)
            receipt = {'schema': 'szl.release-evidence/v1', 'source_revision': rev, 'artifact_sha256': wrong}
            write(root, 'receipts/registry_catalog_r1.json', json.dumps(receipt, separators=(',', ':')))
            code, verdict, out = self.run_verifier(root)
            self.assertEqual(code, 1)
            self.assertIn('DIGEST_MISMATCH', out)

    def test_replay_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, rev, digest = self.make_root(tmp, catalog=MUTATED)
            code, verdict, out = self.run_verifier(root)
            self.assertEqual(code, 1)
            self.assertIn('REPLAY_MISMATCH', out)

    def test_rev_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = hashlib.sha1(b'szl-missing-revision' + bytes([10])).hexdigest()
            root, rev, digest = self.make_root(tmp)
            receipt = {'schema': 'szl.release-evidence/v1', 'source_revision': missing, 'artifact_sha256': digest}
            write(root, 'receipts/registry_catalog_r1.json', json.dumps(receipt, separators=(',', ':')))
            code, verdict, out = self.run_verifier(root)
            self.assertEqual(code, 1)
            self.assertIn('REV_NOT_FOUND', out)

    def test_duplicate_receipt_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, rev, digest = self.make_root(tmp)
            q = chr(34)
            raw = (chr(123) + q + 'schema' + q + ':' + q + 'szl.release-evidence/v1' + q + ',' +
                   q + 'schema' + q + ':' + q + 'szl.release-evidence/v1' + q + ',' +
                   q + 'source_revision' + q + ':' + q + rev + q + ',' +
                   q + 'artifact_sha256' + q + ':' + q + digest + q + '}')
            write(root, 'receipts/registry_catalog_r1.json', raw)
            code, verdict, out = self.run_verifier(root)
            self.assertEqual(code, 1)
            self.assertIn('DUPLICATE_RECEIPT_FIELD', out)

    def test_publish_extra_field_schema_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, rev, digest = self.make_root(tmp)
            receipt = {'schema': 'szl.release-evidence/v1', 'source_revision': rev, 'artifact_sha256': digest, 'publication_authorized': True}
            write(root, 'receipts/registry_catalog_r1.json', json.dumps(receipt, separators=(',', ':')))
            code, verdict, out = self.run_verifier(root)
            self.assertEqual(code, 1)
            self.assertIn('RECEIPT_SCHEMA_MISMATCH', out)

    def test_missing_receipts_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, verdict, out = self.run_verifier(tmp)
            self.assertEqual(code, 1)
            self.assertIn('NO_RECEIPTS', out)

    def test_artifact_not_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, rev, digest = self.make_root(tmp, two_catalogs=True)
            code, verdict, out = self.run_verifier(root)
            self.assertEqual(code, 1)
            self.assertIn('ARTIFACT_NOT_UNIQUE', out)


if __name__ == '__main__':
    unittest.main()
