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
from enum import Enum
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


class FrontendType(str, Enum):
    """Broad frontend classification (Static Web Analysis brief §3/§5).
    `STATIC_WEB` and `FRAMEWORK_WEB` are not exclusive of "has a backend" —
    `FULL_STACK_WEB` takes precedence over both when backend framework
    evidence is also present in the same project (brief §26: framework
    evidence has precedence over static-HTML evidence, never the reverse).
    """

    STATIC_WEB = "static_web"
    FRAMEWORK_WEB = "framework_web"
    FULL_STACK_WEB = "full_stack_web"
    UNKNOWN_WEB = "unknown_web"


@dataclass(frozen=True)
class FrontendSignal:
    """A bounded-heuristic evidence signal (routes/components/forms/API
    clients). `note` always states the scan bound so callers never present
    this as exhaustive coverage (skill.md §4.1, Frontend Adapter brief §12/§13:
    "detected route evidence", never "all routes").
    """

    status: DetectionConfidence
    count: int
    evidence: list[Evidence] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "count": self.count,
            "evidence": _evidence_list_to_dicts(self.evidence),
            "note": self.note,
        }


@dataclass
class FrontendInfo:
    """Normalized frontend/web-application discovery evidence (Frontend
    Adapter brief §11). Framework/language/build-system/test-framework facts
    are *not* duplicated here — they already live on `ProjectModel.frameworks`
    / `.languages` / `.build_systems` / `.test_frameworks`; this model only
    carries evidence kinds that have no existing home.
    """

    detected: bool = False
    detection_confidence: DetectionConfidence = DetectionConfidence.UNKNOWN
    detection_evidence: list[Evidence] = field(default_factory=list)
    routes: FrontendSignal = field(
        default_factory=lambda: FrontendSignal(DetectionConfidence.UNKNOWN, 0, [], "not scanned")
    )
    components: FrontendSignal = field(
        default_factory=lambda: FrontendSignal(DetectionConfidence.UNKNOWN, 0, [], "not scanned")
    )
    forms: FrontendSignal = field(
        default_factory=lambda: FrontendSignal(DetectionConfidence.UNKNOWN, 0, [], "not scanned")
    )
    api_clients: FrontendSignal = field(
        default_factory=lambda: FrontendSignal(DetectionConfidence.UNKNOWN, 0, [], "not scanned")
    )
    build_scripts: dict[str, str] = field(default_factory=dict)
    test_scripts: dict[str, str] = field(default_factory=dict)
    frontend_test_directories: list[str] = field(default_factory=list)
    env_public_keys: list[str] = field(default_factory=list)

    # Static Web Analysis brief §3-§20: broad classification + HTML/CSS/JS
    # structural evidence, so a plain static site is a first-class frontend
    # type, not something only manifest/config-driven frameworks get.
    frontend_type: FrontendType | None = None
    entry_points: list[str] = field(default_factory=list)
    web_roots: list[str] = field(default_factory=list)
    html_page_count: int = 0
    css_file_count: int = 0
    js_file_count: int = 0
    css_frameworks: list[str] = field(default_factory=list)
    responsive: FrontendSignal = field(
        default_factory=lambda: FrontendSignal(DetectionConfidence.UNKNOWN, 0, [], "not scanned")
    )
    auth_ui: FrontendSignal = field(
        default_factory=lambda: FrontendSignal(DetectionConfidence.UNKNOWN, 0, [], "not scanned")
    )

    # Static-web capability evidence (Static Web Analysis & Assessment
    # Semantics Hardening brief §14-§21): a single rich HTML file (heavy
    # inline CSS/JS, browser API usage) must not be misreported as "CSS: 0,
    # JavaScript: 0" just because those bytes never live in a separate
    # .css/.js file - `inline_*_count` is additive to, never a replacement
    # for, `css_file_count`/`js_file_count` (external files).
    inline_css_count: int = 0
    inline_js_count: int = 0
    interactive_ui: FrontendSignal = field(
        default_factory=lambda: FrontendSignal(DetectionConfidence.UNKNOWN, 0, [], "not scanned")
    )
    browser_apis: list[str] = field(default_factory=list)
    application_pattern: str | None = None
    external_resources: list[str] = field(default_factory=list)
    csp: FrontendSignal = field(
        default_factory=lambda: FrontendSignal(DetectionConfidence.UNKNOWN, 0, [], "not scanned")
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "detection_confidence": self.detection_confidence.value,
            "detection_evidence": _evidence_list_to_dicts(self.detection_evidence),
            "frontend_type": self.frontend_type.value if self.frontend_type else None,
            "entry_points": self.entry_points,
            "web_roots": self.web_roots,
            "html_page_count": self.html_page_count,
            "css_file_count": self.css_file_count,
            "js_file_count": self.js_file_count,
            "css_frameworks": self.css_frameworks,
            "routes": self.routes.to_dict(),
            "components": self.components.to_dict(),
            "forms": self.forms.to_dict(),
            "api_clients": self.api_clients.to_dict(),
            "responsive": self.responsive.to_dict(),
            "auth_ui": self.auth_ui.to_dict(),
            "inline_css_count": self.inline_css_count,
            "inline_js_count": self.inline_js_count,
            "interactive_ui": self.interactive_ui.to_dict(),
            "browser_apis": self.browser_apis,
            "application_pattern": self.application_pattern,
            "external_resources": self.external_resources,
            "csp": self.csp.to_dict(),
            "build_scripts": self.build_scripts,
            "test_scripts": self.test_scripts,
            "frontend_test_directories": self.frontend_test_directories,
            "env_public_keys": self.env_public_keys,
        }


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
    frontend: FrontendInfo = field(default_factory=FrontendInfo)
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
            "frontend": self.frontend.to_dict(),
            "secrets": [x.to_dict() for x in self.secrets],
            "warnings": self.warnings,
        }
