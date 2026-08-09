"""Deterministic percentile calculation.

Uses the **nearest-rank method**: for a sorted ascending list of `n` values
and percentile `p` (0-100), `rank = ceil(p/100 * n)`, clamped to `[1, n]`;
the result is `sorted_values[rank - 1]`. This is a standard, simple,
fully-deterministic definition (no interpolation) that always returns an
actually-observed sample value rather than an interpolated number between
two samples — appropriate for latency reporting, where "P95 was this
specific observed request" is more meaningful than a synthetic interpolated
value. Documented explicitly per the Phase 4 brief §10's requirement to not
just write an unexplained one-liner.
"""

from __future__ import annotations

import math

from universal_test.testing.performance.models import LatencyStats


def percentile(sorted_values: list[float], p: float) -> float:
    """`sorted_values` must already be sorted ascending and non-empty."""
    n = len(sorted_values)
    if n == 0:
        raise ValueError("percentile() requires at least one value")
    if n == 1:
        return sorted_values[0]
    rank = math.ceil((p / 100.0) * n)
    rank = max(1, min(rank, n))
    return sorted_values[rank - 1]


def compute_latency_stats(durations_ms: list[float]) -> LatencyStats | None:
    """Returns `None` for zero samples — there is no latency to report, and
    reporting a fabricated 0ms would overclaim (skill.md §4.1).
    """
    if not durations_ms:
        return None
    ordered = sorted(durations_ms)
    n = len(ordered)
    return LatencyStats(
        min_ms=ordered[0],
        mean_ms=sum(ordered) / n,
        p50_ms=percentile(ordered, 50),
        p90_ms=percentile(ordered, 90),
        p95_ms=percentile(ordered, 95),
        p99_ms=percentile(ordered, 99),
        max_ms=ordered[-1],
    )
