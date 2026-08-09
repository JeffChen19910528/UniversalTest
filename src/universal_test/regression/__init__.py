"""Baseline storage and regression detection (Phase 7).

`snapshot.build_snapshot()` compacts an already-computed discovery/
functional/performance/database/assessment result into a `BaselineSnapshot`;
`baseline_store.save_baseline()`/`load_baseline()` persist/read it as JSON;
`engine.compare()` compares two snapshots into a `RegressionSummary`. This
package never re-discovers a project, re-executes a request, or reconnects
to a database — it only compares results the caller already produced,
mirroring `assessment/`'s "aggregate, don't recompute" contract.
"""

from universal_test.regression.baseline_store import load_baseline, save_baseline
from universal_test.regression.engine import compare
from universal_test.regression.models import (
    BaselineSnapshot,
    ChangeType,
    MetricDelta,
    RegressionCategory,
    RegressionFinding,
    RegressionSummary,
)
from universal_test.regression.snapshot import build_snapshot

__all__ = [
    "load_baseline",
    "save_baseline",
    "compare",
    "build_snapshot",
    "BaselineSnapshot",
    "ChangeType",
    "MetricDelta",
    "RegressionCategory",
    "RegressionFinding",
    "RegressionSummary",
]
