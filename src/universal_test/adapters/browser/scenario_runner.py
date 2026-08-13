"""ScenarioRunner: sequential execution of a `WebScenario`'s steps
(Phase 11 spec §21-§26).

Reuses the existing Browser Adapter executor + Core `AssertionEngine`/
`TestEngine` directly -- no second test engine, no second Playwright
execution path (spec §3). Each step is synthesized into a minimal
`TestCase` (one action OR one assertion, never both) and run via
`TestEngine.run(test_case, executor)`, sharing the SAME live page across
the whole scenario -- one browser context per run, matching the existing
"no concurrency" design (spec §9/§27 of the Phase 9 spec, unchanged here).

A step that does not PASS stops the scenario: subsequent steps are
recorded SKIPPED, never executed (spec §21). The scenario-level timeout
cascades into each step via `executor.py`'s `test_timeout_seconds_override`
escape hatch -- the same hard-ceiling mechanism Phase 9 Hardening built,
reused rather than reimplemented (spec §20).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from universal_test.adapters.browser.assertions import build_browser_assertion_engine
from universal_test.adapters.browser.errors import BrowserTargetError, BrowserUnavailableError
from universal_test.adapters.browser.executor import browser_session
from universal_test.adapters.browser.models import BrowserStep
from universal_test.adapters.browser.scenario_loader import MAX_SCENARIO_TIMEOUT_SECONDS
from universal_test.adapters.browser.scenario_models import ASSERT_ACTION_MAP, ScenarioStep, WebScenario, normalize_action
from universal_test.core.engine.test_engine import TestEngine
from universal_test.core.models.enums import ResultStatus
from universal_test.core.models.test_spec import AssertionSpec, TestCase, TestTarget

DEFAULT_SCENARIO_TIMEOUT_SECONDS = 120.0
_MIN_STEP_TIMEOUT_SECONDS = 0.05


@dataclass
class StepResult:
    step_id: str
    action: str
    status: str  # "passed" | "failed" | "error" | "skipped"
    message: str
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id, "action": self.action, "status": self.status,
            "message": self.message, "duration_seconds": round(self.duration_seconds, 3),
        }


@dataclass
class ScenarioResult:
    scenario_id: str
    scenario_name: str
    status: str  # "pass" | "fail" | "error" | "not_assessed"
    target: str | None
    duration_seconds: float = 0.0
    steps: list[StepResult] = field(default_factory=list)
    not_assessed_reason: str | None = None

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def passed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "passed")

    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "failed")

    @property
    def error_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "error")

    @property
    def skipped_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "skipped")

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "status": self.status,
            "target": self.target,
            "duration_seconds": round(self.duration_seconds, 3),
            "step_count": self.step_count,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "error_steps": self.error_steps,
            "skipped_steps": self.skipped_steps,
            "steps": [s.to_dict() for s in self.steps],
            "not_assessed_reason": self.not_assessed_reason,
        }


def missing_environment_variables(scenario: WebScenario) -> list[str]:
    """Referenced-but-unset `value_env` names -- checked once, before any
    browser launches, so a missing secret is a clear pre-flight message
    rather than a confusing mid-scenario failure (spec §13)."""
    names = {s.value_env for s in scenario.steps if s.value_env}
    return sorted(name for name in names if name not in os.environ)


def _build_step_test_case(step: ScenarioStep, resolved_value: str | None) -> TestCase:
    canonical = normalize_action(step.action)
    if step.is_assertion:
        assertion_type = ASSERT_ACTION_MAP[canonical]
        params: dict[str, Any] = {}
        if step.selector is not None:
            params["selector"] = step.selector.to_dict()
        if canonical in ("assert_text", "assert_text_equals"):
            params["value"] = resolved_value if resolved_value is not None else (step.value or "")
        elif canonical == "assert_value":
            params["equals"] = resolved_value if resolved_value is not None else (step.value or "")
        elif canonical == "assert_url":
            params["value"] = step.value or ""
        elif canonical == "assert_url_equals":
            params["equals"] = step.value or ""
        elif canonical == "assert_title":
            if step.value:
                params["equals"] = step.value
        elif canonical == "assert_attribute":
            params["name"] = step.attribute
            params["equals"] = resolved_value if resolved_value is not None else (step.value or "")
        elif canonical == "assert_count":
            if step.count_equals is not None:
                params["equals"] = step.count_equals
            if step.count_min is not None:
                params["min"] = step.count_min
            if step.count_max is not None:
                params["max"] = step.count_max
        return TestCase(
            id=step.id, name=step.id, type="browser_scenario_step",
            target=TestTarget(adapter="browser", extra={"steps": []}),
            assertions=[AssertionSpec(assertion_type, params)],
        )

    nav_value = step.url if canonical == "navigate" and step.url is not None else step.value
    fill_value = resolved_value if resolved_value is not None else nav_value
    browser_step = BrowserStep(action=canonical, selector=step.selector, value=fill_value)
    return TestCase(
        id=step.id, name=step.id, type="browser_scenario_step",
        target=TestTarget(adapter="browser", extra={"steps": [browser_step.to_dict()]}),
        assertions=[],
    )


def _failure_message(result) -> str:
    failing = [a.message for a in result.assertion_results if not a.passed]
    return "; ".join(failing) if failing else result.message


def _overall_status(steps: list[StepResult]) -> str:
    # ERROR (infrastructure) > FAIL (assertion) > PASS -- same "worst signal
    # wins" priority `assessment/rules.py::compute_overall_status` already
    # uses, so scenario status composes with the rest of the tool's
    # semantics rather than inventing a new ladder.
    if any(s.status == "error" for s in steps):
        return "error"
    if any(s.status == "failed" for s in steps):
        return "fail"
    return "pass"


def run_scenario(
    scenario: WebScenario,
    *,
    target: str,
    browser: str = "chromium",
    headless: bool = True,
    navigation_timeout_seconds: float = 15.0,
    action_timeout_seconds: float = 10.0,
    allow_external: bool = False,
    screenshot_dir: str | Path | None = None,
) -> ScenarioResult:
    """Executes `scenario`'s steps sequentially against `target`. Never
    resolves `value_env` values, launches a browser, or sends any traffic
    until every safety/config precondition already holds (target validated
    inside `browser_session()`; missing secrets checked here, first).
    """
    scenario_timeout = scenario.timeout_seconds or DEFAULT_SCENARIO_TIMEOUT_SECONDS
    scenario_timeout = max(1.0, min(scenario_timeout, MAX_SCENARIO_TIMEOUT_SECONDS))

    missing_vars = missing_environment_variables(scenario)
    if missing_vars:
        return ScenarioResult(
            scenario_id=scenario.id, scenario_name=scenario.name, status="not_assessed", target=target,
            not_assessed_reason=f"missing required environment variable(s): {', '.join(missing_vars)}",
        )

    engine = build_browser_assertion_engine()
    test_engine = TestEngine(assertion_engine=engine)

    started = time.monotonic()
    scenario_deadline = started + scenario_timeout
    step_results: list[StepResult] = []
    stopped = False

    try:
        with browser_session(
            target, browser_name=browser, headless=headless,
            navigation_timeout_seconds=navigation_timeout_seconds, action_timeout_seconds=action_timeout_seconds,
            test_timeout_seconds=scenario_timeout, allow_external=allow_external, screenshot_dir=screenshot_dir,
        ) as (executor, _screenshots):
            for step in scenario.steps:
                if stopped:
                    step_results.append(StepResult(
                        step.id, step.action, "skipped", "not executed: a prior step did not pass",
                    ))
                    continue

                remaining = scenario_deadline - time.monotonic()
                if remaining <= 0:
                    step_results.append(StepResult(
                        step.id, step.action, "error", "scenario exceeded its configured timeout",
                    ))
                    stopped = True
                    continue

                resolved_value = os.environ[step.value_env] if step.value_env else None
                test_case = _build_step_test_case(step, resolved_value)
                per_step_cap = step.timeout_seconds or action_timeout_seconds
                test_case.target.extra["test_timeout_seconds_override"] = max(
                    _MIN_STEP_TIMEOUT_SECONDS, min(per_step_cap, remaining),
                )

                step_started = time.monotonic()
                result = test_engine.run(test_case, executor)
                duration = time.monotonic() - step_started

                if result.status == ResultStatus.FAILED:
                    step_results.append(StepResult(step.id, step.action, "failed", _failure_message(result), duration))
                    stopped = True
                elif result.status == ResultStatus.ERROR:
                    step_results.append(StepResult(step.id, step.action, "error", result.message, duration))
                    stopped = True
                elif result.status == ResultStatus.PASSED:
                    step_results.append(StepResult(step.id, step.action, "passed", result.message, duration))
                else:
                    # UNKNOWN: only reachable for a pure action step (no assertions attached) that
                    # the executor ran without raising -- the action itself succeeded (spec §22's
                    # "Click Login / PASS" case). An assertion step always carries exactly one
                    # assertion, so it can never land here.
                    step_results.append(StepResult(step.id, step.action, "passed", "action executed", duration))
    except BrowserUnavailableError as exc:
        return ScenarioResult(
            scenario_id=scenario.id, scenario_name=scenario.name, status="not_assessed", target=target,
            not_assessed_reason=str(exc),
        )
    except BrowserTargetError as exc:
        # Invalid/disallowed target (spec section 15-17): never executed, never a
        # crash -- the same "no_target_reason -> NOT_ASSESSED" pattern
        # `adapters/browser/adapter.py::run()` already established for the
        # single-TestCase smoke test.
        return ScenarioResult(
            scenario_id=scenario.id, scenario_name=scenario.name, status="not_assessed", target=target,
            not_assessed_reason=str(exc),
        )

    duration_seconds = time.monotonic() - started
    return ScenarioResult(
        scenario_id=scenario.id, scenario_name=scenario.name, status=_overall_status(step_results),
        target=target, duration_seconds=duration_seconds, steps=step_results,
    )


_ACTION_DESCRIPTIONS = {
    "navigate": lambda s: f"Navigate to {s.url or s.value or '(target)'}",
    "click": lambda s: f"Click {_selector_label(s)}",
    "fill": lambda s: f"Fill {_selector_label(s)}",
    "select": lambda s: f"Select option on {_selector_label(s)}",
    "check": lambda s: f"Check {_selector_label(s)}",
    "uncheck": lambda s: f"Uncheck {_selector_label(s)}",
    "press": lambda s: f"Press {s.value or '?'} on {_selector_label(s)}",
    "wait_for": lambda s: f"Wait for {_selector_label(s) if s.selector else (s.value or 'load')}",
}


def _selector_label(step: ScenarioStep) -> str:
    if step.selector is None:
        return "(no selector)"
    sel = step.selector
    if sel.type == "role":
        return f"role={sel.role} name={sel.value!r}"
    return f"{sel.type}={sel.value!r}"


def describe_step(step: ScenarioStep) -> str:
    """Human-readable, secret-safe one-line description of a step, for
    dry-run/plan display (spec §14) -- never resolves `value_env`."""
    canonical = normalize_action(step.action)
    if canonical in ASSERT_ACTION_MAP:
        target_desc = _selector_label(step) if step.requires_selector() else (step.value or "")
        return f"Assert {ASSERT_ACTION_MAP[canonical]}: {target_desc}"
    builder = _ACTION_DESCRIPTIONS.get(canonical)
    if builder:
        return builder(step)
    return canonical
