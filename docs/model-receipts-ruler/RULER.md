# Estate Model-Receipts Ruler v1.0

Status: PROPOSE-ONLY (this PR). Adopted 2026-11-22 by the model-receipts council lap
(Kimi governing + Astra + Sol + Mistral-tester; advisory seats, Vibe final adjudicator);
revalidated controls measured 2026-11-24 (see controls-revalidation-20261124.md).

This ruler defines the honest bar for "a model fully showcasing the right receipts"
in the SZLHOLDINGS HF org, per the estate fail-closed doctrine:
UNKNOWN is a first-class value; nothing is ever fabricated; unverified is never green.

## 1. The three ORTHOGONAL axes (never collapse them)

- **Tier** — depth of evidence: T0 / T1 / T2 (below).
- **Completion** — whether the tier's mandatory fields and checks are complete.
  A receipt with honestly-closed UNKNOWN fields can be COMPLETE.
- **Trust** — cryptographic status. While the owner signing credential is unminted,
  every trust_status value is **UNSIGNED_UNVERIFIED**, rendered **amber, never green**.
  A sha256 is a digest, not a signature. Self-hashes go in the external manifest.

## 2. Common envelope (mandatory for EVERY tier)

```text
schema_version            e.g. "1.0-model-receipt"
receipt_id                stable id (suggested "mr-" + sha256(subject)[:12])
subject:
  repo_id                 e.g. "SZLHOLDINGS/qantu"
  repo_type               "model" | "dataset" | "space"
  visibility              "public" | "private"
  revision                FULL HF commit SHA at capture (the tamper anchor while unsigned)
  captured_at             ISO-8601
generator: { name, version }
tier                      "T0" | "T1" | "T2"
status                    COMPLETE | INCOMPLETE | CLASSIFIED_INCOMPLETE | BLOCKED | CONFLICT
honesty:
  what / what_not / limitations / unknowns
signature: { status: "UNSIGNED", reason: "OWNER_CREDENTIAL_UNMINTED" }
trust_status: "UNSIGNED_UNVERIFIED"
```

## 3. Tiers

### T0 — Classified (never "done")
Repo inventoried and classified; no complete artifact receipt can be asserted.
Mandatory: discovery (receipt paths inspected + parse status), artifact_inventory_status,
evidence_search_status, blocking_reasons. Partial material may be retained but never rounded up.

### T1 — Artifact snapshot
Complete, pinned statement of the bytes currently published.
Mandatory: artifact_scope; artifacts[] with EVERY in-scope artifact resolved:
path, size_bytes, sha256, artifact_kind, digest_source (LOCAL_DOWNLOAD | HF_LFS_METADATA),
locally_recomputed (bool), hash_error (explicit when applicable). HF-supplied LFS digests are
allowed but MUST be labeled (digest_source=HF_LFS_METADATA, locally_recomputed=false).
Training facts are TYPED values (below) with honest UNKNOWNs. Evidence search must be
COMPLETED, NOT_APPLICABLE, or explicitly BLOCKED — NOT_STARTED is not done.

### T2 — Evidence-bound provenance
Everything in T1 PLUS a strong, immutable run/transformation binding:
lineage {operation: TRAIN|FINETUNE|MERGE|QUANTIZE|CONVERT|PACKAGE|UNKNOWN, run_id,
code_revision, data_revision, config_digest, base_artifacts}, training_facts (typed),
evidence[] objects (evidence_id, dataset_repo, dataset_revision — IMMUTABLE, not main —
path, sha256, locator, visibility, subject_binding), evaluation provenance.
STRONG BINDINGS: exact output-artifact digest match, or an immutable run ID
content-connected to both sides. Name + approximate timestamp + similar loss = lead only.
**T2 does not require every fact known and does not require a rerun. It requires real
subject-bound evidence. Without it, T1 is the ceiling.**

## 4. Typed fact values (ALL facts, no bare values)

```json
{ "value": 123, "status": "OBSERVED", "evidence_ids": ["ev-1"], "reason": null }
```

