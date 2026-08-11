"""Frontend adapter: discovery + testability assessment only.

Mirrors `adapters/rest/adapter.py`'s shape for architectural completeness
(ARCHITECTURE.md §7's detect/describe/discover/generate_tests/execute/
collect_metrics contract) - see that module's docstring for why the class
wrapper exists alongside free functions.

This adapter deliberately implements only discovery in this version.
`generate_tests`/`execute` are honest stubs, not silent no-ops: actual
browser/UI test generation and execution is reserved for a future Browser
Adapter (Frontend Adapter brief §3/§32/§36) and must not be implied here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from universal_test.core.models.test_spec import TestCase
from universal_test.core.orchestration.orchestrator import RunResult
from universal_test.discovery import filesystem, framework, frontend, manifests
from universal_test.discovery.models import FrontendInfo

NOT_IMPLEMENTED_MESSAGE = (
    "Browser/UI test execution is not implemented in this version - "
    "reserved for a future Browser Adapter. Frontend analysis (discovery + "
    "testability assessment) is available via detect()/discover()."
)


@dataclass(frozen=True)
class AdapterInfo:
    name: str
    version: str
    capabilities: list[str]


def discover(project_path: str | Path) -> FrontendInfo:
    root = Path(project_path).resolve()
    files = filesystem.walk(root)
    bundle = manifests.load_manifests(root, files)
    frameworks = framework.detect_frameworks(files, bundle)
    return frontend.detect_frontend(files, bundle, frameworks)


class FrontendAdapter:
    """Generic adapter-contract wrapper around `discover()` above."""

    info = AdapterInfo(
        name="frontend", version="1", capabilities=["discovery", "testability_assessment"],
    )

    def detect(self, project_path: str | Path) -> bool:
        return discover(project_path).detected

    def describe(self) -> AdapterInfo:
        return self.info

    def discover(self, project_path: str | Path) -> FrontendInfo:
        return discover(project_path)

    def generate_tests(self, frontend_info: FrontendInfo) -> list[TestCase]:
        """Not implemented in this version - browser/UI test generation is a
        future Browser Adapter capability. Returns an empty list rather than
        raising, since "zero tests generated" is itself an honest, safe
        answer for a capability that doesn't exist yet.
        """
        return []

    def execute(self, test_cases: list[TestCase], **kwargs: object) -> RunResult:
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)

    def collect_metrics(self, run_result: RunResult) -> dict:
        return {}
