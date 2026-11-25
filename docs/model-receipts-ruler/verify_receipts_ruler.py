#!/usr/bin/env python3
"""Estate model-receipts ruler validator v1.0 (fail-closed, stdlib-only).

Validates receipt documents against the ruler in RULER.md /
receipt-envelope.schema.json. Exit codes:
  0 = every input document valid
  1 = at least one defect found (defects are typed and printed per document)
  2 = usage / IO error

Honesty rules encoded here (anti-laundering, anti-greenwash):
  - trust_status must be UNSIGNED_UNVERIFIED while signature.status == UNSIGNED
    (an unsigned receipt may never render green);
  - every training fact is a TYPED value: OBSERVED/DERIVED need evidence ids
    (DERIVED also needs its formula), UNKNOWN needs a reason;
  - legacy receipts must carry claims_promoted=false;
  - T2 requires >= 1 evidence object with a strong subject binding; "main" is
    not an immutable dataset revision;
  - artifacts are valid only with a full digest set or an explicit hash_error.

Modes:
  python verify_receipts_ruler.py RECEIPT.json [MORE.json ...]
  python verify_receipts_ruler.py --selftest      # runs the embedded samples; exit 0 iff expectations match

NOTE (2026-11-25): the selftest WAS executed on the owner device (betterwithage,
2026-11-24): 6/6 cases OK, SELFTEST PASS. Execution receipt:
selftest-receipt-20261124.md (this commit). Advisory ruling W27T2 Q2 authorized
replacing the previous not-yet-executed note with this receipt-bearing note.
"""

import json
import sys

FACT_STATUSES = {"OBSERVED", "DERIVED", "REPORTED_UNVERIFIED", "UNKNOWN", "NOT_APPLICABLE", "CONFLICT"}
STRONG_BINDINGS = {"EXACT_OUTPUT_DIGEST_MATCH", "IMMUTABLE_RUN_ID_BINDING", "EXACT_CONFIG_DATA_OUTPUT_BINDING"}


def defect(doc, code, path, msg, defects):
    defects.append({"receipt": doc.get("receipt_id", "<unknown>"), "code": code, "path": path, "msg": msg})


def check_common(doc, defects):
    for key in ("schema_version", "receipt_id", "subject", "generator", "tier", "status", "honesty", "signature", "trust_status"):
        if key not in doc:
            defect(doc, "MISSING_KEY", key, "common envelope key missing", defects)
    sub = doc.get("subject") or {}
    for key in ("repo_id", "repo_type", "visibility", "captured_at"):
        if key not in sub:
            defect(doc, "MISSING_KEY", "subject." + key, "subject field missing", defects)
    if doc.get("tier") not in ("T0", "T1", "T2"):
        defect(doc, "BAD_TIER", "tier", "tier must be T0, T1 or T2", defects)
    hon = doc.get("honesty") or {}
    if not hon.get("what") or not hon.get("what_not"):
        defect(doc, "HONESTY_INCOMPLETE", "honesty", "honesty.what and honesty.what_not are mandatory", defects)
    sig = doc.get("signature") or {}
    trust = doc.get("trust_status")
    if sig.get("status") == "UNSIGNED":
        if sig.get("reason") != "OWNER_CREDENTIAL_UNMINTED":
            defect(doc, "BAD_SIGNATURE_REASON", "signature.reason", "unsigned era reason must be OWNER_CREDENTIAL_UNMINTED", defects)
        if trust != "UNSIGNED_UNVERIFIED":
            defect(doc, "GREENWASH", "trust_status", "unsigned receipt must read UNSIGNED_UNVERIFIED (amber, never green)", defects)
    elif sig.get("status") == "SIGNED":
        if trust != "SIGNED_VERIFIED":
            defect(doc, "TRUST_MISMATCH", "trust_status", "signed receipt must read SIGNED_VERIFIED", defects)
    else:
        defect(doc, "BAD_SIGNATURE", "signature.status", "signature.status must be UNSIGNED or SIGNED", defects)


