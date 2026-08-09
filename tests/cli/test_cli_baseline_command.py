"""CLI-level integration tests for `universal-test baseline save/compare`
and `assess --baseline` (Phase 7)."""

import json
import urllib.request
from pathlib import Path

import pytest

from universal_test.cli.main import main
from tests.adapters.rest.fixture_server import FixtureServer, reset_unstable_counter

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module")
def live_server():
    with FixtureServer() as server:
        yield server


# --- baseline save ----------------------------------------------------------


def test_save_without_output_is_refused(tmp_path):
    exit_code = main(["baseline", "save", str(FIXTURES_DIR / "healthy-project")])
    assert exit_code == 2


def test_save_writes_a_valid_baseline_file(tmp_path):
    output = tmp_path / "baseline.json"
    exit_code = main(["baseline", "save", str(FIXTURES_DIR / "healthy-project"), "--output", str(output)])
    assert exit_code == 0
    assert output.is_file()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert "tool_version" in data
    assert "discovery" in data
    assert "assessment" in data
    assert data["functional"] is None  # no --target was given


def test_save_default_run_sends_no_network_traffic(tmp_path):
    # no --target, no --performance, no --database-profile: discovery only
    output = tmp_path / "baseline.json"
    exit_code = main(["baseline", "save", str(FIXTURES_DIR / "healthy-project"), "--output", str(output)])
    assert exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["functional"] is None
    assert data["performance"] is None
    assert data["database"] is None


def test_save_with_target_captures_functional_test_ids(live_server, tmp_path):
    output = tmp_path / "baseline.json"
    exit_code = main([
        "baseline", "save", str(FIXTURES_DIR / "healthy-project"),
        "--target", live_server.base_url, "--output", str(output),
    ])
    assert exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["functional"] is not None
    assert len(data["functional"]["tests"]) > 0
    assert all("id" in t and "status" in t for t in data["functional"]["tests"])


# --- baseline compare: safety -----------------------------------------------


def test_compare_missing_baseline_flag_is_a_usage_error():
    with pytest.raises(SystemExit) as exc_info:
        main(["baseline", "compare", str(FIXTURES_DIR / "healthy-project")])
    assert exc_info.value.code != 0


def test_compare_nonexistent_baseline_path_is_refused(tmp_path):
    exit_code = main([
        "baseline", "compare", str(FIXTURES_DIR / "healthy-project"),
        "--baseline", str(tmp_path / "does-not-exist.json"),
    ])
    assert exit_code == 2


def test_compare_incompatible_schema_version_is_refused(tmp_path):
    baseline_path = tmp_path / "old.json"
    baseline_path.write_text(json.dumps({
        "schema_version": "99.0", "tool_version": "0.0.1", "generated_at": "t",
        "project": {"path": "p"}, "source": {}, "discovery": {}, "functional": None,
        "performance": None, "database": None, "assessment": {"overall_status": "unknown", "categories": []},
    }), encoding="utf-8")
    exit_code = main([
        "baseline", "compare", str(FIXTURES_DIR / "healthy-project"), "--baseline", str(baseline_path),
    ])
    assert exit_code == 2


