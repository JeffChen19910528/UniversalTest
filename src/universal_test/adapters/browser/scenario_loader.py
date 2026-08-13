"""Scenario file loading + validation (Phase 11 spec §12-§13).

YAML (PyYAML, already a base dependency) since the project's own
`universal-test.yaml` configuration already uses it -- no second config
format/parser. Scenarios live in a dedicated file (default
`universal-test-web.yaml`) rather than being forced into the main
`universal-test.yaml`, per spec §12's own guidance, since a project may
define many scenarios and that would make the main config unwieldy.

Validation is a pure function over already-loaded, in-memory data --
it never touches the network or launches a browser (spec §13: "Configuration
errors must NOT result in browser execution").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from universal_test.adapters.browser.models import ALLOWED_SELECTOR_TYPES
from universal_test.adapters.browser.scenario_models import (
    ALL_ACTIONS,
    ScenarioCollection,
    ScenarioStep,
    WebScenario,
    normalize_action,
)
from universal_test.core.errors import ConfigurationError

DEFAULT_SCENARIO_FILENAME = "universal-test-web.yaml"

_ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ACTIONS_REQUIRING_URL = frozenset({"navigate"})
_ACTIONS_REQUIRING_VALUE = frozenset({"fill", "select", "press"})
_SELECTOR_ACTIONS = frozenset({"click", "fill", "select", "check", "uncheck"})
MAX_SCENARIO_TIMEOUT_SECONDS = 1800.0  # hard ceiling regardless of what a scenario file requests
_MIN_SCENARIO_TIMEOUT_SECONDS = 1.0


def resolve_scenario_path(project_path: str | Path, scenario_file: str | Path | None) -> Path:
    if scenario_file:
        return Path(scenario_file)
    return Path(project_path) / DEFAULT_SCENARIO_FILENAME


def load_scenario_file(path: str | Path) -> ScenarioCollection:
    """Loads (but does not validate) all scenarios from one YAML file.
    Raises `ConfigurationError` for a missing file or malformed YAML --
    the same error type/exit-code convention every other config loader in
    this project already uses (never a bespoke exception type).
    """
    resolved = Path(path)
    if not resolved.is_file():
        raise ConfigurationError(f"scenario file not found: {resolved}")
    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {resolved}: {exc}") from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, dict) or not isinstance(raw.get("scenarios", []), list):
        raise ConfigurationError(f"{resolved} must contain a top-level 'scenarios' list")

    scenarios = [WebScenario.from_dict(s) for s in raw.get("scenarios", []) if isinstance(s, dict)]
    return ScenarioCollection(source_path=str(resolved), scenarios=scenarios)


@dataclass(frozen=True)
class ValidationIssue:
    message: str
    scenario_id: str | None = None
    step_id: str | None = None

    def __str__(self) -> str:
        location = ""
        if self.scenario_id:
            location = f"[{self.scenario_id}" + (f".{self.step_id}" if self.step_id else "") + "] "
        return f"{location}{self.message}"


def _validate_timeout(value, *, label: str, cap: float) -> str | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return f"{label} must be a number, got {value!r}"
    if numeric != numeric or numeric in (float("inf"), float("-inf")):  # NaN/inf
        return f"{label} must be a finite number, got {value!r}"
    if numeric < _MIN_SCENARIO_TIMEOUT_SECONDS or numeric > cap:
        return f"{label} must be between {_MIN_SCENARIO_TIMEOUT_SECONDS} and {cap} seconds, got {numeric}"
    return None


def _validate_step(step: ScenarioStep, scenario_id: str, seen_step_ids: set[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not step.id:
        issues.append(ValidationIssue("step is missing a required 'id'", scenario_id))
        return issues
    if step.id in seen_step_ids:
        issues.append(ValidationIssue(f"duplicate step id {step.id!r}", scenario_id, step.id))
    seen_step_ids.add(step.id)

    canonical = normalize_action(step.action)
    if canonical not in ALL_ACTIONS:
        issues.append(ValidationIssue(f"unknown action {step.action!r}", scenario_id, step.id))
        return issues  # further checks assume a known action

    if canonical in _ACTIONS_REQUIRING_URL and not step.url and not step.value:
        issues.append(ValidationIssue("'navigate' requires a 'url'", scenario_id, step.id))

    if canonical in _ACTIONS_REQUIRING_VALUE and step.value is None and step.value_env is None:
        issues.append(ValidationIssue(f"{step.action!r} requires a 'value' or 'value_env'", scenario_id, step.id))

    if step.requires_selector() and step.selector is None:
        issues.append(ValidationIssue(f"{step.action!r} requires a 'selector'", scenario_id, step.id))

    if step.selector is not None:
        if step.selector.type not in ALLOWED_SELECTOR_TYPES:
            issues.append(ValidationIssue(
                f"invalid selector type {step.selector.type!r}; must be one of {sorted(ALLOWED_SELECTOR_TYPES)}",
                scenario_id, step.id,
            ))
        elif step.selector.type == "role" and not step.selector.role:
            issues.append(ValidationIssue("selector type 'role' requires a 'role' value", scenario_id, step.id))

    if canonical == "assert_attribute" and not step.attribute:
        issues.append(ValidationIssue("'assert_attribute' requires an 'attribute' name", scenario_id, step.id))

    if canonical == "assert_count" and step.count_equals is None and step.count_min is None and step.count_max is None:
        issues.append(ValidationIssue(
            "'assert_count' requires at least one of count_equals/count_min/count_max", scenario_id, step.id,
        ))

    if step.value_env is not None and not _ENV_VAR_NAME_PATTERN.match(step.value_env):
        issues.append(ValidationIssue(f"invalid environment-variable reference {step.value_env!r}", scenario_id, step.id))

    timeout_issue = _validate_timeout(step.timeout_seconds, label="step timeout_seconds", cap=MAX_SCENARIO_TIMEOUT_SECONDS)
    if timeout_issue:
        issues.append(ValidationIssue(timeout_issue, scenario_id, step.id))

    return issues


def validate_scenarios(collection: ScenarioCollection) -> list[ValidationIssue]:
    """Pure, offline validation -- never launches a browser (spec §13)."""
    issues: list[ValidationIssue] = []
    seen_scenario_ids: set[str] = set()

    for scenario in collection.scenarios:
        if not scenario.id:
            issues.append(ValidationIssue("scenario is missing a required 'id'"))
            continue
        if scenario.id in seen_scenario_ids:
            issues.append(ValidationIssue(f"duplicate scenario id {scenario.id!r}", scenario.id))
        seen_scenario_ids.add(scenario.id)

        if not scenario.name:
            issues.append(ValidationIssue("scenario is missing a required 'name'", scenario.id))
        if not scenario.steps:
            issues.append(ValidationIssue("scenario has no steps", scenario.id))

        timeout_issue = _validate_timeout(
            scenario.timeout_seconds, label="scenario timeout_seconds", cap=MAX_SCENARIO_TIMEOUT_SECONDS,
        )
        if timeout_issue:
            issues.append(ValidationIssue(timeout_issue, scenario.id))

        seen_step_ids: set[str] = set()
        for step in scenario.steps:
            issues.extend(_validate_step(step, scenario.id, seen_step_ids))

    return issues


def load_and_validate(project_path: str | Path, scenario_file: str | Path | None) -> tuple[ScenarioCollection, list[ValidationIssue]]:
    path = resolve_scenario_path(project_path, scenario_file)
    collection = load_scenario_file(path)
    return collection, validate_scenarios(collection)