def check_typed_fact(doc, name, fact, defects):
    if not isinstance(fact, dict) or "status" not in fact:
        defect(doc, "FACT_UNTYPED", "training_facts." + name, "facts must be typed objects with a status", defects)
        return
    st = fact.get("status")
    if st not in FACT_STATUSES:
        defect(doc, "BAD_FACT_STATUS", "training_facts." + name, "status must be one of " + ",".join(sorted(FACT_STATUSES)), defects)
    if st in ("OBSERVED", "DERIVED") and not fact.get("evidence_ids"):
        defect(doc, "FACT_NO_EVIDENCE", "training_facts." + name, "OBSERVED/DERIVED facts require evidence_ids", defects)
    if st == "DERIVED" and not fact.get("formula"):
        defect(doc, "DERIVED_NO_FORMULA", "training_facts." + name, "DERIVED facts require their formula", defects)
    if st == "UNKNOWN" and not fact.get("reason"):
        defect(doc, "UNKNOWN_NO_REASON", "training_facts." + name, "UNKNOWN requires a reason, never a fabricated value", defects)


def check_artifact(doc, art, defects):
    if "path" not in art or "artifact_kind" not in art:
        defect(doc, "ARTIFACT_INCOMPLETE", "artifacts[]", "path and artifact_kind are mandatory", defects)
        return
    has_digest = art.get("sha256") and art.get("digest_source") and "locally_recomputed" in art
    has_err = bool(art.get("hash_error"))
    if not has_digest and not has_err:
        defect(doc, "ARTIFACT_NO_DIGEST", "artifacts[" + str(art.get("path")) + "]", "artifacts need a full digest set or an explicit hash_error", defects)
    if art.get("digest_source") == "HF_LFS_METADATA" and art.get("locally_recomputed"):
        defect(doc, "DIGEST_MISLABELED", "artifacts[" + str(art.get("path")) + "]", "provider digests must not claim locally_recomputed", defects)


def check_receipt(doc, defects):
    check_common(doc, defects)
    tier = doc.get("tier")
    legacy = (doc.get("discovery") or {}).get("legacy_receipt")
    if isinstance(legacy, dict) and legacy.get("promoted") is not False:
        defect(doc, "LEGACY_LAUNDERING", "discovery.legacy_receipt.promoted", "legacy claims must stay promoted=false (anti-laundering)", defects)
    for name, fact in (doc.get("training_facts") or {}).items():
        check_typed_fact(doc, name, fact, defects)
    if tier in ("T1", "T2"):
        for art in doc.get("artifacts") or []:
            check_artifact(doc, art, defects)
        if doc.get("artifact_inventory_status") == "NOT_STARTED":
            defect(doc, "INVENTORY_NOT_STARTED", "artifact_inventory_status", "NOT_STARTED is not done", defects)
    if tier == "T2":
        ev = doc.get("evidence") or []
        if not ev:
            defect(doc, "T2_NO_EVIDENCE", "evidence", "T2 requires at least one evidence object (T1 is the ceiling without it)", defects)
            return
        strong = [e for e in ev if e.get("subject_binding") in STRONG_BINDINGS]
        if not strong:
            defect(doc, "T2_NO_STRONG_BINDING", "evidence", "no strong subject binding; leads are not promotable", defects)
        for e in strong:
            if not e.get("dataset_revision") or e.get("dataset_revision") in ("main", "master"):
                defect(doc, "EVIDENCE_MOVING_REF", "evidence[" + str(e.get("evidence_id")) + "]", "evidence must pin an immutable dataset revision", defects)
            for key in ("evidence_id", "dataset_repo", "path", "sha256", "locator", "visibility"):
                if not e.get(key):
                    defect(doc, "EVIDENCE_INCOMPLETE", "evidence[" + str(e.get("evidence_id")) + "]." + key, "strong evidence objects require all fields", defects)


def validate_doc(doc):
    defects = []
    check_receipt(doc, defects)
    return defects


