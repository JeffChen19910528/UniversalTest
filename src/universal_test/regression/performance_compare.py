"""Performance regression: per-concurrency-level metric comparison against
configurable tolerances (brief §8/§10) with correct metric-direction
semantics (brief §9) — latency/error-rate/timeouts are `lower_is_better`,
RPS is `higher_is_better`. Nothing here hard-codes a percentage; every
tolerance comes from the `thresholds` dict passed in
(`RegressionConfig.performance`, see `core/configuration/config.py`).

A concurrency level present in only one of baseline/current is noted, not
scored — comparing across different concurrency levels would compare
unlike things (brief §5's "missing data isn't a regression" applied to a
level that simply wasn't re-run).
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.regression.models import (
    ChangeType,
    MetricDelta,
    PerformanceSnapshot,
    RegressionCategory,
    RegressionFinding,
)
from universal_test.regression.rules import status_from_findings

# (metric key, human label, direction, threshold key into the config dict)
_LATENCY_METRICS = [
    ("p50_ms", "P50 latency", "p50_percent"),
    ("p90_ms", "P90 latency", "p90_percent"),
    ("p95_ms", "P95 latency", "p95_percent"),
    ("p99_ms", "P99 latency", "p99_percent"),
]


def _percent_delta(baseline_value: float | None, current_value: float | None) -> float | None:
    if baseline_value is None or current_value is None or baseline_value == 0:
        return None
    return ((current_value - baseline_value) / baseline_value) * 100.0


def _compare_level(
    concurrency: int, b_metrics: dict, c_metrics: dict, thresholds: dict[str, float],
) -> tuple[list[MetricDelta], list[RegressionFinding]]:
    metrics: list[MetricDelta] = []
    findings: list[RegressionFinding] = []

    for key, label, threshold_key in _LATENCY_METRICS:
        b_val, c_val = b_metrics.get(key), c_metrics.get(key)
        threshold = thresholds.get(threshold_key)
        pct = _percent_delta(b_val, c_val)
        if b_val is None or c_val is None or pct is None:
            change = ChangeType.NOT_COMPARABLE
        elif threshold is not None and pct > threshold:
            change = ChangeType.REGRESSED
        elif threshold is not None and pct < -threshold:
            change = ChangeType.IMPROVED
        else:
            change = ChangeType.UNCHANGED
        metrics.append(MetricDelta(
            name=f"{label} (concurrency={concurrency})", baseline_value=b_val, current_value=c_val,
            direction="lower_is_better", change=change,
            absolute_delta=(c_val - b_val) if (b_val is not None and c_val is not None) else None,
            percent_delta=pct, threshold_percent=threshold,
        ))
        if change == ChangeType.REGRESSED:
            findings.append(RegressionFinding(
                id=f"PERF-{key.upper()}-C{concurrency}", category="Performance", change=change,
                severity=Severity.HIGH, confidence=1.0,
                title=f"{label} regressed at concurrency={concurrency}: {b_val:.1f}ms -> {c_val:.1f}ms (+{pct:.1f}%)",
                description=(
                    f"{label} increased by {pct:.1f}%, exceeding the configured tolerance of "
                    f"{threshold:.1f}% ({threshold_key})."
                ),
                evidence=[Evidence("performance_metric", {
                    "metric": key, "concurrency": concurrency, "baseline_ms": b_val, "current_ms": c_val,
                    "percent_delta": round(pct, 2), "threshold_percent": threshold,
                })],
                recommendation=f"Investigate the {label.lower()} increase at concurrency={concurrency}.",
            ))

    # RPS: higher is better.
    b_rps, c_rps = b_metrics.get("rps"), c_metrics.get("rps")
    rps_threshold = thresholds.get("rps_percent")
    rps_pct = _percent_delta(b_rps, c_rps)
    if b_rps is None or c_rps is None or rps_pct is None:
        rps_change = ChangeType.NOT_COMPARABLE
    elif rps_threshold is not None and rps_pct < -rps_threshold:
        rps_change = ChangeType.REGRESSED
    elif rps_threshold is not None and rps_pct > rps_threshold:
        rps_change = ChangeType.IMPROVED
    else:
        rps_change = ChangeType.UNCHANGED
    metrics.append(MetricDelta(
        name=f"RPS (concurrency={concurrency})", baseline_value=b_rps, current_value=c_rps,
        direction="higher_is_better", change=rps_change,
        absolute_delta=(c_rps - b_rps) if (b_rps is not None and c_rps is not None) else None,
        percent_delta=rps_pct, threshold_percent=rps_threshold,
    ))
    if rps_change == ChangeType.REGRESSED:
        findings.append(RegressionFinding(
            id=f"PERF-RPS-C{concurrency}", category="Performance", change=rps_change,
            severity=Severity.HIGH, confidence=1.0,
            title=f"Throughput regressed at concurrency={concurrency}: {b_rps:.1f} -> {c_rps:.1f} RPS ({rps_pct:.1f}%)",
            description=(
                f"RPS dropped by {abs(rps_pct):.1f}%, exceeding the configured tolerance of "
                f"{rps_threshold:.1f}% (rps_percent)."
            ),
            evidence=[Evidence("performance_metric", {
                "metric": "rps", "concurrency": concurrency, "baseline": b_rps, "current": c_rps,
                "percent_delta": round(rps_pct, 2), "threshold_percent": rps_threshold,
            })],
            recommendation=f"Investigate the throughput drop at concurrency={concurrency}.",
        ))

    # Error rate: lower is better, absolute (percentage-point) tolerance.
    b_err, c_err = b_metrics.get("error_rate_percent"), c_metrics.get("error_rate_percent")
    err_threshold = thresholds.get("error_rate_absolute")
    if b_err is None or c_err is None:
        err_change = ChangeType.NOT_COMPARABLE
        err_delta = None
    else:
        err_delta = c_err - b_err
        if err_threshold is not None and err_delta > err_threshold:
            err_change = ChangeType.REGRESSED
        elif err_threshold is not None and err_delta < -err_threshold:
            err_change = ChangeType.IMPROVED
        else:
            err_change = ChangeType.UNCHANGED
    metrics.append(MetricDelta(
        name=f"Error rate % (concurrency={concurrency})", baseline_value=b_err, current_value=c_err,
        direction="lower_is_better", change=err_change, absolute_delta=err_delta, threshold_absolute=err_threshold,
    ))
    if err_change == ChangeType.REGRESSED:
        findings.append(RegressionFinding(
            id=f"PERF-ERRRATE-C{concurrency}", category="Performance", change=err_change,
            severity=Severity.HIGH, confidence=1.0,
            title=f"Error rate regressed at concurrency={concurrency}: {b_err:.2f}% -> {c_err:.2f}%",
            description=(
                f"Error rate increased by {err_delta:.2f} percentage points, exceeding the configured "
                f"tolerance of {err_threshold:.2f} points (error_rate_absolute)."
            ),
            evidence=[Evidence("performance_metric", {
                "metric": "error_rate_percent", "concurrency": concurrency, "baseline": b_err, "current": c_err,
                "absolute_delta": round(err_delta, 3), "threshold_absolute": err_threshold,
            })],
            recommendation=f"Investigate the increased error rate at concurrency={concurrency}.",
        ))

    return metrics, findings


def compare_performance(
    baseline: PerformanceSnapshot | None, current: PerformanceSnapshot | None, thresholds: dict[str, float],
) -> RegressionCategory:
    if baseline is None or current is None:
        return RegressionCategory(
            name="Performance",
            status=AssessmentStatus.NOT_ASSESSED,
            summary="performance results are not available in the baseline and/or the current run",
            reason="baseline and current must both have run performance testing (--performance) to compare",
        )

    b_levels = {lv.concurrency: lv.metrics for lv in baseline.levels}
    c_levels = {lv.concurrency: lv.metrics for lv in current.levels}
    common = sorted(set(b_levels) & set(c_levels))
    only_baseline = sorted(set(b_levels) - set(c_levels))
    only_current = sorted(set(c_levels) - set(b_levels))

    if not common:
        return RegressionCategory(
            name="Performance", status=AssessmentStatus.NOT_ASSESSED,
            summary="no matching concurrency level exists in both the baseline and the current run",
            reason=f"baseline levels: {sorted(b_levels)}, current levels: {sorted(c_levels)}",
        )

    all_metrics: list[MetricDelta] = []
    all_findings: list[RegressionFinding] = []
    for concurrency in common:
        metrics, findings = _compare_level(concurrency, b_levels[concurrency], c_levels[concurrency], thresholds)
        all_metrics.extend(metrics)
        all_findings.extend(findings)

    status = status_from_findings(all_findings)
    summary = f"{len(common)} concurrency level(s) compared, {len(all_findings)} finding(s) raised"
    if only_baseline or only_current:
        summary += f" (levels only in baseline: {only_baseline}, only in current: {only_current})"

    return RegressionCategory(name="Performance", status=status, summary=summary, findings=all_findings, metrics=all_metrics)
