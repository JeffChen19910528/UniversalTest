"""Output rendering for `universal-test browser test` (spec §32).

Mirrors `adapters/rest/serializers.py`'s shape: lightweight, adapter-specific
renderers for the standalone command; the shared `assess` report sections
live in `reporting/` instead.
"""

from __future__ import annotations

import json

from universal_test.adapters.browser.models import BrowserRunResult
from universal_test.core.models.enums import ResultStatus


def plan_to_text(result: BrowserRunResult, *, allow_external: bool) -> str:
    lines = [
        f"Target: {result.target or '(none)'}",
        f"Browser: {result.browser}",
        f"Safety: external navigation {'ALLOWED' if allow_external else 'blocked (localhost/127.0.0.1/::1/file:// only)'}",
        "No credentials will be guessed.",
        "",
        f"Test plan: {len(result.test_cases)} test case(s)",
        "",
    ]
    for tc in result.test_cases:
        steps = tc.target.extra.get("steps", [])
        lines.append(f"{tc.id}: {tc.name}")
        for step in steps:
            lines.append(f"  - {step.get('action')} {step.get('selector', {}).get('value', '')}".rstrip())
        for assertion in tc.assertions:
            lines.append(f"  assert {assertion.type} {assertion.params}")
        lines.append("")
    return "\n".join(lines)


def dry_run_to_text(result: BrowserRunResult, *, allow_external: bool = False) -> str:
    return plan_to_text(result, allow_external=allow_external) + "\nNo browser was launched (dry run)."


def dry_run_to_json(result: BrowserRunResult) -> str:
    return json.dumps(result.to_dict(), indent=2)


def run_to_text(result: BrowserRunResult) -> str:
    if not result.executed:
        reason = result.not_assessed_reason or result.no_target_reason or "not executed"
        return f"NOT ASSESSED: {reason}"

    run_result = result.run_result
    summary = run_result.summary
    lines = [f"Target: {result.target}", f"Browser: {result.browser}", "", "Summary", "-------"]
    for status in ResultStatus:
        lines.append(f"{status.value.upper()}: {summary.get(status.value, 0)}")
    lines.append("")
    for r in run_result.results:
        lines.append(f"{r.id}: {r.status.value.upper()} - {r.message}")
        for a in r.assertion_results:
            marker = "PASS" if a.passed else "FAIL"
            lines.append(f"  [{marker}] {a.assertion.type}: {a.message}")
    if result.screenshots:
        lines.append("")
        lines.append("Screenshots:")
        for path in result.screenshots:
            lines.append(f"  - {path}")
    return "\n".join(lines)


def run_to_json(result: BrowserRunResult) -> str:
    return json.dumps(result.to_dict(), indent=2)


def run_to_markdown(result: BrowserRunResult) -> str:
    if not result.executed:
        reason = result.not_assessed_reason or result.no_target_reason or "not executed"
        return f"# Browser Test Run\n\n> NOT ASSESSED: {reason}\n"

    run_result = result.run_result
    summary = run_result.summary
    lines = ["# Browser Test Run", "", f"- Target: {result.target}", f"- Browser: {result.browser}", "",
              "| Status | Count |", "|---|---|"]
    for status in ResultStatus:
        lines.append(f"| {status.value} | {summary.get(status.value, 0)} |")
    lines.append("")
    lines.append("| ID | Status | Message |")
    lines.append("|---|---|---|")
    for r in run_result.results:
        lines.append(f"| {r.id} | {r.status.value} | {r.message} |")
    return "\n".join(lines)
