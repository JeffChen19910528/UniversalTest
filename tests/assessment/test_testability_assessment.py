from universal_test.core.models.enums import AssessmentStatus
from universal_test.discovery import discover
from universal_test.assessment.testability_assessment import assess_testability


def test_healthy_project_with_openapi_and_tests_and_target_passes():
    model = discover("tests/fixtures/healthy-project")
    category = assess_testability(model, has_confirmed_openapi=True, target_provided=True)
    assert category.status == AssessmentStatus.PASS


def test_unknown_project_is_unknown_testability():
    model = discover("tests/fixtures/unknown-project")
    category = assess_testability(model, has_confirmed_openapi=False, target_provided=False)
    assert category.status == AssessmentStatus.UNKNOWN


def test_testability_never_reaches_fail():
    # even with nothing at all detected, testability caps at UNKNOWN, never FAIL --
    # it is a limitation, not a defect (Phase 5 brief §11).
    model = discover("tests/fixtures/unknown-project")
    category = assess_testability(model, has_confirmed_openapi=False, target_provided=False)
    assert category.status != AssessmentStatus.FAIL


def test_one_good_signal_is_warning():
    model = discover("tests/fixtures/healthy-project")
    category = assess_testability(model, has_confirmed_openapi=False, target_provided=False)
    # test framework + test dirs are GOOD, but no confirmed openapi/target -> still >=2 good signals
    # so use a project with exactly one signal instead:
    from universal_test.discovery.models import ProjectModel
    single_signal_model = ProjectModel(root_path="x", tool_version="0", scanned_at="now")
    single_signal_model.test_frameworks = model.test_frameworks  # one GOOD signal
    category = assess_testability(single_signal_model, has_confirmed_openapi=False, target_provided=False)
    assert category.status == AssessmentStatus.WARNING


def test_database_detected_without_adapter_is_not_assessed_signal():
    from universal_test.discovery.models import DatabaseDetection, ProjectModel
    from universal_test.core.models.enums import DetectionConfidence
    model = ProjectModel(root_path="x", tool_version="0", scanned_at="now")
    model.databases = [DatabaseDetection(name="PostgreSQL", confidence=DetectionConfidence.DETECTED)]
    category = assess_testability(model, has_confirmed_openapi=False, target_provided=False)
    signals = category.evidence[0].data
    assert signals["Database testability"] == "NOT_ASSESSED"
