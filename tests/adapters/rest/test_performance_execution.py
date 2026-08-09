from universal_test.core.models.enums import AssessmentStatus
from universal_test.testing.performance import PerformanceRunner, build_load_profile
from universal_test.testing.performance.models import PerformanceRequest
from universal_test.adapters.rest.auth import AuthConfig
from universal_test.adapters.rest.performance import resolve_auth_headers, resolve_performance_target
from universal_test.adapters.rest.performance_executor import make_performance_executor
from .fixture_server import UNSTABLE_FAILURE_EVERY_NTH, VALID_BEARER_TOKEN, reset_unstable_counter


def test_fast_endpoint_all_succeed(live_server):
    executor, close = make_performance_executor(live_server.base_url, request_timeout_seconds=5.0)
    profile, _ = build_load_profile("custom", concurrency=[5], requests=30)
    runner = PerformanceRunner(executor)
    request = PerformanceRequest(method="GET", path="/fast")
    result = runner.run(live_server.base_url, "GET /fast", request, profile)
    close()

    level = result.levels[0]
    assert level.metrics.total_requests == 30
    assert level.metrics.failed_requests == 0
    assert level.metrics.latency is not None


def test_error_endpoint_all_fail_as_http_error(live_server):
    executor, close = make_performance_executor(live_server.base_url, request_timeout_seconds=5.0)
    profile, _ = build_load_profile("custom", concurrency=[1], requests=10)
    runner = PerformanceRunner(executor)
    request = PerformanceRequest(method="GET", path="/error")
    result = runner.run(live_server.base_url, "GET /error", request, profile)
    close()

    level = result.levels[0]
    assert level.metrics.failed_requests == 10
    assert level.metrics.http_error_count == 10
    assert level.metrics.error_rate_percent == 100.0


def test_unstable_endpoint_has_partial_failures(live_server):
    reset_unstable_counter()
    executor, close = make_performance_executor(live_server.base_url, request_timeout_seconds=5.0)
    profile, _ = build_load_profile("custom", concurrency=[1], requests=UNSTABLE_FAILURE_EVERY_NTH * 3)
    runner = PerformanceRunner(executor)
    request = PerformanceRequest(method="GET", path="/unstable")
    result = runner.run(live_server.base_url, "GET /unstable", request, profile)
    close()

    level = result.levels[0]
    assert level.metrics.failed_requests == 3  # exactly every Nth request, deterministic
    assert level.metrics.successful_requests == 6


def test_slow_endpoint_triggers_timeout_with_short_client_timeout(live_server):
    executor, close = make_performance_executor(live_server.base_url, request_timeout_seconds=0.05)
    profile, _ = build_load_profile("custom", concurrency=[1], requests=3)
    runner = PerformanceRunner(executor)
    request = PerformanceRequest(method="GET", path="/slow")
    result = runner.run(live_server.base_url, "GET /slow", request, profile)
    close()

    level = result.levels[0]
    assert level.metrics.timeout_count == 3
    assert level.metrics.failed_requests == 3


def test_connection_failure_reported_as_network_error():
    import socket

    # bind then immediately close a real loopback socket so the OS reliably
    # sends an immediate RST for the now-unbound port, instead of Windows
    # silently dropping packets to certain low/reserved ports (which reads
    # as a slow timeout rather than a fast refusal).
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    unused_port = probe.getsockname()[1]
    probe.close()
    target = f"http://127.0.0.1:{unused_port}"

    executor, close = make_performance_executor(target, request_timeout_seconds=5.0)
    profile, _ = build_load_profile("custom", concurrency=[1], requests=2)
    runner = PerformanceRunner(executor)
    request = PerformanceRequest(method="GET", path="/fast")
    result = runner.run(target, "GET /fast", request, profile)
    close()

    level = result.levels[0]
    assert level.metrics.network_error_count == 2
    assert level.metrics.successful_requests == 0


def test_threshold_evaluation_against_real_traffic(live_server):
    executor, close = make_performance_executor(live_server.base_url, request_timeout_seconds=5.0)
    profile, _ = build_load_profile("custom", concurrency=[2], requests=20)
    runner = PerformanceRunner(executor)
    request = PerformanceRequest(method="GET", path="/fast")
    result = runner.run(
        live_server.base_url, "GET /fast", request, profile,
        thresholds={"p95_ms": 5000, "error_rate_percent": 1, "min_rps": 0.01},
    )
    close()

    for t in result.levels[0].thresholds:
        assert t.status == AssessmentStatus.PASS


def test_auth_header_applied_to_every_request(live_server):
    auth_config = AuthConfig(bearer_token=VALID_BEARER_TOKEN)
    headers, query = resolve_auth_headers(spec=None, endpoint=None, auth_config=auth_config)
    assert headers == {"Authorization": f"Bearer {VALID_BEARER_TOKEN}"}

    executor, close = make_performance_executor(
        live_server.base_url, request_timeout_seconds=5.0, auth_headers=headers, auth_query=query,
    )
    profile, _ = build_load_profile("custom", concurrency=[1], requests=5)
    runner = PerformanceRunner(executor)
    request = PerformanceRequest(method="GET", path="/secure")
    result = runner.run(live_server.base_url, "GET /secure", request, profile)
    close()

    assert result.levels[0].metrics.successful_requests == 5


def test_endpoint_resolution_reuses_phase3_request_generation(openapi_fixture_path):
    spec, endpoint, request, notes = resolve_performance_target(
        openapi_fixture_path("openapi-basic"), endpoint_path="/users", method="POST",
    )
    assert request.method == "POST"
    assert request.json_body == {"name": "test string", "email": "test string"}
    assert request.content_type == "application/json"
