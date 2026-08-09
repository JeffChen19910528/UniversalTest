"""Rendering for the performance test plan (dry-run/confirmation) and results.

Lives alongside the model it renders (`PerformanceResult`), same convention
as `discovery/serializers.py` and `adapters/rest/serializers.py` — not the
general Phase 5 report generator.
"""

from __future__ import annotations

import json

from universal_test.testing.performance.models import LoadProfile, PerformanceResult


def plan_to_text(target: str, endpoint_label: str, profile: LoadProfile, thresholds: dict[str, float] | None = None) -> str:
    lines = ["Performance Test Plan", "=" * 22, "", "Target:", target, "", "Endpoint:", endpoint_label, ""]
    lines += ["Profile:", profile.profile_type.value, ""]
    lines += ["Concurrency:", ", ".join(str(c) for c in profile.concurrency_levels), ""]

    if profile.requests_per_level is not None:
        lines += ["Requests per level:", str(profile.requests_per_level), ""]
        estimated = profile.estimated_total_requests()
        lines += ["Estimated requests:", str(estimated), ""]
    else:
        lines += ["Duration per level (seconds):", str(profile.duration_seconds_per_level), ""]
        total_duration = (profile.duration_seconds_per_level or 0) * len(profile.concurrency_levels)
        lines += ["Estimated duration (seconds):", str(total_duration), ""]

    lines += ["Estimated maximum concurrency:", str(max(profile.concurrency_levels)), ""]

    if profile.stop_on_error_rate_percent is not None or profile.stop_on_p95_ms is not None:
        lines.append("Stress stop conditions:")
        if profile.stop_on_error_rate_percent is not None:
            lines.append(f"  error_rate_percent > {profile.stop_on_error_rate_percent}")
        if profile.stop_on_p95_ms is not None:
            lines.append(f"  p95_ms > {profile.stop_on_p95_ms}")
        lines.append("")

    if thresholds:
        lines.append("Thresholds:")
        for name, limit in thresholds.items():
            lines.append(f"  {name}: {limit}")
        lines.append("")

    return "\n".join(lines)


def result_to_text(result: PerformanceResult) -> str:
    lines = [
        f"Target: {result.target}",
        f"Endpoint: {result.endpoint}",
        f"Profile: {result.profile.profile_type.value}",
        "",
    ]
    for level in result.levels:
        m = level.metrics
        lines.append(f"Concurrency: {level.concurrency}")
        lines.append(f"  Total requests:      {m.total_requests}")
        lines.append(f"  Successful:          {m.successful_requests}")
        lines.append(f"  Failed:              {m.failed_requests}")
        lines.append(f"  Error rate:          {m.error_rate_percent:.2f}%")
        lines.append(f"  Timeouts:            {m.timeout_count}")
        lines.append(f"  Network errors:      {m.network_error_count}")
        lines.append(f"  HTTP errors:         {m.http_error_count}")
        lines.append(f"  Duration:            {m.duration_seconds:.2f}s")
        lines.append(f"  RPS (total):         {m.rps:.2f}")
        lines.append(f"  RPS (successful):    {m.successful_rps:.2f}")
        if m.latency:
            lines.append(
                f"  Latency ms:          min={m.latency.min_ms:.1f} "
                f"p50={m.latency.p50_ms:.1f} p90={m.latency.p90_ms:.1f} "
                f"p95={m.latency.p95_ms:.1f} p99={m.latency.p99_ms:.1f} max={m.latency.max_ms:.1f}"
            )
        else:
            lines.append("  Latency ms:          UNKNOWN (no samples)")
        if level.thresholds:
            lines.append("  Thresholds:")
            for t in level.thresholds:
                observed = "UNKNOWN" if t.observed is None else f"{t.observed:.2f}"
                lines.append(f"    {t.name} (limit {t.limit}): observed={observed} -> {t.status.value.upper()}")
        lines.append("")

    if result.stopped_early:
        lines.append(f"Stopped early: {result.stop_reason}")
        lines.append("")
    if result.warnings:
        lines.append("Warnings")
        lines.append("-" * 8)
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


def result_to_json(result: PerformanceResult) -> str:
    return json.dumps(result.to_dict(), indent=2)


def result_to_markdown(result: PerformanceResult) -> str:
    lines = [
        "# Performance Test Result", "",
        f"- Target: {result.target}",
        f"- Endpoint: {result.endpoint}",
        f"- Profile: {result.profile.profile_type.value}",
        "",
        "| Concurrency | Total | Success | Failed | Error % | RPS | P50 | P90 | P95 | P99 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for level in result.levels:
        m = level.metrics
        lat = m.latency
        p50 = f"{lat.p50_ms:.1f}" if lat else "N/A"
        p90 = f"{lat.p90_ms:.1f}" if lat else "N/A"
        p95 = f"{lat.p95_ms:.1f}" if lat else "N/A"
        p99 = f"{lat.p99_ms:.1f}" if lat else "N/A"
        lines.append(
            f"| {level.concurrency} | {m.total_requests} | {m.successful_requests} | {m.failed_requests} | "
            f"{m.error_rate_percent:.2f} | {m.rps:.2f} | {p50} | {p90} | {p95} | {p99} |"
        )
    lines.append("")

    if any(level.thresholds for level in result.levels):
        lines.append("## Thresholds")
        lines.append("")
        lines.append("| Concurrency | Threshold | Limit | Observed | Status |")
        lines.append("|---|---|---|---|---|")
        for level in result.levels:
            for t in level.thresholds:
                observed = "UNKNOWN" if t.observed is None else f"{t.observed:.2f}"
                lines.append(f"| {level.concurrency} | {t.name} | {t.limit} | {observed} | {t.status.value} |")
        lines.append("")

    if result.stopped_early:
        lines.append(f"> Stopped early: {result.stop_reason}")
        lines.append("")
    if result.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)
