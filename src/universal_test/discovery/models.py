"""Normalized, framework-independent discovery data model (skill.md §6, this
project's Phase 2 brief). Every detection carries `confidence` +
`evidence` — never a bare assertion — per skill.md §4.1/§4.3.

These models are Core-facing (the assessment/reporting layers will consume
`ProjectModel`) but live under `discovery/` because they describe the
*discovery* domain specifically, distinct from the generic `TestCase`/
`TestResult` models in `core.models`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from universal_test.core.models.enums import DetectionConfidence
from universal_test.core.models.evidence import Evidence


def _evidence_list_to_dicts(evidence: list[Evidence]) -> list[dict[str, Any]]:
    return [e.to_dict() for e in evidence]


@dataclass(frozen=True)
class Detection:
    """Base shape shared by every kind of discovery finding."""

    name: str
    confidence: DetectionConfidence
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "confidence": self.confidence.value,
            "evidence": _evidence_list_to_dicts(self.evidence),
        }


@dataclass(frozen=True)
class LanguageDetection(Detection):
    file_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["file_count"] = self.file_count
        return d


@dataclass(frozen=True)
class ProjectTypeDetection(Detection):
    pass


@dataclass(frozen=True)
class FrameworkDetection(Detection):
    pass


@dataclass(frozen=True)
class BuildSystemDetection(Detection):
    pass


@dataclass(frozen=True)
class InfrastructureDetection(Detection):
    pass


@dataclass(frozen=True)
class DatabaseDetection(Detection):
    pass


@dataclass(frozen=True)
class ApiDetection(Detection):
    kind: str = "unknown"  # e.g. "openapi", "swagger", "graphql", "rest_config"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["kind"] = self.kind
        return d


@dataclass(frozen=True)
class TestFrameworkDetection(Detection):
    pass


@dataclass(frozen=True)
class SecretFinding:
    """A *potential* secret pattern match. The value is never captured — only
    its location and the pattern type that matched (skill.md §26, Phase 2 brief).
    Presence of a pattern is not itself a vulnerability finding; callers must
    not upgrade this to a security verdict.
    """

    file: str
    line: int
    pattern_type: str
    confidence: DetectionConfidence = DetectionConfidence.INFERRED

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "type": self.pattern_type,
            "value": "[REDACTED]",
            "confidence": self.confidence.value,
        }


@dataclass
class RepositoryInfo:
    is_git: bool = False
    root: str | None = None
    branch: str | None = None
    commit: str | None = None
    dirty: bool | None = None
    note: str | None = None  # e.g. "git executable not found" — UNKNOWN reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_git": self.is_git,
            "root": self.root,
            "branch": self.branch,
            "commit": self.commit,
            "dirty": self.dirty,
            "note": self.note,
        }


@dataclass
class ProjectModel:
    """Root normalized discovery result for one scanned project."""

    root_path: str
    tool_version: str
    scanned_at: str
    repository: RepositoryInfo = field(default_factory=RepositoryInfo)
    file_count: int = 0
    test_directories: list[str] = field(default_factory=list)
    languages: list[LanguageDetection] = field(default_factory=list)
    primary_language: str | None = None
    project_types: list[ProjectTypeDetection] = field(default_factory=list)
    frameworks: list[FrameworkDetection] = field(default_factory=list)
    build_systems: list[BuildSystemDetection] = field(default_factory=list)
    infrastructure: list[InfrastructureDetection] = field(default_factory=list)
    databases: list[DatabaseDetection] = field(default_factory=list)
    apis: list[ApiDetection] = field(default_factory=list)
    test_frameworks: list[TestFrameworkDetection] = field(default_factory=list)
    secrets: list[SecretFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # non-fatal issues encountered (skill.md §17 safety)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_path": self.root_path,
            "tool_version": self.tool_version,
            "scanned_at": self.scanned_at,
            "repository": self.repository.to_dict(),
            "file_count": self.file_count,
            "test_directories": self.test_directories,
            "languages": [x.to_dict() for x in self.languages],
            "primary_language": self.primary_language,
            "project_types": [x.to_dict() for x in self.project_types],
            "frameworks": [x.to_dict() for x in self.frameworks],
            "build_systems": [x.to_dict() for x in self.build_systems],
            "infrastructure": [x.to_dict() for x in self.infrastructure],
            "databases": [x.to_dict() for x in self.databases],
            "apis": [x.to_dict() for x in self.apis],
            "test_frameworks": [x.to_dict() for x in self.test_frameworks],
            "secrets": [x.to_dict() for x in self.secrets],
            "warnings": self.warnings,
        }