def test_compare_is_read_only_never_modifies_the_baseline_file(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    main(["baseline", "save", str(FIXTURES_DIR / "healthy-project"), "--output", str(baseline_path)])
    before_content = baseline_path.read_bytes()
    before_mtime = baseline_path.stat().st_mtime_ns

    exit_code = main([
        "baseline", "compare", str(FIXTURES_DIR / "healthy-project"), "--baseline", str(baseline_path),
    ])
    assert exit_code == 0
    assert baseline_path.read_bytes() == before_content
    assert baseline_path.stat().st_mtime_ns == before_mtime


def test_compare_without_target_sends_no_network_traffic(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    main(["baseline", "save", str(FIXTURES_DIR / "healthy-project"), "--output", str(baseline_path)])

    output_path = tmp_path / "regression.json"
    exit_code = main([
        "baseline", "compare", str(FIXTURES_DIR / "healthy-project"),
        "--baseline", str(baseline_path), "--format", "json", "--output", str(output_path),
    ])
    assert exit_code == 0
    regression = json.loads(output_path.read_text(encoding="utf-8"))
    functional_cat = next(c for c in regression["categories"] if c["name"] == "Functional")
    assert functional_cat["status"] == "not_assessed"


def test_compare_same_project_no_changes_is_pass(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    main(["baseline", "save", str(FIXTURES_DIR / "healthy-project"), "--output", str(baseline_path)])

    output_path = tmp_path / "regression.json"
    exit_code = main([
        "baseline", "compare", str(FIXTURES_DIR / "healthy-project"),
        "--baseline", str(baseline_path), "--format", "json", "--output", str(output_path),
    ])
    assert exit_code == 0
    regression = json.loads(output_path.read_text(encoding="utf-8"))
    assert regression["status"] == "pass"


# --- functional regression end-to-end ---------------------------------------


def test_functional_regression_detected_end_to_end(live_server, tmp_path):
    reset_unstable_counter()
    baseline_path = tmp_path / "baseline.json"
    # 1st request to /unstable: n=1, 1 % 3 != 0 -> succeeds
    exit_code = main([
        "baseline", "save", str(FIXTURES_DIR / "regression-project"),
        "--target", live_server.base_url, "--output", str(baseline_path),
    ])
    assert exit_code == 0
    baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline_data["functional"]["tests"][0]["status"] == "passed"

    # bump the shared unstable counter to 2 with one throwaway request
    urllib.request.urlopen(f"{live_server.base_url}/unstable").read()

    # 3rd request to /unstable: n=3, 3 % 3 == 0 -> fails
    output_path = tmp_path / "regression.json"
    exit_code = main([
        "baseline", "compare", str(FIXTURES_DIR / "regression-project"),
        "--target", live_server.base_url, "--baseline", str(baseline_path),
        "--format", "json", "--output", str(output_path),
    ])
    assert exit_code == 0
    regression = json.loads(output_path.read_text(encoding="utf-8"))
    assert regression["status"] == "fail"
    functional_cat = next(c for c in regression["categories"] if c["name"] == "Functional")
    assert functional_cat["status"] == "fail"
    assert len(functional_cat["findings"]) == 1
    assert functional_cat["findings"][0]["severity"] == "high"
    assert functional_cat["findings"][0]["change"] == "regressed"


# --- performance regression end-to-end --------------------------------------


def test_performance_regression_detected_end_to_end(live_server, tmp_path):
    baseline_path = tmp_path / "baseline.json"
    exit_code = main([
        "baseline", "save", str(FIXTURES_DIR / "unknown-project"),
        "--target", live_server.base_url, "--endpoint", "/fast", "--method", "GET",
        "--performance", "--profile", "custom", "--concurrency", "1", "--requests", "5", "--yes",
        "--output", str(baseline_path),
    ])
    assert exit_code == 0
    baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline_data["performance"] is not None

    output_path = tmp_path / "regression.json"
    exit_code = main([
        "baseline", "compare", str(FIXTURES_DIR / "unknown-project"),
        "--target", live_server.base_url, "--endpoint", "/slow", "--method", "GET",
        "--performance", "--profile", "custom", "--concurrency", "1", "--requests", "5", "--yes",
        "--baseline", str(baseline_path), "--format", "json", "--output", str(output_path),
    ])
    assert exit_code == 0
    regression = json.loads(output_path.read_text(encoding="utf-8"))
    performance_cat = next(c for c in regression["categories"] if c["name"] == "Performance")
    assert performance_cat["status"] == "fail"
    assert any(f["severity"] == "high" for f in performance_cat["findings"])


# --- assess --baseline integration ------------------------------------------


def test_assess_with_baseline_includes_regression_section(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    main(["baseline", "save", str(FIXTURES_DIR / "healthy-project"), "--output", str(baseline_path)])

    report_dir = tmp_path / "reports"
    exit_code = main([
        "assess", str(FIXTURES_DIR / "healthy-project"), "--baseline", str(baseline_path),
        "--output", str(report_dir),
    ])
    assert exit_code == 0
    report = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
    assert report["regression"] is not None
    assert report["regression"]["status"] == "pass"
    markdown = (report_dir / "report.md").read_text(encoding="utf-8")
    assert "## Regression" in markdown
    html = (report_dir / "report.html").read_text(encoding="utf-8")
    assert "Regression" in html


def test_assess_without_baseline_has_no_regression_section(tmp_path):
    report_dir = tmp_path / "reports"
    exit_code = main(["assess", str(FIXTURES_DIR / "healthy-project"), "--output", str(report_dir)])
    assert exit_code == 0
    report = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
    assert report["regression"] is None


def test_assess_invalid_baseline_path_does_not_crash(tmp_path):
    report_dir = tmp_path / "reports"
    exit_code = main([
        "assess", str(FIXTURES_DIR / "healthy-project"),
        "--baseline", str(tmp_path / "does-not-exist.json"), "--output", str(report_dir),
    ])
    # Phase 8: an explicitly-supplied --baseline that can't be loaded is a
    # configuration error (exit 2) -- assess still writes a full report (so a CI
    # operator can see what happened) but the exit code correctly signals a
    # broken invocation rather than silently reporting success.
    assert exit_code == 2
    report = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
    assert report["regression"] is None


# --- database regression end-to-end -----------------------------------------


def _write_sqlite_profile(path: Path, db_path: Path) -> None:
    path.write_text(
        f"database:\n  engine: sqlite\n  path: {db_path.as_posix()}\n  readonly: true\n", encoding="utf-8",
    )


def test_database_schema_change_detected_end_to_end(tmp_path):
    basic_profile = tmp_path / "basic.yaml"
    relations_profile = tmp_path / "relations.yaml"
    _write_sqlite_profile(basic_profile, FIXTURES_DIR / "database" / "sqlite-basic" / "app.db")
    _write_sqlite_profile(relations_profile, FIXTURES_DIR / "database" / "sqlite-relations" / "app.db")

    baseline_path = tmp_path / "baseline.json"
    exit_code = main([
        "baseline", "save", str(FIXTURES_DIR / "database-project"),
        "--database-profile", str(basic_profile), "--output", str(baseline_path),
    ])
    assert exit_code == 0

    output_path = tmp_path / "regression.json"
    exit_code = main([
        "baseline", "compare", str(FIXTURES_DIR / "database-project"),
        "--database-profile", str(relations_profile), "--baseline", str(baseline_path),
        "--format", "json", "--output", str(output_path),
    ])
    assert exit_code == 0
    regression = json.loads(output_path.read_text(encoding="utf-8"))
    database_cat = next(c for c in regression["categories"] if c["name"] == "Database")
    # sqlite-basic has 1 table ("items"); sqlite-relations has 3 -- schema changed, but never a FAIL
    assert database_cat["status"] in ("pass", "warning")
    assert len(database_cat["findings"]) > 0
    assert all(f["severity"] == "info" for f in database_cat["findings"])


# --- secret redaction --------------------------------------------------------


def test_bearer_token_never_appears_in_baseline_file(tmp_path, monkeypatch):
    from tests.adapters.rest.fixture_server import VALID_BEARER_TOKEN
    monkeypatch.setenv("FIXTURE_TOKEN", VALID_BEARER_TOKEN)
    baseline_path = tmp_path / "baseline.json"
    with FixtureServer() as server:
        exit_code = main([
            "baseline", "save", str(FIXTURES_DIR / "openapi-auth"), "--target", server.base_url,
            "--bearer-token-env", "FIXTURE_TOKEN", "--output", str(baseline_path),
        ])
    assert exit_code == 0
    assert VALID_BEARER_TOKEN not in baseline_path.read_text(encoding="utf-8")


def test_bearer_token_never_appears_in_compare_output(tmp_path, monkeypatch):
    from tests.adapters.rest.fixture_server import VALID_BEARER_TOKEN
    monkeypatch.setenv("FIXTURE_TOKEN", VALID_BEARER_TOKEN)
    baseline_path = tmp_path / "baseline.json"
    output_path = tmp_path / "regression.json"
    with FixtureServer() as server:
        main([
            "baseline", "save", str(FIXTURES_DIR / "openapi-auth"), "--target", server.base_url,
            "--bearer-token-env", "FIXTURE_TOKEN", "--output", str(baseline_path),
        ])
        exit_code = main([
            "baseline", "compare", str(FIXTURES_DIR / "openapi-auth"), "--target", server.base_url,
            "--bearer-token-env", "FIXTURE_TOKEN", "--baseline", str(baseline_path),
            "--format", "json", "--output", str(output_path),
        ])
    assert exit_code == 0
    assert VALID_BEARER_TOKEN not in output_path.read_text(encoding="utf-8")
