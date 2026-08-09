from universal_test.core.models.enums import AssessmentStatus
from universal_test.regression.models import ChangeType, PerformanceLevelSnapshot, PerformanceSnapshot
from universal_test.regression.performance_compare import compare_performance

_THRESHOLDS = {
    "p50_percent": 10.0, "p90_percent": 10.0, "p95_percent": 10.0, "p99_percent": 10.0,
    "rps_percent": 10.0, "error_rate_absolute": 1.0,
}


def _snapshot(concurrency: int, **metrics) -> PerformanceSnapshot:
    base = {
        "p50_ms": 50.0, "p90_ms": 90.0, "p95_ms": 100.0, "p99_ms": 120.0,
        "rps": 100.0, "successful_rps": 100.0, "error_rate_percent": 0.0,
        "timeout_count": 0, "network_error_count": 0, "http_error_count": 0, "total_requests": 100,
    }
    base.update(metrics)
    return PerformanceSnapshot(target="t", endpoint="GET /x", levels=[
        PerformanceLevelSnapshot(concurrency=concurrency, metrics=base)
    ])


def test_missing_baseline_is_not_assessed():
    category = compare_performance(None, _snapshot(1), _THRESHOLDS)
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_missing_current_is_not_assessed():
    category = compare_performance(_snapshot(1), None, _THRESHOLDS)
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_no_matching_concurrency_level_is_not_assessed():
    category = compare_performance(_snapshot(1), _snapshot(5), _THRESHOLDS)
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_below_tolerance_is_no_finding():
    baseline = _snapshot(1, p95_ms=200.0)
    current = _snapshot(1, p95_ms=205.0)  # +2.5%, within 10% tolerance
    category = compare_performance(baseline, current, _THRESHOLDS)
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_exactly_at_tolerance_boundary_is_not_a_regression():
    baseline = _snapshot(1, p95_ms=200.0)
    current = _snapshot(1, p95_ms=220.0)  # exactly +10%
    category = compare_performance(baseline, current, _THRESHOLDS)
    assert category.status == AssessmentStatus.PASS


def test_above_tolerance_latency_regression():
    baseline = _snapshot(1, p95_ms=200.0)
    current = _snapshot(1, p95_ms=264.0)  # +32%
    category = compare_performance(baseline, current, _THRESHOLDS)
    assert category.status == AssessmentStatus.FAIL
    p95_findings = [f for f in category.findings if "P95" in f.title]
    assert len(p95_findings) == 1


def test_throughput_regression_rps_drop():
    baseline = _snapshot(1, rps=820.0)
    current = _snapshot(1, rps=760.0)  # -7.3%, within 10% tolerance -> should NOT regress
    category = compare_performance(baseline, current, _THRESHOLDS)
    assert not any("Throughput" in f.title for f in category.findings)

    current_worse = _snapshot(1, rps=700.0)  # -14.6%, exceeds 10% tolerance
    category2 = compare_performance(baseline, current_worse, _THRESHOLDS)
    assert any("Throughput" in f.title for f in category2.findings)
    assert category2.status == AssessmentStatus.FAIL


def test_rps_increase_is_improved_not_regression():
    baseline = _snapshot(1, rps=100.0)
    current = _snapshot(1, rps=150.0)
    category = compare_performance(baseline, current, _THRESHOLDS)
    assert category.status == AssessmentStatus.PASS
    rps_metric = next(m for m in category.metrics if m.name.startswith("RPS"))
    assert rps_metric.change == ChangeType.IMPROVED


def test_error_rate_regression_absolute_threshold():
    baseline = _snapshot(1, error_rate_percent=0.5)
    current = _snapshot(1, error_rate_percent=3.0)  # +2.5 points, exceeds 1.0 absolute threshold
    category = compare_performance(baseline, current, _THRESHOLDS)
    assert category.status == AssessmentStatus.FAIL
    assert any("Error rate" in f.title for f in category.findings)


def test_error_rate_small_change_not_a_regression():
    baseline = _snapshot(1, error_rate_percent=0.5)
    current = _snapshot(1, error_rate_percent=1.0)  # +0.5 points, within tolerance
    category = compare_performance(baseline, current, _THRESHOLDS)
    assert not any("Error rate" in f.title for f in category.findings)


def test_zero_baseline_value_is_not_comparable_for_percent_metric():
    baseline = _snapshot(1, p95_ms=0.0)
    current = _snapshot(1, p95_ms=50.0)
    category = compare_performance(baseline, current, _THRESHOLDS)
    p95_metric = next(m for m in category.metrics if "P95" in m.name)
    assert p95_metric.change == ChangeType.NOT_COMPARABLE
    assert not any("P95" in f.title for f in category.findings)


def test_zero_current_value_error_rate_is_improvement():
    baseline = _snapshot(1, error_rate_percent=5.0)
    current = _snapshot(1, error_rate_percent=0.0)
    category = compare_performance(baseline, current, _THRESHOLDS)
    assert not any("Error rate" in f.title for f in category.findings)
    assert category.status == AssessmentStatus.PASS


def test_no_thresholds_configured_never_raises_or_flags_a_regression():
    baseline = _snapshot(1, p95_ms=100.0)
    current = _snapshot(1, p95_ms=500.0)
    category = compare_performance(baseline, current, {})
    # with no threshold configured, nothing crosses a (nonexistent) limit -> no finding
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []
