"""Real-browser ScenarioRunner tests (Phase 11 spec §21-§26, §48).

Exercises the actual sequential execution engine against
`tests/fixtures/browser-scenario-app/` -- a deterministic, local-only
fixture with Home/Login/Dashboard/Search states.
"""

from __future__ import annotations

import os
import time
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

from universal_test.adapters.browser.local_server import serve_directory
from universal_test.adapters.browser.models import BrowserSelector
from universal_test.adapters.browser.scenario_models import ScenarioStep, WebScenario
from universal_test.adapters.browser.scenario_runner import (
    missing_environment_variables,
    run_scenario,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "browser-scenario-app"


def _login_scenario(password="demo123", timeout_seconds=None, extra_steps=None):
    steps = [
        ScenarioStep(id="open", action="navigate", url="login.html"),
        ScenarioStep(id="enter-user", action="fill", selector=BrowserSelector("label", "Username"), value_env="TEST_USERNAME"),
        ScenarioStep(id="enter-pass", action="fill", selector=BrowserSelector("label", "Password"), value_env="TEST_PASSWORD"),
        ScenarioStep(id="login", action="click", selector=BrowserSelector("role", "Login", role="button")),
        ScenarioStep(id="dashboard", action="assert_visible", selector=BrowserSelector("text", "Dashboard")),
    ]
    if extra_steps:
        steps.extend(extra_steps)
    return WebScenario(id="login-smoke", name="Login Smoke Test", steps=steps, timeout_seconds=timeout_seconds)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TEST_USERNAME", "demo")
    monkeypatch.setenv("TEST_PASSWORD", "demo123")


def test_scenario_passes_with_correct_credentials():
    with serve_directory(FIXTURES) as base_url:
        result = run_scenario(_login_scenario(), target=base_url)
    assert result.status == "pass"
    assert result.passed_steps == 5
    assert result.failed_steps == 0
    assert result.error_steps == 0
    assert result.skipped_steps == 0


def test_scenario_fails_with_wrong_credentials_and_stops(monkeypatch):
    monkeypatch.setenv("TEST_PASSWORD", "wrong-password")
    extra = [ScenarioStep(id="never-runs", action="assert_title", value="Dashboard")]
    with serve_directory(FIXTURES) as base_url:
        result = run_scenario(_login_scenario(extra_steps=extra), target=base_url)
    assert result.status == "fail"
    assert result.failed_steps == 1
    # The step after the failed assertion must never have executed (spec section 21).
    never_ran = next(s for s in result.steps if s.step_id == "never-runs")
    assert never_ran.status == "skipped"


def test_missing_required_env_var_is_not_assessed(monkeypatch):
    monkeypatch.delenv("TEST_PASSWORD", raising=False)
    scenario = _login_scenario()
    assert "TEST_PASSWORD" in missing_environment_variables(scenario)
    with serve_directory(FIXTURES) as base_url:
        result = run_scenario(scenario, target=base_url)
    assert result.status == "not_assessed"
    assert "TEST_PASSWORD" in result.not_assessed_reason
    assert result.steps == []  # never launched a browser


def test_unreachable_target_is_error():
    scenario = _login_scenario()
    result = run_scenario(scenario, target="http://127.0.0.1:39130/")
    assert result.status == "error"
    assert result.steps[0].status == "error"


def test_search_scenario_assert_count_and_text():
    scenario = WebScenario(
        id="search", name="Search",
        steps=[
            ScenarioStep(id="open", action="navigate", url="search.html"),
            ScenarioStep(id="query", action="fill", selector=BrowserSelector("placeholder", "Search"), value="widget"),
            ScenarioStep(id="go", action="click", selector=BrowserSelector("role", "Search", role="button")),
            ScenarioStep(id="count", action="assert_text", selector=BrowserSelector("css", "#result-count"), value="3 results"),
            ScenarioStep(id="items", action="assert_count", selector=BrowserSelector("css", "#results li"), count_equals=3),
        ],
    )
    with serve_directory(FIXTURES) as base_url:
        result = run_scenario(scenario, target=base_url)
    assert result.status == "pass"
    assert result.passed_steps == 5


def test_scenario_step_never_leaks_secret_value_in_result():
    with serve_directory(FIXTURES) as base_url:
        result = run_scenario(_login_scenario(), target=base_url)
    dumped = str(result.to_dict())
    assert "demo123" not in dumped


def test_scenario_timeout_is_a_true_hard_ceiling():
    # A step waiting for an element that never appears, with a generous
    # per-step timeout but a tight scenario timeout -- total wall-clock
    # must stay close to the scenario timeout, not the step timeout.
    scenario = WebScenario(
        id="slow", name="Slow",
        steps=[
            ScenarioStep(id="open", action="navigate", url="/"),
            ScenarioStep(
                id="wait", action="wait_for", selector=BrowserSelector("css", "#never-appears"),
                timeout_seconds=10.0,
            ),
        ],
        timeout_seconds=2.0,
    )
    with serve_directory(FIXTURES) as base_url:
        started = time.monotonic()
        result = run_scenario(scenario, target=base_url, action_timeout_seconds=10.0)
        elapsed = time.monotonic() - started
    assert elapsed < 6.0, f"scenario timeout was not enforced as a hard ceiling (took {elapsed:.1f}s)"
    assert result.status == "error"


def test_scenario_cleanup_no_orphan_after_run():
    with serve_directory(FIXTURES) as base_url:
        run_scenario(_login_scenario(), target=base_url)
    # A fresh scenario run right after must still work -- proves the prior
    # session's browser/context/driver cleanup completed (spec section 47).
    with serve_directory(FIXTURES) as base_url2:
        result = run_scenario(_login_scenario(), target=base_url2)
    assert result.status == "pass"


def test_external_target_rejected_without_allow_external():
    scenario = _login_scenario()
    result = run_scenario(scenario, target="https://example.com")
    assert result.status == "not_assessed"
    assert "external" in result.not_assessed_reason or "allow-external" in result.not_assessed_reason
    assert result.steps == []  # rejected before any browser launched
