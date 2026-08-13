"""HTTP-level tests for browser/UI testing exposed through the existing
`/api/assess` pipeline (Phase 9 spec section 30/53): the GUI never launches
Playwright itself or computes a verdict -- it only sets the same
`AssessmentRequest` fields the CLI's `--browser`/`--target`/`--yes` flags
set, and renders whatever `Browser Testing` category the backend returns.
"""

import json
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from universal_test.gui.server import LOOPBACK_HOST, make_server

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def running_server():
    server = make_server(host=LOOPBACK_HOST, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _post(server, path, body):
    url = f"http://{LOOPBACK_HOST}:{server.server_port}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read()


def _get(server, path):
    url = f"http://{LOOPBACK_HOST}:{server.server_port}{path}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.status, resp.read()


def _wait_for_result(server, run_id):
    for _ in range(100):
        status, body = _get(server, f"/api/assess/{run_id}/result")
        result = json.loads(body)
        if result["status"] == "complete":
            return result
        time.sleep(0.05)
    pytest.fail("assessment did not complete in time")


def test_browser_not_assessed_by_default(running_server, tmp_path):
    status, body = _post(running_server, "/api/assess", {
        "project_path": str(FIXTURES_DIR / "browser-static-basic"), "output_dir": str(tmp_path),
    })
    assert status == 200
    run_id = json.loads(body)["run_id"]
    result = _wait_for_result(running_server, run_id)

    browser_cat = next(c for c in result["result"]["assessment"]["categories"] if c["name"] == "Browser Testing")
    assert browser_cat["status"] == "not_assessed"


def test_browser_checked_without_confirmation_never_launches(running_server, tmp_path):
    status, body = _post(running_server, "/api/assess", {
        "project_path": str(FIXTURES_DIR / "browser-static-basic"), "output_dir": str(tmp_path),
        "run_browser": True, "browser_confirmed": False, "browser_target": "http://127.0.0.1:1/",
    })
    assert status == 200
    run_id = json.loads(body)["run_id"]
    result = _wait_for_result(running_server, run_id)

    browser_cat = next(c for c in result["result"]["assessment"]["categories"] if c["name"] == "Browser Testing")
    assert browser_cat["status"] == "not_assessed"
    assert "confirmation" in browser_cat["reason"]


def _chromium_launchable() -> bool:
    try:
        playwright_sync_api = pytest.importorskip("playwright.sync_api")
        with playwright_sync_api.sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


def test_browser_confirmed_and_reachable_target_runs(running_server, tmp_path):
    if not _chromium_launchable():
        pytest.skip(
            "Chromium binary is not installed -- run `universal-test browser install` "
            "(or `python -m playwright install chromium`) to enable this test"
        )
    fixture_index = (FIXTURES_DIR / "browser-static-basic" / "index.html").resolve()
    target = "file://" + str(fixture_index).replace("\\", "/")
    status, body = _post(running_server, "/api/assess", {
        "project_path": str(FIXTURES_DIR / "browser-static-basic"), "output_dir": str(tmp_path),
        "run_browser": True, "browser_confirmed": True, "browser_target": target,
    })
    assert status == 200
    run_id = json.loads(body)["run_id"]
    result = _wait_for_result(running_server, run_id)

    browser_cat = next(c for c in result["result"]["assessment"]["categories"] if c["name"] == "Browser Testing")
    assert browser_cat["status"] in {"pass", "warning", "fail"}
