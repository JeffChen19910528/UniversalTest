from universal_test.core.models.enums import AssessmentStatus, FindingClassification
from universal_test.testing.performance.models import (
    LevelResult,
    LoadProfile,
    LoadProfileType,
    PerformanceMetrics,
    PerformanceResult,
    PerformanceThresholdResult,
)
from universal_test.assessment.performance_assessment import assess_performance


def _metrics(total=10, failed=0, timeouts=0, network=0, http=0) -> PerformanceMetrics:
    return PerformanceMetrics(
        total_requests=total, successful_requests=total - failed, failed_requests=failed,
        timeout_count=timeouts, network_error_count=network, http_error_count=http,
        duration_seconds=1.0, rps=float(total), successful_rps=float(total - failed), latency=None,
    )


def _profile() -> LoadProfile:
    return LoadProfile(profile_type=LoadProfileType.LOAD, concurrency_levels=[1], requests_per_level=10)


def test_not_enabled_is_not_assessed():
    category = assess_performance(None, "performance execution was not enabled")
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_all_successful_no_thresholds_is_pass():
    result = PerformanceResult(target="t", endpoint="e", profile=_profile(), levels=[
        LevelResult(concurrency=1, metrics=_metrics())
    ])
    category = assess_performance(result, None)
    assert category.status == AssessmentStatus.PASS


def test_total_network_failure_is_fail():
    result = PerformanceResult(target="t", endpoint="e", profile=_profile(), levels=[
        LevelResult(concurrency=1, metrics=_metrics(total=10, failed=10, network=10))
    ])
    category = assess_performance(result, None)
    assert category.status == AssessmentStatus.FAIL


def test_threshold_breach_is_warning_not_fail():
    threshold = PerformanceThresholdResult(name="p95_ms", limit=500, observed=812, status=AssessmentStatus.FAIL)
    result = PerformanceResult(target="t", endpoint="e", profile=_profile(), levels=[
        LevelResult(concurrency=50, metrics=_metrics(total=10, http=0), thresholds=[threshold])
    ])
    category = assess_performance(result, None)
    assert category.status == AssessmentStatus.WARNING
    assert len(category.findings) == 1
    assert "p95_ms" in category.findings[0].title
    assert category.findings[0].classification == FindingClassification.DEFECT


def test_threshold_pass_does_not_create_a_finding():
    threshold = PerformanceThresholdResult(name="error_rate_percent", limit=1, observed=0.0, status=AssessmentStatus.PASS)
    result = PerformanceResult(target="t", endpoint="e", profile=_profile(), levels=[
        LevelResult(concurrency=1, metrics=_metrics(), thresholds=[threshold])
    ])
    category = assess_performance(result, None)
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_partial_http_errors_is_warning():
    result = PerformanceResult(target="t", endpoint="e", profile=_profile(), levels=[
        LevelResult(concurrency=1, metrics=_metrics(total=10, failed=2, http=2))
    ])
    category = assess_performance(result, None)
    assert category.status == AssessmentStatus.WARNING
