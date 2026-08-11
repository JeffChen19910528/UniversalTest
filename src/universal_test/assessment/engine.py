"""Orchestrates every category assessor into one `ProjectAssessment`
(Phase 5 brief §2). This module only aggregates results Phases 2-4 already
produced — it never re-discovers, re-executes, or re-computes metrics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from universal_test import __version__
from universal_test.core.orchestration.orchestrator import RunResult
from universal_test.discovery.models import ProjectModel
from universal_test.testing.performance.models import PerformanceResult
from universal_test.adapters.database.adapter import DatabaseDiscoveryResult
from universal_test.assessment.configuration_assessment import assess_configuration_hygiene
from universal_test.assessment.database_assessment import assess_database_health, database_testability_signal
from universal_test.assessment.discovery_assessment import (
    assess_build_health,
    assess_project_discovery,
    assess_test_infrastructure,
)
from universal_test.assessment.frontend_assessment import assess_frontend_health
from universal_test.assessment.functional_assessment import assess_functional_health
from universal_test.assessment.models import SCHEMA_VERSION, CoverageItem, ProjectAssessment, UnassessedArea
from universal_test.assessment.performance_assessment import assess_performance
from universal_test.assessment.rules import compute_application_health, compute_overall_status
from universal_test.assessment.testability_assessment import assess_testability

LIMITATIONS = [
    "This is an initial automated assessment, not a security audit.",
    "It does not prove the software is secure.",
    "It does not prove the absence of bugs.",
    "It does not prove business-logic correctness.",
    "It does not prove production readiness.",
    "It does not prove complete test coverage.",
]


def _compute_coverage(
    model: ProjectModel, generated_count: int, run_result: RunResult | None, perf_result: PerformanceResult | None,
    database_result: DatabaseDiscoveryResult | None,
) -> list[CoverageItem]:
    items = [CoverageItem("Discovery", 100.0)]

    api_found = any(a.kind == "openapi" for a in model.apis)
    items.append(CoverageItem(
        "API Discovery", 100.0 if api_found else 0.0,
        reason=None if api_found else "no OpenAPI/Swagger document was found",
    ))

    if run_result is not None:
        executed = sum(run_result.summary.get(k, 0) for k in ("passed", "failed", "error"))
        percent = round((executed / generated_count) * 100, 1) if generated_count else 0.0
        items.append(CoverageItem("Functional Execution", percent))
    else:
        items.append(CoverageItem("Functional Execution", 0.0, reason="no execution target was provided"))

    if perf_result is not None and perf_result.levels:
        items.append(CoverageItem("Performance Execution", 100.0))
    else:
        items.append(CoverageItem("Performance Execution", 0.0, reason="performance execution was not enabled"))

    if database_result is not None and database_result.info is not None:
        items.append(CoverageItem("Database", 100.0))
    elif database_result is not None:
        items.append(CoverageItem("Database", 0.0, reason=database_result.not_assessed_reason))
    else:
        items.append(CoverageItem(
            "Database", 0.0, reason="database credentials/access were not explicitly configured",
        ))

    items.append(CoverageItem("Frontend Discovery", 100.0))
    if model.frontend.detected:
        items.append(CoverageItem(
            "Browser/UI Execution", 0.0,
            reason="browser automation adapter is not enabled in this version",
        ))
    return items


def _compute_unassessed(
    model: ProjectModel, run_result: RunResult | None, perf_result: PerformanceResult | None,
    database_result: DatabaseDiscoveryResult | None,
) -> list[UnassessedArea]:
    areas: list[UnassessedArea] = []

    if database_result is None:
        if model.databases:
            areas.append(UnassessedArea(
                "Database integration",
                "database evidence was detected but no --database-profile was configured",
            ))
    elif database_result.info is None:
        areas.append(UnassessedArea("Database integration", database_result.not_assessed_reason or "database could not be assessed"))
    if run_result is not None and run_result.summary.get("skipped", 0):
        areas.append(UnassessedArea(
            "Authenticated API paths",
            f"{run_result.summary['skipped']} test(s) require authentication credentials that were not supplied",
        ))
    if run_result is None:
        areas.append(UnassessedArea("Functional correctness under load", "no execution target was provided"))
    if perf_result is None:
        areas.append(UnassessedArea("Performance", "performance execution was not enabled (pass --performance)"))
    if model.frontend.detected:
        areas.append(UnassessedArea(
            "Browser/UI Execution", "Browser automation adapter is not enabled in this version.",
        ))
    areas.append(UnassessedArea(
        "Business logic correctness", "no formal business specification is available to validate against",
    ))
    return areas


def build_assessment(
    *,
    project_path: str | Path,
    target: str | None,
    model: ProjectModel,
    generated_count: int,
    run_result: RunResult | None,
    functional_not_run_reason: str | None,
    perf_result: PerformanceResult | None,
    performance_not_run_reason: str | None,
    has_confirmed_openapi: bool,
    database_result: DatabaseDiscoveryResult | None = None,
) -> ProjectAssessment:
    db_signal = database_testability_signal(database_result, bool(model.databases))
    categories = [
        assess_project_discovery(model),
        assess_build_health(model),
        assess_testability(model, has_confirmed_openapi, target is not None, db_signal),
        assess_functional_health(run_result, generated_count, functional_not_run_reason),
        assess_performance(perf_result, performance_not_run_reason),
        assess_database_health(database_result),
        assess_configuration_hygiene(model),
        assess_test_infrastructure(model),
        assess_frontend_health(model),
    ]

    overall = compute_overall_status([c.status for c in categories])
    application_health = compute_application_health(categories)
    coverage = _compute_coverage(model, generated_count, run_result, perf_result, database_result)
    unassessed = _compute_unassessed(model, run_result, perf_result, database_result)
    assessment_completeness = (
        "full" if not unassessed and all(c.percent == 100.0 for c in coverage) else "partial"
    )

    recommendations = sorted({
        finding.recommendation for category in categories for finding in category.findings if finding.recommendation
    })

    return ProjectAssessment(
        schema_version=SCHEMA_VERSION,
        tool_version=__version__,
        generated_at=datetime.now(timezone.utc).isoformat(),
        project_path=str(project_path),
        target=target,
        overall_status=overall,
        application_health=application_health,
        assessment_completeness=assessment_completeness,
        categories=categories,
        coverage=coverage,
        unassessed=unassessed,
        recommendations=recommendations,
        limitations=list(LIMITATIONS),
        warnings=list(model.warnings),
    )
