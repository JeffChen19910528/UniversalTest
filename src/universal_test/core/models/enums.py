"""Status vocabularies.

Three distinct enums answer three distinct questions (skill.md §4.1, §20):
did we run it, how did the run go, and how confident is a discovery fact.
Never collapse these into one enum — that is exactly the kind of overclaiming
skill.md prohibits (e.g. "no test found" must not become "failed").
"""

from __future__ import annotations

from enum import Enum


class ResultStatus(str, Enum):
    """Outcome of executing a single test case."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    UNKNOWN = "unknown"


class AssessmentStatus(str, Enum):
    """Outcome of one assessment category (skill.md §12)."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_ASSESSED = "not_assessed"


class DetectionConfidence(str, Enum):
    """How a discovery fact was established (skill.md §4.1)."""

    DETECTED = "detected"
    INFERRED = "inferred"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Severity of a Finding, independent of whether the underlying test passed."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
