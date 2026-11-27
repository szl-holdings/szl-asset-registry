"""Step 2: per-repo metadata via GraphQL (batched) + git ls-remote head cross-check.
Reads file *contents* (README/packaging/workflows) only for PUBLIC repos; private repos
get metadata + file *names* only (privacy: private content is never copied into the snapshot).
Resumable: checkpoints raw/github/repo_details.json after every batch."""
import os, sys, json, re, subprocess
from .common import *
ORG = "szl-holdings"; TOK = os.environ["GITHUB_TOKEN"]
RAW = os.path.join(RAW_ROOT, "github")
OUT = f"{RAW}/repo_details.json"
MAXTXT = 60000
PKG_FILES = ["pyproject.toml", "setup.py", "setup.cfg", "package.json", "wrangler.toml", "wrangler.jsonc", "wrangler.json", "Dockerfile", "requirements.txt", "Cargo.toml", "go.mod", "pnpm-workspace.yaml", "lerna.json", "action.yml", "action.yaml"]

def frag(i, name, content):
    blobs = ""
    if content:
        for j, f in enumerate(["README.md", "pyproject.toml", "package.json", "wrangler.toml", "wrangler.jsonc", "wrangler.json", "setup.py"]):
            blobs += f' b{j}:object(expression:"HEAD:{f}"){{... on Blob{{byteSize isTruncated text}}}}'
        wf = ' wf:object(expression:"HEAD:.github/workflows"){... on Tree{entries{name type object{... on Blob{byteSize text}}}}}'
    else:
        wf = ' wf:object(expression:"HEAD:.github/workflows"){... on Tree{entries{name type}}}'
    return f'''r{i}:repository(owner:"{ORG}",name:"{name}"){{
 databaseId nameWithOwner visibility isPrivate isArchived isFork isTemplate isMirror isEmpty description homepageUrl createdAt updatedAt pushedAt diskUsage
 primaryLanguage{{name}} licenseInfo{{spdxId name}} repositoryTopics(first:50){{nodes{{topic{{name}}}}}}
 defaultBranchRef{{name target{{... on Commit{{oid committedDate}}}}}}
 openPRs:pullRequests(states:OPEN){{totalCount}} allPRs:pullRequests{{totalCount}} openIssues:issues(states:OPEN){{totalCount}} allIssues:issues{{totalCount}}
 releases{{totalCount}} latestRelease{{tagName publishedAt}} tags:refs(refPrefix:"refs/tags/"){{totalCount}} branches:refs(refPrefix:"refs/heads/"){{totalCount}}
 root:object(expression:"HEAD:"){{... on Tree{{entries{{name type}}}}}}{wf}{blobs}
}}'''

def ls_remote(name):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    r = subprocess.run(["git", "-c", "credential.helper=!gh auth git-credential", "ls-remote", f"https://github.com/{ORG}/{name}.git", "HEAD", "refs/heads/*"], capture_output=True, text=True, env=env, timeout=90)
    if r.returncode: return {"error": r.stderr.strip()[:200]}
    heads = {}; head = None
    for ln in r.stdout.splitlines():
        sha, ref = ln.split("\t")
        if ref == "HEAD": head = sha
        else: heads[ref[len("refs/heads/"):]] = sha
    return {"HEAD": head, "heads": heads}

def main():
    enum = json.load(open(f"{RAW}/enum_rest.json"))["repos"]
    byname = {r["name"]: r for r in enum}
    state = json.load(open(OUT)) if os.path.exists(OUT) else {"repos": {}}
    todo = [n for n in sorted(byname) if n not in state["repos"]]
    print("todo", len(todo), flush=True)
    B = 2
    for s in range(0, len(todo), B):
        batch = todo[s:s + B]
        q = "query{" + " ".join(frag(i, n, not byname[n]["private"]) for i, n in enumerate(batch)) + " rateLimit{remaining resetAt cost}}"
        d = http_json("https://api.github.com/graphql", TOK, method="POST", body={"query": q})
        if d.get("errors") and not d.get("data"):
            raise SystemExit(json.dumps(d["errors"])[:500])
        for i, n in enumerate(batch):
            node = (d.get("data") or {}).get(f"r{i}")
            rec = {"gql": node, "gql_errors": [e for e in d.get("errors", []) if e.get("path", [""])[0] == f"r{i}"], "rest": byname[n], "observed_at": utcnow()}
            rec["ls_remote"] = ls_remote(n)
            state["repos"][n] = rec
        write_json(OUT, state)
        print(f"{len(state['repos'])}/{len(byname)} remaining_rate={d['data']['rateLimit']['remaining']}", flush=True)
    state["completed_at"] = utcnow()
    write_json(OUT, state)

if __name__ == "__main__":
    main()
