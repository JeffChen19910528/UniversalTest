"""Deterministic, CI-provider-independent Quality Gate (Phase 8).

`evaluate()` is the single entry point: takes an already-built
`ProjectAssessment` + optional `RegressionSummary` + `QualityGatePolicy`,
returns a `QualityGateResult` carrying a stable `ExitCode`. No GitHub
Actions/GitLab/Jenkins/Azure-specific logic exists anywhere in this
package — see `examples/ci/*` for provider templates, which only ever
shell out to the plain `universal-test` CLI.
"""

from universal_test.quality_gate.engine import evaluate
from universal_test.quality_gate.models import (
    DEFAULT_POLICY,
    ExitCode,
    QualityGateFinding,
    QualityGatePolicy,
    QualityGateResult,
    QualityGateRule,
    QualityGateStatus,
    exit_code_for,
)
from universal_test.quality_gate.ci_detection import detect_ci_environment

__all__ = [
    "evaluate",
    "DEFAULT_POLICY",
    "ExitCode",
    "QualityGateFinding",
    "QualityGatePolicy",
    "QualityGateResult",
    "QualityGateRule",
    "QualityGateStatus",
    "exit_code_for",
    "detect_ci_environment",
]
