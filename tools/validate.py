"""Validate asset_map.json structure and identity conformance.

Checks (v2, consult v480): stats/coverage arithmetic, family domains,
method/source_repo coherence, unique (id, type) identities, and the
composite pin key grammar over every mapped asset: every map row must
render as a parseable "{type}/{id}" key so the drift gate's fail-closed
keying covers the whole map (zero misses required).
"""

import json
import re
import sys

ID_SEGMENT = r"[A-Za-z0-9][A-Za-z0-9._-]*"
PIN_KEY_RE = re.compile(
    r"(models|datasets|spaces)/(" + ID_SEGMENT + "/" + ID_SEGMENT + r")"
)
FAMS = {
    "laptop-lora-training",
    "candidate-eval-20261104",
    "run-artifact-store",
    "corpus-benchmark",
    "marketing-surface",
    "other",
}


def main():
    m = json.load(open("asset_map.json", encoding="utf-8"))
    assets = m["assets"]
    mapped = [a for a in assets if a["method"] in ("name", "card", "override")]
    unmapped = [a for a in assets if a["method"] == "unmapped"]
    assert len(mapped) + len(unmapped) == len(assets)
    assert m["coverage"]["mapped"] == len(mapped), "coverage.mapped mismatch"
    assert m["coverage"]["unmapped"] == len(unmapped), "coverage.unmapped mismatch"
    seen = set()
    grammar_misses = []
    for a in assets:
        assert a["type"] in ("models", "datasets", "spaces"), a
        assert a["id"] and a["family"] in FAMS, a
        identity = (a["id"], a["type"])
        assert identity not in seen, "duplicate_id_type_pair: %s" % (a["id"],)
        seen.add(identity)
        composite = "%s/%s" % (a["type"], a["id"])
        if not PIN_KEY_RE.fullmatch(composite):
            grammar_misses.append(composite)
        if a["method"] != "unmapped":
            assert a["source_repo"] and a["method"] in ("name", "card", "override"), a
        else:
            assert a["source_repo"] is None, a
    assert not grammar_misses, "composite key grammar misses: %s" % grammar_misses[:5]
    famsum = sum(m["unmapped_family_counts"].values())
    assert famsum == len(unmapped), (famsum, len(unmapped))
    stats = m["stats"]
    assert stats["name"] + stats["card"] + stats["override"] == len(mapped), "stats mapped mismatch"
    print(
        "VALIDATE OK assets=%d mapped=%d unmapped=%d unique_identities=%d grammar_misses=0"
        % (len(assets), len(mapped), len(unmapped), len(seen))
    )


if __name__ == "__main__":
    sys.exit(main())
