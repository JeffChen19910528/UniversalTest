from universal_test.core.models.enums import AssessmentStatus, ResultStatus
from universal_test.core.models.result import TestResult
from universal_test.core.orchestration.orchestrator import RunResult
from universal_test.discovery import discover
from universal_test.assessment import build_assessment
from universal_test.assessment.models import SCHEMA_VERSION


def _build_for(fixture: str, **overrides):
    model = discover(f"tests/fixtures/{fixture}")
    kwargs = dict(
        project_path=f"tests/fixtures/{fixture}", target=None, model=model, generated_count=0,
        run_result=None, functional_not_run_reason="no execution target was provided",
        perf_result=None, performance_not_run_reason="performance execution was not enabled",
        has_confirmed_openapi=False,
    )
    kwargs.update(overrides)
    return build_assessment(**kwargs)


def test_schema_version_present():
    assessment = _build_for("healthy-project")
    assert assessment.schema_version == SCHEMA_VERSION


def test_eight_categories_present():
    assessment = _build_for("healthy-project")
    names = {c.name for c in assessment.categories}
    assert names == {
        "Project Discovery", "Build / Project Health", "Testability", "Functional Health",
        "Performance", "Database Health", "Configuration Hygiene", "Test Infrastructure",
    }


def test_database_not_assessed_without_profile():
    assessment = _build_for("healthy-project")
    database = next(c for c in assessment.categories if c.name == "Database Health")
    assert database.status == AssessmentStatus.NOT_ASSESSED
    assert database.reason == "database credentials/access were not explicitly configured"


def test_all_pass_healthy_project_with_mock_functional_result():
    results = [TestResult(id=f"T-{i}", category="functional", status=ResultStatus.PASSED, message="") for i in range(3)]
    assessment = _build_for(
        "healthy-project", target="http://localhost:8000",
        run_result=RunResult(results=results), generated_count=3, functional_not_run_reason=None,
        has_confirmed_openapi=True,
    )
    functional = next(c for c in assessment.categories if c.name == "Functional Health")
    assert functional.status == AssessmentStatus.PASS


def test_functional_failures_propagate_to_overall_warning():
    results = [
        TestResult(id="T-1", category="functional", status=ResultStatus.PASSED, message=""),
        TestResult(id="T-2", category="functional", status=ResultStatus.FAILED, message=""),
    ]
    assessment = _build_for(
        "healthy-project", target="http://localhost:8000",
        run_result=RunResult(results=results), generated_count=2, functional_not_run_reason=None,
    )
    assert assessment.overall_status == AssessmentStatus.WARNING


def test_no_target_no_openapi_unknown_project():
    assessment = _build_for("unknown-project")
    functional = next(c for c in assessment.categories if c.name == "Functional Health")
    performance = next(c for c in assessment.categories if c.name == "Performance")
    assert functional.status == AssessmentStatus.NOT_ASSESSED
    assert performance.status == AssessmentStatus.NOT_ASSESSED
    # Build Health / Test Infrastructure correctly report WARNING (no build system,
    # no test framework) even for an unrecognized project -- that's real, actionable
    # signal, not noise, so overall lands on WARNING rather than UNKNOWN.
    assert assessment.overall_status == AssessmentStatus.WARNING


def test_coverage_has_five_items():
    assessment = _build_for("healthy-project")
    names = {c.name for c in assessment.coverage}
    assert names == {"Discovery", "API Discovery", "Functional Execution", "Performance Execution", "Database"}


def test_unassessed_always_includes_business_logic():
    assessment = _build_for("healthy-project")
    assert any(u.name == "Business logic correctness" for u in assessment.unassessed)


def test_limitations_present_and_non_empty():
    assessment = _build_for("healthy-project")
    assert len(assessment.limitations) >= 3
    assert all(isinstance(x, str) for x in assessment.limitations)


def test_recommendations_deduplicated_and_deterministic():
    results = [
        TestResult(id="T-1", category="functional", status=ResultStatus.FAILED, message=""),
        TestResult(id="T-2", category="functional", status=ResultStatus.FAILED, message=""),
    ]
    a1 = _build_for(
        "healthy-project", target="x", run_result=RunResult(results=results),
        generated_count=2, functional_not_run_reason=None,
    )
    a2 = _build_for(
        "healthy-project", target="x", run_result=RunResult(results=results),
        generated_count=2, functional_not_run_reason=None,
    )
    assert a1.recommendations == a2.recommendations
    assert len(a1.recommendations) == len(set(a1.recommendations))


def test_empty_project_is_handled(tmp_path):
    model = discover(tmp_path)
    assessment = build_assessment(
        project_path=str(tmp_path), target=None, model=model, generated_count=0, run_result=None,
        functional_not_run_reason="no execution target was provided", perf_result=None,
        performance_not_run_reason="performance execution was not enabled", has_confirmed_openapi=False,
    )
    # never crashes on a totally empty project; overall_status is still one of the
    # defined values (WARNING here, since Build Health/Test Infra both flag correctly)
    assert assessment.overall_status in (AssessmentStatus.UNKNOWN, AssessmentStatus.WARNING)
