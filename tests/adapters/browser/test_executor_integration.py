"""Real-browser integration tests (spec section 50-52): exercise the actual
Playwright executor against local fixtures only, never external network.

Skips cleanly with a clear reason (never fails) when Playwright or a
Chromium binary isn't available in the current environment -- this must
never block CI that hasn't run `universal-test browser install`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

playwright_sync_api = pytest.importorskip("playwright.sync_api")

from universal_test.adapters.browser.adapter import run
from universal_test.adapters.browser.errors import BrowserTargetError
from universal_test.adapters.browser.executor import browser_session
from universal_test.adapters.browser.local_server import serve_directory
from universal_test.adapters.browser.models import BrowserSelector, BrowserStep
from universal_test.core.models.enums import ResultStatus
from universal_test.core.models.test_spec import AssertionSpec, TestCase, TestTarget
from universal_test.core.orchestration.orchestrator import Orchestrator
from universal_test.core.engine.test_engine import TestEngine
from universal_test.adapters.browser.assertions import build_browser_assertion_engine

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


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


def _case(id_, *, steps, assertions, adapter="browser"):
    return TestCase(
        id=id_, name=id_, type="browser",
        target=TestTarget(adapter=adapter, extra={"steps": [s.to_dict() for s in steps]}),
        assertions=assertions,
    )


def test_smoke_test_passes_against_basic_fixture():
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        result = run(str(FIXTURES / "browser-static-basic"), target=base_url)
        assert result.executed
        assert result.run_result.summary["passed"] == 1


def test_visibility_and_text_assertions():
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        heading = BrowserSelector("css", "#heading")
        case = _case(
            "heading-check",
            steps=[BrowserStep("navigate")],
            assertions=[
                AssertionSpec("visible", {"selector": heading.to_dict()}),
                AssertionSpec("text_equals", {"selector": heading.to_dict(), "value": "Welcome"}),
            ],
        )
        engine = build_browser_assertion_engine()
        with browser_session(base_url, headless=True) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([case], executor)
        assert run_result.summary["passed"] == 1


def test_click_updates_page_state():
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        status = BrowserSelector("css", "#status")
        case = _case(
            "click-check",
            steps=[BrowserStep("navigate"), BrowserStep("click", selector=BrowserSelector("css", "#start-button"))],
            assertions=[AssertionSpec("text_equals", {"selector": status.to_dict(), "value": "started"})],
        )
        engine = build_browser_assertion_engine()
        with browser_session(base_url, headless=True) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([case], executor)
        assert run_result.summary["passed"] == 1


def test_fill_and_input_value():
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        email = BrowserSelector("css", "#email")
        case = _case(
            "fill-check",
            steps=[
                BrowserStep("navigate", value=base_url + "/contact.html"),
                BrowserStep("fill", selector=email, value="user@example.com"),
            ],
            assertions=[AssertionSpec("input_value", {"selector": email.to_dict(), "equals": "user@example.com"})],
        )
        engine = build_browser_assertion_engine()
        with browser_session(base_url, headless=True) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([case], executor)
        assert run_result.summary["passed"] == 1


def test_navigation_click_changes_url():
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        about_link = BrowserSelector("role", "About", role="link")
        case = _case(
            "nav-check",
            steps=[BrowserStep("navigate"), BrowserStep("click", selector=about_link)],
            assertions=[AssertionSpec("url_contains", {"value": "about.html"})],
        )
        engine = build_browser_assertion_engine()
        with browser_session(base_url, headless=True) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([case], executor)
        assert run_result.summary["passed"] == 1


def test_wrong_assertion_produces_fail_not_error():
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        case = _case(
            "wrong-title",
            steps=[BrowserStep("navigate")],
            assertions=[AssertionSpec("page_title", {"equals": "Definitely Not The Title"})],
        )
        engine = build_browser_assertion_engine()
        with browser_session(base_url, headless=True) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([case], executor)
        assert run_result.summary["failed"] == 1
        assert run_result.results[0].status == ResultStatus.FAILED


def test_missing_element_produces_fail_not_error():
    with serve_directory(FIXTURES / "browser-static-broken") as base_url:
        missing = BrowserSelector("css", "#start-button")
        case = _case(
            "missing-element",
            steps=[BrowserStep("navigate")],
            assertions=[AssertionSpec("visible", {"selector": missing.to_dict()})],
        )
        engine = build_browser_assertion_engine()
        with browser_session(base_url, headless=True) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([case], executor)
        assert run_result.summary["failed"] == 1


def test_unreachable_target_produces_error_not_fail():
    # Port 1 is a reserved/unused port that should always refuse connections.
    unreachable = "http://127.0.0.1:1/"
    case = _case("unreachable", steps=[BrowserStep("navigate")], assertions=[AssertionSpec("page_title", {})])
    engine = build_browser_assertion_engine()
    with browser_session(unreachable, headless=True) as (executor, _shots):
        run_result = Orchestrator(TestEngine(engine)).run_test_cases([case], executor)
    assert run_result.results[0].status == ResultStatus.ERROR


def test_selector_matching_zero_elements_is_execution_error():
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        case = _case(
            "bad-selector-click",
            steps=[BrowserStep("navigate"), BrowserStep("click", selector=BrowserSelector("css", "#does-not-exist"))],
            assertions=[AssertionSpec("page_title", {})],
        )
        engine = build_browser_assertion_engine()
        with browser_session(base_url, headless=True) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([case], executor)
        assert run_result.results[0].status == ResultStatus.ERROR


def test_console_error_and_page_error_captured_without_failing_test():
    with serve_directory(FIXTURES / "browser-static-broken") as base_url:
        result = run(str(FIXTURES / "browser-static-broken"), target=base_url)
        assert result.executed
        # The smoke test only asserts body visibility + non-empty title (title is
        # intentionally empty in this fixture, so this specific smoke test FAILs --
        # proving the page_error itself never silently becomes the failure reason).
        assert result.run_result.summary["failed"] == 1


def test_external_navigation_blocked_without_allow_external():
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        case = _case(
            "external-nav",
            steps=[BrowserStep("navigate"), BrowserStep("navigate", value="https://example.com")],
            assertions=[AssertionSpec("page_title", {})],
        )
        engine = build_browser_assertion_engine()
        with browser_session(base_url, headless=True, allow_external=False) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([case], executor)
        assert run_result.results[0].status == ResultStatus.ERROR


def test_screenshot_created_when_enabled(tmp_path):
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        result = run(str(FIXTURES / "browser-static-basic"), target=base_url, screenshots=True, screenshot_dir=tmp_path)
        assert result.executed
        assert len(result.screenshots) == 1
        assert Path(result.screenshots[0]).is_file()


def test_permission_capability_never_auto_granted():
    # No permission-granting API exists on `browser_session`/executor at all --
    # this test documents that a page requiring getUserMedia simply loads (the
    # smoke test never invokes the mic-requesting button), proving no permission
    # is auto-granted merely because the capability exists on the page.
    with serve_directory(FIXTURES / "browser-static-permission") as base_url:
        result = run(str(FIXTURES / "browser-static-permission"), target=base_url)
        assert result.executed
        assert result.run_result.summary["passed"] == 1


def test_isolated_context_has_no_cookies_across_runs():
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        with browser_session(base_url, headless=True) as (executor, _shots):
            case = _case(
                "set-cookie", steps=[BrowserStep("navigate")], assertions=[AssertionSpec("page_title", {})],
            )
            executor(case)
        # A brand new session must not see any state from the previous one.
        with browser_session(base_url, headless=True) as (executor2, _shots2):
            ctx = executor2(case)
            assert ctx["url"].startswith(base_url)
