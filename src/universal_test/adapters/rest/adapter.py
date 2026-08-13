"""REST adapter orchestration: ties discovery/parsing/generation/execution together.

`run()` is what the CLI calls. `RestAdapter` additionally implements the
generic adapter contract from ARCHITECTURE.md §7 (`detect/describe/discover/
generate_tests/execute/collect_metrics`) for architectural completeness.
`AdapterInfo` now lives in `core.adapter_info` — factored out once the
Frontend and Browser adapters needed the same shape.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from universal_test.core.adapter_info import AdapterInfo
from universal_test.core.models.enums import ResultStatus
from universal_test.core.models.test_spec import TestCase
from universal_test.core.orchestration.orchestrator import Orchestrator, RunResult
from universal_test.adapters.rest.auth import AuthConfig, available_scheme_names
from universal_test.adapters.rest.discovery_bridge import find_openapi_candidates, select_specification
from universal_test.adapters.rest.executor import make_executor
from universal_test.adapters.rest.models import ApiSpecification
from universal_test.adapters.rest.normalizer import parse_specification
from universal_test.adapters.rest.test_generation import generate_test_cases

DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass
class RestRunResult:
    specification: ApiSpecification
    test_cases: list[TestCase]
    run_result: RunResult | None
    executed: bool
    no_target_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "specification": self.specification.to_dict(),
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "run_result": self.run_result.to_dict() if self.run_result else None,
            "executed": self.executed,
            "no_target_reason": self.no_target_reason,
        }


def _apply_control_overrides(run_result: RunResult, test_cases: list[TestCase]) -> RunResult:
    """Rewrite the (assertion-free, hence Phase-1-default-`UNKNOWN`) results for
    test cases the executor deliberately did not execute, using the specific
    `result_status`/`reason` `test_generation.py` attached — see that
    module's docstring for why this is a post-processing pass rather than a
    Core change.
    """
    new_results = []
    for test_case, result in zip(test_cases, run_result.results):
        control = test_case.request.get("_control", {})
        if not control.get("execute", True) and result.status == ResultStatus.UNKNOWN:
            desired_status = ResultStatus.SKIPPED if control.get("result_status") == "skipped" else ResultStatus.UNKNOWN
            result = dataclasses.replace(result, status=desired_status, message=control.get("reason", result.message))
        new_results.append(result)
    return RunResult(results=new_results)


def run(
    project_path: str | Path,
    *,
    openapi_override: str | None = None,
    target: str | None = None,
    auth_config: AuthConfig | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    dry_run: bool = False,
) -> RestRunResult:
    spec_path = select_specification(Path(project_path), openapi_override)
    spec = parse_specification(spec_path)

    auth_config = auth_config or AuthConfig()
    available = available_scheme_names(auth_config, spec.security_schemes)
    test_cases = generate_test_cases(spec, available)

    if dry_run:
        return RestRunResult(specification=spec, test_cases=test_cases, run_result=None, executed=False)
    if not target:
        return RestRunResult(
            specification=spec, test_cases=test_cases, run_result=None, executed=False,
            no_target_reason="No execution target specified.",
        )

    executor = make_executor(target, spec.security_schemes, auth_config, timeout_seconds)
    try:
        run_result = Orchestrator().run_test_cases(test_cases, executor)
    finally:
        executor.client.close()  # type: ignore[attr-defined]

    run_result = _apply_control_overrides(run_result, test_cases)
    return RestRunResult(specification=spec, test_cases=test_cases, run_result=run_result, executed=True)


class RestAdapter:
    """Generic adapter-contract wrapper around the functions above."""

    info = AdapterInfo(name="rest", version="1", capabilities=["discovery", "functional_testing"])

    def detect(self, project_path: str | Path) -> bool:
        return bool(find_openapi_candidates(Path(project_path)))

    def describe(self) -> AdapterInfo:
        return self.info

    def discover(self, project_path: str | Path, openapi_override: str | None = None) -> ApiSpecification:
        spec_path = select_specification(Path(project_path), openapi_override)
        return parse_specification(spec_path)

    def generate_tests(self, specification: ApiSpecification, auth_config: AuthConfig | None = None) -> list[TestCase]:
        auth_config = auth_config or AuthConfig()
        available = available_scheme_names(auth_config, specification.security_schemes)
        return generate_test_cases(specification, available)

    def execute(self, test_cases: list[TestCase], target: str, security_schemes: dict,
                auth_config: AuthConfig | None = None, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> RunResult:
        auth_config = auth_config or AuthConfig()
        executor = make_executor(target, security_schemes, auth_config, timeout_seconds)
        try:
            run_result = Orchestrator().run_test_cases(test_cases, executor)
        finally:
            executor.client.close()  # type: ignore[attr-defined]
        return _apply_control_overrides(run_result, test_cases)

    def collect_metrics(self, run_result: RunResult) -> dict:
        return run_result.summary
