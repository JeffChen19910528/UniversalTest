"""Baseline + comparison domain model (Phase 7 brief §2/§3).

`BaselineSnapshot` is what `baseline save` persists to disk and what
`baseline compare`/`assess --baseline` load back — a compact, versioned,
technology-independent record of one assess run's evidence (discovery,
functional, performance, database, assessment summaries), never a bare
overall-status string (brief §2: "不要只保存 Overall Status"). Comparison
output (`RegressionSummary`) deliberately reuses the same
category/finding/evidence shape `assessment/models.py` already established,
plus `MetricDelta` for the numeric side of a comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.core.models.evidence import Evidence

SCHEMA_VERSION = "1.0"


class ChangeType(str, Enum):
    """How one comparable item changed between baseline and current.

    `ADDED`/`REMOVED` are never themselves a regression verdict (brief §7:
    "不要直接判定 removed test 為 regression") — they describe what happened,
    not whether it's good or bad.
    """

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    UNCHANGED = "unchanged"
    NOT_COMPARABLE = "not_comparable"


@dataclass(frozen=True)
class MetricDelta:
    """One numeric metric compared between baseline and current.

    `direction` records the metric's semantics so the comparator never
    treats "current > baseline" as regression uniformly (brief §9):
    `lower_is_better` (latency, error rate, timeouts), `higher_is_better`
    (RPS/throughput), or `neutral` (a count with no inherent "better").
    """

    name: str
    baseline_value: float | None
    current_value: float | None
    direction: str  # "lower_is_better" | "higher_is_better" | "neutral"
    change: ChangeType
    absolute_delta: float | None = None
    percent_delta: float | None = None
    threshold_percent: float | None = None
    threshold_absolute: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "baseline_value": self.baseline_value,
            "current_value": self.current_value,
            "direction": self.direction,
            "change": self.change.value,
            "absolute_delta": self.absolute_delta,
            "percent_delta": self.percent_delta,
            "threshold_percent": self.threshold_percent,
            "threshold_absolute": self.threshold_absolute,
        }


@dataclass(frozen=True)
class RegressionFinding:
    """Mirrors `assessment.models.AssessmentFinding`'s shape deliberately —
    same consumer contract (JSON/Markdown/HTML renderers, severity vocabulary)
    — but keyed by `change: ChangeType` instead of `status: AssessmentStatus`,
    since a regression finding answers "what changed", not "did this pass".
    """

    id: str
    category: str
    change: ChangeType
    severity: Severity
    confidence: float
    title: str
    description: str
    evidence: list[Evidence] = field(default_factory=list)
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "change": self.change.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "title": self.title,
            "description": self.description,
            "evidence": [e.to_dict() for e in self.evidence],
            "recommendation": self.recommendation,
        }


@dataclass
class RegressionCategory:
    name: str
    status: AssessmentStatus
    summary: str
    reason: str | None = None  # required when status is NOT_ASSESSED
    findings: list[RegressionFinding] = field(default_factory=list)
    metrics: list[MetricDelta] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "summary": self.summary,
            "reason": self.reason,
            "findings": [f.to_dict() for f in self.findings],
            "metrics": [m.to_dict() for m in self.metrics],
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class RegressionSummary:
    schema_version: str
    compatible: bool
    baseline_meta: dict[str, Any]
    current_meta: dict[str, Any]
    status: AssessmentStatus
    categories: list[RegressionCategory] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def findings(self) -> list[RegressionFinding]:
        return [f for category in self.categories for f in category.findings]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "compatible": self.compatible,
            "baseline": self.baseline_meta,
            "current": self.current_meta,
            "status": self.status.value,
            "categories": [c.to_dict() for c in self.categories],
            "findings": [f.to_dict() for f in self.findings],
            "warnings": self.warnings,
        }


# --- BaselineSnapshot: what `baseline save` persists -----------------------


@dataclass(frozen=True)
class SourceInfo:
    is_git: bool
    commit: str | None
    branch: str | None
    dirty: bool | None

    def to_dict(self) -> dict[str, Any]:
        return {"is_git": self.is_git, "commit": self.commit, "branch": self.branch, "dirty": self.dirty}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SourceInfo":
        return SourceInfo(
            is_git=bool(data.get("is_git", False)), commit=data.get("commit"),
            branch=data.get("branch"), dirty=data.get("dirty"),
        )


@dataclass(frozen=True)
class DiscoverySnapshot:
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    apis: list[str] = field(default_factory=list)
    test_frameworks: list[str] = field(default_factory=list)
    infrastructure: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "languages": self.languages, "frameworks": self.frameworks, "databases": self.databases,
            "apis": self.apis, "test_frameworks": self.test_frameworks, "infrastructure": self.infrastructure,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "DiscoverySnapshot":
        return DiscoverySnapshot(**{k: list(data.get(k, [])) for k in (
            "languages", "frameworks", "databases", "apis", "test_frameworks", "infrastructure"
        )})


@dataclass(frozen=True)
class FunctionalTestEntry:
    id: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status}


@dataclass(frozen=True)
class FunctionalSnapshot:
    target: str | None
    generated_count: int
    summary: dict[str, int]
    tests: list[FunctionalTestEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target, "generated_count": self.generated_count,
            "summary": self.summary, "tests": [t.to_dict() for t in self.tests],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "FunctionalSnapshot":
        return FunctionalSnapshot(
            target=data.get("target"), generated_count=int(data.get("generated_count", 0)),
            summary=dict(data.get("summary", {})),
            tests=[FunctionalTestEntry(id=t["id"], status=t["status"]) for t in data.get("tests", [])],
        )


@dataclass(frozen=True)
class PerformanceLevelSnapshot:
    concurrency: int
    metrics: dict[str, float | int | None]

    def to_dict(self) -> dict[str, Any]:
        return {"concurrency": self.concurrency, "metrics": self.metrics}


@dataclass(frozen=True)
class PerformanceSnapshot:
    target: str | None
    endpoint: str | None
    levels: list[PerformanceLevelSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"target": self.target, "endpoint": self.endpoint, "levels": [lv.to_dict() for lv in self.levels]}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "PerformanceSnapshot":
        return PerformanceSnapshot(
            target=data.get("target"), endpoint=data.get("endpoint"),
            levels=[
                PerformanceLevelSnapshot(concurrency=lv["concurrency"], metrics=dict(lv["metrics"]))
                for lv in data.get("levels", [])
            ],
        )


@dataclass(frozen=True)
class DatabaseTableSnapshot:
    schema: str
    name: str
    columns: list[str]
    primary_key: list[str] | None
    foreign_key_count: int
    index_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "name": self.name, "columns": self.columns,
            "primary_key": self.primary_key, "foreign_key_count": self.foreign_key_count,
            "index_count": self.index_count,
        }

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "DatabaseTableSnapshot":
        return DatabaseTableSnapshot(
            schema=data["schema"], name=data["name"], columns=list(data.get("columns", [])),
            primary_key=data.get("primary_key"), foreign_key_count=int(data.get("foreign_key_count", 0)),
            index_count=int(data.get("index_count", 0)),
        )


@dataclass(frozen=True)
class DatabaseSnapshot:
    engine: str
    database_name: str | None
    summary: dict[str, int]
    tables: list[DatabaseTableSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine, "database_name": self.database_name,
            "summary": self.summary, "tables": [t.to_dict() for t in self.tables],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "DatabaseSnapshot":
        return DatabaseSnapshot(
            engine=data["engine"], database_name=data.get("database_name"),
            summary=dict(data.get("summary", {})),
            tables=[DatabaseTableSnapshot.from_dict(t) for t in data.get("tables", [])],
        )


@dataclass(frozen=True)
class AssessmentCategorySnapshot:
    name: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status}


@dataclass(frozen=True)
class AssessmentSnapshot:
    overall_status: str
    categories: list[AssessmentCategorySnapshot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"overall_status": self.overall_status, "categories": [c.to_dict() for c in self.categories]}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "AssessmentSnapshot":
        return AssessmentSnapshot(
            overall_status=data["overall_status"],
            categories=[AssessmentCategorySnapshot(name=c["name"], status=c["status"]) for c in data.get("categories", [])],
        )


@dataclass(frozen=True)
class BaselineSnapshot:
    schema_version: str
    tool_version: str
    generated_at: str
    project_path: str
    source: SourceInfo
    discovery: DiscoverySnapshot
    functional: FunctionalSnapshot | None
    performance: PerformanceSnapshot | None
    database: DatabaseSnapshot | None
    assessment: AssessmentSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tool_version": self.tool_version,
            "generated_at": self.generated_at,
            "project": {"path": self.project_path},
            "source": self.source.to_dict(),
            "discovery": self.discovery.to_dict(),
            "functional": self.functional.to_dict() if self.functional else None,
            "performance": self.performance.to_dict() if self.performance else None,
            "database": self.database.to_dict() if self.database else None,
            "assessment": self.assessment.to_dict(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "BaselineSnapshot":
        return BaselineSnapshot(
            schema_version=data["schema_version"],
            tool_version=data.get("tool_version", "unknown"),
            generated_at=data.get("generated_at", "unknown"),
            project_path=data.get("project", {}).get("path", "unknown"),
            source=SourceInfo.from_dict(data.get("source", {})),
            discovery=DiscoverySnapshot.from_dict(data.get("discovery", {})),
            functional=FunctionalSnapshot.from_dict(data["functional"]) if data.get("functional") else None,
            performance=PerformanceSnapshot.from_dict(data["performance"]) if data.get("performance") else None,
            database=DatabaseSnapshot.from_dict(data["database"]) if data.get("database") else None,
            assessment=AssessmentSnapshot.from_dict(data.get("assessment", {"overall_status": "unknown", "categories": []})),
        )
