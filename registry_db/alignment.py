"""Alignment classification (pure functions; fixtures in tests/test_registry_db_alignment.py).

States (uppercase, never NULL): ALIGNED | BEHIND | DRIFTED | UNTRACEABLE | UNKNOWN

Rules (strict on purpose -- only a machine-verifiable pin may yield ALIGNED / BEHIND / DRIFTED):
  grade verified_pin  (HF sync/publish commit title, or szl-source-binding.json with a 40-hex revision)
      pin == upstream head                 -> ALIGNED
      upstream head ahead of pin           -> BEHIND
      pin ahead of head / diverged         -> DRIFTED  (Chakana fix #2)
      pin sha not found upstream           -> UNTRACEABLE
      comparison not performed             -> UNKNOWN
  grade declared      (card/asset-map/pyproject/wrangler declares a source repo; may carry a pin)
      -> UNKNOWN, reason records the comparison (declared pin is a claim, not a build record)
  grade referenced    (text mention only)  -> UNKNOWN
  no binding at all, asset is a built artifact (hf model/dataset/space/kernel, pypi, worker, pages)
      -> UNTRACEABLE
  asset types that are not built from source (buckets, collections, zones, dns, d1, r2, kv, tunnels,
  routes, access apps, worker domains) -> UNKNOWN, reason "no source build by design"
  github_repo -> ALIGNED, reason "GitHub default branch is the source authority"

Lifecycle (Chakana fix #3): PRESENT | ABSENT | COVERAGE_GAP
  ABSENT only after a successful authoritative listing of that type.
  Private/unreadable, or a listing that did not complete, is COVERAGE_GAP, never ABSENT.
"""
ALIGNMENT_STATES = ("ALIGNED", "BEHIND", "DRIFTED", "UNTRACEABLE", "UNKNOWN")
LIFECYCLES = ("PRESENT", "ABSENT", "COVERAGE_GAP")
GRADE_RANK = {"verified_pin": 3, "declared": 2, "referenced": 1}
STATE_RANK = {"ALIGNED": 4, "BEHIND": 3, "DRIFTED": 2, "UNKNOWN": 1, "UNTRACEABLE": 0}
BUILT = {"hf_model", "hf_dataset", "hf_space", "hf_kernel", "pypi_project", "cf_worker", "cf_pages_project"}
NO_SOURCE_BY_DESIGN = {"hf_bucket", "hf_collection", "cf_zone", "cf_dns_record", "cf_route", "cf_d1", "cf_r2", "cf_kv", "cf_tunnel", "cf_access_app", "cf_worker_domain"}

def norm_alignment(s):
    if s is None:
        return "UNKNOWN"
    u = str(s).upper()
    return u if u in ALIGNMENT_STATES else "UNKNOWN"

def norm_lifecycle(s):
    if not s:
        return "PRESENT"
    u = str(s).upper()
    return {"PRESENT": "PRESENT", "ABSENT": "ABSENT", "COVERAGE_GAP": "COVERAGE_GAP"}.get(u, "PRESENT")

def norm_visibility(s):
    if not s or str(s).lower() == "unknown":
        return "UNKNOWN"
    return s  # public / private / internal stay as stored in 0001 (lowercase)

def comparison_from_compare_status(status):
    """GitHub compare API status for base=pin ... head=upstream_head."""
    return {"identical": "identical", "ahead": "upstream_ahead", "behind": "pin_ahead", "diverged": "diverged"}.get(status, "not_compared")

def classify_binding(grade, pin, upstream_head, comparison, pin_found=True):
    if grade == "verified_pin":
        if pin is None:
            return "UNKNOWN", "verified-pin binding without a pin value"
        if not pin_found:
            return "UNTRACEABLE", f"pin {pin[:8]} not found in upstream repository"
        if pin == upstream_head or comparison == "identical":
            return "ALIGNED", f"sync pin {pin[:8]} == upstream head {str(upstream_head)[:8]}"
        if comparison == "upstream_ahead":
            return "BEHIND", f"sync pin {pin[:8]} is an ancestor of upstream head {str(upstream_head)[:8]}"
        if comparison in ("pin_ahead", "diverged"):
            return "DRIFTED", f"verified pin {pin[:8]} is {comparison.replace('_', ' ')} relative to default-branch head {str(upstream_head)[:8]}"
        return "UNKNOWN", f"sync pin {pin[:8]} not compared with upstream head"
    if grade == "declared":
        if pin:
            return "UNKNOWN", f"declared source only; declared pin {str(pin)[:8]} comparison={comparison}"
        return "UNKNOWN", "declared source repository, no sha pin recorded"
    if grade == "referenced":
        return "UNKNOWN", "referenced in text only; not verified as the source"
    return "UNKNOWN", "unrecognised binding grade"

def classify_asset(asset_type, bindings, lifecycle=None):
    """bindings: list of dicts with grade, alignment_state, alignment_reason, upstream_asset_id.
    Returns (state, reason, best_upstream_id). States are uppercase.
    Ruling (a): an ABSENT asset cannot be compared, so alignment is UNKNOWN
    (never a carried-over UNTRACEABLE from its last live binding)."""
    if norm_lifecycle(lifecycle) == "ABSENT":
        return "UNKNOWN", "ABSENT: no current revision; last known from prior observation", None
    if asset_type == "github_repo":
        return "ALIGNED", "GitHub default branch is the source authority", None
    if not bindings:
        if asset_type in BUILT:
            return "UNTRACEABLE", "no source repository binding found (no sync pin, source-binding file, card mapping, config or reference)", None
        return "UNKNOWN", "no source build by design for this asset type", None
    def key(b):
        st = norm_alignment(b["alignment_state"])
        return (GRADE_RANK.get(b["grade"], 0), STATE_RANK[st])
    best = sorted(bindings, key=key, reverse=True)[0]
    return norm_alignment(best["alignment_state"]), best["alignment_reason"], best["upstream_asset_id"]

def version_tuple(v):
    """Conservative PEP 440 subset: dotted ints with optional pre/post/dev suffix kept as tail. None if unparsable."""
    import re
    m = re.match(r"^(\d+(?:\.\d+)*)((?:a|b|rc|\.post|\.dev)\d*)?$", v or "")
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).split(".")), m.group(2) or ""

def compare_versions(pin_v, head_v):
    a, b = version_tuple(pin_v), version_tuple(head_v)
    if a is None or b is None:
        return "not_compared"
    if a == b:
        return "identical"
    return "upstream_ahead" if b[0] > a[0] or (b[0] == a[0] and a[1] and not b[1]) else "pin_ahead" if a[0] > b[0] else "diverged"

def vanished_lifecycle(asset_type, coverage_by_type):
    """Chakana fix #3: ABSENT only when the type's listing this run was authoritative; otherwise COVERAGE_GAP."""
    cov = coverage_by_type.get(asset_type) or {}
    if cov.get("listing_authoritative"):
        return "ABSENT"
    return "COVERAGE_GAP"

def pep503_name(name):
    """PEP 503 normalized project name (used as PyPI external_id; PyPI has no numeric id)."""
    import re
    return re.sub(r"[-_.]+", "-", (name or "").strip()).lower()
