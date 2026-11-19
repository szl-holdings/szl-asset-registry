import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from registry_db.ingest import build_snapshot

def build(raw_dir, out_dir):
    os.environ["REGISTRY_RAW_DIR"] = raw_dir
    build_snapshot.RAW = raw_dir
    out = os.path.join(out_dir, "snapshot.json"); build_snapshot.main(out, quiet=True)
    with open(out) as f: return json.load(f)