Allowed status: OBSERVED | DERIVED | REPORTED_UNVERIFIED | UNKNOWN | NOT_APPLICABLE | CONFLICT.
- OBSERVED/DERIVED require non-empty evidence_ids; DERIVED also requires its formula.
- UNKNOWN requires a reason. Never a fabricated zero or float.
- CONFLICT preserves competing claims and BLOCKS promotion of the affected assertion.

## 5. Failure modes that this ruler exists to prevent

1. **Retroactive provenance laundering** — hashing today's artifact and finding a
   similarly-named historical log does NOT prove the log produced the artifact.
   A polished 419-receipt dashboard that quietly overstates lineage (a "false T2")
   is worse than persistent UNKNOWN.
2. **Green-washing** — any display of an unsigned receipt as verified/green.
3. **Legacy laundering** — legacy claims are preserved verbatim (claims_promoted=false)
   and re-adjudicated individually before promotion into authoritative fields.

## 6. "Done" gate (per repo)

A model counts receipt-done only if: (1) complete T1 or T2; (2) artifact inventory and
digest methods unambiguous; (3) every promoted claim evidenced or explicitly UNKNOWN /
NOT_APPLICABLE; (4) evidence recovery actually performed; (5) no unresolved conflict or
validator error; (6) JSON receipt, README rendering, and external index agree;
(7) it still displays UNSIGNED—UNVERIFIED (until the owner credential is minted).

## 7. Scoreboard (never one green percentage)

Report SEPARATE counts: classified | T1_complete | T2_complete | locally_hashed |
provider_digest_only | published | blocked | conflicted.

## 8. Publication policy

Wave-logs dataset is the evidence/index layer (PRIMARY). The model repo is the
presentation layer: a model is "published" when `RECEIPTS/BASELINE_RECEIPT.json` and its
generated README receipts-section land as ONE commit, with pre/post revisions, original
README hash, receipt content hash, and rollback records in wave-logs. Rollback = new
revert commit, never force-push, never history deletion. NO big-bang: validated tranches
only; 5-repo stratified pilots before each new class; 10-repo publication batches.
GitHub remains source of truth: schema, validator, and renderer generate from
GitHub-controlled code; direct HF publications must be backported in the same tranche.

## 9. Tranche order (adopted)

All-419 metadata freeze -> 11 DEEP revalidation controls -> 20 SHALLOW -> 16 NONE ->
107 receipts-dir -> 265 other-named. Batches bounded by aggregate download bytes.
Systemic schema/digest/privacy/rendering defect halts the publication batch;
a repo-specific failure stays visible in the denominator.

## 10. Target data model (structural improvement, adopted direction)

A typed, content-addressed evidence graph (nodes: repo@revision, artifact@sha256,
run/transformation@evidence-revision, receipt@content-hash; edges record binding type).
Per-model receipts, README sections, and the org dashboard are VIEWS generated from the
graph. Shared LFS objects are hashed once. Signatures and corrections become superseding
attestations rather than rewrites. Operation-specific provenance (TRAIN vs FINETUNE vs
MERGE vs QUANTIZE vs CONVERT vs PACKAGE) replaces forced training facts on non-training repos.

## Adoption provenance

- 2026-11-22 council lap (4 seats healthy, receipts in wave-logs mesh/2026-11-22/ouroboros/model-receipts-lap1/):
  419/419 classified (11 DEEP / 20 SHALLOW / 107 / 265 / 16), B0 ledger, 20 T1 candidates,
  16 absence markers, 17-file readback-verified publish + correction-of-record.
- 2026-11-24 web-seat control revalidation: 11/11 controls re-measured read-only
  (this PR, controls-revalidation-20261124.md), one digest independently corroborated
  via HF LFS metadata (receipt_agent.npz, 8aca4d24..., cross-repo pointer match).
- HONEST GATE CLEARED BY MEASUREMENT (2026-11-24): the validator selftest was
  executed on the owner device, 6/6 cases OK, SELFTEST PASS
  (selftest-receipt-20261124.md in this directory; advisory GO W27T2 Q2).
