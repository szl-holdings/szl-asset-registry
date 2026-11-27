"""Synthetic raw-metadata fixtures (no network, no real data) for registry_db tests."""
import json, os

H1 = "1" * 40; H2 = "2" * 40; OLD = "9" * 40

def _w(root, rel, obj):
    p = os.path.join(root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f: json.dump(obj, f)

def repo_gql(name, head, private=False, db_id=1):
    return {"databaseId": db_id, "nameWithOwner": f"szl-holdings/{name}", "visibility": "PRIVATE" if private else "PUBLIC", "isPrivate": private, "isArchived": False, "isFork": False,
            "isTemplate": False, "isMirror": False, "isEmpty": False, "description": "d", "homepageUrl": None, "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-02T00:00:00Z",
            "pushedAt": "2026-01-02T00:00:00Z", "diskUsage": 10, "primaryLanguage": {"name": "Python"}, "licenseInfo": {"spdxId": "Apache-2.0", "name": "Apache"},
            "repositoryTopics": {"nodes": [{"topic": {"name": "szl"}}]}, "defaultBranchRef": {"name": "main", "target": {"oid": head, "committedDate": "2026-01-02T00:00:00Z"}},
            "openPRs": {"totalCount": 1}, "allPRs": {"totalCount": 2}, "openIssues": {"totalCount": 0}, "allIssues": {"totalCount": 0}, "releases": {"totalCount": 0}, "latestRelease": None,
            "tags": {"totalCount": 0}, "branches": {"totalCount": 1}, "root": {"entries": []}, "wf": {"entries": []}}

def write_raw(root, hf_pin=H1, repo_head=H2, with_compare=True):
    """repo `core` (public, head=repo_head), repo `secret` (private), HF space bound by sync pin, HF model unbound, pypi project, cf worker."""
    obs = "2026-11-19T12:00:00Z"
    det = {"repos": {n: {"gql": repo_gql(n, h, pr, i), "gql_errors": [], "rest": {}, "observed_at": obs, "ls_remote": {"HEAD": h, "heads": {"main": h}}}
                     for i, (n, h, pr) in enumerate([("core", repo_head, False), ("secret", H1, True)], 1)}, "completed_at": obs}
    _w(root, "github/repo_details.json", det)
    _w(root, "github/enum_rest.json", {"observed_at": obs, "repos": [{"name": "core"}, {"name": "secret"}]})
    _w(root, "github/enum_graphql.json", {"observed_at": obs, "totalCount": 2, "nodes": []})
    _w(root, "github/enum_ghcli.json", {"observed_at": obs, "repos": [{}, {}]})
    _w(root, "github/repo_facts.json", {"observed_at": obs, "facts": {"core": {"workflows": ["ci.yml"], "tree_packaging_paths": ["pyproject.toml"], "migration_files": [], "tree_file_count": 5, "content_scanned": True},
                                                                       "secret": {"workflows": [], "tree_packaging_paths": [], "migration_files": [], "tree_file_count": 1, "content_scanned": False}}})
    _w(root, "github/candidate_bindings.json", {"observed_at": obs, "refs": [
        {"repo": "core", "kind": "pypi", "target_type": "project", "target_id": "szl-core", "evidence_path": "core:pyproject.toml#project.name", "snippet": "name=szl-core version=0.2.0"},
        {"repo": "core", "kind": "cloudflare", "target_type": "worker_script", "target_id": "core-worker", "evidence_path": "core:wrangler.toml#L1", "snippet": 'name = "core-worker"'},
        {"repo": "core", "kind": "hf", "target_type": "model", "target_id": "SZLHOLDINGS/orphan-ref", "evidence_path": "core:README.md#L3", "snippet": "see huggingface.co/SZLHOLDINGS/orphan-ref"}]})
    _w(root, "github/asset_map_szl-asset-registry.json", {"assets": [{"id": "SZLHOLDINGS/declared-model", "source_repo": "core", "method": "card"}]})
    _w(root, "github/audit_repo_events.json", {"events": []})
    cmp_ = {}
    if with_compare and hf_pin != repo_head: cmp_[f"core@{hf_pin}...{repo_head}"] = {"status": "ahead"}
    _w(root, "github/compare.json", {"pairs": cmp_})
    items = lambda kind, rows: {"count": len(rows), "unique": len(rows), "private": 0, "items": rows}
    _w(root, "hf/hf_inventory.json", {"observed_at": obs, "overview_counts": {"numModels": 3, "numDatasets": 0, "numSpaces": 1, "numKernels": 0, "numBuckets": 0},
        "kinds": {"model": items("model", [{"id": "SZLHOLDINGS/declared-model", "sha": "a" * 40, "private": True, "tags": ["x"]}, {"id": "SZLHOLDINGS/orphan-ref", "sha": "b" * 40, "private": False},
                                          {"id": "SZLHOLDINGS/no-source", "sha": "c" * 40, "private": False}]),
                  "dataset": items("dataset", []), "space": items("space", [{"id": "SZLHOLDINGS/core-space", "sha": "d" * 40, "private": False, "sdk": "static", "runtime": {"stage": "RUNNING"}}]),
                  "kernel": items("kernel", []), "bucket": items("bucket", []), "collection": items("collection", [])}})
    _w(root, "hf/hf_commits.json", {"items": {"space:SZLHOLDINGS/core-space": {"head": "d" * 40, "pin": {"repo": "core", "sha": hf_pin, "commit": "d" * 40, "title": f"deploy(hf): sync szl-holdings/core@{hf_pin}", "date": obs}, "latest_title": "t", "observed_at": obs}}})
    _w(root, "hf/hf_card_pins.json", {"items": {}})
    _w(root, "pypi/pypi_inventory.json", {"completed_at": obs, "projects": {
        "szl-core": {"exists": True, "name": "szl-core", "latest": "0.2.0", "n_releases": 2, "versions": ["0.1.0", "0.2.0"], "summary": "s", "project_urls": {"Source": "https://github.com/szl-holdings/core"},
                     "home_page": None, "author": "a", "license": "Apache-2.0", "yanked": False, "org_linked": True, "observed_at": obs,
                     "files": [{"filename": "szl_core-0.2.0.tar.gz", "sha256": "e" * 64, "upload_time": obs}, {"filename": "szl_core-0.2.0-py3-none-any.whl", "sha256": "f" * 64, "upload_time": obs}]},
        "not-published": {"exists": False, "http": 404, "observed_at": obs}}})
    _w(root, "hf/hf_source_bindings.json", {"items": {
        "space:SZLHOLDINGS/core-space": {
            "observed_at": obs,
            "evidence_path": "hf/hf_source_bindings.json#items.space:SZLHOLDINGS/core-space",
            "doc": {"schema": "szl.hf-card-source-binding/v1",
                    "source": {"repository": "szl-holdings/core", "revision": hf_pin,
                               "assets": {"app.py": {"bytes": 1, "sha256": "a" * 64}}},
                    "target": {"repo_id": "SZLHOLDINGS/core-space", "repo_type": "space"}}
        }
    }})
    _w(root, "cloudflare/cf_inventory.json", {"observed_at": obs, "gaps": [], "accounts": [{"id": "acct", "name": "a"}], "zones": [],
        "per_account": {"acct": {"workers_scripts": [{"id": "core-worker", "tag": "tag-core-worker", "etag": "0" * 64, "modified_on": obs, "handlers": ["fetch"]}, {"id": "stray-worker", "tag": "tag-stray-worker", "etag": "1" * 64}],
                                 "d1": [], "r2_buckets": [], "kv": [], "tunnels": [], "access_apps": [], "workers_domains": [],
                                 "pages_projects": [{"name": "szl-portal", "id": "page-uuid-1", "subdomain": "szl-portal.pages.dev", "production_branch": "main", "created_on": obs}]}}, "per_zone": {}})
    # PEP 740 attested pin for szl-core (H1 ancestor of repo_head when they differ)
    _w(root, "github/pypi_pin_compare.json", {f"szl-holdings/core@{hf_pin}": {"head": repo_head, "http_ok": True,
        "result": {"status": "identical" if hf_pin == repo_head else "ahead", "ahead_by": 0 if hf_pin == repo_head else 1, "behind_by": 0},
        "err": None, "observed_at": obs}})
