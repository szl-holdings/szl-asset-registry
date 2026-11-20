"""Offline drift gate for durable asset-to-source pins (identity model v2).

Keying (consult v480, Kimi resp e3f63149..., AMEND-APPROVED): Hub identity is
(id, type); the real asset_map.json holds legal cross-type twins, so pin keys
are composite "{type}/{id}" with the exact grammar

    ^(models|datasets|spaces)/[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$

and every asset must be accounted for: pinned, or in a declared, per-asset
reasoned backlog. Missing accounting = defect, fail-closed. An absent pins
file is a reported unseeded state: a green zero-pin verdict, never a skip.

Implementation doctrine (consult v480, Mistral resp c12bd881...): fullmatch
parsing (no `$` newline landmine), fixed defect ordering, byte-stable
verdict output, verify-after-read is the seeder's job, not the gate's.

Exit contract: 0 = valid (or unseeded), 1 = defects, 2 = input error.
"""

import argparse
import json
import re
import sys
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
ASSET_TYPES = ("models", "datasets", "spaces")
ID_SEGMENT = r"[A-Za-z0-9][A-Za-z0-9._-]*"
PIN_KEY_RE = re.compile(
    r"(models|datasets|spaces)/(" + ID_SEGMENT + "/" + ID_SEGMENT + r")"
)
BARE_ID_RE = re.compile(ID_SEGMENT + "/" + ID_SEGMENT)
REVISION_RE = re.compile(r"[0-9a-f]{40}")
README_SHA_RE = re.compile(r"[0-9a-f]{64}")
PINNED_UTC_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
MAX_INPUT_BYTES = 4 * 1024 * 1024
BACKLOG_REASONS = (
    "no_hub_readme",
    "card_method_deferred",
    "override_method_deferred",
    "unmapped_method_deferred",
    "source_moved_during_measurement",
)

REASON_RANK = {
    reason: rank
    for rank, reason in enumerate(
        (
            "composite_pin_key_malformed",
            "pin_key_type_prefix_invalid",
            "pin_key_bare_id",
            "pin_asset_unknown",
            "pin_asset_unmapped",
            "pin_asset_unmapped_method",
            "duplicate_pin_key",
            "pin_not_object",
            "missing_required_field",
            "source_repo_mismatch",
            "revision_sha_mutable_ref",
            "revision_sha_invalid",
            "readme_sha256_invalid",
            "evidence_quote_empty",
            "pinned_utc_invalid",
            "backlog_key_invalid",
            "backlog_asset_unknown",
            "backlog_reason_invalid",
            "backlog_entry_conflicts_pin",
            "missing_backlog_entry",
            "duplicate_id_type_pair",
        )
    )
}


class InputError(Exception):
    """An input cannot be safely evaluated (exit 2)."""


def _reject_json_constant(value):
    raise ValueError(f"non-standard JSON constant: {value}")


def _read_bounded(path):
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise InputError(
                f"input exceeds {MAX_INPUT_BYTES} byte cap"
            )
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InputError("unable to read input") from exc


def _load_asset_map(path):
    """Parse asset_map with duplicate-key detection; raise InputError on dups."""
    text = _read_bounded(path)
    try:
        return json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_pairs_no_duplicates,
        )
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        message = str(exc)
        if message.startswith("duplicate JSON object key:"):
            raise InputError(message) from exc
        raise InputError("malformed JSON") from exc


def _pairs_no_duplicates(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"duplicate JSON object key: {key}")
        document[key] = value
    return document


def _load_pins_pairs(text):
    """Parse the pins document preserving duplicate-key evidence.

    Duplicate keys keep last (so the run continues) and are reported as
    defects by the caller through the returned duplicate ledger. The
    reserved key "__duplicates__" is reserved for the parser; source
    documents must not use it as a field name.
    """
    def pairs_hook(pairs):
        seen = {}
        dups = []
        for key, value in pairs:
            if key in seen:
                dups.append(key)
            seen[key] = value
        if dups:
            seen["__duplicates__"] = dups
        return seen

    def clean(value, collector, prefix):
        if isinstance(value, dict):
            if "__duplicates__" in value:
                for sub in value.pop("__duplicates__"):
                    collector.append(prefix + sub)
            return {
                key: clean(item, collector, f"{prefix}{key}.")
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                clean(item, collector, f"{prefix}{index}.")
                for index, item in enumerate(value)
            ]
        return value

    try:
        document = json.loads(
            text, parse_constant=_reject_json_constant, object_pairs_hook=pairs_hook
        )
    except (json.JSONDecodeError, ValueError, RecursionError):
        raise InputError("malformed JSON") from None
    duplicates: list = []
    try:
        document = clean(document, duplicates, "")
    except RecursionError:
        raise InputError("malformed JSON") from None
    if not isinstance(document, dict):
        raise InputError("source_pins must be an object")
    return document, sorted(set(duplicates))


