"""Deterministic Quality Gate evaluation (Phase 8 brief §1/§2). One
function, `evaluate()`, is the entire policy-application logic — no other
module in this package or in `cli/main.py` re-implements any part of the
fail/warn/pass/error decision. Given the same `ProjectAssessment`/
`RegressionSummary`/`QualityGatePolicy`, always produces the same
`QualityGateResult` (no randomness, no wall-clock dependence beyond
whatever `assessment`/`regression` already captured upstream).
"""

from __future__ import annotations

from universal_test.assessment.models import ProjectAssessment
from universal_test.regression.models import RegressionSummary
from universal_test.quality_gate.models import (
    DEFAULT_POLICY,
    QualityGateFinding,
    QualityGatePolicy,
    QualityGateResult,
    QualityGateStatus,
    exit_code_for,
)
from universal_test.quality_gate.signals import collect_rules


def _build_summary(
    assessment: ProjectAssessment, regression: RegressionSummary | None, findings: list[QualityGateFinding],
) -> dict:
    functional_cat = next((c for c in assessment.categories if c.name == "Functional Health"), None)
    performance_cat = next((c for c in assessment.categories if c.name == "Performance"), None)
    database_cat = next((c for c in assessment.categories if c.name == "Database Health"), None)

    severity_counts: dict[str, int] = {}
    if regression is not None:
        for f in regression.findings:
            severity_counts[f.severity.value] = severity_counts.get(f.severity.value, 0) + 1

    return {
        "overall_assessment_status": assessment.overall_status.value,
        "functional_status": functional_cat.status.value if functional_cat else None,
        "performance_status": performance_cat.status.value if performance_cat else None,
        "database_status": database_cat.status.value if database_cat else None,
        "regression_status": regression.status.value if regression is not None else None,
        "regression_findings_by_severity": severity_counts,
        "fail_count": sum(1 for f in findings if f.level == "fail"),
        "warning_count": sum(1 for f in findings if f.level == "warning"),
    }


def evaluate(
    assessment: ProjectAssessment, regression: RegressionSummary | None, policy: QualityGatePolicy = DEFAULT_POLICY,
) -> QualityGateResult:
    infra_signals, quality_signals = collect_rules(assessment, regression)

    # An infra signal (total transport wipeout) short-circuits to ERROR/exit 3
    # UNLESS the policy explicitly opts that exact (category, value) into
    # fail_on/warn_on -- brief §18: "除非 user explicitly configures otherwise".
    unresolved_infra = []
    for signal in infra_signals:
        if policy.classify(signal.category, signal.value) is None:
            unresolved_infra.append(signal)
        else:
            quality_signals.append(signal)

    findings: list[QualityGateFinding] = []
    for signal in quality_signals:
        level = policy.classify(signal.category, signal.value)
        if level is not None:
            findings.append(QualityGateFinding(
                rule=f"{signal.category}.{signal.value}", level=level, id=signal.id,
                title=signal.title, description=signal.description,
            ))

    summary = _build_summary(assessment, regression, findings)

    if unresolved_infra:
        reason = "; ".join(f"{s.title}" for s in unresolved_infra)
        result = QualityGateResult(
            status=QualityGateStatus.ERROR, exit_code=int(exit_code_for(QualityGateStatus.ERROR)),
            findings=findings, summary=summary, reason=reason,
        )
        return result

    if any(f.level == "fail" for f in findings):
        status = QualityGateStatus.FAIL
    elif any(f.level == "warning" for f in findings):
        status = QualityGateStatus.WARNING
    else:
        status = QualityGateStatus.PASS

    return QualityGateResult(status=status, exit_code=int(exit_code_for(status)), findings=findings, summary=summary)
