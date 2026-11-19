"""Alignment classification (pure functions; fixtures in tests/test_registry_db_alignment.py).

States: aligned | behind | untraceable | unknown   (UNKNOWN is explicit, never NULL)

Rules (strict on purpose -- only a machine-verifiable pin may yield aligned/behind):
  grade verified_pin  (HF sync/publish commit title "szl-holdings/<repo>@<40sha>")
      pin == upstream head                 -> aligned
      upstream head ahead of pin           -> behind
      pin ahead of head / diverged         -> unknown (pin not an ancestor of default branch)
      pin sha not found upstream           -> untraceable
      comparison not performed             -> unknown
  grade declared      (card/asset-map/pyproject/wrangler declares a source repo; may carry a pin)
      -> unknown, reason records the comparison (declared pin is a claim, not a build record)
  grade referenced    (text mention only)  -> unknown
  no binding at all, asset is a built artifact (hf model/dataset/space/kernel, pypi, worker)
      -> untraceable
  asset types that are not built from source (buckets, collections, zones, dns, d1, r2, kv, tunnels,
  routes, access apps) -> unknown, reason "no source build by design"
  github_repo -> aligned, reason "GitHub default branch is the source authority"
"""
GRADE_RANK = {"verified_pin": 3, "declared": 2, "referenced": 1}
BUILT = {"hf_model", "hf_dataset", "hf_space", "hf_kernel", "pypi_project", "cf_worker"}
NO_SOURCE_BY_DESIGN = {"hf_bucket", "hf_collection", "cf_zone", "cf_dns_record", "cf_route", "cf_d1", "cf_r2", "cf_kv", "cf_tunnel", "cf_access_app", "cf_worker_domain"}

def comparison_from_compare_status(status):
    """GitHub compare API status for base=pin ... head=upstream_head."""
    return {"identical": "identical", "ahead": "upstream_ahead", "behind": "pin_ahead", "diverged": "diverged"}.get(status, "not_compared")

def classify_binding(grade, pin, upstream_head, comparison, pin_found=True):
    if grade == "verified_pin":
        if pin is None: return "unknown", "verified-pin binding without a pin value"
        if not pin_found: return "untraceable", f"pin {pin[:8]} not found in upstream repository"
        if pin == upstream_head or comparison == "identical": return "aligned", f"sync pin {pin[:8]} == upstream head {str(upstream_head)[:8]}"
        if comparison == "upstream_ahead": return "behind", f"sync pin {pin[:8]} is an ancestor of upstream head {str(upstream_head)[:8]}"
        if comparison in ("pin_ahead", "diverged"): return "unknown", f"sync pin {pin[:8]} is {comparison.replace('_', ' ')} relative to default-branch head {str(upstream_head)[:8]}"
        return "unknown", f"sync pin {pin[:8]} not compared with upstream head"
    if grade == "declared":
        if pin: return "unknown", f"declared source only; declared pin {pin[:8]} comparison={comparison}"
        return "unknown", "declared source repository, no sha pin recorded"
    if grade == "referenced":
        return "unknown", "referenced in text only; not verified as the source"
    return "unknown", "unrecognised binding grade"

def classify_asset(asset_type, bindings):
    """bindings: list of dicts with grade, alignment_state, alignment_reason, upstream_asset_id.
    Returns (state, reason, best_upstream_id)."""
    if asset_type == "github_repo":
        return "aligned", "GitHub default branch is the source authority", None
    if not bindings:
        if asset_type in BUILT: return "untraceable", "no source repository binding found (no sync pin, card mapping, config or reference)", None
        return "unknown", "no source build by design for this asset type", None
    def key(b):
        st = {"aligned": 3, "behind": 2, "unknown": 1, "untraceable": 0}[b["alignment_state"]]
        return (GRADE_RANK[b["grade"]], st)
    best = sorted(bindings, key=key, reverse=True)[0]
    return best["alignment_state"], best["alignment_reason"], best["upstream_asset_id"]

def version_tuple(v):
    """Conservative PEP 440 subset: dotted ints with optional pre/post/dev suffix kept as tail. None if unparsable."""
    import re
    m = re.match(r"^(\d+(?:\.\d+)*)((?:a|b|rc|\.post|\.dev)\d*)?$", v or "")
    if not m: return None
    return tuple(int(x) for x in m.group(1).split(".")), m.group(2) or ""

def compare_versions(pin_v, head_v):
    a, b = version_tuple(pin_v), version_tuple(head_v)
    if a is None or b is None: return "not_compared"
    if a == b: return "identical"
    return "upstream_ahead" if b[0] > a[0] or (b[0] == a[0] and a[1] and not b[1]) else "pin_ahead" if a[0] > b[0] else "diverged"
