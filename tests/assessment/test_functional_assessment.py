from universal_test.core.models.enums import AssessmentStatus, ResultStatus
from universal_test.core.models.result import TestResult
from universal_test.core.orchestration.orchestrator import RunResult
from universal_test.assessment.functional_assessment import assess_functional_health


def _result(status: ResultStatus, i: int = 0) -> TestResult:
    return TestResult(id=f"T-{i}", category="functional", status=status, message="")


def test_no_target_is_not_assessed():
    category = assess_functional_health(None, generated_count=5, not_run_reason="no execution target was provided")
    assert category.status == AssessmentStatus.NOT_ASSESSED
    assert category.reason == "no execution target was provided"


def test_all_passed_is_pass():
    run_result = RunResult(results=[_result(ResultStatus.PASSED, i) for i in range(5)])
    category = assess_functional_health(run_result, generated_count=5, not_run_reason=None)
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_some_failed_is_warning_with_finding():
    results = [_result(ResultStatus.PASSED, i) for i in range(3)] + [_result(ResultStatus.FAILED, 3)]
    run_result = RunResult(results=results)
    category = assess_functional_health(run_result, generated_count=4, not_run_reason=None)
    assert category.status == AssessmentStatus.WARNING
    assert any(f.id == "FUNC-FAILED" for f in category.findings)


def test_all_errored_is_fail():
    results = [_result(ResultStatus.ERROR, i) for i in range(4)]
    run_result = RunResult(results=results)
    category = assess_functional_health(run_result, generated_count=4, not_run_reason=None)
    assert category.status == AssessmentStatus.FAIL
    assert any(f.id == "FUNC-ERROR" for f in category.findings)


def test_only_skipped_and_unknown_is_unknown():
    results = [_result(ResultStatus.SKIPPED, 0), _result(ResultStatus.UNKNOWN, 1)]
    run_result = RunResult(results=results)
    category = assess_functional_health(run_result, generated_count=2, not_run_reason=None)
    assert category.status == AssessmentStatus.UNKNOWN


def test_summary_reports_all_counts():
    results = [
        _result(ResultStatus.PASSED, 0), _result(ResultStatus.FAILED, 1),
        _result(ResultStatus.SKIPPED, 2), _result(ResultStatus.UNKNOWN, 3),
    ]
    run_result = RunResult(results=results)
    category = assess_functional_health(run_result, generated_count=4, not_run_reason=None)
    assert "Passed: 1" in category.summary
    assert "Failed: 1" in category.summary
    assert "Skipped: 1" in category.summary
    assert "Unknown: 1" in category.summary
