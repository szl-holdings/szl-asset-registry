"""Step 3: HF Hub org SZLHOLDINGS metadata (models, datasets, spaces, kernels, buckets, collections).
Read-only GET listing; no files/weights downloaded. Count cross-check vs org overview num* fields."""
import os, sys, json
from .common import *
ORG = "SZLHOLDINGS"
TOK = os.environ.get("HF_TOKEN_SZL") or os.environ["HF_TOKEN"]
RAW = os.path.join(RAW_ROOT, "hf")
EXP = ["sha", "private", "lastModified", "createdAt", "tags", "gated", "disabled", "downloads", "likes", "cardData", "library_name", "pipeline_tag", "gguf", "inference"]
SPACE_EXP = ["sha", "private", "lastModified", "createdAt", "tags", "sdk", "runtime", "cardData", "likes", "disabled"]
KERNEL_EXP = ["sha", "private", "lastModified", "createdAt", "tags", "cardData", "downloads", "likes"]
DS_EXP = ["sha", "private", "lastModified", "createdAt", "tags", "gated", "disabled", "downloads", "likes", "cardData", "description"]
KINDS = {"model": ("models", EXP), "dataset": ("datasets", DS_EXP), "space": ("spaces", SPACE_EXP), "kernel": ("kernels", KERNEL_EXP)}

def listing(path, exp=None, extra=""):
    q = f"https://huggingface.co/api/{path}?author={ORG}&limit=1000{extra}"
    if exp: q += "".join(f"&expand[]={e}" for e in exp)
    return [x for p in paginate_link(q, TOK) for x in p]

def main():
    ts = utcnow(); out = {"observed_at": ts, "org": ORG, "kinds": {}}
    ov = http_json(f"https://huggingface.co/api/organizations/{ORG}/overview", TOK)
    out["overview_counts"] = {k: ov.get(k) for k in ["numModels", "numDatasets", "numSpaces", "numKernels", "numBuckets", "numPapers"]}
    for kind, (path, exp) in KINDS.items():
        items = listing(path, exp)
        ids = [i["id"] for i in items]
        out["kinds"][kind] = {"count": len(items), "unique": len(set(ids)), "private": sum(1 for i in items if i.get("private")), "items": items}
        print(kind, len(items), "unique", len(set(ids)), "private", out["kinds"][kind]["private"], flush=True)
        write_json(f"{RAW}/hf_inventory.json", out)
    b = http_json(f"https://huggingface.co/api/buckets/{ORG}", TOK)
    out["kinds"]["bucket"] = {"count": len(b), "unique": len({x['id'] for x in b}), "private": sum(1 for x in b if x.get("private")), "items": b}
    pages = paginate_link(f"https://huggingface.co/api/collections?owner={ORG}&limit=100", TOK)
    cols = [c for p in pages for c in p]
    out["kinds"]["collection"] = {"count": len(cols), "unique": len({c['slug'] for c in cols}), "private": sum(1 for c in cols if c.get("private")), "items": cols}
    print("bucket", len(b), "collection", len(cols))
    write_json(f"{RAW}/hf_inventory.json", out)
    ovm = {"model": "numModels", "dataset": "numDatasets", "space": "numSpaces", "kernel": "numKernels", "bucket": "numBuckets"}
    for k, f in ovm.items():
        print(f"{k}: listed={out['kinds'][k]['count']} overview={out['overview_counts'][f]}")

if __name__ == "__main__":
    main()
