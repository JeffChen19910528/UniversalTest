"""Bounded, Universal-Test-owned static file server (spec §17-§18, §47).

Used to test a project's static site over http://127.0.0.1:<port> instead
of relying on `file://`'s inconsistent behavior. Binds loopback only,
picks an OS-assigned ephemeral port, and is guaranteed to shut down on
context exit -- never leaves an orphaned server, and never executes any
project script (`npm run dev`, etc. are explicitly out of scope).
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import threading
from pathlib import Path
from typing import Iterator

LOOPBACK_HOST = "127.0.0.1"

# Chromium refuses to navigate to a fixed list of ports it considers unsafe
# (net::ERR_UNSAFE_PORT) -- e.g. 1720 (H.323 Gatekeeper Discovery). An
# OS-assigned ephemeral port (port 0) can occasionally land on one of these,
# which previously surfaced as flaky `BrowserNetworkError`s with no obvious
# cause. See Chromium's `net/base/port_util.cc` kRestrictedPorts.
_CHROMIUM_RESTRICTED_PORTS = frozenset({
    1, 7, 9, 11, 13, 15, 17, 19, 20, 21, 22, 23, 25, 37, 42, 43, 53, 69, 77, 79,
    87, 95, 101, 102, 103, 104, 109, 110, 111, 113, 115, 117, 119, 123, 135,
    137, 139, 143, 161, 179, 389, 427, 465, 512, 513, 514, 515, 526, 530, 531,
    532, 540, 548, 554, 556, 563, 587, 601, 636, 989, 990, 993, 995, 1719,
    1720, 1723, 2049, 3659, 4045, 5060, 5061, 6000, 6566, 6665, 6666, 6667,
    6668, 6669, 6697, 10080,
})
_MAX_BIND_ATTEMPTS = 10


def _bind_avoiding_restricted_ports(handler) -> http.server.ThreadingHTTPServer:
    last_server: http.server.ThreadingHTTPServer | None = None
    for _ in range(_MAX_BIND_ATTEMPTS):
        server = http.server.ThreadingHTTPServer((LOOPBACK_HOST, 0), handler)
        if server.server_address[1] not in _CHROMIUM_RESTRICTED_PORTS:
            return server
        server.server_close()  # this specific port is unsafe for a browser to navigate to -- retry
        last_server = server
    return last_server  # pragma: no cover - astronomically unlikely to exhaust every retry


@contextlib.contextmanager
def serve_directory(root: str | Path) -> Iterator[str]:
    """Yields the base URL (e.g. "http://127.0.0.1:54321") of a server
    serving `root` for the duration of the `with` block. Server thread is
    a daemon and is explicitly shut down in `finally`. Never binds a port
    Chromium itself refuses to navigate to (see `_CHROMIUM_RESTRICTED_PORTS`).
    """
    root_path = Path(root).resolve()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root_path))
    server = _bind_avoiding_restricted_ports(handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
