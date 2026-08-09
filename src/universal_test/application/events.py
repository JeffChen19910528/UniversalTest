"""Structured progress events for GUI/CLI-agnostic consumers (Post-V1 GUI brief §11).

Core/CLI never depends on this module; only the GUI layer does. Stage names
are stable, machine-readable strings — the GUI translates them to
human-readable Traditional Chinese / English text, never the other way
around (brief §29: internal values stay English/machine-readable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STAGE_PROJECT_SCAN = "project_scan"
STAGE_FUNCTIONAL_TEST = "functional_test"
STAGE_PERFORMANCE_TEST = "performance_test"
STAGE_DATABASE_ASSESSMENT = "database_assessment"
STAGE_REGRESSION = "regression"
STAGE_ASSESSMENT = "assessment"
STAGE_REPORT_GENERATION = "report_generation"

PHASE_STARTED = "started"
PHASE_COMPLETED = "completed"
PHASE_SKIPPED = "skipped"
PHASE_FAILED = "failed"

# Fixed stage order the GUI renders as a checklist (brief §10). Regression is
# appended dynamically only when a baseline was provided.
STAGE_ORDER = [
    STAGE_PROJECT_SCAN,
    STAGE_FUNCTIONAL_TEST,
    STAGE_PERFORMANCE_TEST,
    STAGE_DATABASE_ASSESSMENT,
    STAGE_ASSESSMENT,
    STAGE_REPORT_GENERATION,
]


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    phase: str  # started | completed | skipped | failed
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """`"<stage>_<phase>"`, e.g. `"functional_test_started"` — matches the
        literal event names enumerated in the GUI brief §11.
        """
        return f"{self.stage}_{self.phase}"

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "phase": self.phase, "name": self.name, "message": self.message, "detail": self.detail}
