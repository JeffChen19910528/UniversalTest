"""Rendering for the standalone `universal-test baseline compare` command.
Same lightweight convention as every other phase's own serializers
(`discovery/serializers.py`, `adapters/rest/serializers.py`,
`adapters/database/serializers.py`) — the unified Phase 5 report's
Regression section (`reporting/markdown_report.py`/`html_report.py`) reuses
the same `RegressionSummary` model but renders inline as part of that
larger document instead of calling these functions directly.
"""

from __future__ import annotations

import json

from universal_test.regression.models import RegressionSummary


def result_to_text(summary: RegressionSummary) -> str:
    lines = [
        "Regression Comparison", "=" * 22, "",
        f"Status: {summary.status.value.upper()}", "",
        f"Baseline: {summary.baseline_meta['generated_at']} (tool {summary.baseline_meta['tool_version']})",
        f"Current:  {summary.current_meta['generated_at']} (tool {summary.current_meta['tool_version']})",
        "",
    ]
    for category in summary.categories:
        lines.append(f"{category.name}")
        lines.append("-" * len(category.name))
        lines.append(f"Status: {category.status.value.upper()} - {category.summary}")
        if category.reason:
            lines.append(f"Reason: {category.reason}")
        for finding in category.findings:
            lines.append(f"  [{finding.severity.value.upper()}] {finding.title}")
        lines.append("")
    if summary.warnings:
        lines.append("Warnings")
        lines.append("-" * 8)
        for w in summary.warnings:
            lines.append(f"- {w}")
        lines.append("")
    return "\n".join(lines)


def result_to_json(summary: RegressionSummary) -> str:
    return json.dumps(summary.to_dict(), indent=2)


def result_to_markdown(summary: RegressionSummary) -> str:
    lines = ["# Regression Comparison", "", f"**Status: {summary.status.value.upper()}**", ""]
    lines.append(f"- Baseline: {summary.baseline_meta['generated_at']} (tool {summary.baseline_meta['tool_version']})")
    lines.append(f"- Current: {summary.current_meta['generated_at']} (tool {summary.current_meta['tool_version']})")
    lines.append("")
    for category in summary.categories:
        lines.append(f"## {category.name}")
        lines.append("")
        lines.append(f"**Status: {category.status.value.upper()}** - {category.summary}")
        if category.reason:
            lines.append(f"\n> Reason: {category.reason}")
        lines.append("")
        for finding in category.findings:
            lines.append(f"- [{finding.severity.value.upper()}] {finding.title}")
        lines.append("")
    if summary.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in summary.warnings:
            lines.append(f"- {w}")
        lines.append("")
    return "\n".join(lines)
