"""CLI-level integration tests for Phase 8: exit-code contract, --ci mode,
CI environment detection, and quality-gate secret redaction."""

import json
import socket
import sys
from pathlib import Path

import pytest

from universal_test.cli.main import main
from tests.adapters.rest.fixture_server import FixtureServer

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


# --- exit code contract (0/1/2/3) -------------------------------------------


def test_exit_0_when_gate_passes(tmp_path):
    exit_code = main(["assess", str(FIXTURES_DIR / "healthy-project"), "--output", str(tmp_path)])
    assert exit_code == 0


def test_exit_1_when_gate_fails(live_server, tmp_path):
    exit_code = main([
        "assess", str(FIXTURES_DIR / "failed-functional-project"), "--target", live_server.base_url,
        "--output", str(tmp_path),
    ])
    assert exit_code == 1


def test_exit_2_on_unsupported_assess_format(tmp_path):
    # "text" is a valid --format choice for other subcommands but 'assess' only
    # supports json/markdown/html/all -- this must be a clean exit 2, not a crash.
    exit_code = main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--format", "text", "--output", str(tmp_path),
    ])
    assert exit_code == 2


def test_exit_2_on_nonexistent_project_path():
    exit_code = main(["assess", "/does/not/exist/at/all"])
    assert exit_code == 2


def test_exit_3_on_unreachable_target(tmp_path):
    exit_code = main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--target", f"http://127.0.0.1:{_unused_port()}",
        "--output", str(tmp_path),
    ])
    assert exit_code == 3


def test_exit_codes_are_distinct_not_collapsed():
    # the four contract values (0/1/2/3) must never collapse into "any nonzero == failure"
    assert len({0, 1, 2, 3}) == 4


# --- --ci mode: non-interactive, no hang, does not imply --yes -------------


def test_ci_mode_without_yes_never_hangs_and_sends_no_traffic(tmp_path):
    output = tmp_path / "reports"
    exit_code = main([
        "assess", str(FIXTURES_DIR / "unknown-project"), "--target", "http://127.0.0.1:1",
        "--endpoint", "/x", "--method", "GET", "--performance", "--ci",
        "--output", str(output),
    ])
    # returns promptly (no input() call) and performance was never executed
    assert exit_code == 0
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["performance"] is None


def test_ci_mode_forces_noninteractive_even_if_stdin_looks_like_a_tty(monkeypatch, tmp_path):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    output = tmp_path / "reports"
    exit_code = main([
        "assess", str(FIXTURES_DIR / "unknown-project"), "--target", "http://127.0.0.1:1",
        "--endpoint", "/x", "--method", "GET", "--performance", "--ci",
        "--output", str(output),
    ])
    assert exit_code == 0
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["performance"] is None  # never prompted, never executed


def test_ci_flag_alone_does_not_authorize_traffic(live_server, tmp_path):
    output = tmp_path / "reports"
    exit_code = main([
        "assess", str(FIXTURES_DIR / "unknown-project"), "--target", live_server.base_url,
        "--endpoint", "/fast", "--method", "GET", "--performance", "--ci",
        "--output", str(output),
    ])
    assert exit_code == 0
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["performance"] is None  # --ci without --yes still refuses


def test_ci_flag_with_yes_executes_real_traffic(live_server, tmp_path):
    output = tmp_path / "reports"
    exit_code = main([
        "assess", str(FIXTURES_DIR / "unknown-project"), "--target", live_server.base_url,
        "--endpoint", "/fast", "--method", "GET", "--performance", "--ci", "--yes",
        "--requests", "3", "--concurrency", "1",
        "--output", str(output),
    ])
    assert exit_code == 0
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["performance"] is not None


