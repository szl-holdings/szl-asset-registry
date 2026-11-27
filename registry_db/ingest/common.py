"""Shared read-only HTTP helpers for the SZL asset-registry ingest (stdlib only).

Rules enforced here: GET/POST-GraphQL-query only, paced, honours 429/403-secondary
limits via Retry-After / x-ratelimit-reset, never logs credentials.
"""
import http.client, json, os, time, urllib.request, urllib.error, urllib.parse, datetime

RAW_ROOT = os.environ.get("REGISTRY_RAW_DIR") or os.path.abspath("raw")
UA = "szl-asset-registry-ingest/0.1 (read-only metadata)"
MIN_INTERVAL = float(os.environ.get("INGEST_MIN_INTERVAL", "0.25"))
_last = {"t": 0.0}

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _pace():
    d = time.time() - _last["t"]
    if d < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - d)
    _last["t"] = time.time()

def http_json(url, token=None, method="GET", body=None, headers=None, max_retries=6, return_headers=False):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    if headers:
        h.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    delay = 2.0
    for attempt in range(max_retries):
        _pace()
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                out = json.loads(raw) if raw else None
                return (out, dict(r.headers)) if return_headers else out
        except urllib.error.HTTPError as e:
            hd = _CI(e.headers)
            if e.code in (429, 403, 502, 503, 504):
                ra = hd.get("Retry-After")
                rem = hd.get("x-ratelimit-remaining") or hd.get("X-RateLimit-Remaining")
                if ra:
                    wait = float(ra)
                elif rem == "0" and hd.get("x-ratelimit-reset"):
                    wait = max(1.0, float(hd["x-ratelimit-reset"]) - time.time() + 1)
                elif e.code in (429, 403):
                    wait = delay
                else:
                    wait = delay
                if e.code == 403 and not ra and rem != "0":
                    # plain permission 403: do not retry, surface it
                    raise HttpErr(e.code, url, e.read()[:300].decode("utf8", "replace"))
                wait = min(wait, 900)
                print(f"  [backoff {e.code}] sleeping {wait:.0f}s", flush=True)
                time.sleep(wait)
                delay = min(delay * 2, 120)
                continue
            raise HttpErr(e.code, url, e.read()[:300].decode("utf8", "replace"))
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as e:
            time.sleep(delay); delay = min(delay * 2, 120)
            if attempt == max_retries - 1:
                raise HttpErr(0, url, str(e))
    raise HttpErr(0, url, "retries exhausted")

class _CI:
    """case-insensitive header view"""
    def __init__(self, h): self.h = h
    def get(self, k, d=None): return self.h.get(k, d) if self.h is not None else d
    def __getitem__(self, k):
        v = self.get(k)
        if v is None: raise KeyError(k)
        return v

class HttpErr(Exception):
    def __init__(self, code, url, msg):
        super().__init__(f"HTTP {code} {url}: {msg}")
        self.code, self.url, self.msg = code, url, msg

def paginate_link(url, token, per_page_key="per_page=100", headers=None):
    """Follow RFC5988 Link rel=next to the end."""
    out = []
    while url:
        data, hd = http_json(url, token, headers=headers, return_headers=True)
        out.append(data)
        link = hd.get("Link") or hd.get("link") or ""
        nxt = None
        for part in link.split(","):
            if 'rel="next"' in part:
                nxt = part[part.index("<") + 1: part.index(">")]
        url = nxt
    return out

def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(tmp, path)
