"""Browser adapter orchestration (spec §3, §25, §34-§36).

`run()` is what the CLI/Application Service Layer calls -- mirrors
`adapters/rest/adapter.py::run()`'s shape: dry-run never launches a
browser, missing target is reported (never guessed), Playwright/browser
unavailability is caught and reported as `not_assessed_reason` (never
raised as an uncaught exception, never conflated with a test failure).
`BrowserAdapter` additionally implements the generic adapter contract
(ARCHITECTURE.md §7) for architectural completeness alongside REST/Frontend.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from universal_test.adapters.browser.assertions import build_browser_assertion_engine
from universal_test.adapters.browser.errors import BrowserTargetError, BrowserUnavailableError
from universal_test.adapters.browser.executor import DEFAULT_TEST_TIMEOUT_SECONDS, browser_session
from universal_test.adapters.browser.models import BrowserRunResult
from universal_test.adapters.browser.target_policy import validate_target
from universal_test.adapters.browser.test_generation import generate_smoke_test
from universal_test.adapters.frontend.adapter import discover as discover_frontend
from universal_test.core.adapter_info import AdapterInfo
from universal_test.core.engine.test_engine import TestEngine
from universal_test.core.models.test_spec import TestCase
from universal_test.core.orchestration.orchestrator import Orchestrator, RunResult

DEFAULT_NAVIGATION_TIMEOUT_SECONDS = 15.0
DEFAULT_ACTION_TIMEOUT_SECONDS = 10.0


def _safe_discover_frontend(project_path: str | Path):
    with contextlib.suppress(Exception):
        return discover_frontend(project_path)
    return None


def run(
    project_path: str | Path,
    *,
    target: str | None = None,
    test_cases: list[TestCase] | None = None,
    allow_external: bool = False,
    browser: str = "chromium",
    headless: bool = True,
    navigation_timeout_seconds: float = DEFAULT_NAVIGATION_TIMEOUT_SECONDS,
    action_timeout_seconds: float = DEFAULT_ACTION_TIMEOUT_SECONDS,
    test_timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS,
    screenshots: bool = False,
    screenshot_dir: str | Path | None = None,
    dry_run: bool = False,
) -> BrowserRunResult:
    frontend_info = _safe_discover_frontend(project_path)

    if test_cases is None:
        test_cases = [generate_smoke_test(target, frontend_info)] if target else []

    if dry_run:
        return BrowserRunResult(test_cases=test_cases, executed=False, target=target, browser=browser)

    if not target:
        return BrowserRunResult(
            test_cases=test_cases, executed=False, target=target, browser=browser,
            no_target_reason="no execution target was specified (browser testing requires an explicit --target)",
        )

    try:
        validate_target(target, allow_external=allow_external)
    except BrowserTargetError as exc:
        return BrowserRunResult(
            test_cases=test_cases, executed=False, target=target, browser=browser, no_target_reason=str(exc),
        )

    resolved_screenshot_dir: Path | None = None
    if screenshots:
        resolved_screenshot_dir = Path(screenshot_dir) if screenshot_dir else Path("reports") / "screenshots"
        resolved_screenshot_dir.mkdir(parents=True, exist_ok=True)

    test_engine = TestEngine(assertion_engine=build_browser_assertion_engine())

    try:
        with browser_session(
            target, browser_name=browser, headless=headless,
            navigation_timeout_seconds=navigation_timeout_seconds,
            action_timeout_seconds=action_timeout_seconds,
            test_timeout_seconds=test_timeout_seconds,
            allow_external=allow_external, screenshot_dir=resolved_screenshot_dir,
        ) as (executor, screenshots_taken):
            run_result = Orchestrator(test_engine).run_test_cases(test_cases, executor)
    except BrowserUnavailableError as exc:
        return BrowserRunResult(
            test_cases=test_cases, executed=False, target=target, browser=browser, not_assessed_reason=str(exc),
        )

    return BrowserRunResult(
        test_cases=test_cases, run_result=run_result, executed=True, target=target,
        browser=browser, screenshots=list(screenshots_taken),
    )


class BrowserAdapter:
    """Generic adapter-contract wrapper around `run()` above."""

    info = AdapterInfo(name="browser", version="1", capabilities=["ui_testing"])

    def detect(self, project_path: str | Path) -> bool:
        info = _safe_discover_frontend(project_path)
        return bool(info and info.detected)

    def describe(self) -> AdapterInfo:
        return self.info

    def discover(self, project_path: str | Path):
        return discover_frontend(project_path)

    def generate_tests(self, target: str | None, frontend_info=None) -> list[TestCase]:
        return [generate_smoke_test(target, frontend_info)] if target else []

    def execute(
        self, test_cases: list[TestCase], target: str, allow_external: bool = False,
        browser: str = "chromium", headless: bool = True,
        navigation_timeout_seconds: float = DEFAULT_NAVIGATION_TIMEOUT_SECONDS,
        action_timeout_seconds: float = DEFAULT_ACTION_TIMEOUT_SECONDS,
        test_timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS,
    ) -> RunResult:
        validate_target(target, allow_external=allow_external)
        test_engine = TestEngine(assertion_engine=build_browser_assertion_engine())
        with browser_session(
            target, browser_name=browser, headless=headless,
            navigation_timeout_seconds=navigation_timeout_seconds,
            action_timeout_seconds=action_timeout_seconds, test_timeout_seconds=test_timeout_seconds,
            allow_external=allow_external,
        ) as (executor, _screenshots):
            return Orchestrator(test_engine).run_test_cases(test_cases, executor)

    def collect_metrics(self, run_result: RunResult | None) -> dict:
        return run_result.summary if run_result is not None else {}
