"""Aggregate a batch of PerformanceSamples into PerformanceMetrics.

RPS/successful-RPS are defined against the *wall-clock* duration of the
concurrency level's run (not the sum of per-request durations, which would
overstate throughput under concurrency) — Phase 4 brief §11: "需要明確定義:
total elapsed time".
"""

from __future__ import annotations

from universal_test.testing.performance.models import ErrorType, PerformanceMetrics, PerformanceSample
from universal_test.testing.performance.percentiles import compute_latency_stats


def aggregate(samples: list[PerformanceSample], wall_clock_duration_seconds: float) -> PerformanceMetrics:
    total = len(samples)
    successful = sum(1 for s in samples if s.success)
    failed = total - successful

    timeout_count = sum(1 for s in samples if s.error_type == ErrorType.TIMEOUT)
    http_error_count = sum(1 for s in samples if s.error_type == ErrorType.HTTP_ERROR)
    # NETWORK_ERROR and TARGET_ERROR are both "the request layer itself failed"
    # (as opposed to a completed HTTP exchange with an error status); reported
    # together as one bucket, matching the brief's "network error / connection
    # error" grouping (§12) without inventing a 4th metrics field for a
    # narrower distinction the report doesn't need.
    network_error_count = sum(
        1 for s in samples if s.error_type in (ErrorType.NETWORK_ERROR, ErrorType.TARGET_ERROR)
    )

    latency = compute_latency_stats([s.duration_ms for s in samples])

    rps = total / wall_clock_duration_seconds if wall_clock_duration_seconds > 0 else 0.0
    successful_rps = successful / wall_clock_duration_seconds if wall_clock_duration_seconds > 0 else 0.0

    return PerformanceMetrics(
        total_requests=total,
        successful_requests=successful,
        failed_requests=failed,
        timeout_count=timeout_count,
        network_error_count=network_error_count,
        http_error_count=http_error_count,
        duration_seconds=wall_clock_duration_seconds,
        rps=rps,
        successful_rps=successful_rps,
        latency=latency,
    )
