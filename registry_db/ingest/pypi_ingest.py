"""Step 4: PyPI metadata for candidate project names found in szl-holdings repo references
(pyproject names, pip install lines, pypi.org links, nested pyprojects).
Uses the documented per-project JSON API with targeted lookups only (no crawling, no search, no HTML
pages -- those sit behind a bot challenge and are not bypassed). Paced >=1 req/s; 429 honoured.
NOTE: pypi.org/robots.txt lists /pypi/*/json under Disallow for crawlers; this job issues a bounded
list of single-project GETs from its own candidate list. Operators may disable with --no-pypi."""
import os, sys, json
from . import common
common.MIN_INTERVAL = 1.0
from .common import *
RAW = RAW_ROOT
OUT = f"{RAW}/pypi/pypi_inventory.json"
IS_SZL = ("github.com/szl-holdings", "szlholdings", "szl-holdings", "huggingface.co/szlholdings")

def candidates():
    refs = json.load(open(f"{RAW}/github/candidate_bindings.json"))["refs"]
    c = {}
    for r in refs:
        if r["kind"] == "pypi" and r["target_type"] == "project":
            c.setdefault(r["target_id"].lower().replace("_", "-"), []).append(r["evidence_path"])
    return c

def main():
    cands = candidates()
    st = json.load(open(OUT)) if os.path.exists(OUT) else {"projects": {}}
    for i, (name, ev) in enumerate(sorted(cands.items())):
        if name in st["projects"]: continue
        rec = {"candidate_evidence": sorted(set(ev))[:10], "observed_at": utcnow()}
        try:
            j = http_json(f"https://pypi.org/pypi/{name}/json", None)
            info = j["info"]; latest = info["version"]
            files = j.get("urls", [])
            blob = json.dumps([info.get("home_page"), info.get("project_urls"), info.get("author_email"), info.get("maintainer_email"), info.get("author"), info.get("summary")]).lower()
            rec.update({"exists": True, "name": info["name"], "latest": latest, "n_releases": len(j.get("releases", {})), "versions": sorted(j.get("releases", {}).keys())[-30:],
                        "summary": (info.get("summary") or "")[:200], "project_urls": info.get("project_urls"), "home_page": info.get("home_page"),
                        "author": info.get("author"), "license": info.get("license_expression") or info.get("license"), "yanked": info.get("yanked"),
                        "files": [{"filename": f["filename"], "sha256": f["digests"]["sha256"], "upload_time": f.get("upload_time_iso_8601"), "size": f.get("size"), "yanked": f.get("yanked")} for f in files],
                        "org_linked": any(k in blob for k in IS_SZL)})
        except HttpErr as e:
            rec.update({"exists": False, "http": e.code} if e.code == 404 else {"exists": None, "error": e.code, "msg": e.msg[:100]})
        st["projects"][name] = rec
        if i % 10 == 0: write_json(OUT, st); print(len(st["projects"]), "/", len(cands), flush=True)
    st["completed_at"] = utcnow(); write_json(OUT, st)
    ex = [n for n, r in st["projects"].items() if r.get("exists")]
    print("candidates", len(cands), "exist", len(ex), "org_linked", sum(1 for n in ex if st["projects"][n]["org_linked"]), "404", sum(1 for r in st["projects"].values() if r.get("exists") is False))

if __name__ == "__main__":
    main()
