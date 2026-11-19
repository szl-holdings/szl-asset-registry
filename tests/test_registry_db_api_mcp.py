import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import json, os, shutil, sqlite3, tempfile, unittest
from registry_db import api, loader, mcp_server, receipts
from registry_db_fixtures import write_raw
import ingest_snapshot_helper as helper

class ApiMcpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); raw = os.path.join(self.tmp, "raw"); write_raw(raw)
        self.db = os.path.join(self.tmp, "r.db"); loader.load(self.db, helper.build(raw, self.tmp)); self.ob = os.path.join(self.tmp, "ob")
        self.ro = api.connect_ro(self.db)
    def tearDown(self): self.ro.close(); shutil.rmtree(self.tmp)

    def test_read_connection_cannot_write(self):
        for sql in ("DELETE FROM assets", "UPDATE assets SET name='x'", "INSERT INTO receipts (seq) VALUES (1)", "DROP TABLE assets"):
            with self.assertRaisesRegex(sqlite3.OperationalError, "readonly"): self.ro.execute(sql)

    def test_query_filters_and_pagination(self):
        r = api.query_assets(self.ro, asset_type="hf_model"); self.assertEqual(r["total"], 3)
        r = api.query_assets(self.ro, alignment_state="untraceable"); self.assertEqual({i["asset_id"] for i in r["items"]}, {"hf_model:SZLHOLDINGS/no-source", "cf_worker:cloudflare/stray-worker"})
        r = api.query_assets(self.ro, limit=2); self.assertEqual((len(r["items"]), r["total"] > 2), (2, True))
        self.assertEqual(api.query_assets(self.ro, name_like="%")["total"], 0)       # LIKE wildcards are escaped

    def test_get_asset_returns_facts_with_evidence_and_bindings(self):
        a = api.get_asset(self.ro, "hf_space:SZLHOLDINGS/core-space")
        self.assertEqual(a["asset"]["alignment_state"], "behind")
        self.assertTrue(all(f["evidence_path"] and f["observed_at"] for f in a["facts"].values()))
        self.assertEqual(a["bindings"][0]["pin_comparison"], "upstream_ahead")
        self.assertIsNone(api.get_asset(self.ro, "nope"))

    def test_mcp_tools_have_no_delete_and_dispatch(self):
        names = [t["name"] for t in mcp_server.TOOLS]
        self.assertFalse([n for n in names if "delete" in n or "remove" in n])
        out = mcp_server.handle(self.ro, self.ob, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(len(out["result"]["tools"]), len(names))
        res = mcp_server.handle(self.ro, self.ob, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "registry_verify_receipts", "arguments": {}}})
        self.assertTrue(json.loads(res["result"]["content"][0]["text"])["ok"])
        bad = mcp_server.handle(self.ro, self.ob, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "registry_delete_asset", "arguments": {}}})
        self.assertTrue(bad["result"]["isError"])
        unk = mcp_server.handle(self.ro, self.ob, {"jsonrpc": "2.0", "id": 4, "method": "nope"}); self.assertEqual(unk["error"]["code"], -32601)

    def test_mcp_propose_requires_actor_and_reason(self):
        r = mcp_server.handle(self.ro, self.ob, {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "registry_propose_update",
              "arguments": {"actor": "agent:a", "asset_id": "hf_model:SZLHOLDINGS/no-source", "change_kind": "mark_absent", "proposed": {}, "reason": ""}}})
        self.assertTrue(r["result"]["isError"])
        self.assertFalse(os.path.exists(self.ob) and os.listdir(self.ob))

    def test_stdio_roundtrip(self):
        import subprocess, sys
        env = dict(os.environ, PYTHONPATH=os.path.join(os.path.dirname(__file__), ".."))
        p = subprocess.run([sys.executable, "-m", "registry_db.mcp_server", "--db", self.db, "--outbox", self.ob], input='{"jsonrpc":"2.0","id":1,"method":"initialize"}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n',
                           capture_output=True, text=True, env=env, timeout=30)
        lines = [json.loads(l) for l in p.stdout.splitlines()]; self.assertEqual([l["id"] for l in lines], [1, 2])

if __name__ == "__main__":
    unittest.main()
