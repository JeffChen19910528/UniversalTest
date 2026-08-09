"""Assessment-category regression: compares each Phase 5 category's status
between baseline and current, matched by name (brief §13). Underlying
evidence stays available separately — the current run's own `report.json`
already carries the full `ProjectAssessment`; this comparison only tracks
the *transition*, per the brief's explicit "但不要只依 overall status" —
category-level, not just the single overall status string.

Severity ladder (brief §14, applied literally):
    PASS -> WARNING : MEDIUM
    PASS -> FAIL     : HIGH
    WARNING -> FAIL   : HIGH
Any transition involving UNKNOWN/NOT_ASSESSED on either side is treated as
"not enough data to call it a regression" (brief §5), not scored.
"""

from __future__ import annotations

from universal_test.core.models.enums import Severity
from universal_test.core.models.evidence import Evidence
from universal_test.regression.models import (
    AssessmentSnapshot,
    ChangeType,
    RegressionCategory,
    RegressionFinding,
)
from universal_test.regression.rules import status_from_findings

_INDETERMINATE = {"unknown", "not_assessed"}

# (baseline_status, current_status) -> severity, for the specific worsening transitions the brief names
_REGRESSION_SEVERITY = {
    ("pass", "warning"): Severity.MEDIUM,
    ("pass", "fail"): Severity.HIGH,
    ("warning", "fail"): Severity.HIGH,
}
_IMPROVEMENT_PAIRS = {("warning", "pass"), ("fail", "pass"), ("fail", "warning")}


def compare_assessment(baseline: AssessmentSnapshot, current: AssessmentSnapshot) -> RegressionCategory:
    b_by_name = {c.name: c.status for c in baseline.categories}
    c_by_name = {c.name: c.status for c in current.categories}
    common = sorted(set(b_by_name) & set(c_by_name))

    findings: list[RegressionFinding] = []
    for name in common:
        b_status, c_status = b_by_name[name], c_by_name[name]
        if b_status == c_status:
            continue
        if b_status in _INDETERMINATE or c_status in _INDETERMINATE:
            continue  # missing/undecided data is not a regression (brief §5)
        if (b_status, c_status) in _IMPROVEMENT_PAIRS:
            continue
        severity = _REGRESSION_SEVERITY.get((b_status, c_status))
        if severity is None:
            continue  # a transition the brief didn't name a severity for (e.g. pass<->pass duplicates) — no finding
        findings.append(RegressionFinding(
            id=f"ASSESS-{name.replace(' ', '_').upper()}", category="Assessment", change=ChangeType.REGRESSED,
            severity=severity, confidence=1.0,
            title=f"{name}: {b_status.upper()} -> {c_status.upper()}",
            description=f"Assessment category '{name}' changed from {b_status} to {c_status} since the baseline.",
            evidence=[Evidence("assessment_category", {"category": name, "baseline": b_status, "current": c_status})],
            recommendation=f"Review the '{name}' category's findings in the current report for the underlying cause.",
        ))

    status = status_from_findings(findings)
    summary = f"{len(common)} categor{'y' if len(common) == 1 else 'ies'} compared, {len(findings)} finding(s) raised"
    return RegressionCategory(name="Assessment", status=status, summary=summary, findings=findings)
