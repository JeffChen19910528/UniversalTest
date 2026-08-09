"""Canonical end-to-end pipeline test (V1 hardening audit section 9).

Runs every implemented subcommand against `tests/fixtures/e2e-project/` --
a single fixture with an OpenAPI spec, a SQLite database, Docker/CI/test-
framework evidence, and a fixture secret pattern -- entirely against
controlled local infrastructure (the offline stdlib fixture HTTP server and
a local SQLite file). No public internet access anywhere in this file.
"""

import json
from pathlib import Path

import pytest

from universal_test.cli.main import main
from tests.adapters.rest.fixture_server import FixtureServer, VALID_BEARER_TOKEN

FIXTURE = str(Path(__file__).parent.parent / "fixtures" / "e2e-project")
DB_PATH = Path(__file__).parent.parent / "fixtures" / "e2e-project" / "database" / "app.db"


@pytest.fixture(scope="module")
def live_server():
    with FixtureServer() as server:
        yield server


@pytest.fixture(scope="module")
def db_profile(tmp_path_factory):
    path = tmp_path_factory.mktemp("e2e-db-profile") / "database.yaml"
    path.write_text(
        f"database:\n  engine: sqlite\n  path: {DB_PATH.as_posix()}\n  readonly: true\n", encoding="utf-8",
    )
    return str(path)


def test_01_scan(tmp_path):
    output = tmp_path / "scan.json"
    exit_code = main(["scan", FIXTURE, "--format", "json", "--output", str(output)])
    assert exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert "PostgreSQL" in [d["name"] for d in data["databases"]]
    assert "Docker" in [i["name"] for i in data["infrastructure"]]
    assert data["secrets"], "the fixture's own secret pattern must be detected"
    # the fixture's real secret value must never appear anywhere in scan output
    assert "s3cr3tFixtureValue123" not in json.dumps(data)


def test_02_test_dry_run(tmp_path):
    output = tmp_path / "dry_run.json"
    exit_code = main(["test", FIXTURE, "--dry-run", "--format", "json", "--output", str(output)])
    assert exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["discovered_endpoints"] >= 2
    assert data["executed"] is False


def test_03_test_executed(live_server, tmp_path):
    output = tmp_path / "test_run.json"
    exit_code = main([
        "test", FIXTURE, "--target", live_server.base_url, "--format", "json", "--output", str(output),
    ])
    assert exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["run_result"]["summary"]["passed"] >= 1


def test_04_performance(live_server, tmp_path):
    output = tmp_path / "perf.json"
    exit_code = main([
        "performance", FIXTURE, "--target", live_server.base_url, "--endpoint", "/fast", "--method", "GET",
        "--profile", "custom", "--concurrency", "1", "--requests", "3", "--yes",
        "--format", "json", "--output", str(output),
    ])
    assert exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["levels"][0]["metrics"]["total_requests"] == 3


def test_05_database(db_profile, tmp_path):
    output = tmp_path / "db.json"
    exit_code = main([
        "database", FIXTURE, "--database-profile", db_profile, "--format", "json", "--output", str(output),
    ])
    assert exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["connected"] is True
    assert any(t["name"] == "users" for s in data["database"]["schemas"] for t in s["tables"])


def test_06_assess_full(live_server, db_profile, tmp_path, monkeypatch):
    monkeypatch.setenv("E2E_TOKEN", VALID_BEARER_TOKEN)
    output = tmp_path / "reports"
    exit_code = main([
        "assess", FIXTURE, "--target", live_server.base_url, "--database-profile", db_profile,
        "--bearer-token-env", "E2E_TOKEN", "--output", str(output),
    ])
    # exit 0 (pass) or 1 (a real quality-gate finding) are both legitimate outcomes here --
    # what matters is it's deterministic and never crashes (asserted via report presence below).
    assert exit_code in (0, 1)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0"
    assert report["database"] is not None
    assert report["quality_gate"] is not None
    full_text = json.dumps(report) + (output / "report.md").read_text(encoding="utf-8") + (output / "report.html").read_text(encoding="utf-8")
    assert "s3cr3tFixtureValue123" not in full_text
    assert VALID_BEARER_TOKEN not in full_text


def test_07_baseline_save(live_server, db_profile, tmp_path):
    baseline_path = tmp_path / "baseline.json"
    exit_code = main([
        "baseline", "save", FIXTURE, "--target", live_server.base_url, "--database-profile", db_profile,
        "--output", str(baseline_path),
    ])
    assert exit_code == 0
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert data["functional"] is not None
    assert data["database"] is not None


def test_08_baseline_compare(live_server, db_profile, tmp_path):
    baseline_path = tmp_path / "baseline.json"
    main([
        "baseline", "save", FIXTURE, "--target", live_server.base_url, "--database-profile", db_profile,
        "--output", str(baseline_path),
    ])
    before = baseline_path.read_bytes()

    output = tmp_path / "regression.json"
    exit_code = main([
        "baseline", "compare", FIXTURE, "--target", live_server.base_url, "--database-profile", db_profile,
        "--baseline", str(baseline_path), "--format", "json", "--output", str(output),
    ])
    assert exit_code == 0
    regression = json.loads(output.read_text(encoding="utf-8"))
    assert regression["status"] == "pass"  # comparing the project against itself
    # baseline compare must never modify the baseline file it read
    assert baseline_path.read_bytes() == before


def test_09_full_pipeline_is_deterministic(live_server, db_profile, tmp_path):
    """Running assess twice against identical inputs produces identical
    assessment/regression/quality_gate content -- every field except the
    handful of real wall-clock timestamps a fresh scan/run legitimately
    produces each time (generated_at, discovery.scanned_at)."""
    def _strip_timestamps(data: dict) -> dict:
        data.pop("generated_at", None)
        data.get("discovery", {}).pop("scanned_at", None)
        return data

    reports = []
    for i in range(2):
        output = tmp_path / f"run{i}"
        main([
            "assess", FIXTURE, "--target", live_server.base_url, "--database-profile", db_profile,
            "--output", str(output),
        ])
        data = json.loads((output / "report.json").read_text(encoding="utf-8"))
        reports.append(_strip_timestamps(data))
    assert reports[0] == reports[1]
