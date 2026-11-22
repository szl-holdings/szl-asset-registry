#!/usr/bin/env python3
"""Estate manifest audit tool. Contract is the single source of truth."""
import argparse
import json
import re
import sys
from datetime import date

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PUB_PREFIXES = ("DOI:", "arXiv:", "github:")


def _iso(s):
    if not isinstance(s, str) or not ISO_RE.match(s):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def _str(v):
    return isinstance(v, str) and len(v) > 0


def audit(manifest):
    """Return list of defect strings (unsorted; caller sorts)."""
    d = []
    if not isinstance(manifest, dict):
        return ["manifest:not-object"]

    meta = manifest.get("metadata")
    if not isinstance(meta, dict):
        d.append("metadata:missing-or-not-object")
    else:
        if not _str(meta.get("repo_name")):
            d.append("metadata.repo_name:missing-or-not-str")
        if not _iso(meta.get("last_audit_date")):
            d.append("metadata.last_audit_date:missing-or-bad-iso-date")
        ll = meta.get("loop_level")
        if not isinstance(ll, int) or isinstance(ll, bool) or not 1 <= ll <= 10:
            d.append("metadata.loop_level:missing-or-out-of-range")

    ec = manifest.get("estate_context")
    if not isinstance(ec, dict):
        d.append("estate_context:missing-or-not-object")
    else:
        if not _str(ec.get("purpose_domain")):
            d.append("estate_context.purpose_domain:missing-or-not-str")
        bc = ec.get("baseline_commit")
        if not isinstance(bc, str) or not SHA_RE.match(bc):
            d.append("estate_context.baseline_commit:missing-or-not-40hex")
        lp = ec.get("leader_profiles")
        if not isinstance(lp, list):
            d.append("estate_context.leader_profiles:missing-or-not-list")
        else:
            for i, p in enumerate(lp):
                if not isinstance(p, dict) or not _str(p.get("name")) \
                        or not _str(p.get("url")) or not _iso(p.get("checked_date")):
                    d.append("estate_context.leader_profiles[%d]:invalid" % i)

    ei = manifest.get("evidence_index")
    if not isinstance(ei, dict):
        d.append("evidence_index:missing-or-not-object")
    else:
        pubs = ei.get("publications")
        if not isinstance(pubs, list):
            d.append("evidence_index.publications:missing-or-not-list")
        else:
            for i, p in enumerate(pubs):
                if not isinstance(p, dict):
                    d.append("evidence_index.publications[%d]:invalid" % i)
                    continue
                pid = p.get("id")
                if not isinstance(pid, str) or not pid.startswith(PUB_PREFIXES):
                    d.append("evidence_index.publications[%d].id:bad-prefix" % i)
                if not _str(p.get("link")):
                    d.append("evidence_index.publications[%d].link:missing" % i)
                if not _str(p.get("applicability")):
                    d.append("evidence_index.publications[%d].applicability:missing" % i)
        if not isinstance(ei.get("gap_register"), list):
            d.append("evidence_index.gap_register:missing-or-not-list")
        if not isinstance(ei.get("prioritized_changes"), list):
            d.append("evidence_index.prioritized_changes:missing-or-not-list")

    et = manifest.get("execution_trace")
    if not isinstance(et, dict):
        d.append("execution_trace:missing-or-not-object")

    ll = meta.get("loop_level") if isinstance(meta, dict) else None
    if isinstance(ll, int) and not isinstance(ll, bool) and ll >= 2 and isinstance(et, dict):
        if not _str(et.get("upgrade_pr_url")):
            d.append("execution_trace.upgrade_pr_url:required-at-loop>=2")

    return d


def verdict(manifest):
    defects = sorted(audit(manifest))
    return {
        "defects": defects,
        "defect_count": len(defects),
        "ok": not defects,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='?')
    parser.add_argument('--manifest')
    args = parser.parse_args()
    manifest_path = args.manifest or args.path
    def reject_constant(value):
        raise ValueError('invalid JSON constant: ' + value)
    try:
        if manifest_path:
            with open(manifest_path, 'r', encoding='utf-8') as handle:
                data = json.load(handle, parse_constant=reject_constant)
        else:
            data = json.load(sys.stdin, parse_constant=reject_constant)
    except Exception as exc:
        error = 'manifest error: ' + str(exc)
        result = {
            'defects': [error],
            'defect_count': 1,
            'ok': False,
        }
        print(json.dumps(result, sort_keys=True, separators=(',', ':')))
        sys.exit(1)
    result = verdict(data)
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    sys.exit(0 if result['ok'] else 1)


if __name__ == "__main__":
    main()