def _classify_pin_key(key):
    """Return (identity, reason_token); identity is (type, id) when valid."""
    if isinstance(key, str) and PIN_KEY_RE.fullmatch(key):
        parts = key.split("/", 1)
        return (parts[1], parts[0]), None  # identity is (id, type)
    if isinstance(key, str) and BARE_ID_RE.fullmatch(key):
        return None, "pin_key_bare_id"
    if isinstance(key, str) and "/" in key:
        rest = key.split("/", 1)[1]
        if BARE_ID_RE.fullmatch(rest):
            return None, "pin_key_type_prefix_invalid"
        return None, "composite_pin_key_malformed"
    return None, "composite_pin_key_malformed"


def _asset_index(document):
    """Return (asset_total, mapped, methods) where identity is (id, type)."""
    if not isinstance(document, dict) or not isinstance(
        document.get("assets"), list
    ):
        raise InputError("asset_map must contain an assets array")

    assets = document["assets"]
    mapped = {}
    methods = {}
    seen = set()

    for asset in assets:
        if not isinstance(asset, dict):
            raise InputError("asset_map contains an invalid asset entry")
        asset_id = asset.get("id")
        asset_type = asset.get("type")
        method = asset.get("method")
        if not isinstance(asset_id, str) or not asset_id:
            raise InputError("asset_map contains an invalid asset id")
        if asset_type not in ASSET_TYPES:
            raise InputError("asset_map contains an invalid asset type")
        if not isinstance(method, str):
            raise InputError("asset_map contains an invalid asset method")
        identity = (asset_id, asset_type)
        if identity in seen:
            raise InputError("duplicate asset identity (id+type)")
        seen.add(identity)
        methods[identity] = method
        if method in MAPPED_METHODS:
            mapped[identity] = asset

    return len(assets), mapped, methods


def _defect(asset_id, field, reason):
    return {"asset_id": asset_id, "field": field, "reason": reason}


def _check_pin(key, pin, asset):
    """Ordered per-pin field checks; returns defects for this pin only."""
    defects = []
    if not isinstance(pin, dict):
        return [_defect(key, "pin", "pin_not_object")]

    for field in REQUIRED_PIN_FIELDS:
        if field not in pin:
            defects.append(_defect(key, field, "missing_required_field"))

    if "source_repo" in pin and pin["source_repo"] != asset.get(
        "source_repo"
    ):
        defects.append(_defect(key, "source_repo", "source_repo_mismatch"))

    if "revision_sha" in pin:
        revision = pin["revision_sha"]
        if isinstance(revision, str) and revision in MUTABLE_REVISIONS:
            defects.append(
                _defect(key, "revision_sha", "revision_sha_mutable_ref")
            )
        elif not isinstance(revision, str) or not REVISION_RE.fullmatch(
            revision
        ):
            defects.append(_defect(key, "revision_sha", "revision_sha_invalid"))

    if "readme_sha256" in pin:
        readme = pin["readme_sha256"]
        if not isinstance(readme, str) or not README_SHA_RE.fullmatch(readme):
            defects.append(
                _defect(key, "readme_sha256", "readme_sha256_invalid")
            )

    if "evidence_quote" in pin:
        quote = pin["evidence_quote"]
        if not isinstance(quote, str) or not quote.strip():
            defects.append(_defect(key, "evidence_quote", "evidence_quote_empty"))

    if "pinned_utc" in pin:
        stamp = pin["pinned_utc"]
        if not isinstance(stamp, str) or not PINNED_UTC_RE.fullmatch(stamp):
            defects.append(_defect(key, "pinned_utc", "pinned_utc_invalid"))

    return defects


def _sort_defects(defects):
    return sorted(
        defects,
        key=lambda item: (
            str(item["asset_id"]),
            item["field"],
            REASON_RANK.get(item["reason"], len(REASON_RANK)),
        ),
    )


