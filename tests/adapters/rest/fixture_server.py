"""A tiny, fully-offline loopback HTTP server used to exercise the REST
executor against real HTTP requests without touching any external network
(Phase 3 brief §16: "if real HTTP execution is needed, build a local test
server fixture" / "don't use external websites as a test dependency").

stdlib-only, no new test dependency.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VALID_BEARER_TOKEN = "testtoken123"
VALID_API_KEY = "testapikey456"
SESSION_COOKIE_VALUE = "sess_9f8e7d6c5b4a"  # /with-cookie: V1 hardening audit -- cookie redaction check
SLOW_ENDPOINT_DELAY_SECONDS = 0.3
UNSTABLE_FAILURE_EVERY_NTH = 3  # /unstable: every Nth request fails deterministically

_unstable_lock = threading.Lock()
_unstable_counter = {"n": 0}


def reset_unstable_counter() -> None:
    """Deterministic /unstable behavior is per-test; call this before relying
    on the "every Nth request fails" pattern from a known starting point.
    """
    with _unstable_lock:
        _unstable_counter["n"] = 0


class _FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:  # silence default request logging
        pass

    def _send_json(self, status: int, payload, extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler naming convention
        if self.path == "/users":
            self._send_json(200, [{"id": 1, "name": "Alice"}])
        elif self.path == "/widgets":
            self._send_json(200, {"id": 1, "name": "Widget"})
        elif self.path == "/widgets-broken":
            self._send_json(200, {"unexpected_field": True})
        elif self.path == "/health":
            self._send_json(200, {"status": "ok"})
        elif self.path == "/slow":
            time.sleep(SLOW_ENDPOINT_DELAY_SECONDS)
            self._send_json(200, {"status": "eventually ok"})
        elif self.path == "/fast":
            self._send_json(200, {"status": "ok"})
        elif self.path == "/error":
            self._send_json(500, {"error": "internal error"})
        elif self.path == "/unstable":
            with _unstable_lock:
                _unstable_counter["n"] += 1
                n = _unstable_counter["n"]
            if n % UNSTABLE_FAILURE_EVERY_NTH == 0:
                self._send_json(500, {"error": "unstable failure"})
            else:
                self._send_json(200, {"status": "ok"})
        elif self.path == "/secure":
            auth = self.headers.get("Authorization", "")
            if auth == f"Bearer {VALID_BEARER_TOKEN}":
                self._send_json(200, {"status": "ok"})
            else:
                self._send_json(401, {"error": "unauthorized"})
        elif self.path == "/secure-apikey":
            if self.headers.get("X-API-Key") == VALID_API_KEY:
                self._send_json(200, {"status": "ok"})
            else:
                self._send_json(401, {"error": "unauthorized"})
        elif self.path == "/with-cookie":
            self._send_json(200, {"status": "ok"}, extra_headers={
                "Set-Cookie": f"session={SESSION_COOKIE_VALUE}; HttpOnly; Path=/",
            })
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw_body = self.rfile.read(length) if length else b""
        content_type = self.headers.get("Content-Type", "")

        if self.path != "/users":
            self._send_json(404, {"error": "not found"})
            return
        if "application/json" not in content_type:
            self._send_json(400, {"error": "unsupported content type"})
            return
        try:
            data = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            self._send_json(400, {"error": "malformed json"})
            return
        if not isinstance(data, dict) or "name" not in data or "email" not in data:
            self._send_json(400, {"error": "missing required field"})
            return
        self._send_json(201, {"id": 2, **data})


class FixtureServer:
    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "FixtureServer":
        reset_unstable_counter()
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __enter__(self) -> "FixtureServer":
        return self.start()

    def __exit__(self, *exc_info) -> None:
        self.stop()
