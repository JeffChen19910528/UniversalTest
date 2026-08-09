from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.regression.assessment_compare import compare_assessment
from universal_test.regression.models import AssessmentCategorySnapshot, AssessmentSnapshot


def _snap(**category_statuses) -> AssessmentSnapshot:
    return AssessmentSnapshot(
        overall_status="pass",
        categories=[AssessmentCategorySnapshot(name=name, status=status) for name, status in category_statuses.items()],
    )


def test_pass_to_pass_no_finding():
    category = compare_assessment(_snap(Functional="pass"), _snap(Functional="pass"))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_pass_to_warning_is_medium():
    category = compare_assessment(_snap(Functional="pass"), _snap(Functional="warning"))
    assert category.status == AssessmentStatus.WARNING
    assert category.findings[0].severity == Severity.MEDIUM


def test_pass_to_fail_is_high():
    category = compare_assessment(_snap(Functional="pass"), _snap(Functional="fail"))
    assert category.status == AssessmentStatus.FAIL
    assert category.findings[0].severity == Severity.HIGH


def test_warning_to_fail_is_high():
    category = compare_assessment(_snap(Functional="warning"), _snap(Functional="fail"))
    assert category.status == AssessmentStatus.FAIL
    assert category.findings[0].severity == Severity.HIGH


def test_fail_to_pass_is_improvement_no_finding():
    category = compare_assessment(_snap(Functional="fail"), _snap(Functional="pass"))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_indeterminate_transition_is_not_a_finding():
    category = compare_assessment(_snap(Functional="not_assessed"), _snap(Functional="fail"))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_category_only_in_one_side_is_ignored():
    category = compare_assessment(_snap(Functional="pass"), _snap(Performance="fail"))
    assert category.findings == []


def test_multiple_categories_independent():
    baseline = _snap(Functional="pass", Performance="pass")
    current = _snap(Functional="fail", Performance="pass")
    category = compare_assessment(baseline, current)
    assert len(category.findings) == 1
    assert "Functional" in category.findings[0].title
