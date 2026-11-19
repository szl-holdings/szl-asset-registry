"""Step 2b: derive packaging flags + candidate bindings (HF / PyPI / Cloudflare) with evidence paths
from the already-fetched public-repo text. Candidates only: a reference is evidence, not proof of ownership."""
import os, sys, json, re, tomllib
from .common import utcnow, write_json, RAW_ROOT
RAW = os.path.join(RAW_ROOT, "github")
FILES = ["README.md", "pyproject.toml", "package.json", "wrangler.toml", "wrangler.jsonc", "wrangler.json", "setup.py"]
HF_RE = re.compile(r"huggingface\.co/(?:(spaces|datasets|kernels)/)?(SZLHOLDINGS|szlholdings)/([A-Za-z0-9_.-]+)", re.I)
HF_ID_RE = re.compile(r"""['"](SZLHOLDINGS)/([A-Za-z0-9_.-]{2,80})['"]""")
PYPI_URL_RE = re.compile(r"pypi\.org/(?:project|pypi)/([A-Za-z0-9_.-]+)", re.I)
PIP_RE = re.compile(r"pip3? install(?: -[-\w]+(?: \S+)?)* ['\"]?((?:szl|a11oy|hatun|khipu)[A-Za-z0-9_.-]*)", re.I)
CF_NAME_RE = re.compile(r'^\s*"?name"?\s*[=:]\s*"([A-Za-z0-9_.-]+)"', re.M)
CF_D1_RE = re.compile(r'database_name"?\s*[=:]\s*"([^"]+)"')
CF_R2_RE = re.compile(r'bucket_name"?\s*[=:]\s*"([^"]+)"')
CF_ROUTE_RE = re.compile(r'(?:pattern|custom_domain)"?\s*[=:]\s*"?([A-Za-z0-9_.*/-]+\.(?:com|net)[A-Za-z0-9_.*/-]*)')
CF_HOST_RE = re.compile(r"\b([a-z0-9-]+\.(?:a-11-oy\.com|a11oy\.net)|[a-z0-9-]+\.workers\.dev|[a-z0-9-]+\.pages\.dev)\b", re.I)

def line_of(text, pos): return text.count("\n", 0, pos) + 1

def scan(text, path, repo, out, is_workflow=False):
    def add(kind, ttype, tid, pos, rx_snip=None):
        ln = line_of(text, pos)
        snip = text.splitlines()[ln - 1].strip()[:160] if text else ""
        out.append({"repo": repo, "kind": kind, "target_type": ttype, "target_id": tid, "evidence_path": f"{repo}:{path}#L{ln}", "snippet": snip})
    for m in HF_RE.finditer(text):
        t = {"spaces": "space", "datasets": "dataset", "kernels": "kernel"}.get((m.group(1) or "model").lower(), "model")
        add("hf", t, f"SZLHOLDINGS/{m.group(3).rstrip('.')}", m.start())
    for m in HF_ID_RE.finditer(text):
        add("hf", "unknown", f"SZLHOLDINGS/{m.group(2)}", m.start())
    for m in PYPI_URL_RE.finditer(text): add("pypi", "project", m.group(1).lower(), m.start())
    for m in PIP_RE.finditer(text): add("pypi", "project", m.group(1).lower(), m.start())
    if is_workflow and re.search(r"pypa/gh-action-pypi-publish|twine upload|uv publish|trusted.?publish", text, re.I):
        m = re.search(r"pypa/gh-action-pypi-publish|twine upload|uv publish|trusted.?publish", text, re.I)
        add("pypi", "publisher_workflow", repo, m.start())
    if os.path.basename(path).startswith("wrangler"):
        m = CF_NAME_RE.search(text)
        if m: add("cloudflare", "worker_script", m.group(1), m.start(1))
        for m in CF_D1_RE.finditer(text): add("cloudflare", "d1", m.group(1), m.start())
        for m in CF_R2_RE.finditer(text): add("cloudflare", "r2", m.group(1), m.start())
        for m in CF_ROUTE_RE.finditer(text): add("cloudflare", "route", m.group(1), m.start())
    else:
        for m in CF_HOST_RE.finditer(text): add("cloudflare", "hostname", m.group(1).lower(), m.start())
    if is_workflow and re.search(r"wrangler[- ]action|wrangler deploy|cloudflare/wrangler", text, re.I):
        m = re.search(r"wrangler[- ]action|wrangler deploy|cloudflare/wrangler", text, re.I)
        add("cloudflare", "deploy_workflow", repo, m.start())

