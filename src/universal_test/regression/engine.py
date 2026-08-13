"""Orchestrates every category comparator into one `RegressionSummary`
(Phase 7 brief). Only ever compares two already-built `BaselineSnapshot`s —
never re-runs discovery/functional/performance/database itself (that
happens once, upstream, in `cli/main.py`'s shared pipeline, exactly like
`assessment/engine.py::build_assessment()` only aggregates Phase 2-4
results rather than re-computing them).
"""

from __future__ import annotations

from universal_test.assessment.rules import compute_overall_status
from universal_test.regression.assessment_compare import compare_assessment
from universal_test.regression.browser_compare import compare_browser
from universal_test.regression.database_compare import compare_database
from universal_test.regression.discovery_compare import compare_discovery
from universal_test.regression.functional_compare import compare_functional
from universal_test.regression.models import SCHEMA_VERSION, BaselineSnapshot, RegressionSummary
from universal_test.regression.performance_compare import compare_performance
from universal_test.regression.scenario_compare import compare_scenario


def compare(
    baseline: BaselineSnapshot, current: BaselineSnapshot, *, performance_thresholds: dict[str, float],
) -> RegressionSummary:
    categories = [
        compare_functional(baseline.functional, current.functional),
        compare_performance(baseline.performance, current.performance, performance_thresholds),
        compare_database(baseline.database, current.database),
        compare_discovery(baseline.discovery, current.discovery),
        compare_assessment(baseline.assessment, current.assessment),
        compare_browser(baseline.browser, current.browser),
        compare_scenario(baseline.scenario, current.scenario),
    ]

    warnings = []
    if baseline.tool_version != current.tool_version:
        warnings.append(
            f"baseline was captured with tool version {baseline.tool_version}, "
            f"current run is tool version {current.tool_version} - comparison proceeds, but be aware "
            "of behavior differences between versions"
        )

    overall = compute_overall_status([c.status for c in categories])
    return RegressionSummary(
        schema_version=SCHEMA_VERSION,
        compatible=True,
        baseline_meta={
            "tool_version": baseline.tool_version, "generated_at": baseline.generated_at,
            "project_path": baseline.project_path, "source": baseline.source.to_dict(),
        },
        current_meta={
            "tool_version": current.tool_version, "generated_at": current.generated_at,
            "project_path": current.project_path, "source": current.source.to_dict(),
        },
        status=overall,
        categories=categories,
        warnings=warnings,
    )
