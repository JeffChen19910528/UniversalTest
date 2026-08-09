"""CLI-level tests for `universal-test performance`."""

import json
from pathlib import Path

import pytest

from universal_test.cli.main import main
from tests.adapters.rest.fixture_server import VALID_BEARER_TOKEN, FixtureServer

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module")
def live_server():
    with FixtureServer() as server:
        yield server


def test_missing_target_is_refused_even_with_dry_run():
    exit_code = main(["performance", str(FIXTURES_DIR / "openapi-basic"), "--dry-run"])
    assert exit_code == 2


def test_dry_run_shows_plan_and_executes_nothing(capsys):
    exit_code = main([
        "performance", str(FIXTURES_DIR / "openapi-basic"), "--target", "http://localhost:9",
        "--endpoint", "/users", "--method", "GET", "--dry-run",
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Performance Test Plan" in out
    assert "No requests executed." in out


def test_invalid_concurrency_is_a_clean_error(capsys):
    exit_code = main([
        "performance", str(FIXTURES_DIR / "openapi-basic"), "--target", "http://localhost:9",
        "--endpoint", "/users", "--method", "GET", "--profile", "custom",
        "--concurrency", "not-a-number", "--dry-run",
    ])
    assert exit_code == 2


def test_invalid_duration_is_a_clean_error(capsys):
    exit_code = main([
        "performance", str(FIXTURES_DIR / "openapi-basic"), "--target", "http://localhost:9",
        "--endpoint", "/users", "--method", "GET", "--duration", "-5", "--dry-run",
    ])
    assert exit_code == 2


def test_invalid_requests_is_a_clean_error(capsys):
    exit_code = main([
        "performance", str(FIXTURES_DIR / "openapi-basic"), "--target", "http://localhost:9",
        "--endpoint", "/users", "--method", "GET", "--requests", "999999", "--dry-run",
    ])
    assert exit_code == 2


def test_custom_profile_without_concurrency_is_a_clean_error(capsys):
    exit_code = main([
        "performance", str(FIXTURES_DIR / "openapi-basic"), "--target", "http://localhost:9",
        "--endpoint", "/users", "--method", "GET", "--profile", "custom", "--dry-run",
    ])
    assert exit_code == 2


def test_execution_against_live_server_yes_flag_skips_prompt(live_server, capsys):
    exit_code = main([
        "performance", str(FIXTURES_DIR / "openapi-basic"), "--target", live_server.base_url,
        "--endpoint", "/users", "--method", "GET", "--requests", "10", "--concurrency", "2",
        "--yes", "--format", "json",
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["levels"][0]["metrics"]["total_requests"] == 10


def test_bearer_token_never_appears_in_performance_output(live_server, monkeypatch, capsys):
    monkeypatch.setenv("FIXTURE_TOKEN", VALID_BEARER_TOKEN)
    exit_code = main([
        "performance", str(FIXTURES_DIR / "openapi-auth"), "--target", live_server.base_url,
        "--endpoint", "/secure", "--method", "GET", "--requests", "5", "--concurrency", "1",
        "--yes", "--bearer-token-env", "FIXTURE_TOKEN",
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert VALID_BEARER_TOKEN not in out
    assert "Authorization" not in out


def test_multiple_endpoints_without_selection_is_a_clean_error(capsys):
    exit_code = main([
        "performance", str(FIXTURES_DIR / "openapi-basic"), "--target", "http://localhost:9", "--dry-run",
    ])
    assert exit_code == 2
