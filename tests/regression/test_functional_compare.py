from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.regression.functional_compare import compare_functional
from universal_test.regression.models import ChangeType, FunctionalSnapshot, FunctionalTestEntry


def _snapshot(tests: dict[str, str], target="http://x") -> FunctionalSnapshot:
    summary = {}
    for status in tests.values():
        summary[status] = summary.get(status, 0) + 1
    return FunctionalSnapshot(
        target=target, generated_count=len(tests), summary=summary,
        tests=[FunctionalTestEntry(id=k, status=v) for k, v in tests.items()],
    )


def test_missing_baseline_is_not_assessed():
    category = compare_functional(None, _snapshot({"API-001": "passed"}))
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_missing_current_is_not_assessed():
    category = compare_functional(_snapshot({"API-001": "passed"}), None)
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_pass_to_pass_no_finding():
    category = compare_functional(_snapshot({"API-001": "passed"}), _snapshot({"API-001": "passed"}))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_pass_to_fail_is_regression_high_severity():
    category = compare_functional(_snapshot({"API-001": "passed"}), _snapshot({"API-001": "failed"}))
    assert category.status == AssessmentStatus.FAIL
    assert len(category.findings) == 1
    finding = category.findings[0]
    assert finding.change == ChangeType.REGRESSED
    assert finding.severity == Severity.HIGH
    assert "API-001" in finding.title


def test_pass_to_error_is_also_regression():
    category = compare_functional(_snapshot({"API-001": "passed"}), _snapshot({"API-001": "error"}))
    assert category.status == AssessmentStatus.FAIL


def test_fail_to_pass_is_improvement_no_finding():
    category = compare_functional(_snapshot({"API-001": "failed"}), _snapshot({"API-001": "passed"}))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_test_added_is_not_a_finding():
    category = compare_functional(_snapshot({}), _snapshot({"API-002": "passed"}))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_test_removed_is_not_a_regression_finding():
    category = compare_functional(_snapshot({"API-002": "passed"}), _snapshot({}))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_pass_to_skipped_is_medium_changed_not_regression():
    category = compare_functional(_snapshot({"API-001": "passed"}), _snapshot({"API-001": "skipped"}))
    assert category.status == AssessmentStatus.WARNING
    assert len(category.findings) == 1
    assert category.findings[0].change == ChangeType.CHANGED
    assert category.findings[0].severity == Severity.MEDIUM


def test_unchanged_failure_is_not_a_new_regression():
    # baseline already had this failure -- it should not be re-reported as a new regression
    category = compare_functional(_snapshot({"API-001": "failed"}), _snapshot({"API-001": "failed"}))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_mixed_regression_and_improvement():
    baseline = _snapshot({"API-001": "passed", "API-002": "failed", "API-003": "passed"})
    current = _snapshot({"API-001": "failed", "API-002": "passed", "API-003": "passed"})
    category = compare_functional(baseline, current)
    assert category.status == AssessmentStatus.FAIL
    assert len(category.findings) == 1  # only API-001 regressed; API-002 improved (no finding)
    assert "API-001" in category.findings[0].title


def test_aggregate_metric_deltas_present():
    baseline = _snapshot({"API-001": "passed", "API-002": "failed"})
    current = _snapshot({"API-001": "passed", "API-002": "failed", "API-003": "failed"})
    category = compare_functional(baseline, current)
    failed_metric = next(m for m in category.metrics if m.name == "failed_count")
    assert failed_metric.baseline_value == 1
    assert failed_metric.current_value == 2
    assert failed_metric.absolute_delta == 1
