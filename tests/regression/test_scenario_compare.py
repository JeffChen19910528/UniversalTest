from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.regression.scenario_compare import compare_scenario
from universal_test.regression.models import ChangeType, ScenarioSnapshot, ScenarioTestEntry


def _snapshot(tests: dict[str, str]) -> ScenarioSnapshot:
    summary = {}
    for status in tests.values():
        summary[status] = summary.get(status, 0) + 1
    return ScenarioSnapshot(summary=summary, tests=[ScenarioTestEntry(id=k, status=v) for k, v in tests.items()])


def test_missing_baseline_is_not_assessed():
    category = compare_scenario(None, _snapshot({"login-smoke": "pass"}))
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_missing_current_is_not_assessed():
    category = compare_scenario(_snapshot({"login-smoke": "pass"}), None)
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_pass_to_pass_no_finding():
    category = compare_scenario(_snapshot({"login-smoke": "pass"}), _snapshot({"login-smoke": "pass"}))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_pass_to_fail_is_regression_high_severity():
    category = compare_scenario(_snapshot({"login-smoke": "pass"}), _snapshot({"login-smoke": "fail"}))
    assert category.status == AssessmentStatus.FAIL
    finding = category.findings[0]
    assert finding.change == ChangeType.REGRESSED
    assert finding.severity == Severity.HIGH
    assert "login-smoke" in finding.title


def test_scenario_id_stability_across_runs():
    # Same scenario id must be recognized as the same identity even when its
    # status changes -- the whole point of the spec's "stable scenario IDs" rule.
    baseline = _snapshot({"login-smoke": "pass", "search": "pass"})
    current = _snapshot({"login-smoke": "pass", "search": "fail"})
    category = compare_scenario(baseline, current)
    assert len(category.findings) == 1
    assert "search" in category.findings[0].title
    assert "login-smoke" not in category.findings[0].title


def test_fail_to_pass_is_improvement_no_finding():
    category = compare_scenario(_snapshot({"login-smoke": "fail"}), _snapshot({"login-smoke": "pass"}))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_unchanged_failure_is_not_a_new_regression():
    category = compare_scenario(_snapshot({"login-smoke": "fail"}), _snapshot({"login-smoke": "fail"}))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []
