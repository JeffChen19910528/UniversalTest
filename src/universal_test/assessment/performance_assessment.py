"""Performance: aggregate Phase 4's `PerformanceResult` — never recompute
RPS/percentiles/error-rate, only roll them up (Phase 5 brief §9).
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, FindingClassification, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.testing.performance.models import PerformanceResult
from universal_test.assessment.models import AssessmentCategory, AssessmentFinding
from universal_test.assessment.rules import execution_health_status


def assess_performance(perf_result: PerformanceResult | None, not_run_reason: str | None) -> AssessmentCategory:
    if perf_result is None:
        return AssessmentCategory(
            name="Performance", status=AssessmentStatus.NOT_ASSESSED,
            summary="performance execution was not enabled",
            reason=not_run_reason or "performance execution was not enabled",
        )

    total_attempted = sum(level.metrics.total_requests for level in perf_result.levels)
    total_transport_failed = sum(
        level.metrics.timeout_count + level.metrics.network_error_count for level in perf_result.levels
    )
    total_http_errors = sum(level.metrics.http_error_count for level in perf_result.levels)

    status = execution_health_status(total_attempted, total_transport_failed, total_http_errors)

    findings: list[AssessmentFinding] = []
    for level in perf_result.levels:
        for threshold in level.thresholds:
            if threshold.status != AssessmentStatus.FAIL:
                continue
            is_latency = threshold.name.endswith("_ms")
            findings.append(AssessmentFinding(
                id=f"PERF-{level.concurrency}-{threshold.name}", category="Performance",
                status=AssessmentStatus.WARNING, severity=Severity.MEDIUM, confidence=0.9,
                title=f"{threshold.name} exceeded its configured threshold at concurrency={level.concurrency}",
                description=f"Observed {threshold.observed}, configured limit {threshold.limit}.",
                evidence=[Evidence("performance_threshold", {
                    "concurrency": level.concurrency, "metric": threshold.name,
                    "observed": threshold.observed, "limit": threshold.limit,
                })],
                recommendation=(
                    "Investigate slow endpoint behavior under this concurrency level: review "
                    "database queries, downstream dependencies, and server-side resource utilization."
                    if is_latency else
                    "Investigate elevated error rate or reduced throughput under this concurrency level."
                ),
                classification=FindingClassification.DEFECT,
            ))
            if status == AssessmentStatus.PASS:
                status = AssessmentStatus.WARNING  # a threshold breach always surfaces, even with 0 transport failures

    level_summaries = ", ".join(f"concurrency={l.concurrency}: {l.metrics.total_requests} req" for l in perf_result.levels)
    summary = f"{len(perf_result.levels)} concurrency level(s) executed ({level_summaries})"
    if perf_result.stopped_early:
        summary += f"; stopped early: {perf_result.stop_reason}"

    evidence = [Evidence("performance_levels", {
        "levels": [level.concurrency for level in perf_result.levels],
        "stopped_early": perf_result.stopped_early,
    })]
    return AssessmentCategory(name="Performance", status=status, summary=summary, findings=findings, evidence=evidence)
