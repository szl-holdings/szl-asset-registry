"""Step 7: assemble raw metadata files into ONE deterministic snapshot (snapshots/snapshot.json).
Pure function of the raw files (no network). snapshot sha256 is the idempotency key for loading."""
import os, sys, json, hashlib, glob
from .common import utcnow, RAW_ROOT
RAW = RAW_ROOT
TOOL_VERSION = "0.1.0"
ORG, HFORG = "szl-holdings", "SZLHOLDINGS"
HF_TYPE = {"model": "hf_model", "dataset": "hf_dataset", "space": "hf_space", "kernel": "hf_kernel", "bucket": "hf_bucket", "collection": "hf_collection"}

def jl(p):
    with open(os.path.join(RAW, p)) as f: return json.load(f)
def sha_file(p):
    with open(os.path.join(RAW, p), "rb") as f: return hashlib.sha256(f.read()).hexdigest()

def main(out_path, quiet=False):
    gh = jl("github/repo_details.json"); enum = jl("github/enum_rest.json"); gq = jl("github/enum_graphql.json")
    facts_f = jl("github/repo_facts.json"); refs = jl("github/candidate_bindings.json")["refs"]
    hf = jl("hf/hf_inventory.json"); hfc = jl("hf/hf_commits.json")["items"]
    cards = jl("hf/hf_card_pins.json")["items"] if os.path.exists(f"{RAW}/hf/hf_card_pins.json") else {}
    py = jl("pypi/pypi_inventory.json"); cf = jl("cloudflare/cf_inventory.json")
    cmp_ = jl("github/compare.json")["pairs"] if os.path.exists(f"{RAW}/github/compare.json") else {}
    amap = {a["id"]: a for a in jl("github/asset_map_szl-asset-registry.json")["assets"]}
    audit = jl("github/audit_repo_events.json")["events"] if os.path.exists(f"{RAW}/github/audit_repo_events.json") else []
    heads = {n: r["gql"]["defaultBranchRef"]["target"]["oid"] for n, r in gh["repos"].items()}
    assets = {}; bindings = []; crefs = []

    def add(aid, atype, ns, name, ext, vis, obs, ev, facts, rev=None):
        assets[aid] = {"asset_id": aid, "asset_type": atype, "namespace": ns, "name": name, "external_id": ext, "visibility": vis,
                       "observed_at": obs, "evidence_path": ev, "facts": {k: v for k, v in facts.items() if v is not None},
                       "revision": rev or {"kind": "none", "revision": None, "digest_sha256": None, "digest_filename": None}}

    # --- GitHub
    vis_events = {}
    for e in audit:
        if e.get("action") == "repo.access" and e.get("repo", "").startswith(ORG + "/"):
            vis_events.setdefault(e["repo"].split("/", 1)[1], []).append({"at_ms": e.get("@timestamp"), "visibility": e.get("visibility"), "actor": e.get("actor")})
    for n, r in sorted(gh["repos"].items()):
        g = r["gql"]; priv = g["isPrivate"]; f = facts_f["facts"].get(n, {})
        ev = f"github/repo_details.json#repos.{n}"
        vis = g["visibility"].lower()
        facts = {"default_branch": g["defaultBranchRef"]["name"], "head_sha": g["defaultBranchRef"]["target"]["oid"], "head_committed_at": g["defaultBranchRef"]["target"]["committedDate"],
                 "head_sha_ls_remote": (r["ls_remote"] or {}).get("HEAD"), "archived": g["isArchived"], "is_fork": g["isFork"], "is_template": g["isTemplate"], "is_mirror": g["isMirror"], "is_empty": g["isEmpty"],
                 "topics": sorted(t["topic"]["name"] for t in g["repositoryTopics"]["nodes"]), "language": (g["primaryLanguage"] or {}).get("name"), "size_kb": g["diskUsage"],
                 "pushed_at": g["pushedAt"], "created_at": g["createdAt"], "license_spdx": (g["licenseInfo"] or {}).get("spdxId"),
                 "open_prs": g["openPRs"]["totalCount"], "total_prs": g["allPRs"]["totalCount"], "open_issues": g["openIssues"]["totalCount"], "total_issues": g["allIssues"]["totalCount"],
                 "releases": g["releases"]["totalCount"], "latest_release": (g["latestRelease"] or {}).get("tagName"), "tags": g["tags"]["totalCount"], "branches": g["branches"]["totalCount"],
                 "workflows": f.get("workflows"), "packaging_files": f.get("tree_packaging_paths"), "migration_files": len(f.get("migration_files") or []),
                 "tree_file_count": f.get("tree_file_count"), "content_scanned": f.get("content_scanned"),
                 "homepage": None if priv else g["homepageUrl"], "description": None if priv else g["description"], "visibility_events": vis_events.get(n) or None}
        add(f"github_repo:{ORG}/{n}", "github_repo", ORG, n, str(g["databaseId"]), vis, r["observed_at"], ev, facts,
            {"kind": "git_sha", "revision": g["defaultBranchRef"]["target"]["oid"], "digest_sha256": None, "digest_filename": None})

    # --- HF
    hf_obs = hf["observed_at"]
    for kind, blk in hf["kinds"].items():
        atype = HF_TYPE[kind]
        for it in blk["items"]:
            hid = it["id"] if kind != "collection" else it["slug"]
            name = hid.split("/", 1)[1] if "/" in hid else hid
            private = bool(it.get("private"))
            card = it.get("cardData") or {}
            c = hfc.get(f"{kind}:{hid}") or {}; cp = cards.get(f"{kind}:{hid}") or {}
            facts = {"sha": it.get("sha"), "last_modified": it.get("lastModified") or it.get("updatedAt"), "created_at": it.get("createdAt"), "tags": sorted(it.get("tags") or []) or None,
                     "gated": it.get("gated"), "disabled": it.get("disabled"), "downloads": it.get("downloads"), "likes": it.get("likes"), "license": card.get("license"),
                     "library_name": it.get("library_name") or card.get("library_name"), "pipeline_tag": it.get("pipeline_tag") or card.get("pipeline_tag"), "base_model": card.get("base_model"),
                     "sdk": it.get("sdk"), "runtime_stage": (it.get("runtime") or {}).get("stage"), "latest_commit_title": (None if private else c.get("latest_title")),
                     "size_bytes": it.get("size"), "total_files": it.get("totalFiles"), "title": it.get("title") if kind == "collection" else None}
            rev = {"kind": "hf_revision", "revision": it.get("sha"), "digest_sha256": None, "digest_filename": None} if it.get("sha") else None
            add(f"{atype}:{HFORG}/{name}" if kind != "collection" else f"{atype}:{HFORG}/{name}", atype, HFORG, name, it.get("_id") or it.get("id"),
                "private" if private else "public", hf_obs, f"hf/hf_inventory.json#kinds.{kind}.items[{hid}]", facts, rev)
            aid = f"{atype}:{HFORG}/{name}"
            if c.get("pin") and c["pin"]["repo"] in heads:
                p = c["pin"]; head = heads[p["repo"]]
                cmp_key = f"{p['repo']}@{p['sha']}...{head}"
                status = "identical" if p["sha"] == head else (cmp_.get(cmp_key) or {}).get("status")
                bindings.append({"asset_id": aid, "upstream_asset_id": f"github_repo:{ORG}/{p['repo']}", "kind": "sync_commit_pin", "grade": "verified_pin", "pinned_ref": p["sha"], "upstream_head": head,
                                 "compare_status": status, "observed_at": c["observed_at"], "evidence_path": f"hf/hf_commits.json#items.{kind}:{hid}.pin"})
            for pin in cp.get("pins") or []:
                if pin["repo"] in heads:
                    head = heads[pin["repo"]]
                    cmp_key = f"{pin['repo']}@{pin['sha']}...{head}"
                    status = "identical" if pin["sha"] == head else (cmp_.get(cmp_key) or {}).get("status")
                    bindings.append({"asset_id": aid, "upstream_asset_id": f"github_repo:{ORG}/{pin['repo']}", "kind": "declared_map", "grade": "declared", "pinned_ref": pin["sha"], "upstream_head": head,
                                     "compare_status": status, "observed_at": cp["observed_at"], "evidence_path": f"hf/hf_card_pins.json#items.{kind}:{hid}.pins[{pin['pattern']}:L{pin['line']}]"})
            am = amap.get(hid)
            if am and am.get("source_repo") and f"github_repo:{ORG}/{am['source_repo']}" in assets:
                bindings.append({"asset_id": aid, "upstream_asset_id": f"github_repo:{ORG}/{am['source_repo']}", "kind": "declared_map", "grade": "declared", "pinned_ref": None, "upstream_head": heads.get(am["source_repo"]),
                                 "compare_status": None, "observed_at": hf_obs, "evidence_path": f"github/asset_map_szl-asset-registry.json#assets[{hid}](method={am.get('method')})"})

    # --- PyPI
    py_obs = py.get("completed_at") or utcnow()
    for name, p in sorted(py["projects"].items()):
        if not p.get("exists"): continue
        szl_declared = [r for r in refs if r["kind"] == "pypi" and r["target_type"] == "project" and r["target_id"] == name and "#project.name" in r["evidence_path"]]
        if not (p.get("org_linked") or szl_declared): continue   # third-party names mentioned in docs are not registry assets
        files = p.get("files") or []
        sd = [f for f in files if f["filename"].endswith(".tar.gz")]; wh = [f for f in files if f["filename"].endswith(".whl")]
        pick = (sd or sorted(wh, key=lambda f: f["filename"]) or [None])[0]
        facts = {"latest": p["latest"], "n_releases": p["n_releases"], "recent_versions": p.get("versions"), "summary": p.get("summary"), "license": p.get("license"), "author": p.get("author"),
                 "project_urls": p.get("project_urls"), "org_linked": p.get("org_linked"), "files": [{"filename": f["filename"], "sha256": f["sha256"], "upload_time": f.get("upload_time")} for f in files], "yanked": p.get("yanked")}
        aid = f"pypi_project:pypi/{name}"
        add(aid, "pypi_project", "pypi", name, None, "public", p["observed_at"], f"pypi/pypi_inventory.json#projects.{name}", facts,
            {"kind": "pypi_release", "revision": f"{name}=={p['latest']}", "digest_sha256": pick["sha256"] if pick else None, "digest_filename": pick["filename"] if pick else None})
        for r in szl_declared:
            repo = r["repo"]
            if f"github_repo:{ORG}/{repo}" not in assets: continue
            ver = (r["snippet"].split("version=")[-1] if "version=" in r["snippet"] else None)
            bindings.append({"asset_id": aid, "upstream_asset_id": f"github_repo:{ORG}/{repo}", "kind": "pyproject_in_repo", "grade": "declared", "pinned_ref": ver, "upstream_head": heads[repo],
                             "compare_status": ("version:" + p["latest"]), "observed_at": r.get("observed_at") or py_obs, "evidence_path": r["evidence_path"]})
        for k, u in (p.get("project_urls") or {}).items():
            if u and f"github.com/{ORG}/" in u.lower():
                repo = u.lower().split(f"github.com/{ORG}/", 1)[1].split("/")[0].split("#")[0]
                real = next((n for n in heads if n.lower() == repo), None)
                if real: bindings.append({"asset_id": aid, "upstream_asset_id": f"github_repo:{ORG}/{real}", "kind": "reference_only", "grade": "referenced", "pinned_ref": None, "upstream_head": heads[real],
                                          "compare_status": None, "observed_at": p["observed_at"], "evidence_path": f"pypi/pypi_inventory.json#projects.{name}.project_urls.{k}"})

    # --- Cloudflare
    cf_obs = cf["observed_at"]; acct = cf["accounts"][0]["id"] if cf["accounts"] else "unknown"
    pa = cf["per_account"].get(acct, {})
    for w in pa.get("workers_scripts", []):
        aid = f"cf_worker:cloudflare/{w['id']}"
        add(aid, "cf_worker", "cloudflare", w["id"], w["id"], "unknown", cf_obs, f"cloudflare/cf_inventory.json#per_account.workers_scripts[{w['id']}]",
            {"etag": w.get("etag"), "modified_on": w.get("modified_on"), "created_on": w.get("created_on"), "handlers": w.get("handlers"), "compatibility_date": w.get("compatibility_date"),
             "last_deployed_from": w.get("last_deployed_from"), "has_assets": w.get("has_assets"), "usage_model": w.get("usage_model")},
            {"kind": "worker_etag", "revision": w["id"], "digest_sha256": w.get("etag") if w.get("etag") and len(w["etag"]) == 64 else None, "digest_filename": "deployed-etag"})
    def simple(items, atype, namer, extra, ev_key):
        for x in items:
            nm = namer(x)
            add(f"{atype}:cloudflare/{nm}", atype, "cloudflare", nm, x.get("uuid") or x.get("id"), "unknown", cf_obs, f"cloudflare/cf_inventory.json#per_account.{ev_key}[{nm}]", extra(x))
    simple(pa.get("d1", []), "cf_d1", lambda x: x["name"], lambda x: {"created_at": x.get("created_at"), "file_size": x.get("file_size"), "num_tables": x.get("num_tables"), "version": x.get("version")}, "d1")
    simple(pa.get("r2_buckets", []), "cf_r2", lambda x: x["name"], lambda x: {"created": x.get("creation_date"), "location": x.get("location"), "storage_class": x.get("storage_class")}, "r2_buckets")
    simple(pa.get("kv", []), "cf_kv", lambda x: x["title"], lambda x: {}, "kv")
    simple(pa.get("tunnels", []), "cf_tunnel", lambda x: x["name"], lambda x: {"status": x.get("status"), "created_at": x.get("created_at"), "conns_active_at": x.get("conns_active_at"), "tun_type": x.get("tun_type")}, "tunnels")
    simple(pa.get("access_apps", []), "cf_access_app", lambda x: f"{x.get('name')}:{x['id'][:8]}", lambda x: {"domain": x.get("domain"), "type": x.get("type"), "session_duration": x.get("session_duration")}, "access_apps")
    simple(pa.get("workers_domains", []), "cf_worker_domain", lambda x: x["hostname"], lambda x: {"service": x.get("service"), "zone_name": x.get("zone_name"), "environment": x.get("environment")}, "workers_domains")
    for z in cf["zones"]:
        add(f"cf_zone:cloudflare/{z['name']}", "cf_zone", "cloudflare", z["name"], z["id"], "unknown", cf_obs, f"cloudflare/cf_inventory.json#zones[{z['name']}]", {"status": z.get("status"), "plan": z.get("plan")})
        pz = cf["per_zone"].get(z["id"], {})
        for d in pz.get("dns_records", []):
            nm = f"{d['type']}:{d['name']}:{d['id'][:8]}"
            add(f"cf_dns_record:{z['name']}/{nm}", "cf_dns_record", z["name"], nm, d["id"], "unknown", cf_obs, f"cloudflare/cf_inventory.json#per_zone.{z['name']}.dns_records[{d['id'][:8]}]",
                {"type": d["type"], "fqdn": d["name"], "content": d.get("content"), "proxied": d.get("proxied"), "ttl": d.get("ttl"), "modified_on": d.get("modified_on"), "comment": d.get("comment")})
        for rt in pz.get("worker_routes", []):
            add(f"cf_route:{z['name']}/{rt['pattern']}", "cf_route", z["name"], rt["pattern"], rt["id"], "unknown", cf_obs, f"cloudflare/cf_inventory.json#per_zone.{z['name']}.worker_routes[{rt['id'][:8]}]", {"script": rt.get("script")})
            if rt.get("script") and f"cf_worker:cloudflare/{rt['script']}" in assets:
                pass
    # Cloudflare declared sources from wrangler files
    for r in refs:
        if r["kind"] == "cloudflare" and r["target_type"] in ("worker_script", "d1", "r2"):
            atype = {"worker_script": "cf_worker", "d1": "cf_d1", "r2": "cf_r2"}[r["target_type"]]
            aid = f"{atype}:cloudflare/{r['target_id']}"
            if aid in assets and f"github_repo:{ORG}/{r['repo']}" in assets:
                bindings.append({"asset_id": aid, "upstream_asset_id": f"github_repo:{ORG}/{r['repo']}", "kind": "wrangler_in_repo", "grade": "declared", "pinned_ref": None, "upstream_head": heads[r["repo"]],
                                 "compare_status": None, "observed_at": gh["repos"][r["repo"]]["observed_at"], "evidence_path": r["evidence_path"]})
    # HF assets referenced from repo text (candidate only)
    hf_ids = {a["name"].lower(): a["asset_id"] for a in assets.values() if a["asset_type"].startswith("hf_")}
    seen_ref = set()
    for r in refs:
        if r["kind"] == "hf" and f"github_repo:{ORG}/{r['repo']}" in assets:
            nm = r["target_id"].split("/", 1)[1].lower()
            aid = hf_ids.get(nm)
            if aid and (aid, r["repo"]) not in seen_ref:
                seen_ref.add((aid, r["repo"]))
                bindings.append({"asset_id": aid, "upstream_asset_id": f"github_repo:{ORG}/{r['repo']}", "kind": "reference_only", "grade": "referenced", "pinned_ref": None, "upstream_head": heads[r["repo"]],
                                 "compare_status": None, "observed_at": gh["repos"][r["repo"]]["observed_at"], "evidence_path": r["evidence_path"]})
    for r in refs:
        crefs.append({"from_asset_id": f"github_repo:{ORG}/{r['repo']}", "kind": r["kind"], "target_type": r["target_type"], "target_id": r["target_id"], "evidence_path": r["evidence_path"], "snippet": r["snippet"], "observed_at": gh["repos"][r["repo"]]["observed_at"]})

    # dedupe bindings on PK (asset, upstream, kind): keep the strongest-evidence (prefer pinned)
    best = {}
    for b in bindings:
        k = (b["asset_id"], b["upstream_asset_id"], b["kind"])
        if k not in best or (b["pinned_ref"] and not best[k]["pinned_ref"]): best[k] = b
    bindings = [best[k] for k in sorted(best)]

    # --- coverage
    from collections import Counter
    cnt = Counter(a["asset_type"] for a in assets.values())
    cand_py = set(py["projects"]); exist_py = {n for n, p in py["projects"].items() if p.get("exists")}
    cov = [{"source": "github", "asset_type": "github_repo", "expected": gq["totalCount"], "ingested": cnt["github_repo"], "detail": {"rest": len(enum["repos"]), "graphql_totalCount": gq["totalCount"], "gh_repo_list": len(jl("github/enum_ghcli.json")["repos"]),
            "ls_remote_heads_match": sum(1 for r in gh["repos"].values() if (r["ls_remote"] or {}).get("HEAD") == r["gql"]["defaultBranchRef"]["target"]["oid"]), "private_content_not_scanned": sorted(n for n, r in gh["repos"].items() if r["gql"]["isPrivate"]), "visibility_gaps": []},
            "evidence": "github/enum_rest.json,github/enum_graphql.json,github/enum_ghcli.json"}]
    ov = hf["overview_counts"]
    for kind, f in (("model", "numModels"), ("dataset", "numDatasets"), ("space", "numSpaces"), ("kernel", "numKernels"), ("bucket", "numBuckets")):
        cov.append({"source": "hf", "asset_type": HF_TYPE[kind], "expected": ov[f], "ingested": cnt[HF_TYPE[kind]], "detail": {"overview_field": f}, "evidence": "hf/hf_inventory.json#overview_counts"})
    cov.append({"source": "hf", "asset_type": "hf_collection", "expected": hf["kinds"]["collection"]["count"], "ingested": cnt["hf_collection"], "detail": {"note": "no independent count endpoint; list length only"}, "evidence": "hf/hf_inventory.json#kinds.collection"})
    cov.append({"source": "pypi", "asset_type": "pypi_project", "expected": len(cand_py), "ingested": cnt["pypi_project"], "detail": {"candidates": len(cand_py), "exist_on_pypi": len(exist_py), "not_found_404": sorted(n for n, p in py["projects"].items() if p.get("exists") is False)[:200],
            "missing_reason": "not registry assets: 404 on PyPI (unpublished/private/never-published) or third-party names mentioned in repo text", "third_party_existing_excluded": sorted(n for n in exist_py if f"pypi_project:pypi/{n}" not in assets),
            "discovery": "candidate names from szl-holdings repo text/pyproject; PyPI HTML/maintainer pages are behind a bot challenge and were not used"}, "evidence": "pypi/pypi_inventory.json"})
    for atype, key in (("cf_worker", "workers_scripts"), ("cf_d1", "d1"), ("cf_r2", "r2_buckets"), ("cf_kv", "kv"), ("cf_tunnel", "tunnels"), ("cf_access_app", "access_apps"), ("cf_worker_domain", "workers_domains")):
        cov.append({"source": "cloudflare", "asset_type": atype, "expected": len(pa.get(key, [])), "ingested": cnt[atype], "detail": {}, "evidence": f"cloudflare/cf_inventory.json#per_account.{key}"})
    cov.append({"source": "cloudflare", "asset_type": "cf_zone", "expected": len(cf["zones"]), "ingested": cnt["cf_zone"], "detail": {"gaps": cf["gaps"]}, "evidence": "cloudflare/cf_inventory.json#zones"})
    cov.append({"source": "cloudflare", "asset_type": "cf_dns_record", "expected": sum(len(v.get("dns_records", [])) for v in cf["per_zone"].values()), "ingested": cnt["cf_dns_record"], "detail": {}, "evidence": "cloudflare/cf_inventory.json#per_zone"})
    cov.append({"source": "cloudflare", "asset_type": "cf_route", "expected": sum(len(v.get("worker_routes", [])) for v in cf["per_zone"].values()), "ingested": cnt["cf_route"], "detail": {}, "evidence": "cloudflare/cf_inventory.json#per_zone"})
    for c in cov: c["missing"] = max(0, c["expected"] - c["ingested"]) if c["asset_type"] != "pypi_project" else len(cand_py) - len(exist_py) + len([n for n in exist_py if f"pypi_project:pypi/{n}" not in assets])

    snap = {"meta": {"schema_version": 1, "tool_version": TOOL_VERSION, "observed": {"github": gh.get("completed_at"), "hf": hf_obs, "pypi": py_obs, "cloudflare": cf_obs},
                     "raw_sha256": {p: sha_file(p) for p in sorted(os.path.relpath(x, RAW) for x in glob.glob(f"{RAW}/*/*.json"))}},
            "assets": [assets[k] for k in sorted(assets)], "bindings": bindings, "candidate_refs": sorted(crefs, key=lambda c: (c["from_asset_id"], c["kind"], c["target_type"], c["target_id"], c["evidence_path"])), "coverage": cov}
    body = json.dumps(snap, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    snap["meta"]["snapshot_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f: json.dump(snap, f, sort_keys=True, indent=1)
    if not quiet: print("assets", len(assets), dict(cnt)); print("bindings", len(bindings), Counter((b["kind"], b["grade"]) for b in bindings)); print("candidate_refs", len(crefs)); print("sha256", snap["meta"]["snapshot_sha256"])

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(RAW_ROOT), "snapshots", "snapshot.json"))
