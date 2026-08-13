"""CLI-level integration tests for `universal-test web assess` (Phase 10).

Verifies the guided command reuses the existing `assess`/browser pipeline
(no duplicate execution/assessment logic), stays safe by default (no
target -> NOT_ASSESSED, never a guessed target), supports dry-run without
launching a browser, and requires explicit confirmation for real execution
outside an interactive terminal.
"""

import json
from pathlib import Path

import pytest

playwright_sync_api = pytest.importorskip("playwright.sync_api")


def _chromium_launchable() -> bool:
    try:
        with playwright_sync_api.sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


if not _chromium_launchable():
    pytest.skip(
        "Chromium binary is not installed -- run `universal-test browser install` "
        "(or `python -m playwright install chromium`) to enable these tests",
        allow_module_level=True,
    )

from universal_test.cli.main import main
from universal_test.adapters.browser.local_server import serve_directory

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_web_assess_without_target_is_safe_and_not_assessed(tmp_path):
    exit_code = main(["web", "assess", str(FIXTURES_DIR / "browser-static-basic"), "--output", str(tmp_path)])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    browser_cat = next(c for c in report["assessment"]["categories"] if c["name"] == "Browser Testing")
    assert browser_cat["status"] == "not_assessed"
    assert "target" in browser_cat["reason"]


def test_web_assess_dry_run_never_launches_a_browser(tmp_path, monkeypatch):
    import universal_test.adapters.browser.adapter as adapter_module

    def _fail(*args, **kwargs):
        raise AssertionError("dry-run must never launch a browser")

    # Patch the name actually used at the call site (`adapter.py`'s own
    # `from executor import browser_session` binding), not the origin
    # module's attribute -- patching the latter only works if `adapter.py`
    # is imported *after* the patch, which isn't guaranteed test-run-order.
    monkeypatch.setattr(adapter_module, "browser_session", _fail)

    exit_code = main([
        "web", "assess", str(FIXTURES_DIR / "browser-static-basic"),
        "--target", "http://localhost:9999", "--dry-run",
    ])
    assert exit_code == 0


def test_web_assess_real_run_reports_browser_pass(tmp_path):
    with serve_directory(FIXTURES_DIR / "browser-static-basic") as base_url:
        exit_code = main([
            "web", "assess", str(FIXTURES_DIR / "browser-static-basic"),
            "--target", base_url, "--yes", "--output", str(tmp_path),
        ])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    browser_cat = next(c for c in report["assessment"]["categories"] if c["name"] == "Browser Testing")
    assert browser_cat["status"] == "pass"
    # Web Assessment is scoped to static analysis + browser testing (spec section 1/7) --
    # REST functional/performance/database must stay untouched by this command.
    assert report["performance"] is None
    assert report["database"] is None


def test_web_assess_real_run_without_yes_requires_confirmation_noninteractive(tmp_path):
    with serve_directory(FIXTURES_DIR / "browser-static-basic") as base_url:
        exit_code = main([
            "web", "assess", str(FIXTURES_DIR / "browser-static-basic"),
            "--target", base_url, "--output", str(tmp_path),
        ])
    # Non-interactive session (pytest) with no --yes: browser testing must not
    # silently execute (spec section 44 -- CI/non-interactive never auto-authorizes).
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    browser_cat = next(c for c in report["assessment"]["categories"] if c["name"] == "Browser Testing")
    assert browser_cat["status"] == "not_assessed"


def test_web_assess_external_target_rejected_without_allow_external(tmp_path):
    exit_code = main([
        "web", "assess", str(FIXTURES_DIR / "browser-static-basic"),
        "--target", "https://example.com", "--yes", "--output", str(tmp_path),
    ])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    browser_cat = next(c for c in report["assessment"]["categories"] if c["name"] == "Browser Testing")
    assert browser_cat["status"] == "not_assessed"
    assert "external" in browser_cat["reason"] or "allow-external" in browser_cat["reason"]


def test_web_assess_broken_frontend_reports_understandable_fail(tmp_path):
    with serve_directory(FIXTURES_DIR / "browser-static-broken") as base_url:
        exit_code = main([
            "web", "assess", str(FIXTURES_DIR / "browser-static-broken"),
            "--target", base_url, "--yes", "--output", str(tmp_path),
        ])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    browser_cat = next(c for c in report["assessment"]["categories"] if c["name"] == "Browser Testing")
    assert browser_cat["status"] == "warning"
    finding = next(f for f in report["findings"] if f["id"] == "BROWSER-FAILED")
    assert finding["classification"] == "defect"


def test_web_assess_unreachable_target_reports_error_not_fail(tmp_path):
    exit_code = main([
        "web", "assess", str(FIXTURES_DIR / "browser-static-basic"),
        "--target", "http://127.0.0.1:39124/", "--yes", "--output", str(tmp_path),
    ])
    assert exit_code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    browser_cat = next(c for c in report["assessment"]["categories"] if c["name"] == "Browser Testing")
    error_finding = next(f for f in report["findings"] if f["id"] == "BROWSER-ERROR")
    assert error_finding["classification"] == "execution_failure"
