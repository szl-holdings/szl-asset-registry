"""Step 5: Cloudflare read-only inventory (GET only). Token via env CF_API_TOKEN_SZL/CLOUDFLARE_API_TOKEN (never logged).
Endpoints the token cannot read are recorded as visibility gaps, never silently dropped."""
import os, sys, json
from .common import *
TOK = os.environ.get("CF_API_TOKEN_SZL") or os.environ["CLOUDFLARE_API_TOKEN"]
RAW = os.path.join(RAW_ROOT, "cloudflare")
API = "https://api.cloudflare.com/client/v4"

def cf_list(path, per_page=100, key=None):
    """returns (items, gap) ; follows page-based pagination."""
    items = []; page = 1
    while True:
        sep = "&" if "?" in path else "?"
        try:
            d = http_json(f"{API}{path}{sep}per_page={per_page}&page={page}", TOK)
        except HttpErr as e:
            if e.code == 400 and "8000024" in e.msg and per_page is not None:
                try:   # endpoint rejects pagination params: retry bare once
                    d = http_json(f"{API}{path}", TOK); r = d.get("result") or []
                    return (r if isinstance(r, list) else [r]), None
                except HttpErr as e2:
                    return items, {"path": path, "http": e2.code, "msg": e2.msg[:160]}
            return items, {"path": path, "http": e.code, "msg": e.msg[:160]}
        if not d.get("success"):
            return items, {"path": path, "errors": d.get("errors")}
        r = d.get("result")
        if isinstance(r, dict) and key: r = r.get(key, [])
        if not isinstance(r, list): return ([r] if r else []), None
        items += r
        ri = d.get("result_info") or {}
        if not ri or page >= (ri.get("total_pages") or 1) or not r: break
        page += 1
    return items, None

def main():
    out = {"observed_at": utcnow(), "gaps": [], "accounts": [], "zones": []}
    accts, g = cf_list("/accounts"); out["accounts"] = [{"id": a["id"], "name": a["name"]} for a in accts]
    zones, g2 = cf_list("/zones")
    out["zones"] = [{"id": z["id"], "name": z["name"], "status": z.get("status"), "plan": (z.get("plan") or {}).get("name"), "account": (z.get("account") or {}).get("id")} for z in zones]
    for g_ in (g, g2):
        if g_: out["gaps"].append(g_)
    per = {}
    for a in out["accounts"]:
        aid = a["id"]; r = {}
        def get(name, path, key=None):
            items, gap = cf_list(f"/accounts/{aid}{path}", key=key)
            r[name] = items
            if gap: out["gaps"].append(gap)
            print(f"{name}: {len(items)}" + (f" GAP {gap.get('http') or gap.get('errors')}" if gap else ""), flush=True)
        get("workers_scripts", "/workers/scripts")
        get("workers_domains", "/workers/domains")
        get("d1", "/d1/database")
        get("r2_buckets", "/r2/buckets", key="buckets")
        get("kv", "/storage/kv/namespaces")
        get("tunnels", "/cfd_tunnel?is_deleted=false")
        get("pages_projects", "/pages/projects")
        get("queues", "/queues")
        get("vectorize", "/vectorize/v2/indexes")
        get("hyperdrive", "/hyperdrive/configs")
        get("access_apps", "/access/apps")
        sub, gap = cf_list(f"/accounts/{aid}/workers/subdomain")
        r["workers_subdomain"] = sub
        if gap: out["gaps"].append(gap)
        per[aid] = r
    out["per_account"] = per
    zr = {}
    for z in out["zones"]:
        zid = z["id"]; e = {}
        for name, path in (("dns_records", "/dns_records"), ("worker_routes", "/workers/routes")):
            items, gap = cf_list(f"/zones/{zid}{path}")
            e[name] = items
            if gap: out["gaps"].append(gap)
            print(z["name"], name, len(items), flush=True)
        zr[zid] = e
    out["per_zone"] = zr
    write_json(f"{RAW}/cf_inventory.json", out)
    print("gaps:", json.dumps(out["gaps"])[:600])

if __name__ == "__main__":
    main()
