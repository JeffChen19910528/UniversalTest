from pathlib import Path

from universal_test.core.models.enums import ResultStatus
from universal_test.core.models.result import TestResult
from universal_test.core.orchestration.orchestrator import RunResult
from universal_test.discovery import discover
from universal_test.assessment import build_assessment
from universal_test.regression.snapshot import build_snapshot

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_build_snapshot_from_real_discovery_no_execution():
    model = discover(str(FIXTURES_DIR / "healthy-project"))
    assessment = build_assessment(
        project_path=str(FIXTURES_DIR / "healthy-project"), target=None, model=model, generated_count=0,
        run_result=None, functional_not_run_reason="no target", perf_result=None,
        performance_not_run_reason="not enabled", has_confirmed_openapi=True, database_result=None,
    )
    snapshot = build_snapshot(
        project_path=str(FIXTURES_DIR / "healthy-project"), target=None, model=model, generated_count=0,
        run_result=None, perf_result=None, database_result=None, assessment=assessment,
    )
    assert snapshot.schema_version == "1.0"
    assert "Python" in snapshot.discovery.languages
    assert snapshot.functional is None
    assert snapshot.performance is None
    assert snapshot.database is None
    assert snapshot.assessment.overall_status == assessment.overall_status.value
    assert {c.name for c in snapshot.assessment.categories} == {c.name for c in assessment.categories}


def test_build_snapshot_includes_functional_test_ids():
    model = discover(str(FIXTURES_DIR / "healthy-project"))
    run_result = RunResult(results=[
        TestResult(id="API-001", category="functional", status=ResultStatus.PASSED, message="ok"),
        TestResult(id="API-002", category="functional", status=ResultStatus.FAILED, message="bad"),
    ])
    assessment = build_assessment(
        project_path=str(FIXTURES_DIR / "healthy-project"), target="http://x", model=model, generated_count=2,
        run_result=run_result, functional_not_run_reason=None, perf_result=None,
        performance_not_run_reason="not enabled", has_confirmed_openapi=True, database_result=None,
    )
    snapshot = build_snapshot(
        project_path=str(FIXTURES_DIR / "healthy-project"), target="http://x", model=model, generated_count=2,
        run_result=run_result, perf_result=None, database_result=None, assessment=assessment,
    )
    assert snapshot.functional is not None
    ids = {t.id: t.status for t in snapshot.functional.tests}
    assert ids == {"API-001": "passed", "API-002": "failed"}
    assert snapshot.functional.summary["passed"] == 1
    assert snapshot.functional.summary["failed"] == 1
