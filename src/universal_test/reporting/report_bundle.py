"""The input every Phase 5 report renderer consumes: the assessment plus the
raw per-phase results it was built from, so a report can show both the
rolled-up judgement (`assessment`) and the underlying evidence
(`model`/`run_result`/`perf_result`) side by side (Phase 5 brief §14's JSON
shape needs `discovery`/`functional`/`performance` as their own sections,
not just the assessment summary).
"""

from __future__ import annotations

from dataclasses import dataclass

from universal_test.core.orchestration.orchestrator import RunResult
from universal_test.discovery.models import ProjectModel
from universal_test.testing.performance.models import PerformanceResult
from universal_test.adapters.database.adapter import DatabaseDiscoveryResult
from universal_test.assessment.models import ProjectAssessment
from universal_test.regression.models import RegressionSummary
from universal_test.quality_gate.models import QualityGateResult


@dataclass
class AssessReportBundle:
    assessment: ProjectAssessment
    model: ProjectModel
    run_result: RunResult | None
    generated_count: int
    perf_result: PerformanceResult | None
    database_result: DatabaseDiscoveryResult | None = None
    regression: RegressionSummary | None = None
    quality_gate: QualityGateResult | None = None
