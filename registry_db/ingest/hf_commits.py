"""Step 3b: latest commit titles per HF repo (first page only) to extract the GitHub source pin
`szl-holdings/<repo>@<40-hex>` recorded by sync/publish commits. Titles only; no file content. Resumable."""
import os, sys, json, re
from .common import *
TOK = os.environ.get("HF_TOKEN_SZL") or os.environ["HF_TOKEN"]
RAW = os.path.join(RAW_ROOT, "hf")
OUT = f"{RAW}/hf_commits.json"
SEG = {"model": "models", "dataset": "datasets", "space": "spaces", "kernel": "kernels"}
PIN = re.compile(r"szl-holdings/([A-Za-z0-9_.-]+)@([0-9a-f]{40})")
PIN_SHORT = re.compile(r"szl-holdings/([A-Za-z0-9_.-]+)@([0-9a-f]{7,39})\b")

def main():
    inv = json.load(open(f"{RAW}/hf_inventory.json"))
    st = json.load(open(OUT)) if os.path.exists(OUT) else {"items": {}}
    n = 0
    for kind, seg in SEG.items():
        for it in inv["kinds"][kind]["items"]:
            key = f"{kind}:{it['id']}"
            if key in st["items"]: continue
            try:
                c = http_json(f"https://huggingface.co/api/{seg}/{it['id']}/commits/main", TOK)
                titles = [{"id": x["id"], "title": x["title"], "date": x.get("date")} for x in c[:50]]
                pin = None
                for t in titles:
                    m = PIN.search(t["title"])
                    if m: pin = {"repo": m.group(1), "sha": m.group(2), "commit": t["id"], "title": t["title"][:200], "date": t["date"]}; break
                st["items"][key] = {"head": c[0]["id"] if c else None, "n_commits_page": len(c), "pin": pin, "latest_title": titles[0]["title"][:200] if titles else None, "observed_at": utcnow()}
            except HttpErr as e:
                st["items"][key] = {"error": e.code, "msg": e.msg[:120], "observed_at": utcnow()}
            n += 1
            if n % 25 == 0: write_json(OUT, st); print(len(st["items"]), flush=True)
    st["completed_at"] = utcnow(); write_json(OUT, st); print("done", len(st["items"]))

if __name__ == "__main__":
    main()
