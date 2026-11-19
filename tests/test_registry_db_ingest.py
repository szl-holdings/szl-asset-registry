import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import http.server, json, os, threading, unittest
from registry_db.ingest import common, gh_refs, hf_commits
import re

class Handler(http.server.BaseHTTPRequestHandler):
    calls = 0
    def do_GET(self):
        Handler.calls += 1
        if Handler.calls == 1:
            self.send_response(429); self.send_header("Retry-After", "1"); self.end_headers(); return
        if Handler.calls == 2:
            self.send_response(403); self.send_header("X-RateLimit-Remaining", "0"); self.send_header("X-RateLimit-Reset", str(int(__import__("time").time()) + 1)); self.end_headers(); return
        if self.path == "/forbidden":
            self.send_response(403); self.end_headers(); self.wfile.write(b'{"message":"no"}'); return
        body = json.dumps({"ok": True, "auth": self.headers.get("Authorization")}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

class HttpBackoffTest(unittest.TestCase):
    def test_429_and_rate_limit_403_are_waited_out_then_succeed(self):
        srv = http.server.HTTPServer(("127.0.0.1", 0), Handler); threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            Handler.calls = 0; old = common.MIN_INTERVAL; common.MIN_INTERVAL = 0
            out = common.http_json(f"http://127.0.0.1:{srv.server_port}/x", token="t0k")
            self.assertTrue(out["ok"]); self.assertEqual(Handler.calls, 3)
            with self.assertRaises(common.HttpErr) as cm: common.http_json(f"http://127.0.0.1:{srv.server_port}/forbidden")
            self.assertEqual(cm.exception.code, 403)                      # plain permission denial is surfaced, not retried/dropped
            common.MIN_INTERVAL = old
        finally: srv.shutdown()

    def test_only_get_or_graphql_query_used_by_ingest(self):
        base = os.path.join(os.path.dirname(common.__file__))
        for fn in os.listdir(base):
            if fn.endswith(".py"):
                src = open(os.path.join(base, fn)).read()
                for verb in ('method="PUT"', 'method="PATCH"', 'method="DELETE"', "method='PUT'", "method='DELETE'", "-X PUT", "-X DELETE", "-X PATCH"):
                    self.assertNotIn(verb, src, fn)
                self.assertFalse(re.search(r'method="POST"', src) and fn not in ("gh_enumerate.py", "gh_detail.py"), fn)   # POST only for GraphQL queries
        for fn in ("gh_enumerate.py", "gh_detail.py"):
            src = open(os.path.join(base, fn)).read(); self.assertNotIn("mutation", src.lower())

class ReferenceExtractionTest(unittest.TestCase):
    def test_extracts_hf_pypi_cloudflare_candidates_with_line_evidence(self):
        text = "intro\nSee https://huggingface.co/spaces/SZLHOLDINGS/demo and `pip install szl-widget`\nhost a11oy.a-11-oy.com\n"
        out = []; gh_refs.scan(text, "README.md", "repo1", out)
        got = {(r["kind"], r["target_type"], r["target_id"], r["evidence_path"]) for r in out}
        self.assertIn(("hf", "space", "SZLHOLDINGS/demo", "repo1:README.md#L2"), got)
        self.assertIn(("pypi", "project", "szl-widget", "repo1:README.md#L2"), got)
        self.assertIn(("cloudflare", "hostname", "a11oy.a-11-oy.com", "repo1:README.md#L3"), got)

    def test_wrangler_names_extracted_for_nested_paths(self):
        out = []; gh_refs.scan('name = "my-worker"\n[[d1_databases]]\ndatabase_name = "my-db"\nbucket_name = "b1"\n', "apps/x/wrangler.toml", "r", out)
        got = {(r["target_type"], r["target_id"]) for r in out}
        self.assertEqual(got, {("worker_script", "my-worker"), ("d1", "my-db"), ("r2", "b1")})

    def test_hf_commit_pin_regex(self):
        t = "deploy(hf): sync szl-holdings/a11oy@02fe78903c859aa7ef570b96bcb36724b5d59bb4 derived COPY"
        m = hf_commits.PIN.search(t); self.assertEqual((m.group(1), m.group(2)), ("a11oy", "02fe78903c859aa7ef570b96bcb36724b5d59bb4"))
        self.assertIsNone(hf_commits.PIN.search("sync szl-holdings/a11oy@abc123"))      # short shas are not accepted as verified pins

if __name__ == "__main__":
    unittest.main()
