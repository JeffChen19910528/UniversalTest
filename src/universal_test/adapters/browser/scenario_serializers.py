"""Output rendering for `universal-test browser scenario` (list/validate/
run/dry-run) -- mirrors `adapters/browser/serializers.py`'s shape: a
lightweight, adapter-specific renderer for the standalone command, never a
second reporting system.
"""

from __future__ import annotations

import json

from universal_test.adapters.browser.scenario_loader import ValidationIssue
from universal_test.adapters.browser.scenario_models import ScenarioCollection, WebScenario
from universal_test.adapters.browser.scenario_runner import ScenarioResult, describe_step


def list_to_text(collection: ScenarioCollection) -> str:
    if not collection.scenarios:
        return f"No scenarios found in {collection.source_path}"
    lines = [f"Available scenarios ({collection.source_path}):", ""]
    for scenario in collection.scenarios:
        lines.append(f"  {scenario.id:<24} {scenario.name}")
        if scenario.description:
            lines.append(f"  {'':<24} {scenario.description}")
    return "\n".join(lines)


def list_to_json(collection: ScenarioCollection) -> str:
    return json.dumps({
        "source": collection.source_path,
        "scenarios": [{"id": s.id, "name": s.name, "description": s.description} for s in collection.scenarios],
    }, indent=2)


def validation_to_text(issues: list[ValidationIssue]) -> str:
    if not issues:
        return "No validation issues found."
    lines = [f"{len(issues)} validation issue(s) found:", ""]
    lines += [f"  - {issue}" for issue in issues]
    return "\n".join(lines)


def plan_to_text(scenario: WebScenario, *, target: str | None, allow_external: bool = False) -> str:
    lines = [
        f"Scenario: {scenario.name}",
        f"ID: {scenario.id}",
    ]
    if scenario.description:
        lines.append(f"Description: {scenario.description}")
    lines += [
        f"Target: {target or scenario.target or '(none provided)'}",
        f"Safety: external navigation {'ALLOWED' if allow_external else 'blocked (localhost/127.0.0.1/::1/file:// only)'}",
        "No credentials will be guessed; value_env references are never resolved during dry-run.",
        "",
        "Steps:",
    ]
    for i, step in enumerate(scenario.steps, start=1):
        lines.append(f"  {i}. {describe_step(step)}")
    lines.append("")
    lines.append("No browser was launched; no HTTP requests were sent (dry run).")
    return "\n".join(lines)


def result_to_text(result: ScenarioResult) -> str:
    if result.status == "not_assessed":
        return f"NOT ASSESSED: {result.not_assessed_reason}"
    lines = [
        f"Scenario: {result.scenario_name} ({result.scenario_id})",
        f"Target: {result.target}",
        f"Status: {result.status.upper()}",
        f"Duration: {result.duration_seconds:.2f}s",
        "",
        f"{result.passed_steps} passed, {result.failed_steps} failed, "
        f"{result.error_steps} error, {result.skipped_steps} skipped, {result.step_count} total",
        "",
    ]
    for step in result.steps:
        marker = {"passed": "PASS", "failed": "FAIL", "error": "ERROR", "skipped": "SKIP"}[step.status]
        lines.append(f"  [{marker}] {step.step_id} ({step.action}) - {step.message}")
    return "\n".join(lines)


def result_to_json(result: ScenarioResult) -> str:
    return json.dumps(result.to_dict(), indent=2)


def result_to_markdown(result: ScenarioResult) -> str:
    if result.status == "not_assessed":
        return f"# Scenario Run\n\n> NOT ASSESSED: {result.not_assessed_reason}\n"
    lines = [
        f"# Scenario Run: {result.scenario_name}",
        "",
        f"- ID: `{result.scenario_id}`",
        f"- Target: `{result.target}`",
        f"- Status: **{result.status.upper()}**",
        f"- Duration: {result.duration_seconds:.2f}s",
        "",
        "| Step | Action | Status | Message |",
        "|---|---|---|---|",
    ]
    for step in result.steps:
        lines.append(f"| {step.step_id} | {step.action} | {step.status} | {step.message} |")
    return "\n".join(lines)
