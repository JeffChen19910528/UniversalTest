"""Result models: AssertionResult (single check), TestResult (single test case),
Finding (assessment-category rollup). Shape matches skill.md §4.3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from universal_test.core.models.enums import AssessmentStatus, ResultStatus, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.core.models.test_spec import AssertionSpec


@dataclass(frozen=True)
class AssertionResult:
    assertion: AssertionSpec
    passed: bool
    message: str
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assertion": {"type": self.assertion.type, **self.assertion.params},
            "passed": self.passed,
            "message": self.message,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass(frozen=True)
class TestResult:
    id: str
    category: str
    status: ResultStatus
    message: str
    severity: Severity = Severity.INFO
    confidence: float = 1.0
    evidence: list[Evidence] = field(default_factory=list)
    recommendation: str | None = None
    assertion_results: list[AssertionResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "status": self.status.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "message": self.message,
            "recommendation": self.recommendation,
            "assertion_results": [a.to_dict() for a in self.assertion_results],
        }


@dataclass(frozen=True)
class Finding:
    """Category-level rollup consumed by report generators (skill.md §12)."""

    category: str
    status: AssessmentStatus
    summary: str
    evidence: list[Evidence] = field(default_factory=list)
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "status": self.status.value,
            "summary": self.summary,
            "evidence": [e.to_dict() for e in self.evidence],
            "recommendation": self.recommendation,
        }
