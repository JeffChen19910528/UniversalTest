"""CLI-level tests for `universal-test test`, using the same local fixture
server as tests/adapters/rest (imported directly since tests/cli has no
conftest wiring it in)."""

import json
from pathlib import Path

import pytest

from universal_test.cli.main import main
from tests.adapters.rest.fixture_server import FixtureServer

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module")
def live_server():
    with FixtureServer() as server:
        yield server


def test_dry_run_exits_zero_and_prints_no_requests_executed(capsys):
    exit_code = main(["test", str(FIXTURES_DIR / "openapi-basic"), "--dry-run"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "No HTTP requests executed." in out
    assert "Discovered:" in out


def test_missing_target_prints_required_error_text_and_exits_nonzero(capsys):
    exit_code = main(["test", str(FIXTURES_DIR / "openapi-basic")])
    assert exit_code == 2
    out = capsys.readouterr().out
    assert "No execution target specified" in out
    assert "no HTTP requests were executed" in out


def test_multiple_specs_without_selection_is_a_clean_error(capsys):
    exit_code = main(["test", str(FIXTURES_DIR / "openapi-multiple"), "--dry-run"])
    assert exit_code == 2


def test_explicit_openapi_flag_selects_spec(capsys):
    exit_code = main([
        "test", str(FIXTURES_DIR / "openapi-multiple"), "--dry-run",
        "--openapi", str(FIXTURES_DIR / "openapi-multiple" / "swagger.json"),
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Discovered: 1 endpoints" in out


def test_execution_against_live_server_json_format(live_server, capsys):
    exit_code = main([
        "test", str(FIXTURES_DIR / "openapi-basic"), "--target", live_server.base_url, "--format", "json",
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["executed"] is True
    assert any(r["status"] == "passed" for r in parsed["run_result"]["results"])


def test_bearer_token_env_flag_never_takes_the_secret_directly(live_server, monkeypatch, capsys):
    monkeypatch.setenv("FIXTURE_TOKEN", "testtoken123")
    exit_code = main([
        "test", str(FIXTURES_DIR / "openapi-auth"), "--target", live_server.base_url,
        "--bearer-token-env", "FIXTURE_TOKEN",
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "testtoken123" not in out
    assert "PASSED: 1" in out
