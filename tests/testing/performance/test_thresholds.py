from universal_test.core.models.enums import AssessmentStatus
from universal_test.testing.performance.metrics import aggregate
from universal_test.testing.performance.models import ErrorType, PerformanceSample
from universal_test.testing.performance.thresholds import evaluate_thresholds


def _metrics(latencies_ms, error_count=0, total=None):
    samples = [PerformanceSample(0.0, ms, 200, ErrorType.NONE) for ms in latencies_ms]
    samples += [PerformanceSample(0.0, 1.0, 500, ErrorType.HTTP_ERROR) for _ in range(error_count)]
    return aggregate(samples, wall_clock_duration_seconds=1.0)


def test_all_thresholds_pass():
    metrics = _metrics([10, 20, 30, 40, 50])
    results = evaluate_thresholds(metrics, {"p95_ms": 100, "error_rate_percent": 10, "min_rps": 1})
    assert all(r.status == AssessmentStatus.PASS for r in results)


def test_one_threshold_fails():
    metrics = _metrics([10, 20, 30, 40, 500])  # p95/p99 will be high
    results = evaluate_thresholds(metrics, {"p95_ms": 100})
    assert results[0].status == AssessmentStatus.FAIL


def test_multiple_thresholds_some_fail():
    metrics = _metrics([10] * 10, error_count=5)  # 33% error rate
    results = evaluate_thresholds(metrics, {"p95_ms": 100, "error_rate_percent": 1})
    statuses = {r.name: r.status for r in results}
    assert statuses["p95_ms"] == AssessmentStatus.PASS
    assert statuses["error_rate_percent"] == AssessmentStatus.FAIL


def test_boundary_equality_is_a_pass():
    metrics = _metrics([50, 50, 50])
    results = evaluate_thresholds(metrics, {"p95_ms": 50})
    assert results[0].status == AssessmentStatus.PASS
    assert results[0].observed == 50


def test_min_rps_pass_and_fail():
    metrics = _metrics([10] * 5)  # rps = 5/1.0 = 5.0
    pass_result = evaluate_thresholds(metrics, {"min_rps": 5})[0]
    fail_result = evaluate_thresholds(metrics, {"min_rps": 10})[0]
    assert pass_result.status == AssessmentStatus.PASS
    assert fail_result.status == AssessmentStatus.FAIL


def test_latency_threshold_not_assessed_with_zero_samples():
    metrics = _metrics([])
    results = evaluate_thresholds(metrics, {"p95_ms": 100})
    assert results[0].status == AssessmentStatus.NOT_ASSESSED
    assert results[0].observed is None


def test_min_rps_not_assessed_with_zero_requests():
    metrics = _metrics([])
    results = evaluate_thresholds(metrics, {"min_rps": 10})
    assert results[0].status == AssessmentStatus.NOT_ASSESSED


def test_unrecognized_threshold_key_is_warned_not_silently_ignored():
    metrics = _metrics([10])
    warnings = []
    results = evaluate_thresholds(metrics, {"bogus_key": 1}, warnings)
    assert results == []
    assert len(warnings) == 1
    assert "bogus_key" in warnings[0]


def test_p50_p90_p99_all_recognized():
    metrics = _metrics([10, 20, 30, 40, 50])
    results = evaluate_thresholds(metrics, {"p50_ms": 100, "p90_ms": 100, "p99_ms": 100})
    assert len(results) == 3
    assert all(r.status == AssessmentStatus.PASS for r in results)
