#!/usr/bin/env python3
"""Read-only Hugging Face model-namespace hygiene census.

A Hub listing is NOT proof that a model was trained, evaluated, or released.
This command never publishes, deletes, makes private, or downloads checkpoints.
It uses the public full-list endpoint or a supplied offline JSON snapshot.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ORG = "SZLHOLDINGS"
MAX_MODELS = 1000
WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".bin", ".pt", ".pth", ".onnx")
URL = "https://huggingface.co/api/models?" + urlencode(
    {"author": ORG, "limit": MAX_MODELS, "full": "true"}
)
SOFTWARE_TAGS = {"software", "kernels", "kernel", "not-weights", "test-fixture", "reference"}
CANDIDATE_TAGS = {"proposal-only", "not-promotable", "research-only", "experimental"}


def audit(models: list[dict], *, observed_at: str) -> dict:
    if not isinstance(models, list):
        raise ValueError("Hugging Face response must be a list")
    if len(models) >= MAX_MODELS:
        raise ValueError("Census at API cap: incomplete; do not report complete coverage")
    seen = set()
    rows = []
    for obj in models:
        if not isinstance(obj, dict):
            raise ValueError("Invalid Hub model object")
        repo = obj.get("id", "")
        if not isinstance(repo, str) or not repo.startswith(ORG + "/") or repo in seen:
            raise ValueError("Invalid, out-of-scope, or duplicate repository ID: " + repr(repo))
        seen.add(repo)
        siblings = obj.get("siblings")
        if not isinstance(siblings, list):
            raise ValueError("Missing file inventory for " + repo + "; coverage unavailable")
        filenames = sorted({
            s["rfilename"] for s in siblings
            if isinstance(s, dict) and isinstance(s.get("rfilename"), str)
        })
        if len(filenames) != len(siblings):
            raise ValueError("Incomplete/duplicate file paths for " + repo)
        weight_paths = [
            name for name in filenames
            if name.lower().endswith(WEIGHT_SUFFIXES)
        ]
        tags = set(t.lower() for t in obj.get("tags", []) if isinstance(t, str))
        base = repo.split("/", 1)[1].lower()
        flags = []
        if not weight_paths:
            flags.append("NO_RECOGNIZED_TENSOR_WEIGHT_FILE")
        if not weight_paths and tags.intersection(SOFTWARE_TAGS):
            flags.append("EXPLICIT_SOFTWARE_OR_FIXTURE_IN_MODEL_NAMESPACE")
        if "laptop-lora" in base:
            flags.append("LAPTOP_LORA_VARIANT")
        if "candidate" in base or tags.intersection(CANDIDATE_TAGS):
            flags.append("CANDIDATE_OR_RESEARCH_ONLY")
        if "trained" in base and not weight_paths:
            flags.append("TRAINED_NAME_WITHOUT_RECOGNIZED_TENSOR_WEIGHTS")
        if obj.get("pipeline_tag") == "text-generation" and not weight_paths:
            flags.append("TEXT_GENERATION_LABEL_WITHOUT_RECOGNIZED_TENSOR_WEIGHTS")
        # Filename presence is an observation, NEVER a verified training/eval receipt.
        receipt_artifacts = [
            name for name in filenames
            if ("receipt" in name.lower() or "eval" in name.lower())
            and name.lower().endswith(".json")
        ]
        rows.append({
            "repo": repo,
            "sha": obj.get("sha"),
            "last_modified": obj.get("lastModified"),
            "pipeline_tag": obj.get("pipeline_tag"),
            "public_api_private_field": obj.get("private"),
            "weight_file_count": len(weight_paths),
            "weight_file_paths": weight_paths,
            "receipt_or_eval_json_names": receipt_artifacts,
            "flags": sorted(flags),
            "training_verified": False,
            "quality_verified": False,
            "promotion_authorized": False,
        })
    rows.sort(key=lambda r: r["repo"].lower())
    counts = Counter(flag for row in rows for flag in row["flags"])
    return {
        "schema": "szl.hf.model-hygiene-census/v1",
        "observed_at": observed_at,
        "source": URL,
        "scope": "PUBLIC_API_ONLY",
        "coverage": {"status": "COMPLETE_FOR_RETURNED_PUBLIC_LIST_BELOW_API_CAP", "models": len(rows)},
        "counts": {
            "no_recognized_tensor_weight_file": counts["NO_RECOGNIZED_TENSOR_WEIGHT_FILE"],
            "explicit_software_or_fixture": counts["EXPLICIT_SOFTWARE_OR_FIXTURE_IN_MODEL_NAMESPACE"],
            "laptop_lora_variants": counts["LAPTOP_LORA_VARIANT"],
            "candidate_or_research_only": counts["CANDIDATE_OR_RESEARCH_ONLY"],
            "trained_name_without_recognized_tensor_weights": counts["TRAINED_NAME_WITHOUT_RECOGNIZED_TENSOR_WEIGHTS"],
            "text_generation_label_without_recognized_tensor_weights": counts["TEXT_GENERATION_LABEL_WITHOUT_RECOGNIZED_TENSOR_WEIGHTS"],
        },
        "limits": [
            "Private or inaccessible repositories are not included.",
            "Non-tensor trained models (e.g. JSON/NumPy) may be valid despite absence of listed tensor files.",
            "Checkpoint filename and receipt-artifact presence do not prove training, weights identity, evaluations, runtime, or release.",
            "No file contents or cryptographic weight-to-receipt bindings were independently verified.",
        ],
        "mutation_performed": False,
        "models": rows,
    }


def live_models() -> list[dict]:
    request = Request(URL, headers={"User-Agent": "szl-readonly-hf-hygiene/1.0"})
    with urlopen(request, timeout=40) as response:
        if response.status != 200:
            raise ValueError("Hugging Face API unavailable")
        return json.load(response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--live", action="store_true", help="Public API, GET only")
    group.add_argument("--snapshot", type=Path, help="Offline raw full-model JSON list")
    parser.add_argument("--output", type=Path, help="Write exclusive-create metadata-only report")
    args = parser.parse_args(argv)
    try:
        models = live_models() if args.live else json.loads(args.snapshot.read_text(encoding="utf-8"))
        observed_at = datetime.now(timezone.utc).isoformat()
        report = audit(models, observed_at=observed_at)
        if args.output:
            # Avoid destructive replacement: new report path must be unused.
            with args.output.open("x", encoding="utf-8") as out:
                json.dump(report, out, indent=2, sort_keys=True)
                out.write("\n")
        print(json.dumps({
            "observed_at": report["observed_at"],
            "coverage": report["coverage"],
            "counts": report["counts"],
            "mutation_performed": False,
            "saved_to": str(args.output) if args.output else None,
        }, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("UNAVAILABLE (fail-closed): " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())