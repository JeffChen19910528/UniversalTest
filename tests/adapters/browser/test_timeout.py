"""TestCase wall-clock timeout hardening (Phase 9 hardening pass).

Verifies the timeout hierarchy invariant: `min(step_timeout, remaining
TestCase budget)`, that the hard ceiling is enforced without a watchdog
thread (Playwright's sync API is single-threaded), that a timed-out
TestCase is classified ERROR (never PASS, never silently treated as an
application defect), and that cleanup still completes.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from universal_test.adapters.browser.errors import BrowserTimeoutError
from universal_test.adapters.browser.executor import _remaining_ms

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

from universal_test.adapters.browser.adapter import run
from universal_test.adapters.browser.assertions import build_browser_assertion_engine
from universal_test.adapters.browser.executor import browser_session
from universal_test.adapters.browser.local_server import serve_directory
from universal_test.adapters.browser.models import BrowserSelector, BrowserStep
from universal_test.assessment.browser_assessment import assess_browser_health
from universal_test.core.models.enums import AssessmentStatus, FindingClassification, ResultStatus
from universal_test.core.models.test_spec import AssertionSpec, TestCase, TestTarget
from universal_test.core.engine.test_engine import TestEngine
from universal_test.core.orchestration.orchestrator import Orchestrator

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


# -- Pure budget-calculation unit tests (no browser needed) -----------------

def test_remaining_ms_returns_capped_value_when_budget_available():
    deadline = time.monotonic() + 10.0
    value = _remaining_ms(deadline, cap_ms=5000.0, action="test")
    assert 0 < value <= 5000.0


def test_remaining_ms_never_exceeds_remaining_budget():
    deadline = time.monotonic() + 1.0  # ~1000ms left
    value = _remaining_ms(deadline, cap_ms=999999.0, action="test")
    assert value <= 1100.0  # bounded by remaining budget, not the huge cap


def test_remaining_ms_raises_once_deadline_passed():
    deadline = time.monotonic() - 1.0  # already in the past
    with pytest.raises(BrowserTimeoutError):
        _remaining_ms(deadline, cap_ms=5000.0, action="test")


def test_remaining_ms_child_never_extends_beyond_parent_budget():
    # Spec example: TestCase budget=30s, step 2 starts at t=14 with its own
    # configured timeout of 15s -- effective timeout must be ~min(15, 16), not 15.
    deadline = time.monotonic() + 16.0  # 30s budget, 14s already spent
    value = _remaining_ms(deadline, cap_ms=15000.0, action="step2")
    assert value <= 16000.0
    assert value <= 15000.0


# -- Real-browser hard-ceiling tests -----------------------------------------

def _case_with_slow_wait(action_timeout_seconds_hint: str = "n/a"):
    return TestCase(
        id="slow-wait-for", name="slow-wait-for", type="browser",
        target=TestTarget(adapter="browser", extra={"steps": [
            BrowserStep("navigate").to_dict(),
            BrowserStep("wait_for", selector=BrowserSelector("css", "#ready")).to_dict(),
        ]}),
        assertions=[AssertionSpec("page_title", {})],
    )


def test_testcase_timeout_is_bounded_not_sum_of_step_timeouts():
    """Step's own `action_timeout_seconds` is generous (10s) but the
    TestCase timeout is 2s -- total wall-clock time must stay close to 2s,
    never balloon toward 10s (which is what "sum of step timeouts" would
    produce for a single slow step, and easily 10s+ for multiple).
    """
    with serve_directory(FIXTURES / "browser-static-slow") as base_url:
        engine = build_browser_assertion_engine()
        started = time.monotonic()
        with browser_session(
            base_url, headless=True, action_timeout_seconds=10.0,
            navigation_timeout_seconds=10.0, test_timeout_seconds=2.0,
        ) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([_case_with_slow_wait()], executor)
        elapsed = time.monotonic() - started

        assert elapsed < 6.0, f"TestCase timeout was not enforced as a hard ceiling (took {elapsed:.1f}s)"
        assert run_result.results[0].status == ResultStatus.ERROR


def test_testcase_timeout_never_reported_as_pass():
    with serve_directory(FIXTURES / "browser-static-slow") as base_url:
        engine = build_browser_assertion_engine()
        with browser_session(
            base_url, headless=True, action_timeout_seconds=10.0,
            navigation_timeout_seconds=10.0, test_timeout_seconds=1.5,
        ) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([_case_with_slow_wait()], executor)
        result = run_result.results[0]
        assert result.status != ResultStatus.PASSED
        assert result.status == ResultStatus.ERROR
        assert "test" in result.message.lower() or "exec" in result.message.lower()


def test_timeout_result_is_execution_failure_not_defect_in_assessment():
    """A TestCase timeout must never be silently reclassified as an
    application defect in the assessment layer (spec section 7)."""
    with serve_directory(FIXTURES / "browser-static-slow") as base_url:
        engine = build_browser_assertion_engine()
        with browser_session(
            base_url, headless=True, action_timeout_seconds=10.0,
            navigation_timeout_seconds=10.0, test_timeout_seconds=1.5,
        ) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([_case_with_slow_wait()], executor)

    from universal_test.adapters.browser.models import BrowserRunResult

    browser_result = BrowserRunResult(
        test_cases=[_case_with_slow_wait()], run_result=run_result, executed=True,
        target=base_url, browser="chromium",
    )
    category = assess_browser_health(browser_result, None)
    assert category.status in {AssessmentStatus.WARNING, AssessmentStatus.FAIL}
    error_findings = [f for f in category.findings if f.id == "BROWSER-ERROR"]
    assert len(error_findings) == 1
    assert error_findings[0].classification == FindingClassification.EXECUTION_FAILURE


def test_timeout_cleanup_no_orphan_browser_afterward(tmp_path):
    """After a TestCase times out, `run()` must still complete cleanly and
    leave no leaked browser process -- verified indirectly by confirming a
    second, unrelated `run()` call works normally right afterward."""
    with serve_directory(FIXTURES / "browser-static-slow") as base_url:
        result = run(
            str(FIXTURES / "browser-static-slow"), target=base_url,
            test_cases=[_case_with_slow_wait()],
            navigation_timeout_seconds=10.0, action_timeout_seconds=10.0, test_timeout_seconds=1.5,
        )
        assert result.executed
        assert result.run_result.summary["error"] == 1

    # A fresh run right after must still work -- proves the timed-out session's
    # cleanup (context.close()/browser.close()/playwright.stop()) completed.
    with serve_directory(FIXTURES / "browser-static-basic") as base_url2:
        result2 = run(str(FIXTURES / "browser-static-basic"), target=base_url2)
        assert result2.executed
        assert result2.run_result.summary["passed"] == 1


def test_generous_testcase_timeout_still_allows_slow_page_to_finish():
    """Sanity check the timeout isn't overly aggressive: a TestCase timeout
    comfortably larger than the fixture's delay must still PASS."""
    with serve_directory(FIXTURES / "browser-static-slow") as base_url:
        engine = build_browser_assertion_engine()
        with browser_session(
            base_url, headless=True, action_timeout_seconds=15.0,
            navigation_timeout_seconds=15.0, test_timeout_seconds=15.0,
        ) as (executor, _shots):
            run_result = Orchestrator(TestEngine(engine)).run_test_cases([_case_with_slow_wait()], executor)
        assert run_result.results[0].status == ResultStatus.PASSED
