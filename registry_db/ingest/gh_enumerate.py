"""Step 1: enumerate org repos three independent ways. Metadata only."""
import os, sys, json, subprocess
from .common import *
ORG = "szl-holdings"
TOK = os.environ["GITHUB_TOKEN"]
RAW = os.path.join(RAW_ROOT, "github")
H = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

def rest():
    pages = paginate_link(f"https://api.github.com/orgs/{ORG}/repos?type=all&per_page=100", TOK, headers=H)
    repos = [r for p in pages for r in p]
    return repos, len(pages)

def graphql():
    q = """query($org:String!,$after:String){organization(login:$org){repositories(first:100,after:$after,orderBy:{field:NAME,direction:ASC}){totalCount pageInfo{hasNextPage endCursor} nodes{databaseId nameWithOwner isPrivate visibility isArchived isFork isTemplate isMirror isEmpty}}}}"""
    after = None; nodes = []; total = None
    while True:
        d = http_json("https://api.github.com/graphql", TOK, method="POST", body={"query": q, "variables": {"org": ORG, "after": after}})
        if d.get("errors"):
            raise SystemExit("graphql errors: " + json.dumps(d["errors"])[:400])
        c = d["data"]["organization"]["repositories"]
        total = c["totalCount"]; nodes += c["nodes"]
        if not c["pageInfo"]["hasNextPage"]: break
        after = c["pageInfo"]["endCursor"]
    return nodes, total

def ghcli():
    r = subprocess.run(["gh", "repo", "list", ORG, "--limit", "5000", "--json", "name,nameWithOwner,visibility,isArchived,isFork,isEmpty,id"], capture_output=True, text=True)
    if r.returncode: raise SystemExit("gh failed: " + r.stderr[:300])
    return json.loads(r.stdout)

if __name__ == "__main__":
    ts = utcnow()
    rr, npages = rest(); write_json(f"{RAW}/enum_rest.json", {"observed_at": ts, "pages": npages, "repos": rr})
    gq, gtotal = graphql(); write_json(f"{RAW}/enum_graphql.json", {"observed_at": ts, "totalCount": gtotal, "nodes": gq})
    gc = ghcli(); write_json(f"{RAW}/enum_ghcli.json", {"observed_at": ts, "repos": gc})
    a = {r["full_name"] for r in rr}; b = {n["nameWithOwner"] for n in gq}; c = {n["nameWithOwner"] for n in gc}
    print("REST", len(rr), "pages", npages, "unique", len(a))
    print("GraphQL nodes", len(gq), "totalCount", gtotal, "unique", len(b))
    print("gh repo list", len(gc), "unique", len(c))
    print("REST-GQL", sorted(a-b), "GQL-REST", sorted(b-a), "REST-gh", sorted(a-c), "gh-REST", sorted(c-a))
    from collections import Counter
    print(Counter(r["visibility"] for r in rr)); print("archived", sum(r["archived"] for r in rr), "fork", sum(r["fork"] for r in rr), "template", sum(r["is_template"] for r in rr), "empty(size0)", sum(1 for r in rr if r["size"]==0))
