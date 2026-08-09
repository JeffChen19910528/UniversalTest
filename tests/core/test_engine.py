from universal_test.core.engine.test_engine import TestEngine
from universal_test.core.models.enums import ResultStatus
from universal_test.core.models.test_spec import AssertionSpec, TestCase, TestTarget


def make_case(assertions=None) -> TestCase:
    return TestCase(
        id="T-1",
        name="example",
        type="functional",
        target=TestTarget(adapter="fake", method="GET", path="/x"),
        assertions=assertions or [],
    )


def fake_executor_ok(test_case: TestCase) -> dict:
    return {"status_code": 200, "elapsed_ms": 5, "json": {"ok": True}}


def fake_executor_raises(test_case: TestCase) -> dict:
    raise RuntimeError("connection refused")


def test_run_passes_when_all_assertions_pass():
    engine = TestEngine()
    case = make_case([AssertionSpec("status_code", {"equals": 200})])
    result = engine.run(case, fake_executor_ok)
    assert result.status == ResultStatus.PASSED


def test_run_fails_when_an_assertion_fails():
    engine = TestEngine()
    case = make_case([AssertionSpec("status_code", {"equals": 500})])
    result = engine.run(case, fake_executor_ok)
    assert result.status == ResultStatus.FAILED
    assert result.assertion_results[0].passed is False


def test_run_is_unknown_when_no_assertions_defined():
    engine = TestEngine()
    case = make_case([])
    result = engine.run(case, fake_executor_ok)
    assert result.status == ResultStatus.UNKNOWN


def test_run_is_error_when_executor_raises():
    engine = TestEngine()
    case = make_case([AssertionSpec("status_code", {"equals": 200})])
    result = engine.run(case, fake_executor_raises)
    assert result.status == ResultStatus.ERROR
    assert "connection refused" in result.message
