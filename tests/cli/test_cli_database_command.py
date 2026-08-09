"""CLI-level tests for `universal-test database` and `assess --database-profile`."""

import json
from pathlib import Path

from universal_test.cli.main import main

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
DB_FIXTURES = FIXTURES_DIR / "database"


def _write_profile(tmp_path, db_path, readonly=True) -> Path:
    profile_path = tmp_path / "db.yaml"
    lines = ["database:", "  engine: sqlite", f"  path: {db_path.as_posix()}"]
    if readonly:
        lines.append("  readonly: true")
    profile_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return profile_path


def test_missing_profile_flag_is_a_clean_error():
    exit_code = main(["database", str(FIXTURES_DIR / "healthy-project")])
    assert exit_code == 2


def test_dry_run_shows_plan_and_executes_nothing(tmp_path):
    profile_path = _write_profile(tmp_path, DB_FIXTURES / "sqlite-basic" / "app.db")
    exit_code = main([
        "database", str(FIXTURES_DIR / "healthy-project"),
        "--database-profile", str(profile_path), "--dry-run",
    ])
    assert exit_code == 0


def test_invalid_profile_missing_readonly_is_a_clean_error(tmp_path):
    profile_path = _write_profile(tmp_path, DB_FIXTURES / "sqlite-basic" / "app.db", readonly=False)
    exit_code = main([
        "database", str(FIXTURES_DIR / "healthy-project"), "--database-profile", str(profile_path),
    ])
    assert exit_code == 2


def test_missing_credentials_env_names_still_connects_for_sqlite(tmp_path, capsys):
    # sqlite has no credentials concept -- absence of credentials must not block it
    profile_path = _write_profile(tmp_path, DB_FIXTURES / "sqlite-relations" / "app.db")
    exit_code = main([
        "database", str(FIXTURES_DIR / "healthy-project"), "--database-profile", str(profile_path),
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "customers" in out
    assert "orders" in out


def test_safe_output_contains_no_raw_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DB_USER", "svc_account")
    monkeypatch.setenv("DB_PASSWORD", "TopSecret123")
    profile_path = tmp_path / "db.yaml"
    profile_path.write_text("""
database:
  engine: postgresql
  host: 127.0.0.1
  port: 1
  database: nope
  credentials:
    username_env: DB_USER
    password_env: DB_PASSWORD
  readonly: true
""", encoding="utf-8")
    exit_code = main([
        "database", str(FIXTURES_DIR / "healthy-project"), "--database-profile", str(profile_path),
    ])
    assert exit_code == 2  # connection fails (nothing listening)
    out = capsys.readouterr().out
    assert "TopSecret123" not in out
    assert "svc_account" not in out


def test_json_format_output(tmp_path, capsys):
    profile_path = _write_profile(tmp_path, DB_FIXTURES / "sqlite-basic" / "app.db")
    exit_code = main([
        "database", str(FIXTURES_DIR / "healthy-project"),
        "--database-profile", str(profile_path), "--format", "json",
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["connected"] is True
    assert parsed["profile"]["engine"] == "sqlite"
    assert "credentials" not in json.dumps(parsed["profile"]) or parsed["profile"]["credentials"] in (
        "configured", "not configured",
    )


def test_assess_without_database_profile_is_not_assessed(tmp_path):
    exit_code = main(["assess", str(FIXTURES_DIR / "healthy-project"), "--output", str(tmp_path)])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    db_category = next(c for c in report["assessment"]["categories"] if c["name"] == "Database Health")
    assert db_category["status"] == "not_assessed"
    assert report["database"] is None


def test_assess_with_database_profile_integrates_full_report(tmp_path):
    profile_path = _write_profile(tmp_path, DB_FIXTURES / "sqlite-relations" / "app.db")
    output_dir = tmp_path / "out"
    exit_code = main([
        "assess", str(FIXTURES_DIR / "healthy-project"),
        "--database-profile", str(profile_path), "--output", str(output_dir),
    ])
    assert exit_code == 0

    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    db_category = next(c for c in report["assessment"]["categories"] if c["name"] == "Database Health")
    assert db_category["status"] == "pass"
    assert report["database"] is not None
    assert len(report["database"]["schemas"][0]["tables"]) == 3

    md = (output_dir / "report.md").read_text(encoding="utf-8")
    assert "## Database" in md
    assert "customers" in md

    html_text = (output_dir / "report.html").read_text(encoding="utf-8")
    assert "Database Summary" in html_text


def test_assess_with_invalid_database_profile_degrades_gracefully(tmp_path, capsys):
    profile_path = _write_profile(tmp_path, DB_FIXTURES / "sqlite-basic" / "app.db", readonly=False)
    output_dir = tmp_path / "out"
    exit_code = main([
        "assess", str(FIXTURES_DIR / "healthy-project"),
        "--database-profile", str(profile_path), "--output", str(output_dir),
    ])
    assert exit_code == 0  # assess never hard-crashes on a bad sub-flag
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    db_category = next(c for c in report["assessment"]["categories"] if c["name"] == "Database Health")
    assert db_category["status"] == "not_assessed"
