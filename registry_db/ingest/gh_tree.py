"""Step 2c: recursive tree listing per repo (names only) to find nested packaging files and
wrangler/pyproject configs in monorepos; fetches blob text only for nested wrangler.*/pyproject.toml
of PUBLIC repos. Resumable."""
import os, sys, json, base64, re
from .common import *
ORG = "szl-holdings"; TOK = os.environ["GITHUB_TOKEN"]
RAW = os.path.join(RAW_ROOT, "github")
OUT = f"{RAW}/repo_trees.json"
H = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
INTEREST = re.compile(r"(^|/)(pyproject\.toml|setup\.py|package\.json|wrangler\.(toml|jsonc|json)|Dockerfile|requirements\.txt|Cargo\.toml|go\.mod|action\.ya?ml)$")
NEST_FETCH = re.compile(r"(^|/)(pyproject\.toml|wrangler\.(toml|jsonc|json))$")
MIG = re.compile(r"(^|/)(migrations?|drizzle)/[^/]+\.(sql|ts)$")

def main():
    det = json.load(open(f"{RAW}/repo_details.json"))["repos"]
    st = json.load(open(OUT)) if os.path.exists(OUT) else {"repos": {}}
    for i, (name, rec) in enumerate(sorted(det.items())):
        if name in st["repos"]: continue
        g = rec["gql"]; sha = g["defaultBranchRef"]["target"]["oid"]
        t = http_json(f"https://api.github.com/repos/{ORG}/{name}/git/trees/{sha}?recursive=1", TOK, headers=H)
        paths = [e for e in t.get("tree", []) if e["type"] == "blob"]
        interesting = [e["path"] for e in paths if INTEREST.search(e["path"])]
        migs = [e["path"] for e in paths if MIG.search(e["path"])]
        texts = {}
        if not g["isPrivate"]:
            for e in paths:
                if NEST_FETCH.search(e["path"]) and "/" in e["path"] and e["path"].count("/") <= 4 and e.get("size", 0) < 200000 and len(texts) < 40 and "node_modules" not in e["path"]:
                    b = http_json(f"https://api.github.com/repos/{ORG}/{name}/git/blobs/{e['sha']}", TOK, headers=H)
                    try: texts[e["path"]] = base64.b64decode(b["content"]).decode("utf8", "replace")
                    except Exception: pass
        st["repos"][name] = {"head": sha, "truncated": t.get("truncated", False), "file_count": len(paths), "interesting": interesting, "migrations": migs, "nested_text": texts, "private": g["isPrivate"], "observed_at": utcnow()}
        if i % 10 == 0:
            write_json(OUT, st); print(f"{len(st['repos'])}/{len(det)}", flush=True)
    st["completed_at"] = utcnow(); write_json(OUT, st)
    print("done", len(st["repos"]), "truncated:", [n for n, r in st["repos"].items() if r["truncated"]])

if __name__ == "__main__":
    main()