def test_ci_mode_prints_machine_friendly_summary(tmp_path, capsys):
    main(["assess", str(FIXTURES_DIR / "healthy-project"), "--ci", "--output", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Universal Test Quality Gate" in out
    assert "Exit code:" in out


def test_without_ci_flag_prints_terse_quality_gate_lines(tmp_path, capsys):
    main(["assess", str(FIXTURES_DIR / "healthy-project"), "--output", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Quality Gate:" in out
    assert "Exit code:" in out


# --- CI environment detection never bypasses safety -------------------------


@pytest.mark.parametrize("env_var,value", [
    ("CI", "true"), ("GITHUB_ACTIONS", "true"), ("GITLAB_CI", "true"), ("JENKINS_URL", "http://jenkins.local"),
])
def test_ci_env_var_detection_never_auto_authorizes_traffic(monkeypatch, env_var, value, tmp_path):
    monkeypatch.setenv(env_var, value)
    output = tmp_path / "reports"
    exit_code = main([
        "assess", str(FIXTURES_DIR / "unknown-project"), "--target", "http://127.0.0.1:1",
        "--endpoint", "/x", "--method", "GET", "--performance",
        "--output", str(output),
    ])
    assert exit_code == 0
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["performance"] is None  # env var alone never substitutes for --yes


def test_ci_env_var_detected_and_logged(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    import logging
    caplog.set_level(logging.INFO, logger="universal_test.cli")
    main(["assess", str(FIXTURES_DIR / "healthy-project"), "--output", str(tmp_path)])
    assert any("GitHub Actions" in record.message for record in caplog.records)


# --- bounded CI retry (brief section 19) ------------------------------------


def test_retry_disabled_by_default_no_retry_log(tmp_path, caplog):
    import logging
    caplog.set_level(logging.WARNING, logger="universal_test.cli")
    main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--target", f"http://127.0.0.1:{_unused_port()}",
        "--output", str(tmp_path),
    ])
    assert not any("retrying" in r.message for r in caplog.records)


def test_retry_count_configured_retries_on_total_transport_wipeout(tmp_path, caplog):
    import logging
    (tmp_path / "universal-test.yaml").write_text("ci:\n  retry:\n    count: 1\n", encoding="utf-8")
    caplog.set_level(logging.WARNING, logger="universal_test.cli")
    exit_code = main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--target", f"http://127.0.0.1:{_unused_port()}",
        "--config", str(tmp_path / "universal-test.yaml"), "--output", str(tmp_path / "out"),
    ])
    retry_logs = [r for r in caplog.records if "retrying" in r.message]
    assert len(retry_logs) == 1
    # still a genuine infrastructure error after the retry -- exit 3, not masked
    assert exit_code == 3


def test_retry_never_applies_to_a_real_assertion_failure(live_server, tmp_path, caplog):
    import logging
    (tmp_path / "universal-test.yaml").write_text("ci:\n  retry:\n    count: 1\n", encoding="utf-8")
    caplog.set_level(logging.WARNING, logger="universal_test.cli")
    main([
        "assess", str(FIXTURES_DIR / "failed-functional-project"), "--target", live_server.base_url,
        "--config", str(tmp_path / "universal-test.yaml"), "--output", str(tmp_path / "out"),
    ])
    # a genuine assertion failure (not a transport wipeout) must never be retried
    assert not any("retrying" in r.message for r in caplog.records)


def test_retry_count_is_clamped_to_a_hard_ceiling():
    from universal_test.core.configuration import load_config
    config = load_config(overrides={"ci": {"retry": {"count": 999}}})
    assert config.ci.retry.count <= 2


# --- secret redaction in quality gate output --------------------------------


def test_bearer_token_never_appears_in_quality_gate_output(tmp_path, monkeypatch):
    from tests.adapters.rest.fixture_server import VALID_BEARER_TOKEN
    monkeypatch.setenv("FIXTURE_TOKEN", "wrong-token-causing-a-real-failure")
    output = tmp_path / "reports"
    with FixtureServer() as server:
        exit_code = main([
            "assess", str(FIXTURES_DIR / "openapi-auth"), "--target", server.base_url,
            "--bearer-token-env", "FIXTURE_TOKEN", "--ci", "--output", str(output),
        ])
    # a wrong token causes a real assertion failure -> gate FAIL -> exit 1
    assert exit_code == 1
    for filename in ("report.json", "report.md", "report.html"):
        content = (output / filename).read_text(encoding="utf-8")
        assert VALID_BEARER_TOKEN not in content
        assert "wrong-token-causing-a-real-failure" not in content
