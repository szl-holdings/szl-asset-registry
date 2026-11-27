"""Minimal MCP server (JSON-RPC 2.0 over stdio, stdlib only) exposing the registry READ API.
Opens the database read-only. `registry_propose_update` writes only to the proposal outbox directory;
the single writer files it under a receipt. There is deliberately no delete tool.
Run: python -m registry_db.mcp_server --db local/registry.db --outbox local/outbox"""
import argparse, json, sys
from . import api, __version__

TOOLS = [
    {"name": "registry_query", "description": "List registry assets. Filters: asset_type, alignment_state (ALIGNED|BEHIND|DRIFTED|UNTRACEABLE|UNKNOWN), visibility, name_like, limit<=500, offset.",
     "inputSchema": {"type": "object", "properties": {"asset_type": {"type": "string"}, "alignment_state": {"type": "string", "enum": ["ALIGNED", "BEHIND", "DRIFTED", "UNTRACEABLE", "UNKNOWN"]}, "visibility": {"type": "string"}, "name_like": {"type": "string"}, "limit": {"type": "integer"}, "offset": {"type": "integer"}}}},
    {"name": "registry_get_asset", "description": "One asset with facts (each with observed_at + evidence_path), own revision, source bindings, fact history and proposals.",
     "inputSchema": {"type": "object", "properties": {"asset_id": {"type": "string"}}, "required": ["asset_id"]}},
    {"name": "registry_alignment_summary", "description": "Counts of alignment_state per asset_type.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "registry_coverage", "description": "Expected vs ingested vs missing for the latest ingest run, per source/type.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "registry_verify_receipts", "description": "Recompute the receipt hash chain; returns ok/count/head/error.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "registry_list_receipts", "description": "Newest receipts (who/when/why).", "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
    {"name": "registry_propose_update", "description": "File a proposed change (set_binding|set_fact(key must start 'agent.')|mark_absent|request_delete). Queued in the outbox; applied only after the single writer files it and a human decides, each under a receipt. Requires actor and reason.",
     "inputSchema": {"type": "object", "properties": {"actor": {"type": "string"}, "asset_id": {"type": "string"}, "change_kind": {"type": "string", "enum": list(api.CHANGE_KINDS)}, "proposed": {"type": "object"}, "reason": {"type": "string"}}, "required": ["actor", "asset_id", "change_kind", "proposed", "reason"]}},
]

def call_tool(conn, outbox, name, args):
    if name == "registry_query": return api.query_assets(conn, **{k: v for k, v in args.items() if k in ("asset_type", "alignment_state", "visibility", "name_like", "limit", "offset")})
    if name == "registry_get_asset": return api.get_asset(conn, args["asset_id"]) or {"error": "not found"}
    if name == "registry_alignment_summary": return api.alignment_summary(conn)
    if name == "registry_coverage": return api.coverage(conn)
    if name == "registry_verify_receipts": return api.verify_receipts(conn)
    if name == "registry_list_receipts": return api.list_receipts(conn, args.get("limit", 50))
    if name == "registry_propose_update": return api.propose_update(outbox, conn, **{k: args[k] for k in ("actor", "asset_id", "change_kind", "proposed", "reason")})
    raise KeyError(name)

def handle(conn, outbox, msg):
    mid, method = msg.get("id"), msg.get("method")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "szl-asset-registry", "version": __version__}}}
    if method == "tools/list": return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        p = msg.get("params") or {}
        try:
            res = call_tool(conn, outbox, p.get("name"), p.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(res, sort_keys=True, default=str)}], "isError": False}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}}
    if method and method.startswith("notifications/"): return None
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); ap.add_argument("--outbox", required=True); a = ap.parse_args(argv)
    conn = api.connect_ro(a.db)
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try: out = handle(conn, a.outbox, json.loads(line))
        except Exception as e: out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}
        if out is not None: sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()

if __name__ == "__main__":
    main()
