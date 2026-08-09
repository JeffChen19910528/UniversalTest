"""Output rendering for `universal-test test` (dry-run + executed runs).

Analogous to `discovery.serializers` — these are REST-adapter-specific,
lightweight renderers; the general Phase 5 report generators are a separate,
later concern (see ARCHITECTURE.md).
"""

from __future__ import annotations

import json

from universal_test.core.models.enums import ResultStatus
from universal_test.adapters.rest.adapter import RestRunResult
from universal_test.core.models.test_spec import TestCase


def _expected_status_text(test_case: TestCase) -> str:
    for assertion in test_case.assertions:
        if assertion.type == "status_code":
            return str(assertion.params.get("equals"))
        if assertion.type == "status_code_in":
            return ", ".join(str(v) for v in assertion.params.get("values", []))
    control = test_case.request.get("_control", {})
    if not control.get("execute", True):
        return f"N/A ({control.get('result_status', 'skipped').upper()} - {control.get('reason', 'no reason given')})"
    return "N/A (no assertions)"


def dry_run_to_text(result: RestRunResult) -> str:
    lines = [
        f"Discovered: {len(result.specification.endpoints)} endpoints",
        f"Generated: {len(result.test_cases)} test cases",
        "",
    ]
    for tc in result.test_cases:
        lines.append(tc.id)
        lines.append(tc.name)
        lines.append(f"Expected: {_expected_status_text(tc)}")
        lines.append("")

    if result.specification.warnings:
        lines.append("Warnings")
        lines.append("-" * 8)
        for w in result.specification.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("No HTTP requests executed.")
    return "\n".join(lines)


def dry_run_to_json(result: RestRunResult) -> str:
    return json.dumps({
        "discovered_endpoints": len(result.specification.endpoints),
        "generated_test_cases": len(result.test_cases),
        "test_cases": [
            {"id": tc.id, "name": tc.name, "expected": _expected_status_text(tc)}
            for tc in result.test_cases
        ],
        "warnings": result.specification.warnings,
        "executed": False,
    }, indent=2)


def dry_run_to_markdown(result: RestRunResult) -> str:
    lines = [
        f"# Dry Run: {result.specification.title or result.specification.source_file}",
        "",
        f"- Discovered: {len(result.specification.endpoints)} endpoints",
        f"- Generated: {len(result.test_cases)} test cases",
        "",
        "| ID | Test | Expected |",
        "|---|---|---|",
    ]
    for tc in result.test_cases:
        lines.append(f"| {tc.id} | {tc.name} | {_expected_status_text(tc)} |")
    lines.append("")
    if result.specification.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in result.specification.warnings:
            lines.append(f"- {w}")
        lines.append("")
    lines.append("_No HTTP requests executed._")
    return "\n".join(lines)


def run_to_text(result: RestRunResult) -> str:
    if not result.executed:
        lines = [f"ERROR: {result.no_target_reason}", ""]
        lines.append(
            "The repository was analyzed successfully, but no HTTP requests were executed."
        )
        lines.append("")
        lines.append(f"Discovered: {len(result.specification.endpoints)} endpoints")
        lines.append(f"Generated: {len(result.test_cases)} test cases")
        return "\n".join(lines)

    run_result = result.run_result
    summary = run_result.summary
    lines = [
        f"Target executed. {len(run_result.results)} test cases run.",
        "",
        "Summary",
        "-------",
    ]
    for status in ResultStatus:
        lines.append(f"{status.value.upper()}: {summary.get(status.value, 0)}")
    lines.append("")

    for status in (ResultStatus.FAILED, ResultStatus.ERROR):
        interesting = [r for r in run_result.results if r.status == status]
        if not interesting:
            continue
        lines.append(f"{status.value.upper()} tests")
        lines.append("-" * (len(status.value) + 6))
        for r in interesting:
            lines.append(f"{r.id}: {r.message}")
            for a in r.assertion_results:
                if not a.passed:
                    lines.append(f"  - {a.assertion.type}: {a.message}")
            lines.append("")

    for status in (ResultStatus.SKIPPED, ResultStatus.UNKNOWN):
        interesting = [r for r in run_result.results if r.status == status]
        if not interesting:
            continue
        lines.append(f"{status.value.upper()} tests")
        lines.append("-" * (len(status.value) + 6))
        for r in interesting:
            lines.append(f"{r.id}: {r.message}")
        lines.append("")

    return "\n".join(lines)


def run_to_json(result: RestRunResult) -> str:
    return json.dumps(result.to_dict(), indent=2)


def run_to_markdown(result: RestRunResult) -> str:
    if not result.executed:
        lines = [
            "# Test Run", "",
            f"> ERROR: {result.no_target_reason}", "",
            "The repository was analyzed successfully, but no HTTP requests were executed.", "",
            f"- Discovered: {len(result.specification.endpoints)} endpoints",
            f"- Generated: {len(result.test_cases)} test cases",
        ]
        return "\n".join(lines)

    run_result = result.run_result
    summary = run_result.summary
    lines = ["# Test Run", "", "| Status | Count |", "|---|---|"]
    for status in ResultStatus:
        lines.append(f"| {status.value} | {summary.get(status.value, 0)} |")
    lines.append("")
    lines.append("| ID | Status | Message |")
    lines.append("|---|---|---|")
    for r in run_result.results:
        lines.append(f"| {r.id} | {r.status.value} | {r.message} |")
    return "\n".join(lines)
