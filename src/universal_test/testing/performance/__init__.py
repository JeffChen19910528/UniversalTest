"""Technology-independent performance testing engine (Phase 4).

No HTTP-specific imports anywhere in this package — `PerformanceRunner`
takes a plain `Callable[[PerformanceRequest], PerformanceSample]` supplied
by an adapter (see `adapters/rest/performance_executor.py`).
"""

from universal_test.testing.performance.models import (
    ErrorType,
    LatencyStats,
    LevelResult,
    LoadProfile,
    LoadProfileType,
    PerformanceMetrics,
    PerformanceRequest,
    PerformanceResult,
    PerformanceSample,
    PerformanceThresholdResult,
)
from universal_test.testing.performance.planner import build_load_profile
from universal_test.testing.performance.runner import PerformanceExecutor, PerformanceRunner
from universal_test.testing.performance.serializers import (
    plan_to_text,
    result_to_json,
    result_to_markdown,
    result_to_text,
)

__all__ = [
    "ErrorType",
    "LatencyStats",
    "LevelResult",
    "LoadProfile",
    "LoadProfileType",
    "PerformanceMetrics",
    "PerformanceRequest",
    "PerformanceResult",
    "PerformanceSample",
    "PerformanceThresholdResult",
    "build_load_profile",
    "PerformanceExecutor",
    "PerformanceRunner",
    "plan_to_text",
    "result_to_json",
    "result_to_markdown",
    "result_to_text",
]
