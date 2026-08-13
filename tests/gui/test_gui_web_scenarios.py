"""Phase 11: Web Scenarios GUI backend tests.

`/api/web/scenarios` is read-only (reuses the existing loader/validator,
never launches a browser). `/api/web/scenario/run` executes exactly one
explicitly-selected scenario synchronously through the same
`run_scenario()` the CLI uses, gated on an explicit `confirmed` flag
mirroring the GUI's existing browser-confirmation checkbox pattern.
"""

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from universal_test.gui.server import LOOPBACK_HOST, make_server

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SCENARIO_APP = FIXTURES_DIR / "browser-scenario-app"


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
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def test_web_scenarios_lists_scenarios(running_server):
    status, body = _post(running_server, "/api/web/scenarios", {"project_path": str(SCENARIO_APP)})
    assert status == 200
    result = json.loads(body)
    ids = [s["id"] for s in result["scenarios"]]
    assert "login-smoke" in ids
    assert result["validation_issues"] == []


def test_web_scenarios_never_includes_secret_values(running_server):
    status, body = _post(running_server, "/api/web/scenarios", {"project_path": str(SCENARIO_APP)})
    result = json.loads(body)
    dumped = json.dumps(result)
    assert "demo123" not in dumped


def test_web_scenarios_invalid_project_path(running_server):
    status, body = _post(running_server, "/api/web/scenarios", {"project_path": "Z:/nope"})
    result = json.loads(body)
    assert result["scenarios"] == []
    assert result["error"] == "invalid_project_path"


def test_scenario_run_requires_confirmation(running_server):
    status, body = _post(running_server, "/api/web/scenario/run", {
        "project_path": str(SCENARIO_APP), "scenario_id": "login-smoke",
        "target": "http://127.0.0.1:1/", "confirmed": False,
    })
    assert status == 400
    assert json.loads(body)["error"] == "confirmation_required"


def test_scenario_run_requires_target(running_server):
    status, body = _post(running_server, "/api/web/scenario/run", {
        "project_path": str(SCENARIO_APP), "scenario_id": "login-smoke", "confirmed": True,
    })
    assert status == 400
    assert json.loads(body)["error"] == "target_required"


def test_scenario_run_unknown_scenario_id(running_server):
    status, body = _post(running_server, "/api/web/scenario/run", {
        "project_path": str(SCENARIO_APP), "scenario_id": "does-not-exist",
        "target": "http://127.0.0.1:39140/", "confirmed": True,
    })
    assert status == 404


def test_scenario_run_real_execution(running_server, monkeypatch):
    monkeypatch.setenv("TEST_USERNAME", "demo")
    monkeypatch.setenv("TEST_PASSWORD", "demo123")
    from universal_test.adapters.browser.local_server import serve_directory

    with serve_directory(SCENARIO_APP) as base_url:
        status, body = _post(running_server, "/api/web/scenario/run", {
            "project_path": str(SCENARIO_APP), "scenario_id": "login-smoke",
            "target": base_url, "confirmed": True,
        })
    assert status == 200
    result = json.loads(body)["result"]
    assert result["status"] == "pass"
    assert result["passed_steps"] == 5


def test_scenario_run_external_target_rejected_without_allow_external(running_server):
    status, body = _post(running_server, "/api/web/scenario/run", {
        "project_path": str(SCENARIO_APP), "scenario_id": "login-smoke",
        "target": "https://example.com", "confirmed": True,
    })
    assert status == 200
    result = json.loads(body)["result"]
    assert result["status"] == "not_assessed"
