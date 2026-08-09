"""Quality Gate domain model (Phase 8 brief §1) — technology-independent,
no GitHub/GitLab/Jenkins/Azure logic anywhere in this module or package.
Everything CI-provider-specific lives in `examples/ci/*` templates, which
only ever shell out to the plain `universal-test` CLI.

```
Assessment + Regression -> QualityGate Engine -> ExitCode -> CI Adapter/Template
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


class QualityGateStatus(str, Enum):
    """Outcome of one Quality Gate evaluation.

    `ERROR` is distinct from `FAIL`: it means execution itself couldn't
    produce a trustworthy quality signal (e.g. the target was completely
    unreachable) — brief §18's explicit "Target unavailable 應該是
    execution/infrastructure error，而不是 Quality regression" rule. `FAIL`
    means execution worked and something it measured crossed a configured
    threshold.
    """

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    ERROR = "error"


class ExitCode(IntEnum):
    """The CLI exit-code contract (Phase 8 brief §4) — stable across
    releases; document any future addition here, never repurpose a value.
    """

    QUALITY_GATE_PASSED = 0
    QUALITY_GATE_FAILED = 1
    CONFIGURATION_ERROR = 2
    EXECUTION_ERROR = 3


_STATUS_EXIT_CODE = {
    QualityGateStatus.PASS: ExitCode.QUALITY_GATE_PASSED,
    QualityGateStatus.WARNING: ExitCode.QUALITY_GATE_PASSED,  # a warning does not block a build
    QualityGateStatus.FAIL: ExitCode.QUALITY_GATE_FAILED,
    QualityGateStatus.ERROR: ExitCode.EXECUTION_ERROR,
}


def exit_code_for(status: QualityGateStatus) -> ExitCode:
    return _STATUS_EXIT_CODE[status]


_DEFAULT_FAIL_ON: dict[str, list[str]] = {
    "regression": ["critical", "high"],
    "functional": ["failure"],
    "performance": ["threshold"],
}
_DEFAULT_WARN_ON: dict[str, list[str]] = {
    "regression": ["medium"],
    "database": ["schema_change"],
    "discovery": ["change"],
}


@dataclass(frozen=True)
class QualityGatePolicy:
    """The pure evaluation input — deliberately decoupled from
    `core.configuration.config.QualityGateConfig` (which only exists to load
    this shape from `universal-test.yaml`), the same separation
    `regression/performance_compare.py` already has from `RegressionConfig`.
    `fail_on`/`warn_on` are `category -> [values]` mappings; a value not
    listed in either is neither a failure nor a warning (brief §9).
    """

    fail_on: dict[str, list[str]] = field(default_factory=lambda: {k: list(v) for k, v in _DEFAULT_FAIL_ON.items()})
    warn_on: dict[str, list[str]] = field(default_factory=lambda: {k: list(v) for k, v in _DEFAULT_WARN_ON.items()})

    def classify(self, category: str, value: str) -> str | None:
        """Returns "fail" | "warning" | None for one (category, value) signal."""
        if value in self.fail_on.get(category, []):
            return "fail"
        if value in self.warn_on.get(category, []):
            return "warning"
        return None


DEFAULT_POLICY = QualityGatePolicy()


@dataclass(frozen=True)
class QualityGateRule:
    """One concrete signal collected from the assessment/regression results,
    prior to being classified against a `QualityGatePolicy` (e.g.
    category="regression", value="high"). Collection (what happened) and
    classification (does policy care) are deliberately separate steps —
    `signals.py` only does the former, `engine.py` the latter — so each is
    independently testable.
    """

    category: str
    value: str
    id: str | None
    title: str
    description: str
    is_infra_signal: bool = False  # True for a total-transport-wipeout signal (brief §18)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category, "value": self.value, "id": self.id,
            "title": self.title, "description": self.description,
        }


@dataclass(frozen=True)
class QualityGateFinding:
    """A `QualityGateRule` that policy actually classified as fail/warning —
    what actually shows up in the gate's report, as opposed to every signal
    that was merely collected."""

    rule: str  # "<category>.<value>", e.g. "regression.high"
    level: str  # "fail" | "warning"
    id: str | None
    title: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule, "level": self.level, "id": self.id,
            "title": self.title, "description": self.description,
        }


@dataclass
class QualityGateResult:
    status: QualityGateStatus
    exit_code: int
    findings: list[QualityGateFinding] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None  # populated when status == ERROR

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "exit_code": self.exit_code,
            "reason": self.reason,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
        }
