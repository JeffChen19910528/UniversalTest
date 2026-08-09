from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.assessment.models import AssessmentCategory, ProjectAssessment
from universal_test.regression.models import RegressionCategory, RegressionFinding, RegressionSummary
from universal_test.quality_gate.engine import evaluate
from universal_test.quality_gate.models import QualityGatePolicy, QualityGateStatus


def _assessment(*, overall=AssessmentStatus.PASS, categories=None) -> ProjectAssessment:
    return ProjectAssessment(
        schema_version="1.0", tool_version="0.1.0", generated_at="t", project_path="./p",
        target=None, overall_status=overall, categories=categories or [],
    )


def _category(name, status, reason=None, summary="s") -> AssessmentCategory:
    return AssessmentCategory(name=name, status=status, summary=summary, reason=reason)


def _regression_finding(severity: Severity, category="Regression") -> RegressionFinding:
    from universal_test.regression.models import ChangeType
    return RegressionFinding(
        id="X-1", category=category, change=ChangeType.REGRESSED, severity=severity,
        confidence=1.0, title="t", description="d",
    )


def _regression(*, categories=None, status=AssessmentStatus.PASS) -> RegressionSummary:
    return RegressionSummary(
        schema_version="1.0", compatible=True, baseline_meta={}, current_meta={},
        status=status, categories=categories or [],
    )


def test_all_pass_is_gate_pass():
    assessment = _assessment(overall=AssessmentStatus.PASS, categories=[
        _category("Functional Health", AssessmentStatus.PASS),
        _category("Performance", AssessmentStatus.PASS),
        _category("Database Health", AssessmentStatus.PASS),
    ])
    result = evaluate(assessment, None)
    assert result.status == QualityGateStatus.PASS
    assert result.exit_code == 0
    assert all(f.level != "fail" for f in result.findings)


def test_functional_real_failure_is_gate_fail_by_default():
    assessment = _assessment(overall=AssessmentStatus.WARNING, categories=[
        _category("Functional Health", AssessmentStatus.WARNING),
    ])
    result = evaluate(assessment, None)
    assert result.status == QualityGateStatus.FAIL
    assert result.exit_code == 1
    assert any(f.rule == "functional.failure" for f in result.findings)


def test_functional_unreachable_target_is_infra_error_not_quality_fail():
    assessment = _assessment(overall=AssessmentStatus.FAIL, categories=[
        _category("Functional Health", AssessmentStatus.FAIL),
    ])
    result = evaluate(assessment, None)
    assert result.status == QualityGateStatus.ERROR
    assert result.exit_code == 3
    assert result.reason is not None


def test_functional_unreachable_can_be_opted_into_quality_gate():
    assessment = _assessment(overall=AssessmentStatus.FAIL, categories=[
        _category("Functional Health", AssessmentStatus.FAIL),
    ])
    policy = QualityGatePolicy(fail_on={"functional": ["unreachable"]}, warn_on={})
    result = evaluate(assessment, None, policy)
    assert result.status == QualityGateStatus.FAIL
    assert result.exit_code == 1


def test_performance_unreachable_is_infra_error():
    assessment = _assessment(categories=[_category("Performance", AssessmentStatus.FAIL)])
    result = evaluate(assessment, None)
    assert result.status == QualityGateStatus.ERROR
    assert result.exit_code == 3


def test_performance_threshold_breach_is_gate_fail_by_default():
    assessment = _assessment(overall=AssessmentStatus.WARNING, categories=[
        _category("Performance", AssessmentStatus.WARNING),
    ])
    result = evaluate(assessment, None)
    assert result.status == QualityGateStatus.FAIL
    assert any(f.rule == "performance.threshold" for f in result.findings)


def test_high_regression_is_gate_fail():
    regression = _regression(categories=[
        RegressionCategory(name="Functional", status=AssessmentStatus.FAIL, summary="s",
                            findings=[_regression_finding(Severity.HIGH)]),
    ])
    result = evaluate(_assessment(), regression)
    assert result.status == QualityGateStatus.FAIL
    assert any(f.rule == "regression.high" for f in result.findings)


def test_critical_regression_is_gate_fail():
    regression = _regression(categories=[
        RegressionCategory(name="Functional", status=AssessmentStatus.FAIL, summary="s",
                            findings=[_regression_finding(Severity.CRITICAL)]),
    ])
    result = evaluate(_assessment(), regression)
    assert result.status == QualityGateStatus.FAIL
    assert any(f.rule == "regression.critical" for f in result.findings)


