"""Parse machine-written szl-source-binding.json files as verified (or declared) pins.

Recognised schemas:
  * szl.hf-card-source-binding/v1  — source.repository, source.revision, source.assets.*.sha256, target.repo_id
  * szl.github-to-huggingface-source/v1 — same source fields; target in destination.repoId; digests in managedFiles
A 40-hex source.revision is a verified_pin; anything else is declared only.
"""
import re

HEX40 = re.compile(r"^[0-9a-f]{40}$")
KNOWN = {"szl.hf-card-source-binding/v1", "szl.github-to-huggingface-source/v1"}

def parse(doc):
    """Return a pin dict or None if the document is not a recognised source-binding file."""
    if not isinstance(doc, dict):
        return None
    schema = doc.get("schema")
    src = doc.get("source") or {}
    tgt = doc.get("target") or {}
    dest = doc.get("destination") or {}
    repository = src.get("repository")
    revision = src.get("revision")
    target = tgt.get("repo_id") or dest.get("repoId") or dest.get("repo_id")
    assets = src.get("assets") if isinstance(src.get("assets"), dict) else {}
    managed = doc.get("managedFiles") if isinstance(doc.get("managedFiles"), dict) else {}
    files = assets or managed
    digests = {}
    for path, meta in files.items():
        if isinstance(meta, dict) and isinstance(meta.get("sha256"), str) and len(meta["sha256"]) == 64:
            digests[path] = meta["sha256"]
    if not repository or not revision:
        return None
    owner_name = repository
    repo_name = repository.split("/")[-1]
    if "/" in repository:
        owner_name = repository
    verified = bool(HEX40.fullmatch(revision))
    return {
        "schema": schema,
        "schema_recognised": schema in KNOWN,
        "pin_repository": repository,
        "pin_revision": revision,
        "pin_asset_digests": digests or None,
        "pin_target": target,
        "upstream_repo": repo_name,
        "grade": "verified_pin" if verified else "declared",
        "binding_kind": "source_binding_json",
        "pinned_ref": revision if verified else revision,
    }

def github_asset_id(repository):
    if not repository:
        return None
    parts = repository.strip("/").split("/")
    if len(parts) >= 2:
        return f"github_repo:{parts[-2]}/{parts[-1]}"
    return f"github_repo:szl-holdings/{parts[0]}"