def main():
    st = json.load(open(f"{RAW}/repo_details.json"))["repos"]
    refs = []; facts = {}
    trees = json.load(open(f"{RAW}/repo_trees.json"))["repos"] if os.path.exists(f"{RAW}/repo_trees.json") else {}
    for name, rec in sorted(st.items()):
        g = rec["gql"]; priv = g["isPrivate"]
        root = [e["name"] for e in ((g.get("root") or {}).get("entries") or [])]
        wf_entries = (g.get("wf") or {}).get("entries") or []
        wf = [e["name"] for e in wf_entries]
        pk = [f for f in ["pyproject.toml", "setup.py", "setup.cfg", "package.json", "wrangler.toml", "wrangler.jsonc", "wrangler.json", "Dockerfile", "requirements.txt", "Cargo.toml", "go.mod", "action.yml", "action.yaml"] if f in root]
        pyname = None; pyver = None
        if not priv:
            for i, f in enumerate(FILES):
                b = g.get(f"b{i}")
                if b and b.get("text"):
                    scan(b["text"], f, name, refs)
                    if f == "pyproject.toml":
                        try:
                            t = tomllib.loads(b["text"]); p = t.get("project") or {}; po = (t.get("tool") or {}).get("poetry") or {}
                            pyname = p.get("name") or po.get("name"); pyver = p.get("version") or po.get("version")
                            if pyname: refs.append({"repo": name, "kind": "pypi", "target_type": "project", "target_id": pyname.lower().replace("_", "-"), "evidence_path": f"{name}:pyproject.toml#project.name", "snippet": f"name={pyname} version={pyver}"})
                        except Exception: pass
            for e in wf_entries:
                o = e.get("object") or {}
                if o.get("text"): scan(o["text"], f".github/workflows/{e['name']}", name, refs, True)
        tr = trees.get(name) or {}
        nested_py = []
        for npath, ntext in (tr.get("nested_text") or {}).items():
            scan(ntext, npath, name, refs)
            if npath.endswith("pyproject.toml"):
                try:
                    t = tomllib.loads(ntext); p = t.get("project") or {}
                    if p.get("name"):
                        nested_py.append({"path": npath, "name": p["name"], "version": p.get("version")})
                        refs.append({"repo": name, "kind": "pypi", "target_type": "project", "target_id": p["name"].lower().replace("_", "-"), "evidence_path": f"{name}:{npath}#project.name", "snippet": f"name={p['name']} version={p.get('version')}"})
                except Exception: pass
        facts[name] = {"tree_packaging_paths": tr.get("interesting", []), "migration_files": tr.get("migrations", []), "tree_file_count": tr.get("file_count"), "tree_truncated": tr.get("truncated"), "nested_pyprojects": nested_py, "root_entries": root, "workflows": wf, "packaging_files": pk, "pyproject_name": pyname, "pyproject_version": pyver, "content_scanned": not priv}
    # dedupe
    seen = set(); uniq = []
    for r in refs:
        k = (r["repo"], r["kind"], r["target_type"], r["target_id"], r["evidence_path"])
        if k not in seen: seen.add(k); uniq.append(r)
    write_json(f"{RAW}/repo_facts.json", {"observed_at": utcnow(), "facts": facts})
    write_json(f"{RAW}/candidate_bindings.json", {"observed_at": utcnow(), "refs": uniq})
    from collections import Counter
    print(len(uniq), Counter((r["kind"], r["target_type"]) for r in uniq))
    print("repos with packaging files:", sum(1 for f in facts.values() if f["packaging_files"]), "with workflows:", sum(1 for f in facts.values() if f["workflows"]))

if __name__ == "__main__":
    main()
