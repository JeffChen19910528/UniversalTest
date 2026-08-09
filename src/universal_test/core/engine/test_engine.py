"""TestEngine: run one TestCase through an adapter-supplied executor + AssertionEngine.

No adapter is implemented yet (Phase 3+); the `executor` here is any callable
matching the adapter contract's `execute()` signature. Tests exercise this
with a fake executor. Core never imports a concrete adapter.
"""

from __future__ import annotations

from typing import Callable

from universal_test.core.assertions.engine import AssertionEngine
from universal_test.core.models.enums import ResultStatus, Severity
from universal_test.core.models.evidence import Evidence
from universal_test.core.models.result import TestResult
from universal_test.core.models.test_spec import TestCase

Executor = Callable[[TestCase], dict]


class TestEngine:
    def __init__(self, assertion_engine: AssertionEngine | None = None) -> None:
        self._assertions = assertion_engine or AssertionEngine()

    def run(self, test_case: TestCase, executor: Executor) -> TestResult:
        try:
            context = executor(test_case)
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any adapter failure -> ERROR result
            return TestResult(
                id=test_case.id,
                category=test_case.type,
                status=ResultStatus.ERROR,
                severity=Severity.MEDIUM,
                message=f"executor raised {type(exc).__name__}: {exc}",
                evidence=[Evidence("exception", {"type": type(exc).__name__, "message": str(exc)})],
            )

        if not test_case.assertions:
            return TestResult(
                id=test_case.id,
                category=test_case.type,
                status=ResultStatus.UNKNOWN,
                message="test case defines no assertions; pass/fail cannot be determined",
                evidence=[Evidence("execution", {"context_keys": sorted(context.keys())})],
            )

        assertion_results = [
            self._assertions.evaluate(spec, context) for spec in test_case.assertions
        ]
        all_passed = all(r.passed for r in assertion_results)

        return TestResult(
            id=test_case.id,
            category=test_case.type,
            status=ResultStatus.PASSED if all_passed else ResultStatus.FAILED,
            severity=Severity.INFO if all_passed else Severity.MEDIUM,
            message="all assertions passed" if all_passed else "one or more assertions failed",
            assertion_results=assertion_results,
        )
