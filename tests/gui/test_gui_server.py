"""HTTP-level tests for the local GUI server (Post-V1 GUI brief §18-19/§32).

Verifies: localhost-only binding, static asset serving, project validation,
the full assess -> stream -> result round trip, and that a run without a
target never produces functional execution.
"""

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from universal_test.gui.server import GuiRequestHandler, LOOPBACK_HOST, find_free_port, make_server

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


def _get(server, path):
    url = f"http://{LOOPBACK_HOST}:{server.server_port}{path}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.status, resp.read()


def _post(server, path, body):
    url = f"http://{LOOPBACK_HOST}:{server.server_port}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read()


def test_find_free_port_only_binds_to_loopback():
    port = find_free_port()
    assert isinstance(port, int) and port > 0


def test_make_server_rejects_non_loopback_hosts():
    with pytest.raises(ValueError):
        make_server(host="0.0.0.0", port=0)


def test_index_page_is_served(running_server):
    status, body = _get(running_server, "/")
    assert status == 200
    assert b"Universal Test" in body


def test_static_assets_are_served(running_server):
    status, body = _get(running_server, "/static/style.css")
    assert status == 200
    assert len(body) > 0


def test_index_exposes_quality_gate_regression_and_auth_ui(running_server):
    _, body = _get(running_server, "/")
    html = body.decode("utf-8")
    assert 'id="quality-gate-card"' in html
    assert 'id="regression-card"' in html
    assert 'id="auth-type"' in html
    assert 'id="perf-endpoint-section"' in html
    # Only environment-variable-name inputs, never a raw password/secret field.
    assert 'type="password"' not in html


def test_i18n_translates_backend_category_names_to_traditional_chinese(running_server):
    _, body = _get(running_server, "/static/i18n.js")
    js = body.decode("utf-8")
    for category in [
        "Project Discovery", "Build / Project Health", "Testability", "Functional Health",
        "Performance", "Configuration Hygiene", "Test Infrastructure", "Database Health",
    ]:
        assert f'category_{category}' in js, f"missing zh-TW category mapping for {category!r}"


def test_static_path_traversal_is_rejected(running_server):
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _get(running_server, "/static/../server.py")
    assert exc_info.value.code in (403, 404)


def test_validate_project_rejects_missing_and_empty_paths(running_server, tmp_path):
    status, body = _post(running_server, "/api/validate-project", {"path": ""})
    assert json.loads(body)["valid"] is False

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    status, body = _post(running_server, "/api/validate-project", {"path": str(empty_dir)})
    assert json.loads(body)["valid"] is False
    assert json.loads(body)["reason"] == "empty_directory"


def test_validate_project_accepts_a_real_project(running_server):
    status, body = _post(running_server, "/api/validate-project", {"path": str(FIXTURES_DIR / "openapi-basic")})
    assert json.loads(body)["valid"] is True


def test_assess_without_target_never_executes_functional_tests(running_server, tmp_path):
    status, body = _post(running_server, "/api/assess", {
        "project_path": str(FIXTURES_DIR / "openapi-basic"), "output_dir": str(tmp_path),
    })
    assert status == 200
    run_id = json.loads(body)["run_id"]

    for _ in range(100):
        status, body = _get(running_server, f"/api/assess/{run_id}/result")
        result = json.loads(body)
        if result["status"] == "complete":
            break
        time.sleep(0.05)
    else:
        pytest.fail("assessment did not complete in time")

    assessment = result["result"]["assessment"]
    assert result["result"]["functional_not_run_reason"] is not None
    functional_category = next(c for c in assessment["categories"] if c["name"] == "Functional Health")
    assert functional_category["status"] in {"unknown", "not_assessed"}


def test_assess_rejects_a_nonexistent_project_path(running_server):
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _post(running_server, "/api/assess", {"project_path": "Z:/definitely/not/a/real/path"})
    assert exc_info.value.code == 400
    assert json.loads(exc_info.value.read())["error"] == "invalid_request"


def test_internal_error_never_leaks_traceback_or_secrets(running_server, monkeypatch):
    secret_message = "connect failed: postgres://dbuser:hunter2secret@10.0.0.5/prod, password=hunter2secret, Authorization: Bearer sk-abcde12345"

    def _boom(self, body):
        raise RuntimeError(secret_message)

    monkeypatch.setattr(GuiRequestHandler, "_validate_project", _boom)

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _post(running_server, "/api/validate-project", {"path": "whatever"})
    assert exc_info.value.code == 500
    raw = exc_info.value.read()
    payload = json.loads(raw)

    assert payload["error"] == "internal_error"
    assert "error_id" in payload and payload["error_id"]
    assert "detail" not in payload
    assert "traceback" not in raw.decode("utf-8").lower()
    assert "hunter2secret" not in raw.decode("utf-8")
    assert "sk-abcde12345" not in raw.decode("utf-8")
    assert "RuntimeError" not in raw.decode("utf-8")


