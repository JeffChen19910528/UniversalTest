"""Builds a safety-bounded `LoadProfile` from user-facing parameters.

Every numeric knob has a hard ceiling here — independent of whatever the
CLI validates — so nothing that constructs a `LoadProfile` through this
module can end up with unbounded concurrency/requests/duration (Phase 4
brief §3: "不得無限制 concurrency / requests / duration").
"""

from __future__ import annotations

from universal_test.core.errors import ConfigurationError
from universal_test.testing.performance.models import LoadProfile, LoadProfileType

MAX_CONCURRENCY = 200
MAX_REQUESTS_PER_LEVEL = 2000
MAX_DURATION_SECONDS_PER_LEVEL = 300.0
MAX_LEVELS = 10

DEFAULT_REQUESTS_PER_LEVEL = 50
DEFAULT_LOAD_CONCURRENCY = [1, 10]
DEFAULT_STRESS_MAX_CONCURRENCY = 50
DEFAULT_STRESS_STEPS = [1, 2, 5, 10, 20, 50, 100, 200]
DEFAULT_STRESS_STOP_ERROR_RATE_PERCENT = 50.0


def _validate_concurrency_levels(levels: list[int]) -> None:
    if not levels:
        raise ConfigurationError("at least one concurrency level is required")
    if len(levels) > MAX_LEVELS:
        raise ConfigurationError(f"too many concurrency levels ({len(levels)}); maximum is {MAX_LEVELS}")
    for level in levels:
        if level < 1:
            raise ConfigurationError(f"concurrency must be >= 1, got {level}")
        if level > MAX_CONCURRENCY:
            raise ConfigurationError(f"concurrency {level} exceeds the maximum allowed ({MAX_CONCURRENCY})")


def _resolve_requests_and_duration(
    requests: int | None, duration: float | None, warnings: list[str],
) -> tuple[int | None, float | None]:
    if requests is not None and duration is not None:
        warnings.append("both --requests and --duration were given; --requests takes precedence")
        duration = None

    if requests is not None:
        if requests < 1:
            raise ConfigurationError(f"--requests must be >= 1, got {requests}")
        if requests > MAX_REQUESTS_PER_LEVEL:
            raise ConfigurationError(f"--requests {requests} exceeds the maximum allowed ({MAX_REQUESTS_PER_LEVEL})")
        return requests, None

    if duration is not None:
        if duration <= 0:
            raise ConfigurationError(f"--duration must be > 0, got {duration}")
        if duration > MAX_DURATION_SECONDS_PER_LEVEL:
            raise ConfigurationError(
                f"--duration {duration} exceeds the maximum allowed ({MAX_DURATION_SECONDS_PER_LEVEL}s)"
            )
        return None, duration

    return DEFAULT_REQUESTS_PER_LEVEL, None


def build_load_profile(
    profile_type: str,
    concurrency: list[int] | None = None,
    requests: int | None = None,
    duration: float | None = None,
    max_concurrency: int | None = None,
    stop_on_error_rate_percent: float | None = None,
    stop_on_p95_ms: float | None = None,
) -> tuple[LoadProfile, list[str]]:
    warnings: list[str] = []
    try:
        load_type = LoadProfileType(profile_type)
    except ValueError as exc:
        raise ConfigurationError(
            f"unknown performance profile {profile_type!r}; expected one of "
            f"{[t.value for t in LoadProfileType]}"
        ) from exc

    requests_per_level, duration_per_level = _resolve_requests_and_duration(requests, duration, warnings)

    if load_type == LoadProfileType.BASELINE:
        if concurrency and concurrency != [1]:
            warnings.append("--concurrency is ignored for the baseline profile (always concurrency=1)")
        levels = [1]

    elif load_type == LoadProfileType.LOAD:
        levels = concurrency or list(DEFAULT_LOAD_CONCURRENCY)

    elif load_type == LoadProfileType.STRESS:
        cap = max_concurrency or DEFAULT_STRESS_MAX_CONCURRENCY
        if cap > MAX_CONCURRENCY:
            raise ConfigurationError(f"--max-concurrency {cap} exceeds the maximum allowed ({MAX_CONCURRENCY})")
        if concurrency:
            levels = sorted(set(concurrency))
        else:
            levels = [s for s in DEFAULT_STRESS_STEPS if s <= cap]
            if not levels:
                levels = [min(cap, MAX_CONCURRENCY)]
        if stop_on_error_rate_percent is None and stop_on_p95_ms is None:
            stop_on_error_rate_percent = DEFAULT_STRESS_STOP_ERROR_RATE_PERCENT
            warnings.append(
                f"no stress stop condition given; defaulting to stop_on_error_rate_percent="
                f"{DEFAULT_STRESS_STOP_ERROR_RATE_PERCENT}"
            )

    elif load_type == LoadProfileType.CUSTOM:
        if not concurrency:
            raise ConfigurationError("the 'custom' profile requires an explicit --concurrency list")
        levels = concurrency

    else:  # pragma: no cover - exhaustive over LoadProfileType
        raise ConfigurationError(f"unhandled profile type {load_type!r}")

    _validate_concurrency_levels(levels)

    profile = LoadProfile(
        profile_type=load_type,
        concurrency_levels=levels,
        requests_per_level=requests_per_level,
        duration_seconds_per_level=duration_per_level,
        stop_on_error_rate_percent=stop_on_error_rate_percent,
        stop_on_p95_ms=stop_on_p95_ms,
    )
    return profile, warnings
