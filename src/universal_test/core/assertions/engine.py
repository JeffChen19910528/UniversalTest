"""AssertionEngine: registry + evaluation. Produces AssertionResult, never a bare bool."""

from __future__ import annotations

from universal_test.core.assertions.builtin import BUILTIN_ASSERTIONS, Evaluator
from universal_test.core.errors import AssertionEngineError
from universal_test.core.models.result import AssertionResult
from universal_test.core.models.test_spec import AssertionSpec


class AssertionEngine:
    def __init__(self, register_builtins: bool = True) -> None:
        self._registry: dict[str, Evaluator] = {}
        if register_builtins:
            self._registry.update(BUILTIN_ASSERTIONS)

    def register(self, name: str, evaluator: Evaluator) -> None:
        self._registry[name] = evaluator

    def is_registered(self, name: str) -> bool:
        return name in self._registry

    def evaluate(self, spec: AssertionSpec, context: dict) -> AssertionResult:
        evaluator = self._registry.get(spec.type)
        if evaluator is None:
            raise AssertionEngineError(f"Unknown assertion type: {spec.type!r}")
        try:
            passed, message, evidence = evaluator(spec.params, context)
        except KeyError as exc:
            raise AssertionEngineError(
                f"Assertion {spec.type!r} missing required parameter: {exc}"
            ) from exc
        return AssertionResult(assertion=spec, passed=passed, message=message, evidence=evidence)
