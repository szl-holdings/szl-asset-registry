"""Offline drift gate for durable asset-to-source pins."""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPED_METHODS = {"name", "card", "override"}
MUTABLE_REVISIONS = {"HEAD", "main", "master"}
REQUIRED_PIN_FIELDS = (
    "source_repo",
    "revision_sha",
    "readme_sha256",
    "evidence_quote",
    "pinned_utc",
)
REVISION_RE = re.compile(r"[0-9a-f]{40}")
README_SHA_RE = re.compile(r"[0-9a-f]{64}")


class InputError(Exception):
    """An input cannot be safely evaluated."""


def _reject_json_constant(value):
    raise ValueError(f"non-standard JSON constant: {value}")


def _load_json(path):
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise InputError("unable to read input") from None

    try:
        return json.loads(text, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        raise InputError("malformed JSON") from None


def _asset_index(document):
    if not isinstance(document, dict) or not isinstance(
        document.get("assets"), list
    ):
        raise InputError("asset_map must contain an assets array")

    assets = document["assets"]
    mapped = {}
    seen = set()

    for asset in assets:
        if not isinstance(asset, dict):
            raise InputError("asset_map contains an invalid asset entry")
        asset_id = asset.get("id")
        if not isinstance(asset_id, str) or not asset_id:
            raise InputError("asset_map contains an invalid asset id")
        if asset_id in seen:
            raise InputError("asset_map contains a duplicate asset id")
        seen.add(asset_id)
        if asset.get("method") in MAPPED_METHODS:
            mapped[asset_id] = asset

    return len(assets), mapped


def _pin_mapping(document):
    if not isinstance(document, dict) or not isinstance(
        document.get("pins"), dict
    ):
        raise InputError("source_pins must contain a pins object")
    return document["pins"]


def _defect(asset_id, field, reason):
    return {"asset_id": asset_id, "field": field, "reason": reason}


def evaluate(asset_map_path, pins_path):
    """Return asset_total, pins_total, pins_valid, and defects."""
    try:
        asset_total, mapped = _asset_index(_load_json(asset_map_path))
    except InputError as exc:
        return 0, 0, 0, [_defect("", "asset_map", str(exc))]

    try:
        pins = _pin_mapping(_load_json(pins_path))
    except InputError as exc:
        return asset_total, 0, 0, [_defect("", "source_pins", str(exc))]

    defects = []
    pins_valid = 0

    for asset_id in sorted(pins):
        pin = pins[asset_id]
        defect_count_before = len(defects)
        asset = mapped.get(asset_id)

        if asset is None:
            defects.append(
                _defect(
                    asset_id,
                    "asset_id",
                    "asset id is not a known mapped asset",
                )
            )
            continue

        if not isinstance(pin, dict):
            defects.append(
                _defect(asset_id, "pin", "pin must be a JSON object")
            )
            continue

        for field in REQUIRED_PIN_FIELDS:
            if field not in pin:
                defects.append(
                    _defect(asset_id, field, "missing required field")
                )

        if (
            "source_repo" in pin
            and pin["source_repo"] != asset.get("source_repo")
        ):
            defects.append(
                _defect(
                    asset_id,
                    "source_repo",
                    "does not match asset_map source_repo",
                )
            )

        if "revision_sha" in pin:
            revision = pin["revision_sha"]
            if isinstance(revision, str) and revision in MUTABLE_REVISIONS:
                defects.append(
                    _defect(
                        asset_id,
                        "revision_sha",
                        "mutable refs are not allowed; use a full commit SHA",
                    )
                )
            elif not isinstance(revision, str) or not REVISION_RE.fullmatch(
                revision
            ):
                defects.append(
                    _defect(
                        asset_id,
                        "revision_sha",
                        "must be exactly 40 lowercase hex characters",
                    )
                )

        if "readme_sha256" in pin:
            readme_sha = pin["readme_sha256"]
            if not isinstance(
                readme_sha, str
            ) or not README_SHA_RE.fullmatch(readme_sha):
                defects.append(
                    _defect(
                        asset_id,
                        "readme_sha256",
                        "must be exactly 64 lowercase hex characters",
                    )
                )

        if "evidence_quote" in pin:
            quote = pin["evidence_quote"]
            if not isinstance(quote, str) or not quote.strip():
                defects.append(
                    _defect(
                        asset_id,
                        "evidence_quote",
                        "must be a non-empty string",
                    )
                )

        if "pinned_utc" in pin:
            pinned_utc = pin["pinned_utc"]
            if not isinstance(pinned_utc, str) or not pinned_utc.strip():
                defects.append(
                    _defect(
                        asset_id,
                        "pinned_utc",
                        "must be a non-empty string",
                    )
                )

        if len(defects) == defect_count_before:
            pins_valid += 1

    defects.sort(key=lambda item: (item["asset_id"], item["field"]))
    return asset_total, len(pins), pins_valid, defects


def _generated_utc():
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "asset_map",
        nargs="?",
        type=Path,
        default=REPO_ROOT / "asset_map.json",
    )
    parser.add_argument(
        "pins",
        nargs="?",
        type=Path,
        default=REPO_ROOT / "data" / "source_pins.json",
    )
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    asset_total, pins_total, pins_valid, defects = evaluate(
        args.asset_map, args.pins
    )
    verdict = {
        "tool": "drift_gate",
        "generated": _generated_utc(),
        "asset_total": asset_total,
        "pins_total": pins_total,
        "pins_valid": pins_valid,
        "defects": defects,
    }
    print(
        json.dumps(
            verdict,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    return 0 if not defects else 1


if __name__ == "__main__":
    raise SystemExit(main())
