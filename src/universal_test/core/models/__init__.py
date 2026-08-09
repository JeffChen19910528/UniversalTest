"""Domain models: enums, evidence, framework-independent test spec, and results."""

from universal_test.core.models.enums import (
    AssessmentStatus,
    DetectionConfidence,
    ResultStatus,
    Severity,
)
from universal_test.core.models.evidence import Evidence
from universal_test.core.models.result import AssertionResult, Finding, TestResult
from universal_test.core.models.test_spec import AssertionSpec, TestCase, TestTarget

__all__ = [
    "AssessmentStatus",
    "DetectionConfidence",
    "ResultStatus",
    "Severity",
    "Evidence",
    "AssertionResult",
    "Finding",
    "TestResult",
    "AssertionSpec",
    "TestCase",
    "TestTarget",
]
