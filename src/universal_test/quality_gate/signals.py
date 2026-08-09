"""Collects raw `QualityGateRule` signals from an already-built
`ProjectAssessment`/`RegressionSummary` — never re-discovers, re-executes,
or re-compares anything (same "aggregate, don't recompute" contract every
prior phase's engine module follows). Collection (what happened) is
deliberately kept separate from classification (does policy care, in
`engine.py`) so each half is independently testable.
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus
from universal_test.assessment.models import AssessmentCategory, ProjectAssessment
from universal_test.regression.models import RegressionSummary
from universal_test.quality_gate.models import QualityGateRule


def _find_category(categories: list[AssessmentCategory], name: str) -> AssessmentCategory | None:
    return next((c for c in categories if c.name == name), None)


def _find_regression_category(regression: RegressionSummary, name: str):
    return next((c for c in regression.categories if c.name == name), None)


def collect_rules(
    assessment: ProjectAssessment, regression: RegressionSummary | None,
) -> tuple[list[QualityGateRule], list[QualityGateRule]]:
    """Returns `(infra_signals, quality_signals)`.

    `infra_signals` are total-transport-wipeout conditions (brief §18: "Target
    unavailable 應該是 execution/infrastructure error，而不是 Quality
    regression") — `Functional Health`/`Performance` reaching `FAIL` means
    every attempted request failed at the transport layer
    (`assessment/rules.py::execution_health_status()`'s own definition of
    `FAIL`), not that some check failed. `quality_signals` are everything
    else: real assertion/threshold/regression/database/discovery findings.
    """
    infra: list[QualityGateRule] = []
    quality: list[QualityGateRule] = []

    functional_cat = _find_category(assessment.categories, "Functional Health")
    if functional_cat is not None:
        if functional_cat.status == AssessmentStatus.FAIL:
            infra.append(QualityGateRule(
                category="functional", value="unreachable", id=None,
                title="Functional test target was unreachable",
                description=functional_cat.summary, is_infra_signal=True,
            ))
        elif functional_cat.status == AssessmentStatus.WARNING:
            quality.append(QualityGateRule(
                category="functional", value="failure", id=None,
                title="Functional test failure(s) detected", description=functional_cat.summary,
            ))

    performance_cat = _find_category(assessment.categories, "Performance")
    if performance_cat is not None:
        if performance_cat.status == AssessmentStatus.FAIL:
            infra.append(QualityGateRule(
                category="performance", value="unreachable", id=None,
                title="Performance test target was unreachable",
                description=performance_cat.summary, is_infra_signal=True,
            ))
        elif performance_cat.status == AssessmentStatus.WARNING:
            quality.append(QualityGateRule(
                category="performance", value="threshold", id=None,
                title="Performance threshold breach or partial failure detected",
                description=performance_cat.summary,
            ))

    database_cat = _find_category(assessment.categories, "Database Health")
    if database_cat is not None and database_cat.status == AssessmentStatus.NOT_ASSESSED:
        quality.append(QualityGateRule(
            category="database", value="not_assessed", id=None,
            title="Database was not assessed", description=database_cat.reason or database_cat.summary,
        ))

    if regression is not None:
        for finding in regression.findings:
            quality.append(QualityGateRule(
                category="regression", value=finding.severity.value, id=finding.id,
                title=finding.title, description=finding.description,
            ))

        db_regression_cat = _find_regression_category(regression, "Database")
        if db_regression_cat is not None and db_regression_cat.findings:
            quality.append(QualityGateRule(
                category="database", value="schema_change", id=None,
                title=f"{len(db_regression_cat.findings)} database schema change(s) detected since the baseline",
                description=db_regression_cat.summary,
            ))

        discovery_regression_cat = _find_regression_category(regression, "Discovery")
        if discovery_regression_cat is not None and discovery_regression_cat.findings:
            quality.append(QualityGateRule(
                category="discovery", value="change", id=None,
                title=f"{len(discovery_regression_cat.findings)} discovery change(s) detected since the baseline",
                description=discovery_regression_cat.summary,
            ))

    quality.append(QualityGateRule(
        category="assessment", value=assessment.overall_status.value, id=None,
        title=f"Overall assessment status: {assessment.overall_status.value}",
        description=f"{len(assessment.categories)} categor{'y' if len(assessment.categories) == 1 else 'ies'} assessed",
    ))

    return infra, quality
