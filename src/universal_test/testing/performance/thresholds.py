"""Threshold evaluation — independent, testable component (Phase 4 brief §13:
"不要硬編碼在 runner").

Recognized keys (matching `skill.md` §10/§13's example config):
`p50_ms`/`p90_ms`/`p95_ms`/`p99_ms` (max allowed latency),
`error_rate_percent` (max allowed), `min_rps` (minimum required).
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus
from universal_test.testing.performance.models import PerformanceMetrics, PerformanceThresholdResult

_LATENCY_KEYS = {"p50_ms": "p50_ms", "p90_ms": "p90_ms", "p95_ms": "p95_ms", "p99_ms": "p99_ms"}


def evaluate_thresholds(
    metrics: PerformanceMetrics, thresholds: dict[str, float], warnings: list[str] | None = None,
) -> list[PerformanceThresholdResult]:
    results: list[PerformanceThresholdResult] = []

    for name, limit in thresholds.items():
        if name in _LATENCY_KEYS:
            attr = _LATENCY_KEYS[name]
            if metrics.latency is None:
                results.append(PerformanceThresholdResult(name, limit, None, AssessmentStatus.NOT_ASSESSED))
                continue
            observed = getattr(metrics.latency, attr)
            status = AssessmentStatus.PASS if observed <= limit else AssessmentStatus.FAIL
            results.append(PerformanceThresholdResult(name, limit, observed, status))

        elif name == "error_rate_percent":
            observed = metrics.error_rate_percent
            status = AssessmentStatus.PASS if observed <= limit else AssessmentStatus.FAIL
            results.append(PerformanceThresholdResult(name, limit, observed, status))

        elif name == "min_rps":
            if metrics.total_requests == 0:
                results.append(PerformanceThresholdResult(name, limit, None, AssessmentStatus.NOT_ASSESSED))
                continue
            observed = metrics.rps
            status = AssessmentStatus.PASS if observed >= limit else AssessmentStatus.FAIL
            results.append(PerformanceThresholdResult(name, limit, observed, status))

        else:
            if warnings is not None:
                warnings.append(f"unrecognized performance threshold key: {name!r}; ignored")

    return results
