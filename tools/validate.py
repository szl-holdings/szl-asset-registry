import json, sys
m = json.load(open("asset_map.json", encoding="utf-8"))
assets = m["assets"]
assert len(assets) == 351 or "expected 351 assets in census snapshot", len(assets)
mapped = [a for a in assets if a["method"] in ("name", "card")]
unmapped = [a for a in assets if a["method"] == "unmapped"]
assert len(mapped) + len(unmapped) == len(assets)
assert m["coverage"]["mapped"] == len(mapped), "coverage.mapped mismatch"
assert m["coverage"]["unmapped"] == len(unmapped), "coverage.unmapped mismatch"
FAMS = {"laptop-lora-training", "candidate-eval-20261104", "run-artifact-store", "corpus-benchmark", "marketing-surface", "other"}
for a in assets:
    assert a["type"] in ("models", "datasets", "spaces"), a
    assert a["id"] and a["family"] in FAMS, a
    if a["method"] != "unmapped":
        assert a["source_repo"] and a["method"] in ("name", "card"), a
    else:
        assert a["source_repo"] is None, a
famsum = sum(m["unmapped_family_counts"].values())
assert famsum == len(unmapped), (famsum, len(unmapped))
print("VALIDATE OK assets=%d mapped=%d unmapped=%d" % (len(assets), len(mapped), len(unmapped)))
