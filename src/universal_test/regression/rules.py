"""Deterministic severity-to-status rule shared by every comparator
(Phase 7 brief §14) — one place, not reinvented per category, mirroring how
`assessment/rules.py::compute_overall_status()` is the single source of
truth for the Phase 5 rollup.

    CRITICAL/HIGH present -> FAIL
    MEDIUM/LOW present    -> WARNING
    otherwise             -> PASS

No magic numbers, no weighting/scoring (brief §15: no numeric quality
score) — a category's status is a direct function of the worst finding
severity it produced.
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.regression.models import RegressionFinding


def status_from_findings(findings: list[RegressionFinding]) -> AssessmentStatus:
    severities = {f.severity for f in findings}
    if Severity.CRITICAL in severities or Severity.HIGH in severities:
        return AssessmentStatus.FAIL
    if Severity.MEDIUM in severities or Severity.LOW in severities:
        return AssessmentStatus.WARNING
    return AssessmentStatus.PASS
