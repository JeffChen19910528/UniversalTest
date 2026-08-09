"""Assessment engine: aggregates discovery/functional/performance results
into one evidence-based `ProjectAssessment` (Phase 5).

Deterministic only — no scoring, no AI. See `rules.py` for the overall-status
rule and `engine.py::build_assessment()` for the orchestration entry point.
"""

from universal_test.assessment.engine import build_assessment
from universal_test.assessment.models import (
    AssessmentCategory,
    AssessmentFinding,
    CoverageItem,
    ProjectAssessment,
    UnassessedArea,
)

__all__ = [
    "build_assessment",
    "AssessmentCategory",
    "AssessmentFinding",
    "CoverageItem",
    "ProjectAssessment",
    "UnassessedArea",
]