def test_medium_regression_is_gate_warning_not_fail():
    regression = _regression(categories=[
        RegressionCategory(name="Functional", status=AssessmentStatus.WARNING, summary="s",
                            findings=[_regression_finding(Severity.MEDIUM)]),
    ])
    result = evaluate(_assessment(), regression)
    assert result.status == QualityGateStatus.WARNING
    assert result.exit_code == 0
    assert any(f.rule == "regression.medium" and f.level == "warning" for f in result.findings)


def test_low_and_info_regression_do_not_gate_by_default():
    regression = _regression(categories=[
        RegressionCategory(name="Functional", status=AssessmentStatus.PASS, summary="s",
                            findings=[_regression_finding(Severity.LOW), _regression_finding(Severity.INFO)]),
    ])
    result = evaluate(_assessment(), regression)
    assert result.status == QualityGateStatus.PASS
    assert result.findings == []


def test_database_not_assessed_never_fails_by_default():
    assessment = _assessment(categories=[
        _category("Database Health", AssessmentStatus.NOT_ASSESSED, reason="no --database-profile supplied"),
    ])
    result = evaluate(assessment, None)
    assert result.status == QualityGateStatus.PASS


def test_database_not_assessed_can_be_opted_into_failing():
    assessment = _assessment(categories=[
        _category("Database Health", AssessmentStatus.NOT_ASSESSED, reason="no --database-profile supplied"),
    ])
    policy = QualityGatePolicy(fail_on={"database": ["not_assessed"]}, warn_on={})
    result = evaluate(assessment, None, policy)
    assert result.status == QualityGateStatus.FAIL


def test_unknown_assessment_status_never_fails_by_default():
    assessment = _assessment(overall=AssessmentStatus.UNKNOWN, categories=[
        _category("Functional Health", AssessmentStatus.NOT_ASSESSED),
    ])
    result = evaluate(assessment, None)
    assert result.status == QualityGateStatus.PASS


def test_database_schema_change_is_warning_by_default():
    from universal_test.regression.models import ChangeType
    finding = RegressionFinding(
        id="DB-1", category="Database", change=ChangeType.ADDED, severity=Severity.INFO,
        confidence=1.0, title="table added", description="d",
    )
    regression = _regression(categories=[
        RegressionCategory(name="Database", status=AssessmentStatus.PASS, summary="s", findings=[finding]),
    ])
    result = evaluate(_assessment(), regression)
    assert result.status == QualityGateStatus.WARNING
    assert any(f.rule == "database.schema_change" for f in result.findings)


def test_discovery_change_is_warning_by_default():
    from universal_test.regression.models import ChangeType
    finding = RegressionFinding(
        id="DISC-1", category="Discovery", change=ChangeType.ADDED, severity=Severity.INFO,
        confidence=1.0, title="framework added", description="d",
    )
    regression = _regression(categories=[
        RegressionCategory(name="Discovery", status=AssessmentStatus.PASS, summary="s", findings=[finding]),
    ])
    result = evaluate(_assessment(), regression)
    assert result.status == QualityGateStatus.WARNING
    assert any(f.rule == "discovery.change" for f in result.findings)


def test_mixed_findings_fail_wins_over_warning():
    regression = _regression(categories=[
        RegressionCategory(name="Functional", status=AssessmentStatus.FAIL, summary="s", findings=[
            _regression_finding(Severity.HIGH), _regression_finding(Severity.MEDIUM),
        ]),
    ])
    result = evaluate(_assessment(), regression)
    assert result.status == QualityGateStatus.FAIL
    levels = {f.level for f in result.findings}
    assert "fail" in levels and "warning" in levels


def test_no_regression_data_still_evaluates_deterministically():
    assessment = _assessment(categories=[_category("Functional Health", AssessmentStatus.PASS)])
    result = evaluate(assessment, None)
    assert result.status == QualityGateStatus.PASS
    assert result.summary["regression_status"] is None


def test_custom_policy_can_disable_default_fail_on():
    assessment = _assessment(overall=AssessmentStatus.WARNING, categories=[
        _category("Functional Health", AssessmentStatus.WARNING),
    ])
    policy = QualityGatePolicy(fail_on={}, warn_on={"functional": ["failure"]})
    result = evaluate(assessment, None, policy)
    assert result.status == QualityGateStatus.WARNING
    assert result.exit_code == 0


def test_result_to_dict_shape():
    assessment = _assessment(categories=[_category("Functional Health", AssessmentStatus.PASS)])
    result = evaluate(assessment, None)
    d = result.to_dict()
    assert d["status"] == "pass"
    assert d["exit_code"] == 0
    assert "findings" in d and "summary" in d
