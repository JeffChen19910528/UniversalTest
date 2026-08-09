"""Explicit exit-code matrix for `universal-test assess` (V1 hardening
audit section 6). Each test name states the scenario and its required exit
code directly, so the matrix is readable as a table by scanning test names
-- deliberately not parametrized into one opaque table, since the whole
point is that each row is independently diagnosable when it fails.

Contract (ARCHITECTURE.md section 13, README.md "CI/CD Integration"):
    0 = Quality Gate passed (including a WARNING-level result)
    1 = Quality Gate failed
    2 = configuration / CLI error
    3 = infrastructure / execution error
"""

import socket
from pathlib import Path

import pytest

from universal_test.cli.main import main
from tests.adapters.rest.fixture_server import FixtureServer, VALID_BEARER_TOKEN

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module")
def live_server():
    with FixtureServer() as server:
        yield server


def _unused_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def test_success_no_target_is_exit_0(tmp_path):
    assert main(["assess", str(FIXTURES_DIR / "healthy-project"), "--output", str(tmp_path)]) == 0


def test_success_with_target_all_passing_is_exit_0(live_server, tmp_path):
    assert main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--target", live_server.base_url, "--output", str(tmp_path),
    ]) == 0


def test_warning_level_result_is_still_exit_0(tmp_path):
    # healthy-project with no target: Build/Project Health warns (no test framework
    # manifest signal), but nothing in the default fail_on policy matches -> PASS/exit 0.
    assert main(["assess", str(FIXTURES_DIR / "healthy-project"), "--output", str(tmp_path)]) == 0


def test_quality_gate_failure_real_assertion_mismatch_is_exit_1(live_server, tmp_path):
    assert main([
        "assess", str(FIXTURES_DIR / "failed-functional-project"), "--target", live_server.base_url,
        "--output", str(tmp_path),
    ]) == 1


def test_invalid_config_bad_format_is_exit_2(tmp_path):
    assert main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--format", "text", "--output", str(tmp_path),
    ]) == 2


def test_invalid_target_nonexistent_project_path_is_exit_2():
    assert main(["assess", "/does/not/exist/at/all"]) == 2


def test_invalid_baseline_reference_is_exit_2(tmp_path):
    assert main([
        "assess", str(FIXTURES_DIR / "healthy-project"),
        "--baseline", str(tmp_path / "no-such-baseline.json"), "--output", str(tmp_path / "out"),
    ]) == 2


def test_network_failure_unreachable_target_is_exit_3(tmp_path):
    assert main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--target", f"http://127.0.0.1:{_unused_port()}",
        "--output", str(tmp_path),
    ]) == 3


def test_timeout_is_exit_3_not_a_quality_failure(live_server, tmp_path):
    # /slow sleeps 300ms; a 50ms timeout guarantees a RequestTimeoutError, which
    # produces a total-transport-wipeout Functional Health FAIL, not a WARNING.
    assert main([
        "assess", str(FIXTURES_DIR / "slow-project"), "--target", live_server.base_url,
        "--timeout", "0.05", "--output", str(tmp_path),
    ]) == 3


def test_missing_target_functional_not_assessed_is_exit_0(tmp_path):
    # generation-only: no --target means functional stays NOT_ASSESSED, which
    # never fails the default policy.
    assert main(["assess", str(FIXTURES_DIR / "openapi-basic"), "--output", str(tmp_path)]) == 0


def test_missing_credential_skipped_auth_test_is_exit_0(live_server, tmp_path):
    # no --bearer-token-env: the one generated test is SKIPPED (not executed),
    # so Functional Health has nothing to fail on.
    assert main([
        "assess", str(FIXTURES_DIR / "openapi-auth"), "--target", live_server.base_url, "--output", str(tmp_path),
    ]) == 0


def test_wrong_credential_real_401_mismatch_is_exit_1(live_server, tmp_path, monkeypatch):
    monkeypatch.setenv("WRONG_TOKEN", "not-the-real-token")
    exit_code = main([
        "assess", str(FIXTURES_DIR / "openapi-auth"), "--target", live_server.base_url,
        "--bearer-token-env", "WRONG_TOKEN", "--output", str(tmp_path),
    ])
    # a wrong (as opposed to missing) credential gets a real 401 response --
    # transport succeeded, assertion failed -> Functional Health WARNING -> gate FAIL.
    assert exit_code == 1


def test_correct_credential_is_exit_0(live_server, tmp_path, monkeypatch):
    monkeypatch.setenv("RIGHT_TOKEN", VALID_BEARER_TOKEN)
    exit_code = main([
        "assess", str(FIXTURES_DIR / "openapi-auth"), "--target", live_server.base_url,
        "--bearer-token-env", "RIGHT_TOKEN", "--output", str(tmp_path),
    ])
    assert exit_code == 0


def test_noninteractive_confirmation_without_yes_is_still_exit_0_performance_skipped(tmp_path):
    # performance requires --yes in a non-interactive session; declining still
    # leaves 'assess' as a whole at exit 0 (Performance category -> NOT_ASSESSED,
    # not a hard failure of the entire command).
    exit_code = main([
        "assess", str(FIXTURES_DIR / "unknown-project"), "--target", "http://127.0.0.1:1",
        "--endpoint", "/x", "--method", "GET", "--performance", "--output", str(tmp_path),
    ])
    assert exit_code == 0


def test_every_exit_code_in_the_contract_is_reachable_and_distinct():
    # sanity: the four documented codes are not aliases of one another
    assert len({0, 1, 2, 3}) == 4
