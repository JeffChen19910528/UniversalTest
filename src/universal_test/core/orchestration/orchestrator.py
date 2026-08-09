"""Orchestrator: batch-runs TestCases through TestEngine and summarizes results.

This is the seam later phases extend: discovery -> adapter test generation ->
Orchestrator.run_test_cases() -> assessment -> reporting. Phase 1 only
implements the last link of that chain since nothing upstream exists yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from universal_test.core.engine.test_engine import Executor, TestEngine
from universal_test.core.models.enums import ResultStatus
from universal_test.core.models.result import TestResult
from universal_test.core.models.test_spec import TestCase


@dataclass
class RunResult:
    results: list[TestResult] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts = {status.value: 0 for status in ResultStatus}
        for result in self.results:
            counts[result.status.value] += 1
        return counts

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "results": [r.to_dict() for r in self.results],
        }


class Orchestrator:
    def __init__(self, test_engine: TestEngine | None = None) -> None:
        self._engine = test_engine or TestEngine()

    def run_test_cases(self, test_cases: list[TestCase], executor: Executor) -> RunResult:
        results = [self._engine.run(test_case, executor) for test_case in test_cases]
        return RunResult(results=results)
