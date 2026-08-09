from universal_test.core.models.enums import ResultStatus
from universal_test.core.models.test_spec import AssertionSpec, TestCase, TestTarget
from universal_test.core.orchestration.orchestrator import Orchestrator


def make_case(case_id: str, expected_status: int) -> TestCase:
    return TestCase(
        id=case_id,
        name=case_id,
        type="functional",
        target=TestTarget(adapter="fake"),
        assertions=[AssertionSpec("status_code", {"equals": expected_status})],
    )


def executor(test_case: TestCase) -> dict:
    return {"status_code": 200}


def test_run_test_cases_summarizes_results():
    orchestrator = Orchestrator()
    cases = [make_case("T-1", 200), make_case("T-2", 404)]
    run_result = orchestrator.run_test_cases(cases, executor)

    assert len(run_result.results) == 2
    assert run_result.results[0].status == ResultStatus.PASSED
    assert run_result.results[1].status == ResultStatus.FAILED
    assert run_result.summary["passed"] == 1
    assert run_result.summary["failed"] == 1
    assert run_result.summary["unknown"] == 0


def test_run_result_to_dict():
    orchestrator = Orchestrator()
    run_result = orchestrator.run_test_cases([make_case("T-1", 200)], executor)
    d = run_result.to_dict()
    assert d["summary"]["passed"] == 1
    assert d["results"][0]["id"] == "T-1"
