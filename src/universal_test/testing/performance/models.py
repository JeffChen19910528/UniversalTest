"""Technology-independent performance-testing domain model.

No `httpx` (or any HTTP-specific) import anywhere in this module — Core-ish
technology independence extends to `testing/` too (skill.md §2, Phase 4
brief §1: "Core 不應依賴 httpx"). HTTP execution is supplied externally as a
plain callable; see `runner.py` and `adapters/rest/performance_executor.py`.

`PerformanceSample`/`PerformanceMetrics` deliberately never carry request or
response headers/bodies — only status/timing/error-classification — so
there is no secret-leakage surface in this layer at all, by construction
rather than by redaction (Phase 4 brief §14).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from universal_test.core.models.enums import AssessmentStatus


class LoadProfileType(str, Enum):
    BASELINE = "baseline"
    LOAD = "load"
    STRESS = "stress"
    CUSTOM = "custom"


class ErrorType(str, Enum):
    NONE = "none"
    HTTP_ERROR = "http_error"       # transport succeeded, status >= 400
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"  # connection refused/reset/DNS/etc.
    TARGET_ERROR = "target_error"    # other request-layer failure


@dataclass(frozen=True)
class PerformanceRequest:
    """One fully-resolved, deterministic request to repeat many times.

    Built once per performance run (not regenerated per request) so every
    sample is comparable — see Phase 4 brief §7.
    """

    method: str
    path: str  # path parameters already substituted
    query_params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    json_body: Any = None
    content_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        # headers are never rendered (may carry auth); everything else is
        # already-generated request *shape*, not a secret.
        return {
            "method": self.method, "path": self.path,
            "query_params": self.query_params, "has_body": self.json_body is not None,
        }


@dataclass(frozen=True)
class PerformanceSample:
    start_time: float  # epoch seconds
    duration_ms: float
    status_code: int | None
    error_type: ErrorType = ErrorType.NONE

    @property
    def success(self) -> bool:
        return self.error_type == ErrorType.NONE and self.status_code is not None and self.status_code < 400


@dataclass(frozen=True)
class LatencyStats:
    min_ms: float
    mean_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float

    def to_dict(self) -> dict[str, float]:
        return {
            "min": self.min_ms, "mean": self.mean_ms, "p50": self.p50_ms,
            "p90": self.p90_ms, "p95": self.p95_ms, "p99": self.p99_ms, "max": self.max_ms,
        }


@dataclass(frozen=True)
class PerformanceMetrics:
    total_requests: int
    successful_requests: int
    failed_requests: int
    timeout_count: int
    network_error_count: int
    http_error_count: int
    duration_seconds: float
    rps: float
    successful_rps: float
    latency: LatencyStats | None  # None only when total_requests == 0

    @property
    def error_rate_percent(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate_percent": round(self.error_rate_percent, 3),
            "timeout_count": self.timeout_count,
            "network_error_count": self.network_error_count,
            "http_error_count": self.http_error_count,
            "duration_seconds": round(self.duration_seconds, 3),
            "rps": round(self.rps, 3),
            "successful_rps": round(self.successful_rps, 3),
            "latency_ms": self.latency.to_dict() if self.latency else None,
        }


@dataclass(frozen=True)
class PerformanceThresholdResult:
    name: str
    limit: float
    observed: float | None
    status: AssessmentStatus

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "limit": self.limit, "observed": self.observed, "status": self.status.value}


@dataclass
class LevelResult:
    concurrency: int
    metrics: PerformanceMetrics
    thresholds: list[PerformanceThresholdResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "concurrency": self.concurrency,
            "metrics": self.metrics.to_dict(),
            "thresholds": [t.to_dict() for t in self.thresholds],
        }


@dataclass
class LoadProfile:
    profile_type: LoadProfileType
    concurrency_levels: list[int]
    requests_per_level: int | None = None
    duration_seconds_per_level: float | None = None
    # stress-only stopping conditions (Phase 4 brief §5); ignored by other profile types
    stop_on_error_rate_percent: float | None = None
    stop_on_p95_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_type": self.profile_type.value,
            "concurrency_levels": self.concurrency_levels,
            "requests_per_level": self.requests_per_level,
            "duration_seconds_per_level": self.duration_seconds_per_level,
            "stop_on_error_rate_percent": self.stop_on_error_rate_percent,
            "stop_on_p95_ms": self.stop_on_p95_ms,
        }

    def estimated_total_requests(self) -> int | None:
        if self.requests_per_level is None:
            return None
        return self.requests_per_level * len(self.concurrency_levels)


@dataclass
class PerformanceResult:
    target: str
    endpoint: str  # "METHOD /path", informational
    profile: LoadProfile
    levels: list[LevelResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stopped_early: bool = False
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "endpoint": self.endpoint,
            "profile": self.profile.to_dict(),
            "levels": [level.to_dict() for level in self.levels],
            "warnings": self.warnings,
            "stopped_early": self.stopped_early,
            "stop_reason": self.stop_reason,
        }
