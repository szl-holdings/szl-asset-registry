"""Step 3c: extract card-declared GitHub source pins from each HF repo's README.md (card text, not weights).
Only the extracted (repo, sha, line number) is kept -- never the card body (many repos are private). Resumable."""
import os, sys, json, re, urllib.request, urllib.error
from .common import *
TOK = os.environ.get("HF_TOKEN_SZL") or os.environ["HF_TOKEN"]
RAW = os.path.join(RAW_ROOT, "hf")
OUT = f"{RAW}/hf_card_pins.json"
PFX = {"model": "", "dataset": "datasets/", "space": "spaces/", "kernel": "kernels/"}
PATS = [("observed_at_head", re.compile(r"szl-holdings/([A-Za-z0-9_.-]+)\)?\s+observed at HEAD\s+`([0-9a-f]{40})`")),
        ("authoring_source_blob", re.compile(r"github\.com/szl-holdings/([A-Za-z0-9_.-]+)/blob/([0-9a-f]{40})/")),
        ("repo_at_sha", re.compile(r"szl-holdings/([A-Za-z0-9_.-]+)@([0-9a-f]{40})"))]
MAX = 400000

def fetch(url):
    delay = 2
    for _ in range(6):
        try:
            from . import common; common._pace()
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOK, "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r: return r.read(MAX).decode("utf8", "replace"), r.status
        except urllib.error.HTTPError as e:
            if e.code in (404, 403, 401): return None, e.code
            if e.code == 429:
                time.sleep(float(e.headers.get("Retry-After", delay)) if e.headers else delay); delay = min(delay * 2, 120); continue
            raise
        except Exception: time.sleep(delay); delay = min(delay * 2, 60)
    return None, 0
import time

def main():
    inv = json.load(open(f"{RAW}/hf_inventory.json"))
    st = json.load(open(OUT)) if os.path.exists(OUT) else {"items": {}}
    n = 0
    for kind, pfx in PFX.items():
        for it in inv["kinds"][kind]["items"]:
            key = f"{kind}:{it['id']}"
            if key in st["items"]: continue
            text, code = fetch(f"https://huggingface.co/{pfx}{it['id']}/resolve/main/README.md")
            pins = []
            if text:
                lines = text.splitlines()
                for ln, line in enumerate(lines, 1):
                    for pname, rx in PATS:
                        for m in rx.finditer(line):
                            pins.append({"repo": m.group(1), "sha": m.group(2), "pattern": pname, "line": ln})
            seen = set(); uniq = []
            for p in pins:
                k = (p["repo"], p["sha"], p["pattern"])
                if k not in seen: seen.add(k); uniq.append(p)
            st["items"][key] = {"http": code, "has_readme": text is not None, "pins": uniq, "observed_at": utcnow()}
            n += 1
            if n % 25 == 0: write_json(OUT, st); print(len(st["items"]), flush=True)
    st["completed_at"] = utcnow(); write_json(OUT, st)
    its = st["items"].values()
    print("done", len(st["items"]), "readme", sum(1 for v in its if v["has_readme"]), "with pins", sum(1 for v in its if v["pins"]))

if __name__ == "__main__":
    main()
