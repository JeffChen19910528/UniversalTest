"""Human-readable CI summary + machine-readable JSON for the Quality Gate
(Phase 8 brief §10/§11). Never includes a secret — `QualityGateResult` only
ever carries status strings, finding titles/descriptions sourced from
`AssessmentCategory`/`RegressionFinding` text, and counts; no request/
response body or credential value is reachable from here at all.
"""

from __future__ import annotations

import json

from universal_test.quality_gate.models import QualityGateResult


def result_to_json(result: QualityGateResult) -> str:
    return json.dumps(result.to_dict(), indent=2)


def result_to_text(result: QualityGateResult) -> str:
    lines = ["Universal Test Quality Gate", "=" * 27, ""]

    s = result.summary
    lines.append(f"Functional:   {(s.get('functional_status') or 'not_assessed').upper()}")
    lines.append(f"Performance:  {(s.get('performance_status') or 'not_assessed').upper()}")
    lines.append(f"Database:     {(s.get('database_status') or 'not_assessed').upper()}")
    lines.append(f"Regression:   {(s.get('regression_status') or 'not_assessed').upper()}")
    lines.append("")

    severity_counts = s.get("regression_findings_by_severity") or {}
    if severity_counts:
        lines.append("Regression findings by severity:")
        for severity in ("critical", "high", "medium", "low", "info"):
            if severity in severity_counts:
                lines.append(f"  {severity.upper()}: {severity_counts[severity]}")
        lines.append("")

    if result.findings:
        lines.append("Findings:")
        for f in result.findings:
            lines.append(f"  [{f.level.upper()}] {f.rule}: {f.title}")
        lines.append("")

    if result.reason:
        lines.append(f"Reason: {result.reason}")
        lines.append("")

    lines.append("Quality Gate:")
    lines.append(f"  {result.status.value.upper()}")
    lines.append("")
    lines.append("Exit code:")
    lines.append(f"  {result.exit_code}")

    return "\n".join(lines)
