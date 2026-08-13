"""Unified assessment domain model (Phase 5).

Reuses existing enums rather than inventing new ones: `AssessmentStatus`
(`PASS/WARNING/FAIL/UNKNOWN/NOT_ASSESSED`, defined since Phase 1) for
category/finding-level status, and `Severity`
(`CRITICAL/HIGH/MEDIUM/LOW/INFO`, also Phase 1) for finding severity — status
and severity answer different questions and must never be conflated
(Phase 5 brief §6: "不要把 severity 與 status 混為一談").

Individual functional `TestResult`s still use `ResultStatus` (including
`SKIPPED`) as they always have; nothing here changes that — this module
only adds the category/project-level rollup shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from universal_test.core.models.enums import AssessmentStatus, FindingClassification, Severity
from universal_test.core.models.evidence import Evidence

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class AssessmentFinding:
    id: str
    category: str
    status: AssessmentStatus
    severity: Severity
    confidence: float
    title: str
    description: str
    evidence: list[Evidence] = field(default_factory=list)
    recommendation: str | None = None
    classification: FindingClassification = FindingClassification.INFORMATIONAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "status": self.status.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "title": self.title,
            "description": self.description,
            "evidence": [e.to_dict() for e in self.evidence],
            "recommendation": self.recommendation,
            "classification": self.classification.value,
        }


@dataclass
class AssessmentCategory:
    name: str
    status: AssessmentStatus
    summary: str
    reason: str | None = None  # required when status is NOT_ASSESSED/UNKNOWN
    findings: list[AssessmentFinding] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "summary": self.summary,
            "reason": self.reason,
            "findings": [f.to_dict() for f in self.findings],
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class CoverageItem:
    name: str
    percent: float | None  # None when a percentage isn't meaningful (kept out of arithmetic)
    reason: str | None = None  # why coverage is < 100% / not applicable

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "percent": self.percent, "reason": self.reason}


@dataclass
class UnassessedArea:
    name: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "reason": self.reason}


@dataclass
class ProjectAssessment:
    schema_version: str
    tool_version: str
    generated_at: str
    project_path: str
    target: str | None
    overall_status: AssessmentStatus
    categories: list[AssessmentCategory] = field(default_factory=list)
    coverage: list[CoverageItem] = field(default_factory=list)
    unassessed: list[UnassessedArea] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Additive semantic layer (Static Web Analysis & Assessment Semantics
    # Hardening brief §10/§11/§29) - distinct from `overall_status`, which
    # is unchanged and remains the sole input to Quality Gate/regression/
    # exit-code logic. `application_health`: "no confirmed defect" (PASS)
    # unless something that actually executed (Functional/Performance/
    # Browser Testing) showed a real problem - testability gaps/informational findings
    # never drag this down. `assessment_completeness`: "full" only when
    # every coverage item is 100% and nothing is in `unassessed`.
    application_health: AssessmentStatus = AssessmentStatus.PASS
    assessment_completeness: str = "partial"

    @property
    def findings(self) -> list[AssessmentFinding]:
        return [f for category in self.categories for f in category.findings]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tool_version": self.tool_version,
            "generated_at": self.generated_at,
            "project": {"path": self.project_path, "target": self.target},
            "overall_status": self.overall_status.value,
            "application_health": self.application_health.value,
            "assessment_completeness": self.assessment_completeness,
            "categories": [c.to_dict() for c in self.categories],
            "coverage": [c.to_dict() for c in self.coverage],
            "findings": [f.to_dict() for f in self.findings],
            "unassessed": [u.to_dict() for u in self.unassessed],
            "recommendations": self.recommendations,
            "limitations": self.limitations,
            "warnings": self.warnings,
        }
