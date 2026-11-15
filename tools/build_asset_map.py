#!/usr/bin/env python3
"""Build the HF asset -> GitHub source repo map. Fail-closed: unmapped stays unmapped.

Mapping precedence: overrides.json (curated, evidence-cited) > name match > README card match.
"""
import argparse, datetime, json, os, re, sys
import requests
GH = re.compile(r"github\.com/szl-holdings/([A-Za-z0-9._\-]+)")
def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())
def fam(rid):
    b = rid.split("/", 1)[1] if "/" in rid else rid
    lb = b.lower()
    if "laptop-lora" in lb or lb.endswith("-lora") or "lora-study" in lb:
        return "laptop-lora-training"
    if "candidate" in lb or lb.endswith("-20261104"):
        return "candidate-eval-20261104"
    if any(k in lb for k in ["receipt", "wave-log", "readiness-run", "test-result", "eval-run", "run-log", "release-asset", "artifact", "bom", "energy-attested"]):
        return "run-artifact-store"
    if any(k in lb for k in ["corpus", "doctrine", "thesis", "formula", "lean", "proof", "benchmark", "bench"]):
        return "corpus-benchmark"
    if any(k in lb for k in ["marketing", "brand", "showcase", "why-we-lead", "front-page"]):
        return "marketing-surface"
    return "other"
def load_overrides(path):
    """Load curated overrides.json; keys starting with '_' are documentation."""
    if not path or not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, str)}
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", required=True, help="org_audit.json (GitHub census)")
    ap.add_argument("--census", required=True, help="hf_census.json (Hub census)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--token", default=None, help="HF token (or HF_TOKEN env)")
    ap.add_argument("--overrides", default=None, help="overrides.json (default: alongside this script's repo root)")
    args = ap.parse_args()
    import os
    tok = args.token or os.environ.get("HF_TOKEN")
    audit = json.load(open(args.audit, encoding="utf-8"))
    census = json.load(open(args.census, encoding="utf-8"))
    repos = {a["name"] for a in audit}
    repo_norm = {norm(r): r for r in repos}
    ov = load_overrides(args.overrides or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "overrides.json"))
    H = {}
    if tok:
        H["Authorization"] = "Bearer " + tok
    H["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    def name_match(base):
        n = norm(base)
        if n in repo_norm:
            return repo_norm[n]
        for cut in ["sft", "laptoplora", "lora", "r1", "r2", "r3", "r4", "v1", "v2", "v3", "v4", "v5", "v10", "v11", "v18", "v54", "study5", "trained", "retrain"]:
            if n.endswith(norm(cut)) and len(n) > len(norm(cut)) + 2:
                n2 = n[: -len(norm(cut))]
                if n2 in repo_norm:
                    return repo_norm[n2]
        for rn, r in repo_norm.items():
            if (rn.startswith(n) or n.startswith(rn)) and abs(len(rn) - len(n)) <= 4:
                return r
        return None
    def card_fetch(kind, rid):
        pre = {"models": "", "datasets": "/datasets", "spaces": "/spaces"}[kind]
        try:
            r = requests.get("https://huggingface.co" + pre + "/" + rid + "/raw/main/README.md", headers=H, timeout=15)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        return ""
    out, stats = [], {"name": 0, "card": 0, "override": 0, "unmapped": 0}
    for kind in ("models", "datasets", "spaces"):
        for meta in census[kind]:
            rid = meta["id"]
            base = rid.split("/", 1)[1] if "/" in rid else rid
            rec = {"id": rid, "type": kind, "private": meta.get("private", False), "source_repo": None, "method": "unmapped"}
            r, method = None, "unmapped"
            if rid in ov and ov[rid] in repos:
                r, method = ov[rid], "override"
            if not r:
                nm = name_match(base)
                if nm:
                    r, method = nm, "name"
            if not r:
                hits = [h for h in GH.findall(card_fetch(kind, rid)) if h in repos]
                if hits:
                    from collections import Counter
                    r, method = Counter(hits).most_common(1)[0][0], "card"
            if r:
                rec["source_repo"] = r
                rec["method"] = method
            stats[method if method != "override" else "override"] += 1
            rec["family"] = fam(rid)
            out.append(rec)
    famcounts = {}
    for a in out:
        if a["method"] == "unmapped":
            famcounts[a["family"]] = famcounts.get(a["family"], 0) + 1
    mapped = stats["name"] + stats["card"] + stats["override"]
    doc = {"generated": datetime.date.today().isoformat(), "stats": stats, "coverage": {"total": len(out), "mapped": mapped, "unmapped": stats["unmapped"]}, "unmapped_family_counts": famcounts, "assets": out}
    json.dump(doc, open(args.out, "w", encoding="utf-8"), indent=1)
    print("mapped=%d (name=%d card=%d override=%d) unmapped=%d" % (mapped, stats["name"], stats["card"], stats["override"], stats["unmapped"]))
if __name__ == "__main__":
    main()
