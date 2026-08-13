from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.regression.browser_compare import compare_browser
from universal_test.regression.models import BrowserSnapshot, BrowserTestEntry, ChangeType


def _snapshot(tests: dict[str, str], target="http://localhost:3000") -> BrowserSnapshot:
    summary = {}
    for status in tests.values():
        summary[status] = summary.get(status, 0) + 1
    return BrowserSnapshot(
        target=target, browser="chromium", summary=summary,
        tests=[BrowserTestEntry(id=k, status=v) for k, v in tests.items()],
    )


def test_missing_baseline_is_not_assessed():
    category = compare_browser(None, _snapshot({"browser-smoke-1": "passed"}))
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_missing_current_is_not_assessed():
    category = compare_browser(_snapshot({"browser-smoke-1": "passed"}), None)
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_pass_to_pass_no_finding():
    category = compare_browser(_snapshot({"browser-smoke-1": "passed"}), _snapshot({"browser-smoke-1": "passed"}))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_pass_to_fail_is_regression_high_severity():
    category = compare_browser(_snapshot({"browser-smoke-1": "passed"}), _snapshot({"browser-smoke-1": "failed"}))
    assert category.status == AssessmentStatus.FAIL
    finding = category.findings[0]
    assert finding.change == ChangeType.REGRESSED
    assert finding.severity == Severity.HIGH
    assert "browser-smoke-1" in finding.title


def test_pass_to_error_is_also_regression():
    category = compare_browser(_snapshot({"browser-smoke-1": "passed"}), _snapshot({"browser-smoke-1": "error"}))
    assert category.status == AssessmentStatus.FAIL


def test_fail_to_pass_is_improvement_no_finding():
    category = compare_browser(_snapshot({"browser-smoke-1": "failed"}), _snapshot({"browser-smoke-1": "passed"}))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_unchanged_failure_is_not_a_new_regression():
    category = compare_browser(_snapshot({"browser-smoke-1": "failed"}), _snapshot({"browser-smoke-1": "failed"}))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []
