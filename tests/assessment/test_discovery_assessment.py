from pathlib import Path

from universal_test.core.models.enums import AssessmentStatus, FindingClassification
from universal_test.discovery import discover
from universal_test.assessment.discovery_assessment import (
    assess_build_health,
    assess_project_discovery,
    assess_test_infrastructure,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_healthy_project_discovery_passes():
    model = discover(FIXTURES / "healthy-project")
    category = assess_project_discovery(model)
    assert category.status == AssessmentStatus.PASS


def test_healthy_project_build_health_is_at_least_warning():
    # pyproject.toml with no lockfile only yields INFERRED "pip" evidence (honest,
    # not DETECTED) -- WARNING, not FAIL, and never worse than WARNING here.
    model = discover(FIXTURES / "healthy-project")
    category = assess_build_health(model)
    assert category.status in (AssessmentStatus.PASS, AssessmentStatus.WARNING)


def test_healthy_project_test_infrastructure_passes():
    model = discover(FIXTURES / "healthy-project")
    category = assess_test_infrastructure(model)
    assert category.status == AssessmentStatus.PASS


def test_unknown_project_discovery_is_unknown():
    model = discover(FIXTURES / "unknown-project")
    category = assess_project_discovery(model)
    assert category.status == AssessmentStatus.UNKNOWN
    assert category.reason is not None


def test_unknown_project_build_health_is_warning():
    model = discover(FIXTURES / "unknown-project")
    category = assess_build_health(model)
    assert category.status == AssessmentStatus.WARNING


def test_unknown_project_test_infrastructure_has_finding():
    model = discover(FIXTURES / "unknown-project")
    category = assess_test_infrastructure(model)
    assert category.status == AssessmentStatus.WARNING
    assert any(f.id == "TESTINFRA-001" for f in category.findings)


def test_partial_project_build_health_is_weak_and_has_no_tests():
    model = discover(FIXTURES / "partial-project")
    build = assess_build_health(model)
    tests = assess_test_infrastructure(model)
    # npm is detected but only INFERRED (no lockfile) -> weak-evidence WARNING, not PASS
    assert build.status == AssessmentStatus.WARNING
    assert tests.status == AssessmentStatus.WARNING  # no test framework


def test_discovery_warnings_become_a_finding(tmp_path):
    (tmp_path / "pyproject.toml").write_text("not [ valid toml", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")
    model = discover(tmp_path)
    category = assess_project_discovery(model)
    assert any(f.id == "DISC-001" for f in category.findings)
    assert category.findings[0].status == AssessmentStatus.WARNING
    assert category.findings[0].classification == FindingClassification.INFORMATIONAL


def test_test_infrastructure_finding_is_classified_testability_gap():
    model = discover(FIXTURES / "unknown-project")
    category = assess_test_infrastructure(model)
    finding = next(f for f in category.findings if f.id == "TESTINFRA-001")
    assert finding.classification == FindingClassification.TESTABILITY_GAP
    assert "does not indicate" in finding.description or "does NOT indicate" in finding.description


def test_static_web_project_build_health_is_pass_not_warning():
    # Static Web Analysis brief §7: a plain static site legitimately has no
    # package manager/build system - that must not read as a build problem.
    model = discover(FIXTURES / "frontend-static-basic")
    category = assess_build_health(model)
    assert category.status == AssessmentStatus.PASS
    assert "static website" in (category.reason or "")


def test_static_web_project_discovery_is_pass_not_unknown():
    # Static Web Analysis brief §8: a valid HTML/CSS/JS site must not read
    # as "0 languages, generic project, UNKNOWN".
    model = discover(FIXTURES / "frontend-static-basic")
    category = assess_project_discovery(model)
    assert category.status == AssessmentStatus.PASS