def test_assess_run_failure_reports_only_an_error_id(running_server, monkeypatch, tmp_path):
    secret_message = "db error: password=hunter2secret"

    def _boom(request, on_event=None, config=None):
        raise RuntimeError(secret_message)

    monkeypatch.setattr("universal_test.gui.runs.run_assessment", _boom)

    status, body = _post(running_server, "/api/assess", {
        "project_path": str(FIXTURES_DIR / "openapi-basic"), "output_dir": str(tmp_path),
    })
    run_id = json.loads(body)["run_id"]

    for _ in range(100):
        status, body = _get(running_server, f"/api/assess/{run_id}/result")
        result = json.loads(body)
        if result["status"] != "running":
            break
        time.sleep(0.05)
    else:
        pytest.fail("assessment did not complete in time")

    assert result["status"] == "error"
    assert "error_id" in result and result["error_id"]
    assert "hunter2secret" not in body.decode("utf-8")
    assert "RuntimeError" not in body.decode("utf-8")


def test_duplicate_assess_start_is_rejected_over_http(running_server, monkeypatch, tmp_path):
    started = threading.Event()
    release = threading.Event()

    def _slow_assessment(request, on_event=None, config=None):
        started.set()
        release.wait(timeout=5.0)
        return None

    monkeypatch.setattr("universal_test.gui.runs.run_assessment", _slow_assessment)

    status, body = _post(running_server, "/api/assess", {
        "project_path": str(FIXTURES_DIR / "openapi-basic"), "output_dir": str(tmp_path),
    })
    assert status == 200
    started.wait(timeout=5.0)

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _post(running_server, "/api/assess", {
            "project_path": str(FIXTURES_DIR / "openapi-basic"), "output_dir": str(tmp_path),
        })
    assert exc_info.value.code == 409
    assert json.loads(exc_info.value.read())["error"] == "assessment_already_running"

    release.set()


def test_perf_endpoints_lists_operations_for_a_single_spec(running_server):
    status, body = _post(running_server, "/api/perf/endpoints", {
        "project_path": str(FIXTURES_DIR / "openapi-basic"),
    })
    result = json.loads(body)
    assert "reason" not in result
    methods_paths = {(e["method"], e["path"]) for e in result["endpoints"]}
    assert ("GET", "/users") in methods_paths
    assert ("POST", "/users") in methods_paths


def test_perf_endpoints_reports_no_spec_found(running_server):
    status, body = _post(running_server, "/api/perf/endpoints", {
        "project_path": str(FIXTURES_DIR / "unknown-project"),
    })
    result = json.loads(body)
    assert result["endpoints"] == []
    assert result["reason"] == "no_openapi_spec_found"


def test_perf_endpoints_reports_ambiguous_specs_with_candidates(running_server):
    status, body = _post(running_server, "/api/perf/endpoints", {
        "project_path": str(FIXTURES_DIR / "openapi-multiple"),
    })
    result = json.loads(body)
    assert result["endpoints"] == []
    assert result["reason"] == "multiple_specs_found"
    assert len(result["candidates"]) >= 2


def test_assess_result_exposes_full_regression_and_quality_gate(running_server, tmp_path):
    from universal_test.cli.main import main as cli_main

    baseline_path = tmp_path / "baseline.json"
    assert cli_main(["baseline", "save", str(FIXTURES_DIR / "healthy-project"), "--output", str(baseline_path)]) == 0

    status, body = _post(running_server, "/api/assess", {
        "project_path": str(FIXTURES_DIR / "healthy-project"),
        "baseline_path": str(baseline_path),
        "output_dir": str(tmp_path / "out"),
    })
    run_id = json.loads(body)["run_id"]

    for _ in range(200):
        status, body = _get(running_server, f"/api/assess/{run_id}/result")
        result = json.loads(body)
        if result["status"] == "complete":
            break
        time.sleep(0.05)
    else:
        pytest.fail("assessment did not complete in time")

    payload = result["result"]
    # Regression: identical project vs. its own baseline must be a full
    # RegressionSummary the GUI can render (Final QA Known Issue B), not a
    # bare status string.
    assert payload["regression"] is not None
    assert "status" in payload["regression"] and "categories" in payload["regression"] and "findings" in payload["regression"]

    # Quality Gate: `to_dict()`'s full shape must survive the HTTP boundary,
    # including `findings` and `reason` (Final QA Known Issue C) -- the
    # server must not hand-pick only status/exit_code.
    qg = payload["quality_gate"]
    assert set(["status", "exit_code", "reason", "findings", "summary"]).issubset(qg.keys())


def test_event_stream_reports_completion(running_server, tmp_path):
    status, body = _post(running_server, "/api/assess", {
        "project_path": str(FIXTURES_DIR / "openapi-basic"), "output_dir": str(tmp_path),
    })
    run_id = json.loads(body)["run_id"]

    url = f"http://{LOOPBACK_HOST}:{running_server.server_port}/api/assess/{run_id}/stream"
    with urllib.request.urlopen(url, timeout=10) as resp:
        events = []
        for _ in range(50):
            line = resp.readline().decode("utf-8").strip()
            if line.startswith("data: "):
                payload = json.loads(line[len("data: "):])
                events.append(payload)
                if payload.get("name") == "done":
                    break
    names = [e["name"] for e in events]
    assert "project_scan_started" in names
    assert names[-1] == "done"