def evaluate(asset_map_path, pins_path):
    """Return (exit_code, verdict dict) for the given inputs."""
    try:
        document = _load_asset_map(asset_map_path)
    except InputError as exc:
        verdict = _verdict(0, 0, 0, 0, [], [_defect("", "asset_map", "input_error")])
        verdict["defects"][0]["reason"] = str(exc)
        return 2, verdict

    try:
        asset_total, mapped, methods = _asset_index(document)
    except InputError as exc:
        message = str(exc)
        field = "asset_map"
        reason = "duplicate_id_type_pair" if message.startswith(
            "duplicate asset identity"
        ) else "input_error"
        defect = _defect("", field, reason)
        if reason == "input_error":
            defect["reason"] = message
        return (1 if reason != "input_error" else 2), _verdict(
            0, 0, 0, 0, [], [defect]
        )

    if not pins_path.exists():
        return 0, _verdict(asset_total, 0, 0, 0, [], [])

    try:
        pins_doc, duplicate_keys = _load_pins_pairs(_read_bounded(pins_path))
    except InputError as exc:
        verdict = _verdict(
            asset_total, 0, 0, 0, [], [_defect("", "source_pins", "input_error")]
        )
        verdict["defects"][0]["reason"] = str(exc)
        return 2, verdict

    pins = pins_doc.get("pins")
    backlog = pins_doc.get("backlog", [])
    seed_batch = pins_doc.get("pins_seed_batch", 0)
    if not isinstance(pins, dict):
        return 2, _verdict(
            asset_total,
            0,
            0,
            0,
            [],
            [_defect("", "pins", "source_pins must contain a pins object")],
        )
    if not isinstance(backlog, list):
        return 2, _verdict(
            asset_total,
            0,
            0,
            0,
            [],
            [_defect("", "backlog", "source_pins backlog must be an array")],
        )

    method_by_identity = methods
    defects = []
    pinned_ok = set()
    defects_by_key = {key: [] for key in pins}

    for key in sorted(pins):
        identity, key_reason = _classify_pin_key(key)
        if key_reason is not None:
            defects_by_key[key].append(_defect(key, "asset_id", key_reason))
            continue
        if identity not in method_by_identity:
            defects_by_key[key].append(
                _defect(key, "asset_id", "pin_asset_unknown")
            )
            continue
        method = method_by_identity[identity]
        if method == "unmapped":
            defects_by_key[key].append(
                _defect(key, "asset_id", "pin_asset_unmapped_method")
            )
            continue
        if method not in MAPPED_METHODS:
            defects_by_key[key].append(
                _defect(key, "asset_id", "pin_asset_unmapped")
            )
            continue
        asset = mapped.get(identity)
        if asset is None:
            defects_by_key[key].append(
                _defect(key, "asset_id", "pin_asset_unknown")
            )
            continue
        defects_by_key[key].extend(_check_pin(key, pins[key], asset))
        pinned_ok.add(identity)

    for duplicate in duplicate_keys:
        defects.append(_defect(duplicate, "pins", "duplicate_pin_key"))

    backlog_valid = set()
    for item in backlog:
        if not isinstance(item, dict):
            defects.append(_defect("", "backlog", "backlog_key_invalid"))
            continue
        key = item.get("key")
        reason = item.get("reason")
        identity, key_reason = _classify_pin_key(key)
        if not isinstance(key, str) or key_reason is not None:
            defects.append(_defect(key, "backlog", "backlog_key_invalid"))
            continue
        if identity not in method_by_identity:
            defects.append(_defect(key, "backlog", "backlog_asset_unknown"))
            continue
        if reason not in BACKLOG_REASONS:
            defects.append(_defect(key, "backlog", "backlog_reason_invalid"))
            continue
        if identity in pinned_ok:
            defects.append(
                _defect(key, "backlog", "backlog_entry_conflicts_pin")
            )
            continue
        backlog_valid.add(identity)

    covered = pinned_ok | backlog_valid
    for (asset_id, asset_type) in sorted(method_by_identity):
        if (asset_id, asset_type) not in covered:
            defects.append(
                _defect(
                    f"{asset_type}/{asset_id}",
                    "backlog",
                    "missing_backlog_entry",
                )
            )

    pins_valid = sum(
        1 for key in pins if not defects_by_key[key]
    )

    for key in sorted(defects_by_key):
        defects.extend(defects_by_key[key])

    backlog_mirror = sorted(
        (
            {"key": item.get("key"), "reason": item.get("reason")}
            for item in backlog
            if isinstance(item, dict)
        ),
        key=lambda entry: str(entry.get("key")),
    )

    verdict = _verdict(
        asset_total,
        len(pins),
        pins_valid,
        seed_batch if isinstance(seed_batch, int) else 0,
        backlog_mirror,
        _sort_defects(defects),
    )
    return (1 if defects else 0), verdict


def _verdict(asset_total, pins_total, pins_valid, seed_batch, backlog, defects):
    return {
        "tool": "drift_gate",
        "generated": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "asset_total": asset_total,
        "pins_total": pins_total,
        "pins_valid": pins_valid,
        "pins_seed_batch": seed_batch,
        "backlog_total": len(backlog),
        "backlog": backlog,
        "defects": defects,
    }


def _dump(verdict):
    return json.dumps(verdict, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "asset_map_path",
        nargs="?",
        default=None,
        help="asset map JSON (default: asset_map.json at repo root)",
    )
    parser.add_argument(
        "pins_path",
        nargs="?",
        default=None,
        help="pins JSON (default: data/source_pins.json at repo root)",
    )
    args = parser.parse_args(argv)

    import os

    asset_map_path = Path(
        args.asset_map_path
        or os.environ.get("SZL_ASSET_MAP_PATH")
        or REPO_ROOT / "asset_map.json"
    )
    pins_path = Path(
        args.pins_path
        or os.environ.get("SZL_SOURCE_PINS_PATH")
        or REPO_ROOT / "data" / "source_pins.json"
    )

    exit_code, verdict = evaluate(asset_map_path, pins_path)
    sys.stdout.write(_dump(verdict))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
