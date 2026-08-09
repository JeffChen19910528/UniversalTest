from universal_test.core.models.enums import AssessmentStatus
from universal_test.assessment.models import AssessmentCategory, ProjectAssessment
from universal_test.quality_gate.signals import collect_rules


def _assessment(categories) -> ProjectAssessment:
    return ProjectAssessment(
        schema_version="1.0", tool_version="0.1.0", generated_at="t", project_path="./p",
        target=None, overall_status=AssessmentStatus.PASS, categories=categories,
    )


def test_functional_fail_status_becomes_infra_signal():
    assessment = _assessment([AssessmentCategory(name="Functional Health", status=AssessmentStatus.FAIL, summary="s")])
    infra, quality = collect_rules(assessment, None)
    assert len(infra) == 1
    assert infra[0].category == "functional"
    assert infra[0].value == "unreachable"
    assert infra[0].is_infra_signal is True


def test_functional_warning_status_becomes_quality_signal():
    assessment = _assessment([AssessmentCategory(name="Functional Health", status=AssessmentStatus.WARNING, summary="s")])
    infra, quality = collect_rules(assessment, None)
    assert infra == []
    assert any(r.category == "functional" and r.value == "failure" for r in quality)


def test_functional_pass_produces_no_signal():
    assessment = _assessment([AssessmentCategory(name="Functional Health", status=AssessmentStatus.PASS, summary="s")])
    infra, quality = collect_rules(assessment, None)
    assert infra == []
    assert not any(r.category == "functional" for r in quality)


def test_assessment_overall_status_always_collected():
    assessment = _assessment([])
    infra, quality = collect_rules(assessment, None)
    assert any(r.category == "assessment" and r.value == "pass" for r in quality)


def test_missing_category_produces_no_signal():
    assessment = _assessment([])  # no Functional Health / Performance / Database Health categories at all
    infra, quality = collect_rules(assessment, None)
    assert infra == []
    assert not any(r.category in ("functional", "performance", "database") for r in quality)
