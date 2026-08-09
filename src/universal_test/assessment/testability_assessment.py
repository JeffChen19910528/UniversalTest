"""Testability assessment (Phase 5 brief §11).

Answers "how easy would it be to automatically test this project right
now", never "is this code well-written" — status is capped at WARNING
(never FAIL): poor testability is a limitation to report, not a defect to
fail the project over.
"""

from __future__ import annotations

from universal_test.core.models.enums import AssessmentStatus
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.models import ProjectModel
from universal_test.assessment.models import AssessmentCategory

_GOOD = "GOOD"
_NONE = "NONE"
_PROVIDED = "PROVIDED"
_UNKNOWN = "UNKNOWN"
_NOT_ASSESSED = "NOT_ASSESSED"


def assess_testability(
    model: ProjectModel, has_confirmed_openapi: bool, target_provided: bool,
    database_testability_signal: str | None = None,
) -> AssessmentCategory:
    api_evidence = [a for a in model.apis if a.kind == "openapi"]
    if has_confirmed_openapi:
        api_signal = _GOOD
    elif api_evidence:
        api_signal = "PARTIAL"
    else:
        api_signal = _NONE

    docker_available = any(i.name in ("Docker", "Docker Compose") for i in model.infrastructure)
    database_detected = bool(model.databases)

    # Phase 6 can supply a real signal (GOOD/PARTIAL/NOT_ASSESSED) once a database
    # profile was configured and (dis)connected; without one, a detected database
    # honestly stays NOT_ASSESSED rather than NONE -- discovery evidence alone
    # doesn't mean the database can actually be exercised.
    db_signal = database_testability_signal or (_NOT_ASSESSED if database_detected else _NONE)

    signals = {
        "API specification": api_signal,
        "Test framework": _GOOD if model.test_frameworks else _NONE,
        "Test directories": _GOOD if model.test_directories else _NONE,
        "Local fixture (Docker)": _GOOD if docker_available else _NONE,
        "Local execution target": _PROVIDED if target_provided else _UNKNOWN,
        "Database testability": db_signal,
    }

    good_count = sum(1 for v in signals.values() if v in (_GOOD, _PROVIDED))
    if good_count >= 2:
        status = AssessmentStatus.PASS
    elif good_count == 1:
        status = AssessmentStatus.WARNING
    else:
        status = AssessmentStatus.UNKNOWN

    summary = ", ".join(f"{name}: {value}" for name, value in signals.items())
    evidence = [Evidence("testability_signals", signals)]
    return AssessmentCategory(name="Testability", status=status, summary=summary, evidence=evidence)
