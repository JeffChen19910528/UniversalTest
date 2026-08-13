"""Phase 10: One-Click Web Assessment GUI/backend tests.

`/api/web/detect` is a thin, read-only pre-flight endpoint on top of the
*existing* discovery engine (spec section 8/10/11) -- no second discovery
engine, no HTML re-parsing in the GUI. The actual Web Assessment run still
goes through the existing `/api/assess` pipeline (spec section 41) with a
web-oriented request body; no new run-tracking system.
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


# -- /api/web/detect ----------------------------------------------------

def test_web_detect_reports_static_web_project(running_server):
    status, body = _post(running_server, "/api/web/detect", {
        "project_path": str(FIXTURES_DIR / "browser-static-basic"),
    })
    assert status == 200
    result = json.loads(body)
    assert result["detected"] is True
    assert result["frontend"]["frontend_type"] == "static_web"


def test_web_detect_reports_framework_web_project(running_server):
    status, body = _post(running_server, "/api/web/detect", {
        "project_path": str(FIXTURES_DIR / "react-vite-vitest"),
    })
    result = json.loads(body)
    assert result["detected"] is True
    assert result["frontend"]["frontend_type"] == "framework_web"
    assert "React" in result["frameworks"]


def test_web_detect_reports_not_web_for_backend_only_project(running_server):
    status, body = _post(running_server, "/api/web/detect", {
        "project_path": str(FIXTURES_DIR / "backend-html-template"),
    })
    result = json.loads(body)
    assert result["detected"] is False


def test_web_detect_rejects_invalid_path(running_server):
    status, body = _post(running_server, "/api/web/detect", {"project_path": "Z:/does/not/exist"})
    result = json.loads(body)
    assert result["detected"] is False
    assert result["error"] == "invalid_project_path"


def test_web_detect_never_launches_a_browser(running_server, monkeypatch):
    # Guards against a regression where "detect" accidentally becomes "execute".
    import universal_test.adapters.browser.adapter as browser_adapter

    def _fail(*args, **kwargs):
        raise AssertionError("web/detect must never launch a browser")

    monkeypatch.setattr(browser_adapter, "run", _fail)
    status, body = _post(running_server, "/api/web/detect", {
        "project_path": str(FIXTURES_DIR / "browser-static-basic"),
    })
    assert status == 200


# -- Web Assessment run (reuses /api/assess) -----------------------------

def test_web_assessment_preset_runs_static_web_project(running_server, tmp_path):
    fixture_index = (FIXTURES_DIR / "browser-static-basic" / "index.html").resolve()
    target = "file://" + str(fixture_index).replace("\\", "/")
    status, body = _post(running_server, "/api/assess", {
        "project_path": str(FIXTURES_DIR / "browser-static-basic"), "output_dir": str(tmp_path),
        "run_functional": False, "run_performance": False, "run_database": False,
        "run_browser": True, "browser_confirmed": True, "browser_target": target,
    })
    assert status == 200
    run_id = json.loads(body)["run_id"]
    result = _wait_for_result(running_server, run_id)

    assessment = result["result"]["assessment"]
    browser_cat = next(c for c in assessment["categories"] if c["name"] == "Browser Testing")
    assert browser_cat["status"] in {"pass", "warning", "fail"}
    # Non-programmer-facing distinctness: Application Health / Testability /
    # Assessment Coverage must all be present and independently meaningful.
    assert assessment["application_health"] in {"pass", "warning", "fail"}
    assert assessment["assessment_completeness"] in {"full", "partial"}


def test_web_assessment_without_confirmation_is_not_assessed(running_server, tmp_path):
    status, body = _post(running_server, "/api/assess", {
        "project_path": str(FIXTURES_DIR / "browser-static-basic"), "output_dir": str(tmp_path),
        "run_functional": False, "run_performance": False, "run_database": False,
        "run_browser": True, "browser_confirmed": False, "browser_target": "http://127.0.0.1:1/",
    })
    run_id = json.loads(body)["run_id"]
    result = _wait_for_result(running_server, run_id)
    browser_cat = next(c for c in result["result"]["assessment"]["categories"] if c["name"] == "Browser Testing")
    assert browser_cat["status"] == "not_assessed"
