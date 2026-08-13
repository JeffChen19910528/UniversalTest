"""`local_server.py` reliability: never binds a port Chromium refuses to
navigate to (net::ERR_UNSAFE_PORT) -- a real flaky-test root cause found
while establishing the Phase 10 baseline (an OS-assigned ephemeral port
occasionally landed on Chromium's restricted-port list, e.g. 1720)."""

from __future__ import annotations

from pathlib import Path

from universal_test.adapters.browser.local_server import _CHROMIUM_RESTRICTED_PORTS, serve_directory

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_serve_directory_never_binds_a_chromium_restricted_port():
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        port = int(base_url.rsplit(":", 1)[1])
        assert port not in _CHROMIUM_RESTRICTED_PORTS


def test_serve_directory_repeatedly_avoids_restricted_ports():
    # Run several times to shake out flakiness rather than trusting one pass.
    for _ in range(20):
        with serve_directory(FIXTURES / "browser-static-basic") as base_url:
            port = int(base_url.rsplit(":", 1)[1])
            assert port not in _CHROMIUM_RESTRICTED_PORTS
