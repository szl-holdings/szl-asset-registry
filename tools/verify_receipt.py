import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCHEMA = 'szl.release-evidence/v1'
OUT_SCHEMA = 'szl.registry.evidence-verify/v1'
MAX_BYTES = 16384
EXPECTED = {'schema', 'source_revision', 'artifact_sha256'}
HEX40 = set('0123456789abcdef')
HEX64 = set('0123456789abcdef')


class ReceiptError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def pairs_hook(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise ReceiptError('DUPLICATE_RECEIPT_FIELD')
        seen.add(key)
    return dict(pairs)


def is_hex(value, size, alphabet):
    return isinstance(value, str) and len(value) == size and all(ch in alphabet for ch in value)


def parse_receipt(path):
    try:
        with open(path, 'rb') as handle:
            raw = handle.read()
    except OSError:
        raise ReceiptError('RECEIPT_UNREADABLE')
    if len(raw) > MAX_BYTES:
        raise ReceiptError('RECEIPT_UNREADABLE')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise ReceiptError('RECEIPT_UNREADABLE')
    try:
        obj = json.loads(text, object_pairs_hook=pairs_hook)
    except ReceiptError:
        raise
    except json.JSONDecodeError:
        raise ReceiptError('RECEIPT_UNREADABLE')
    if not isinstance(obj, dict):
        raise ReceiptError('RECEIPT_UNREADABLE')
    keys = set(obj.keys())
    if keys != EXPECTED:
        lowered = {str(key).lower() for key in keys}
        if any('publish' in key or 'publication' in key for key in lowered):
            raise ReceiptError('RECEIPT_SCHEMA_MISMATCH')
        raise ReceiptError('RECEIPT_SCHEMA_MISMATCH')
    if obj.get('schema') != SCHEMA:
        raise ReceiptError('RECEIPT_SCHEMA_MISMATCH')
    revision = obj.get('source_revision')
    digest = obj.get('artifact_sha256')
    if not is_hex(revision, 40, HEX40):
        raise ReceiptError('INVALID_SOURCE')
    if not is_hex(digest, 64, HEX64):
        raise ReceiptError('INVALID_DIGEST')
    return revision, digest


def run_git(root, args, cwd=None):
    command = ['git'] + args
    try:
        return subprocess.run(command, cwd=cwd or root, capture_output=True, text=True)
    except OSError:
        return subprocess.CompletedProcess(command, 127, stdout='', stderr='git unavailable')


def verify_one(root, path):
    try:
        revision, digest = parse_receipt(path)
    except ReceiptError as exc:
        return exc.reason
    cat = run_git(root, ['cat-file', '-e', revision + '^{commit}'])
    if cat.returncode != 0:
        return 'REV_NOT_FOUND'
    base = tempfile.mkdtemp(prefix='szl-verify-')
    worktree = os.path.join(base, 'worktree')
    try:
        add = run_git(root, ['worktree', 'add', '--detach', worktree, revision])
        if add.returncode != 0:
            return 'WORKTREE_FAILED'
        build = subprocess.run([sys.executable, 'tools/build_catalog.py', '.'], cwd=worktree, capture_output=True, text=True)
        if build.returncode != 0:
            return 'BUILD_FAILED'
        diff = subprocess.run(['git', '-C', worktree, 'diff', '--exit-code', '--', 'data/'], capture_output=True, text=True)
        if diff.returncode != 0:
            return 'REPLAY_MISMATCH'
        matches = glob.glob(os.path.join(worktree, 'data', 'repo_catalog_*.json'))
        if len(matches) != 1:
            return 'ARTIFACT_NOT_UNIQUE'
        with open(matches[0], 'rb') as handle:
            artifact = handle.read()
        actual = hashlib.sha256(artifact).hexdigest()
        if actual != digest:
            return 'DIGEST_MISMATCH'
        return None
    except OSError:
        return 'BUILD_FAILED'
    finally:
        subprocess.run(['git', '-C', root, 'worktree', 'remove', '--force', worktree], capture_output=True, text=True)
        shutil.rmtree(base, ignore_errors=True)


def main(argv):
    if len(argv) > 2:
        sys.stderr.write('usage: verify_receipt.py [ROOT]' + chr(10))
        return 2
    root = argv[1] if len(argv) == 2 else '.'
    if not os.path.isdir(root):
        sys.stderr.write('root is not a directory: ' + root + chr(10))
        return 2
    pattern = os.path.join(root, 'receipts', 'registry_catalog_*.json')
    receipts = sorted(glob.glob(pattern))
    reasons = []
    verified = 0
    if not receipts:
        reasons.append('NO_RECEIPTS')
    else:
        for path in receipts:
            reason = verify_one(root, path)
            if reason is None:
                verified += 1
            else:
                reasons.append(reason)
    status = 'VERIFIED' if reasons == [] and verified > 0 else 'HOLD'
    verdict = {'schema': OUT_SCHEMA, 'status': status, 'reasons': reasons, 'receipts_verified': verified, 'publication_authorized': False}
    print(json.dumps(verdict, separators=(',', ':')))
    return 0 if status == 'VERIFIED' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
