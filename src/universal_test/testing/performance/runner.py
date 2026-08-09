"""Bounded-concurrency performance runner.

Uses `concurrent.futures.ThreadPoolExecutor` — no asyncio, no hand-rolled
event loop. I/O-bound HTTP requests are exactly ThreadPoolExecutor's sweet
spot, and it gives correct bounded concurrency (`max_workers=concurrency`)
for free without extra bookkeeping (Phase 4 brief §8: prefer correctness
over "looking efficient").

**Executor contract**: the `PerformanceExecutor` callable passed in must
never raise — it is responsible for catching its own transport errors and
returning a `PerformanceSample` with the appropriate `ErrorType` (see
`adapters/rest/performance_executor.py`). This lets every sample — success
or failure — flow into the same aggregation path uniformly, which is what
"measure everything, don't abort on one failure" requires.
"""

from __future__ import annotations

import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from universal_test.testing.performance.metrics import aggregate
from universal_test.testing.performance.models import (
    LevelResult,
    LoadProfile,
    LoadProfileType,
    PerformanceRequest,
    PerformanceResult,
    PerformanceSample,
)
from universal_test.testing.performance.thresholds import evaluate_thresholds

PerformanceExecutor = Callable[[PerformanceRequest], PerformanceSample]


class PerformanceRunner:
    def __init__(self, executor: PerformanceExecutor, run_timeout_seconds: float | None = None) -> None:
        self._executor = executor
        self._run_timeout_seconds = run_timeout_seconds

    def run(
        self,
        target: str,
        endpoint: str,
        request: PerformanceRequest,
        profile: LoadProfile,
        thresholds: dict[str, float] | None = None,
        cancellation_event: threading.Event | None = None,
    ) -> PerformanceResult:
        cancellation_event = cancellation_event or threading.Event()
        thresholds = thresholds or {}

        result = PerformanceResult(target=target, endpoint=endpoint, profile=profile)
        run_start = time.perf_counter()

        for concurrency in profile.concurrency_levels:
            if cancellation_event.is_set():
                result.stopped_early = True
                result.stop_reason = "cancelled"
                break
            if self._run_timeout_seconds is not None and (time.perf_counter() - run_start) >= self._run_timeout_seconds:
                result.stopped_early = True
                result.stop_reason = f"run timeout ({self._run_timeout_seconds}s) exceeded before concurrency={concurrency}"
                break

            level = self._run_level(request, concurrency, profile, cancellation_event, thresholds, result.warnings)
            result.levels.append(level)

            if profile.profile_type == LoadProfileType.STRESS:
                stop_reason = self._stress_stop_reason(level, profile, concurrency)
                if stop_reason:
                    result.stopped_early = True
                    result.stop_reason = stop_reason
                    break

        return result

    def _stress_stop_reason(self, level: LevelResult, profile: LoadProfile, concurrency: int) -> str | None:
        if profile.stop_on_error_rate_percent is not None:
            if level.metrics.error_rate_percent > profile.stop_on_error_rate_percent:
                return (
                    f"error rate {level.metrics.error_rate_percent:.1f}% exceeded stop threshold "
                    f"{profile.stop_on_error_rate_percent}% at concurrency={concurrency}"
                )
        if profile.stop_on_p95_ms is not None and level.metrics.latency is not None:
            if level.metrics.latency.p95_ms > profile.stop_on_p95_ms:
                return (
                    f"P95 latency {level.metrics.latency.p95_ms:.0f}ms exceeded stop threshold "
                    f"{profile.stop_on_p95_ms}ms at concurrency={concurrency}"
                )
        return None

    def _run_level(
        self,
        request: PerformanceRequest,
        concurrency: int,
        profile: LoadProfile,
        cancellation_event: threading.Event,
        thresholds: dict[str, float],
        warnings: list[str],
    ) -> LevelResult:
        start = time.perf_counter()
        if profile.requests_per_level is not None:
            samples = self._run_fixed_count(request, concurrency, profile.requests_per_level, cancellation_event)
        else:
            duration = profile.duration_seconds_per_level or 0.0
            samples = self._run_for_duration(request, concurrency, duration, cancellation_event)
        elapsed = time.perf_counter() - start

        metrics = aggregate(samples, elapsed)
        threshold_results = evaluate_thresholds(metrics, thresholds, warnings)
        return LevelResult(concurrency=concurrency, metrics=metrics, thresholds=threshold_results)

    def _run_fixed_count(
        self, request: PerformanceRequest, concurrency: int, count: int, cancellation_event: threading.Event,
    ) -> list[PerformanceSample]:
        def _task() -> PerformanceSample | None:
            if cancellation_event.is_set():
                return None
            return self._executor(request)

        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            futures = [pool.submit(_task) for _ in range(count)]
            samples = [f.result() for f in futures]
        return [s for s in samples if s is not None]

    def _run_for_duration(
        self, request: PerformanceRequest, concurrency: int, duration_seconds: float, cancellation_event: threading.Event,
    ) -> list[PerformanceSample]:
        results: queue.SimpleQueue[PerformanceSample] = queue.SimpleQueue()
        deadline = time.perf_counter() + max(0.0, duration_seconds)

        def _worker_loop() -> None:
            while time.perf_counter() < deadline and not cancellation_event.is_set():
                results.put(self._executor(request))

        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            futures = [pool.submit(_worker_loop) for _ in range(concurrency)]
            for f in futures:
                f.result()

        samples: list[PerformanceSample] = []
        while not results.empty():
            samples.append(results.get())
        return samples