VALID_T1 = {
    "schema_version": "1.0-model-receipt",
    "receipt_id": "mr-a1b2c3d4e5f6",
    "subject": {"repo_id": "SZLHOLDINGS/selftest", "repo_type": "model", "visibility": "public", "revision": "deadbeef", "captured_at": "2026-11-24T00:00:00Z"},
    "generator": {"name": "selftest", "version": "1.0"},
    "tier": "T1",
    "status": "INCOMPLETE",
    "honesty": {"what": "inventory at pinned revision", "what_not": "no lineage claim"},
    "signature": {"status": "UNSIGNED", "reason": "OWNER_CREDENTIAL_UNMINTED"},
    "trust_status": "UNSIGNED_UNVERIFIED",
    "artifacts": [{"path": "a.npz", "size_bytes": 6014, "sha256": "8aca4d24c90d6159cbb2bb885c7a94822d715899437f58abe69fb5c9664a1381", "artifact_kind": "weights", "digest_source": "LOCAL_DOWNLOAD", "locally_recomputed": True}],
    "artifact_inventory_status": "PARTIAL",
    "training_facts": {"seed": {"value": 20260721, "status": "OBSERVED", "evidence_ids": ["ev-1"]}, "loss": {"value": None, "status": "UNKNOWN", "reason": "run-record search not started"}},
}

BAD_GREENWASH = dict(VALID_T1, **{"trust_status": "GREEN", "receipt_id": "mr-b2c3d4e5f6a1"})
BAD_UNTYPED = dict(VALID_T1, receipt_id="mr-c3d4e5f6a1b2", training_facts={"loss": 0.5})
BAD_T2_NOEV = {
    "schema_version": "1.0-model-receipt", "receipt_id": "mr-d4e5f6a1b2c3",
    "subject": VALID_T1["subject"], "generator": VALID_T1["generator"], "tier": "T2",
    "status": "COMPLETE", "honesty": {"what": "x", "what_not": "y"},
    "signature": {"status": "UNSIGNED", "reason": "OWNER_CREDENTIAL_UNMINTED"}, "trust_status": "UNSIGNED_UNVERIFIED",
    "artifacts": [], "evidence": []
}
BAD_PROVIDER_LABEL = dict(VALID_T1, receipt_id="mr-e5f6a1b2c3d4",
                          artifacts=[{"path": "a.npz", "size_bytes": 6014, "sha256": "8aca4d24c90d6159cbb2bb885c7a94822d715899437f58abe69fb5c9664a1381", "artifact_kind": "weights", "digest_source": "HF_LFS_METADATA", "locally_recomputed": True}])
BAD_UNKNOWN_NOREASON = dict(VALID_T1, receipt_id="mr-f6a1b2c3d4e5", training_facts={"seed": {"value": None, "status": "UNKNOWN"}})


def selftest():
    cases = [
        ("VALID_T1", VALID_T1, 0),
        ("BAD_GREENWASH", BAD_GREENWASH, 1),
        ("BAD_UNTYPED_FACT", BAD_UNTYPED, 1),
        ("BAD_T2_NO_EVIDENCE", BAD_T2_NOEV, 1),
        ("BAD_PROVIDER_DIGEST_LABEL", BAD_PROVIDER_LABEL, 1),
        ("BAD_UNKNOWN_NO_REASON", BAD_UNKNOWN_NOREASON, 1),
    ]
    failures = []
    for name, doc, expect_defects in cases:
        defects = validate_doc(doc)
        ok = (len(defects) > 0) == (expect_defects > 0)
        print(name, "defects=" + str(len(defects)), "OK" if ok else "SELFTEST_FAIL")
        if not ok:
            failures.append(name)
    print("SELFTEST " + ("PASS" if not failures else "FAIL:" + ",".join(failures)))
    return 0 if not failures else 1


def main(argv):
    if len(argv) < 2:
        print("usage: verify_receipts_ruler.py RECEIPT.json [...] | --selftest", file=sys.stderr)
        return 2
    if argv[1] == "--selftest":
        return selftest()
    total = 0
    for path in argv[1:]:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
        except Exception as exc:  # noqa: BLE001 - fail-closed IO handling
            print("DOC " + path + " IO_ERROR " + str(exc)[:200])
            total += 1
            continue
        defects = validate_doc(doc)
        for d in defects:
            print("DEFECT " + path + " " + d["receipt"] + " " + d["code"] + " @" + d["path"] + ": " + d["msg"])
        if not defects:
            print("RULER_VALIDATED " + path + " " + str(doc.get("receipt_id")))
        total += len(defects)
    print("RULER_VERDICT " + ("CLEAN" if total == 0 else "DEFECTS=" + str(total)))
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
