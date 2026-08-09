"""CLI-level integration tests for `universal-test assess`."""

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


def test_default_run_sends_no_network_traffic_and_succeeds(tmp_path, capsys):
    # no --target, no --performance: discovery only, safe by default
    exit_code = main(["assess", str(FIXTURES_DIR / "healthy-project"), "--output", str(tmp_path)])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["functional"]["result"] is None
    assert report["performance"] is None


def test_default_format_is_all_three_files(tmp_path):
    exit_code = main(["assess", str(FIXTURES_DIR / "healthy-project"), "--output", str(tmp_path)])
    assert exit_code == 0
    assert (tmp_path / "report.json").is_file()
    assert (tmp_path / "report.md").is_file()
    assert (tmp_path / "report.html").is_file()


def test_single_format_writes_only_that_file(tmp_path):
    exit_code = main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--format", "json", "--output", str(tmp_path),
    ])
    assert exit_code == 0
    assert (tmp_path / "report.json").is_file()
    assert not (tmp_path / "report.md").exists()
    assert not (tmp_path / "report.html").exists()


def test_healthy_project_with_target_executes_functional(live_server, tmp_path):
    exit_code = main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--target", live_server.base_url,
        "--output", str(tmp_path),
    ])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    functional_category = next(c for c in report["assessment"]["categories"] if c["name"] == "Functional Health")
    assert functional_category["status"] in ("pass", "warning")
    assert report["functional"]["result"] is not None


def test_failed_functional_project_is_warning(live_server, tmp_path):
    exit_code = main([
        "assess", str(FIXTURES_DIR / "failed-functional-project"), "--target", live_server.base_url,
        "--output", str(tmp_path),
    ])
    # Phase 8: a real assertion failure against a live target is a Quality Gate
    # failure by default (functional.failure is in the default fail_on policy) --
    # exit 1, not 0 (see quality_gate/models.py::ExitCode).
    assert exit_code == 1
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    functional_category = next(c for c in report["assessment"]["categories"] if c["name"] == "Functional Health")
    assert functional_category["status"] == "warning"
    assert report["quality_gate"]["status"] == "fail"


def test_unreachable_target_is_functional_fail(tmp_path):
    import socket
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    unused_port = probe.getsockname()[1]
    probe.close()

    exit_code = main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--target", f"http://127.0.0.1:{unused_port}",
        "--output", str(tmp_path),
    ])
    # Phase 8: a completely unreachable target is an infrastructure/execution error
    # (exit 3), not a quality regression (exit 1) -- brief section 18's explicit
    # "Target unavailable 應該是 execution/infrastructure error，而不是 Quality regression".
    assert exit_code == 3
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    functional_category = next(c for c in report["assessment"]["categories"] if c["name"] == "Functional Health")
    assert functional_category["status"] == "fail"
    assert report["quality_gate"]["status"] == "error"


def test_performance_not_run_without_explicit_flag(live_server, tmp_path):
    exit_code = main([
        "assess", str(FIXTURES_DIR / "slow-project"), "--target", live_server.base_url,
        "--output", str(tmp_path),
    ])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["performance"] is None
    performance_category = next(c for c in report["assessment"]["categories"] if c["name"] == "Performance")
    assert performance_category["status"] == "not_assessed"


def test_performance_with_flag_and_yes_executes_and_breaches_threshold(tmp_path):
    from tests.adapters.rest.fixture_server import FixtureServer as FS
    with FS() as server:
        (tmp_path / "universal-test.yaml").write_text(
            "performance:\n  thresholds:\n    p95_ms: 10\n", encoding="utf-8",
        )
        exit_code = main([
            "assess", str(FIXTURES_DIR / "slow-project"), "--target", server.base_url,
            "--performance", "--yes", "--requests", "5", "--concurrency", "1",
            "--config", str(tmp_path / "universal-test.yaml"),
            "--output", str(tmp_path / "out"),
        ])
    # Phase 8: a threshold breach against a live (reachable) target is a Quality
    # Gate failure by default (performance.threshold is in the default fail_on
    # policy) -- exit 1.
    assert exit_code == 1
    report = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert report["quality_gate"]["status"] == "fail"
    assert report["performance"] is not None
    performance_category = next(c for c in report["assessment"]["categories"] if c["name"] == "Performance")
    assert performance_category["status"] == "warning"
    assert any(f["category"] == "Performance" for f in report["findings"])


def test_unknown_project_everything_not_assessed_or_unknown(tmp_path):
    exit_code = main(["assess", str(FIXTURES_DIR / "unknown-project"), "--output", str(tmp_path)])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    statuses = {c["name"]: c["status"] for c in report["assessment"]["categories"]}
    assert statuses["Functional Health"] == "not_assessed"
    assert statuses["Performance"] == "not_assessed"


def test_partial_project_runs_without_crashing(tmp_path):
    exit_code = main(["assess", str(FIXTURES_DIR / "partial-project"), "--output", str(tmp_path)])
    assert exit_code == 0
    assert (tmp_path / "report.json").is_file()


def test_dry_run_never_executes_even_with_target(tmp_path):
    exit_code = main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--target", "http://127.0.0.1:1",
        "--dry-run", "--output", str(tmp_path),
    ])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["functional"]["result"] is None


def test_bearer_token_never_appears_in_assess_output(tmp_path, monkeypatch):
    from tests.adapters.rest.fixture_server import VALID_BEARER_TOKEN
    monkeypatch.setenv("FIXTURE_TOKEN", VALID_BEARER_TOKEN)
    with FixtureServer() as server:
        exit_code = main([
            "assess", str(FIXTURES_DIR / "openapi-auth"), "--target", server.base_url,
            "--bearer-token-env", "FIXTURE_TOKEN", "--output", str(tmp_path),
        ])
    assert exit_code == 0
    for filename in ("report.json", "report.md", "report.html"):
        content = (tmp_path / filename).read_text(encoding="utf-8")
        assert VALID_BEARER_TOKEN not in content


def test_multiple_specs_marks_functional_not_assessed_not_a_crash(tmp_path):
    exit_code = main(["assess", str(FIXTURES_DIR / "openapi-multiple"), "--output", str(tmp_path)])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    functional_category = next(c for c in report["assessment"]["categories"] if c["name"] == "Functional Health")
    assert functional_category["status"] == "not_assessed"
    assert "multiple" in functional_category["reason"].lower()


def test_overall_status_printed_to_stdout(tmp_path, capsys):
    main(["assess", str(FIXTURES_DIR / "healthy-project"), "--output", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Overall Status:" in out


def test_nonexistent_path_is_a_clean_error():
    exit_code = main(["assess", "/does/not/exist/at/all"])
    assert exit_code == 2
