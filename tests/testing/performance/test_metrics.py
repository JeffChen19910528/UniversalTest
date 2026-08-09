from universal_test.testing.performance.metrics import aggregate
from universal_test.testing.performance.models import ErrorType, PerformanceSample


def _sample(duration_ms, status_code=200, error_type=ErrorType.NONE):
    return PerformanceSample(start_time=0.0, duration_ms=duration_ms, status_code=status_code, error_type=error_type)


def test_aggregate_zero_samples():
    metrics = aggregate([], wall_clock_duration_seconds=1.0)
    assert metrics.total_requests == 0
    assert metrics.successful_requests == 0
    assert metrics.failed_requests == 0
    assert metrics.error_rate_percent == 0.0
    assert metrics.latency is None
    assert metrics.rps == 0.0


def test_aggregate_all_successful():
    samples = [_sample(10.0) for _ in range(10)]
    metrics = aggregate(samples, wall_clock_duration_seconds=1.0)
    assert metrics.total_requests == 10
    assert metrics.successful_requests == 10
    assert metrics.failed_requests == 0
    assert metrics.error_rate_percent == 0.0
    assert metrics.rps == 10.0
    assert metrics.successful_rps == 10.0


def test_aggregate_mixed_http_errors():
    samples = [_sample(10.0, 200) for _ in range(8)] + [_sample(5.0, 500, ErrorType.HTTP_ERROR) for _ in range(2)]
    metrics = aggregate(samples, wall_clock_duration_seconds=1.0)
    assert metrics.total_requests == 10
    assert metrics.successful_requests == 8
    assert metrics.failed_requests == 2
    assert metrics.http_error_count == 2
    assert metrics.error_rate_percent == 20.0


def test_aggregate_timeouts_and_network_errors_counted_separately():
    samples = [
        _sample(0.0, None, ErrorType.TIMEOUT),
        _sample(0.0, None, ErrorType.NETWORK_ERROR),
        _sample(0.0, None, ErrorType.TARGET_ERROR),
        _sample(10.0, 200),
    ]
    metrics = aggregate(samples, wall_clock_duration_seconds=1.0)
    assert metrics.timeout_count == 1
    assert metrics.network_error_count == 2  # NETWORK_ERROR + TARGET_ERROR grouped (see metrics.py docstring)
    assert metrics.http_error_count == 0
    assert metrics.failed_requests == 3
    assert metrics.successful_requests == 1


def test_aggregate_rps_uses_wall_clock_not_sum_of_durations():
    # 10 requests each "took" 100ms but ran concurrently in 0.5s wall-clock
    samples = [_sample(100.0) for _ in range(10)]
    metrics = aggregate(samples, wall_clock_duration_seconds=0.5)
    assert metrics.rps == 20.0  # 10 / 0.5, not 10 / (10*0.1)


def test_aggregate_zero_wall_clock_duration_does_not_divide_by_zero():
    samples = [_sample(1.0)]
    metrics = aggregate(samples, wall_clock_duration_seconds=0.0)
    assert metrics.rps == 0.0
    assert metrics.successful_rps == 0.0


def test_error_rate_percent_is_a_computed_property():
    samples = [_sample(1.0) for _ in range(3)] + [_sample(1.0, 500, ErrorType.HTTP_ERROR)]
    metrics = aggregate(samples, wall_clock_duration_seconds=1.0)
    assert metrics.error_rate_percent == 25.0


def test_to_dict_shape():
    samples = [_sample(10.0)]
    metrics = aggregate(samples, wall_clock_duration_seconds=1.0)
    d = metrics.to_dict()
    assert d["total_requests"] == 1
    assert "latency_ms" in d
    assert d["latency_ms"]["p50"] == 10.0
