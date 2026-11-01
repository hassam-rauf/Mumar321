"""Tiny WooCommerce REST API v3 client (stdlib only).

Auth: HTTPS -> Basic auth with consumer key/secret (same as Make's HTTP module).
      HTTP  -> OAuth 1.0a one-legged signature (WooCommerce rejects Basic auth over plain HTTP).
"""
import base64, hashlib, hmac, json, os, secrets, threading, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path


def load_env(path=Path(__file__).resolve().parent.parent / ".env"):
    """Load KEY=VALUE lines from .env into os.environ (without overriding real env vars)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.split(" #", 1)[0].strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


TRACE = threading.local()  # per-request list of Woo calls (shown in demo mode)


def _trace(entry):
    if hasattr(TRACE, "calls"):
        TRACE.calls.append(entry)


class WooError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body}")
        self.status, self.body = status, body


class Woo:
    def __init__(self, url=None, key=None, secret=None, timeout=15):
        load_env()
        self.base = (url or os.environ["WOO_URL"]).rstrip("/") + "/wp-json/wc/v3"
        self.key = key or os.environ["WOO_CONSUMER_KEY"]
        self.secret = secret or os.environ["WOO_CONSUMER_SECRET"]
        self.timeout = timeout

    # -- auth helpers -------------------------------------------------------
    def _oauth_params(self, method, url, params):
        q = lambda s: urllib.parse.quote(str(s), safe="")
        oauth = {
            "oauth_consumer_key": self.key,
            "oauth_nonce": secrets.token_hex(16),
            "oauth_signature_method": "HMAC-SHA256",
            "oauth_timestamp": str(int(time.time())),
        }
        all_params = {**params, **oauth}
        norm = "%26".join(f"{q(k)}%3D{q(q(v))}" for k, v in sorted(all_params.items()))
        base_string = f"{method}&{q(url)}&{norm}"
        sig = hmac.new((self.secret + "&").encode(), base_string.encode(), hashlib.sha256).digest()
        oauth["oauth_signature"] = base64.b64encode(sig).decode()
        return oauth

    # -- request ------------------------------------------------------------
    def request(self, method, path, params=None, body=None):
        url = self.base + path
        params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        headers = {"Accept": "application/json", "User-Agent": "woo-voiceflow-demo/1.0"}
        if url.startswith("https://"):
            token = base64.b64encode(f"{self.key}:{self.secret}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
        else:
            params.update(self._oauth_params(method, url, params))
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        shown = "/wp-json/wc/v3" + path + ("?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if not k.startswith("oauth_")}) if any(not k.startswith("oauth_") for k in params) else "")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                _trace(f"{method} {shown} -> {r.status}")
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            _trace(f"{method} {shown} -> {e.code}")
            raw = e.read().decode(errors="replace")
            try:
                raw = json.loads(raw)
            except ValueError:
                pass
            raise WooError(e.code, raw) from None

    def get(self, path, **params):
        return self.request("GET", path, params)

    def post(self, path, body):
        return self.request("POST", path, body=body)
