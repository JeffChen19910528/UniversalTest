"""Builds a `BaselineSnapshot` from the same Phase 2-6 result objects
`assessment/engine.py::build_assessment()` already consumes — this module
never re-discovers, re-executes, or re-queries anything; it only compacts
already-computed results into the persisted/compared shape (Phase 7 brief
§2's required fields: tool/schema version, project identity, source
revision, timestamp, discovery/functional/performance/database/assessment
summaries).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from universal_test import __version__
from universal_test.core.orchestration.orchestrator import RunResult
from universal_test.discovery.models import ProjectModel
from universal_test.testing.performance.models import PerformanceResult
from universal_test.adapters.database.adapter import DatabaseDiscoveryResult
from universal_test.assessment.models import ProjectAssessment
from universal_test.regression.models import (
    SCHEMA_VERSION,
    AssessmentCategorySnapshot,
    AssessmentSnapshot,
    BaselineSnapshot,
    BrowserSnapshot,
    BrowserTestEntry,
    DatabaseSnapshot,
    DatabaseTableSnapshot,
    DiscoverySnapshot,
    FunctionalSnapshot,
    FunctionalTestEntry,
    PerformanceLevelSnapshot,
    PerformanceSnapshot,
    ScenarioSnapshot,
    ScenarioTestEntry,
    SourceInfo,
)

_PERFORMANCE_METRIC_KEYS = (
    "p50_ms", "p90_ms", "p95_ms", "p99_ms", "rps", "successful_rps",
    "error_rate_percent", "timeout_count", "network_error_count", "http_error_count", "total_requests",
)


def _discovery_snapshot(model: ProjectModel) -> DiscoverySnapshot:
    return DiscoverySnapshot(
        languages=sorted({x.name for x in model.languages}),
        frameworks=sorted({x.name for x in model.frameworks}),
        databases=sorted({x.name for x in model.databases}),
        apis=sorted({x.name for x in model.apis}),
        test_frameworks=sorted({x.name for x in model.test_frameworks}),
        infrastructure=sorted({x.name for x in model.infrastructure}),
    )


def _functional_snapshot(target: str | None, generated_count: int, run_result: RunResult | None) -> FunctionalSnapshot | None:
    if run_result is None:
        return None
    return FunctionalSnapshot(
        target=target,
        generated_count=generated_count,
        summary=dict(run_result.summary),
        tests=[FunctionalTestEntry(id=r.id, status=r.status.value) for r in run_result.results],
    )


def _performance_snapshot(perf_result: PerformanceResult | None) -> PerformanceSnapshot | None:
    if perf_result is None:
        return None
    levels = []
    for level in perf_result.levels:
        m = level.metrics
        metrics = {
            "p50_ms": m.latency.p50_ms if m.latency else None,
            "p90_ms": m.latency.p90_ms if m.latency else None,
            "p95_ms": m.latency.p95_ms if m.latency else None,
            "p99_ms": m.latency.p99_ms if m.latency else None,
            "rps": m.rps,
            "successful_rps": m.successful_rps,
            "error_rate_percent": m.error_rate_percent,
            "timeout_count": m.timeout_count,
            "network_error_count": m.network_error_count,
            "http_error_count": m.http_error_count,
            "total_requests": m.total_requests,
        }
        levels.append(PerformanceLevelSnapshot(concurrency=level.concurrency, metrics=metrics))
    return PerformanceSnapshot(target=perf_result.target, endpoint=perf_result.endpoint, levels=levels)


def _database_snapshot(database_result: DatabaseDiscoveryResult | None) -> DatabaseSnapshot | None:
    if database_result is None or database_result.info is None:
        return None
    info = database_result.info
    tables = []
    total_fks = 0
    total_indexes = 0
    total_views = 0
    for schema in info.schemas:
        for t in schema.tables:
            tables.append(DatabaseTableSnapshot(
                schema=schema.name, name=t.name,
                columns=sorted(c.name for c in t.columns),
                primary_key=list(t.primary_key.columns) if t.primary_key else None,
                foreign_key_count=len(t.foreign_keys), index_count=len(t.indexes),
            ))
            total_fks += len(t.foreign_keys)
            total_indexes += len(t.indexes)
        total_views += len(schema.views)
    summary = {
        "schemas": len(info.schemas), "tables": len(tables), "views": total_views,
        "foreign_keys": total_fks, "indexes": total_indexes,
    }
    return DatabaseSnapshot(engine=info.engine.value, database_name=info.database_name, summary=summary, tables=tables)


def _browser_snapshot(browser_result) -> BrowserSnapshot | None:
    if browser_result is None or not browser_result.executed:
        return None
    return BrowserSnapshot(
        target=browser_result.target,
        browser=browser_result.browser,
        summary=dict(browser_result.run_result.summary),
        tests=[BrowserTestEntry(id=r.id, status=r.status.value) for r in browser_result.run_result.results],
    )


def _scenario_snapshot(scenario_results) -> ScenarioSnapshot | None:
    executed = [r for r in (scenario_results or []) if r.status != "not_assessed"]
    if not executed:
        return None
    summary: dict[str, int] = {}
    for r in executed:
        summary[r.status] = summary.get(r.status, 0) + 1
    return ScenarioSnapshot(
        summary=summary,
        tests=[ScenarioTestEntry(id=r.scenario_id, status=r.status) for r in executed],
    )


def _assessment_snapshot(assessment: ProjectAssessment) -> AssessmentSnapshot:
    return AssessmentSnapshot(
        overall_status=assessment.overall_status.value,
        categories=[AssessmentCategorySnapshot(name=c.name, status=c.status.value) for c in assessment.categories],
    )


def build_snapshot(
    *,
    project_path: str | Path,
    target: str | None,
    model: ProjectModel,
    generated_count: int,
    run_result: RunResult | None,
    perf_result: PerformanceResult | None,
    database_result: DatabaseDiscoveryResult | None,
    assessment: ProjectAssessment,
    browser_result=None,
    scenario_results=None,
) -> BaselineSnapshot:
    return BaselineSnapshot(
        schema_version=SCHEMA_VERSION,
        tool_version=__version__,
        generated_at=datetime.now(timezone.utc).isoformat(),
        project_path=str(project_path),
        source=SourceInfo(
            is_git=model.repository.is_git, commit=model.repository.commit,
            branch=model.repository.branch, dirty=model.repository.dirty,
        ),
        discovery=_discovery_snapshot(model),
        functional=_functional_snapshot(target, generated_count, run_result),
        performance=_performance_snapshot(perf_result),
        database=_database_snapshot(database_result),
        assessment=_assessment_snapshot(assessment),
        browser=_browser_snapshot(browser_result),
        scenario=_scenario_snapshot(scenario_results),
    )
