"""Step 6: for every verified sync pin that differs from the upstream default-branch head, ask GitHub
how they relate (compare API, per_page=1, metadata only). Missing pin sha => recorded as not found."""
import os, sys, json
from .common import *
ORG = "szl-holdings"; TOK = os.environ["GITHUB_TOKEN"]
RAW = RAW_ROOT
OUT = f"{RAW}/github/compare.json"
H = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

def pairs():
    det = json.load(open(f"{RAW}/github/repo_details.json"))["repos"]
    heads = {n: r["gql"]["defaultBranchRef"]["target"]["oid"] for n, r in det.items()}
    out = set()
    for fn in ("hf/hf_commits.json", "hf/hf_card_pins.json"):
        p = f"{RAW}/{fn}"
        if not os.path.exists(p): continue
        for k, v in json.load(open(p))["items"].items():
            items = ([v["pin"]] if v.get("pin") else []) + (v.get("pins") or [])
            for pin in items:
                if pin["repo"] in heads and pin["sha"] != heads[pin["repo"]]:
                    out.add((pin["repo"], pin["sha"], heads[pin["repo"]]))
    return sorted(out)

def main():
    st = json.load(open(OUT)) if os.path.exists(OUT) else {"pairs": {}}
    todo = [p for p in pairs() if st["pairs"].get(f"{p[0]}@{p[1]}...{p[2]}", {}).get("status", "error") == "error"]
    print("pairs to compare", len(todo), flush=True)
    for i, (repo, pin, head) in enumerate(todo):
        key = f"{repo}@{pin}...{head}"
        try:
            d = http_json(f"https://api.github.com/repos/{ORG}/{repo}/compare/{pin}...{head}?per_page=1", TOK, headers=H)
            st["pairs"][key] = {"status": d["status"], "ahead_by": d["ahead_by"], "behind_by": d["behind_by"], "observed_at": utcnow()}
        except HttpErr as e:
            st["pairs"][key] = {"status": "not_found" if e.code in (404, 422) else "error", "http": e.code, "observed_at": utcnow()}
        if i % 20 == 0: write_json(OUT, st); print(i, len(todo), flush=True)
    write_json(OUT, st); print("done", len(st["pairs"]))

if __name__ == "__main__":
    main()
