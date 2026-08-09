import threading
import time

from universal_test.testing.performance.models import ErrorType, LoadProfileType, PerformanceRequest, PerformanceSample
from universal_test.testing.performance.planner import build_load_profile
from universal_test.testing.performance.runner import PerformanceRunner

REQUEST = PerformanceRequest(method="GET", path="/fast")


def _instant_ok(request: PerformanceRequest) -> PerformanceSample:
    return PerformanceSample(start_time=time.time(), duration_ms=1.0, status_code=200, error_type=ErrorType.NONE)


def test_concurrency_one_runs_sequentially_and_collects_all_samples():
    profile, _ = build_load_profile("custom", concurrency=[1], requests=15)
    runner = PerformanceRunner(_instant_ok)
    result = runner.run("t", "e", REQUEST, profile)
    assert len(result.levels) == 1
    assert result.levels[0].metrics.total_requests == 15


def test_concurrency_greater_than_one_collects_all_samples():
    profile, _ = build_load_profile("custom", concurrency=[8], requests=40)
    runner = PerformanceRunner(_instant_ok)
    result = runner.run("t", "e", REQUEST, profile)
    assert result.levels[0].metrics.total_requests == 40


def test_bounded_concurrency_never_exceeds_configured_max():
    in_flight = {"current": 0, "max_seen": 0}
    lock = threading.Lock()

    def _tracking_executor(request):
        with lock:
            in_flight["current"] += 1
            in_flight["max_seen"] = max(in_flight["max_seen"], in_flight["current"])
        time.sleep(0.02)
        with lock:
            in_flight["current"] -= 1
        return PerformanceSample(start_time=time.time(), duration_ms=20.0, status_code=200, error_type=ErrorType.NONE)

    profile, _ = build_load_profile("custom", concurrency=[4], requests=20)
    runner = PerformanceRunner(_tracking_executor)
    runner.run("t", "e", REQUEST, profile)
    assert in_flight["max_seen"] <= 4


def test_duration_mode_runs_for_roughly_the_configured_time():
    profile, _ = build_load_profile("custom", concurrency=[2], duration=0.2)
    runner = PerformanceRunner(_instant_ok)
    start = time.perf_counter()
    result = runner.run("t", "e", REQUEST, profile)
    elapsed = time.perf_counter() - start
    assert 0.1 < elapsed < 1.0
    assert result.levels[0].metrics.total_requests > 0


def test_failed_requests_are_captured_not_raised():
    def _always_fails(request):
        return PerformanceSample(start_time=time.time(), duration_ms=1.0, status_code=500, error_type=ErrorType.HTTP_ERROR)

    profile, _ = build_load_profile("custom", concurrency=[1], requests=5)
    runner = PerformanceRunner(_always_fails)
    result = runner.run("t", "e", REQUEST, profile)
    assert result.levels[0].metrics.failed_requests == 5
    assert result.levels[0].metrics.http_error_count == 5


def test_network_error_samples_are_captured_not_raised():
    def _network_error(request):
        return PerformanceSample(start_time=time.time(), duration_ms=1.0, status_code=None, error_type=ErrorType.NETWORK_ERROR)

    profile, _ = build_load_profile("custom", concurrency=[1], requests=3)
    runner = PerformanceRunner(_network_error)
    result = runner.run("t", "e", REQUEST, profile)
    assert result.levels[0].metrics.network_error_count == 3


def test_timeout_samples_are_captured_not_raised():
    def _timeout(request):
        return PerformanceSample(start_time=time.time(), duration_ms=1.0, status_code=None, error_type=ErrorType.TIMEOUT)

    profile, _ = build_load_profile("custom", concurrency=[1], requests=3)
    runner = PerformanceRunner(_timeout)
    result = runner.run("t", "e", REQUEST, profile)
    assert result.levels[0].metrics.timeout_count == 3


def test_cancellation_stops_before_later_levels():
    cancel = threading.Event()

    def _cancel_after_first(request):
        cancel.set()
        return _instant_ok(request)

    profile, _ = build_load_profile("custom", concurrency=[1, 100], requests=5)
    runner = PerformanceRunner(_cancel_after_first)
    result = runner.run("t", "e", REQUEST, profile, cancellation_event=cancel)
    assert result.stopped_early is True
    assert result.stop_reason == "cancelled"
    assert len(result.levels) == 1


def test_stress_profile_stops_on_error_rate():
    call_count = {"n": 0}

    def _degrades_over_time(request):
        call_count["n"] += 1
        error = call_count["n"] > 20
        return PerformanceSample(
            start_time=time.time(), duration_ms=1.0, status_code=500 if error else 200,
            error_type=ErrorType.HTTP_ERROR if error else ErrorType.NONE,
        )

    profile, _ = build_load_profile("stress", requests=10, max_concurrency=10, stop_on_error_rate_percent=50.0)
    runner = PerformanceRunner(_degrades_over_time)
    result = runner.run("t", "e", REQUEST, profile)
    assert result.stopped_early is True
    assert "error rate" in result.stop_reason
    assert result.profile.profile_type == LoadProfileType.STRESS


def test_thresholds_are_attached_per_level():
    profile, _ = build_load_profile("custom", concurrency=[1], requests=5)
    runner = PerformanceRunner(_instant_ok)
    result = runner.run("t", "e", REQUEST, profile, thresholds={"p95_ms": 500})
    assert len(result.levels[0].thresholds) == 1
    assert result.levels[0].thresholds[0].name == "p95_ms"


def test_run_timeout_stops_before_starting_a_new_level():
    def _slow(request):
        time.sleep(0.1)
        return _instant_ok(request)

    profile, _ = build_load_profile("custom", concurrency=[1, 1, 1], requests=3)
    runner = PerformanceRunner(_slow, run_timeout_seconds=0.15)
    result = runner.run("t", "e", REQUEST, profile)
    assert result.stopped_early is True
    assert "run timeout" in result.stop_reason
    assert len(result.levels) < 3
