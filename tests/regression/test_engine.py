from universal_test.core.models.enums import AssessmentStatus
from universal_test.regression.engine import compare
from universal_test.regression.models import (
    AssessmentSnapshot,
    BaselineSnapshot,
    DiscoverySnapshot,
    SourceInfo,
)


def _snapshot(tool_version="0.1.0") -> BaselineSnapshot:
    return BaselineSnapshot(
        schema_version="1.0", tool_version=tool_version, generated_at="2026-01-01T00:00:00Z",
        project_path="./p", source=SourceInfo(is_git=False, commit=None, branch=None, dirty=None),
        discovery=DiscoverySnapshot(languages=["Python"]),
        functional=None, performance=None, database=None,
        assessment=AssessmentSnapshot(overall_status="pass", categories=[]),
    )


def test_identical_snapshots_compare_to_overall_pass():
    snap = _snapshot()
    summary = compare(snap, snap, performance_thresholds={})
    assert summary.status == AssessmentStatus.PASS
    assert summary.compatible is True


def test_tool_version_mismatch_produces_a_warning_not_an_error():
    baseline = _snapshot(tool_version="0.1.0")
    current = _snapshot(tool_version="0.2.0")
    summary = compare(baseline, current, performance_thresholds={})
    assert any("0.1.0" in w and "0.2.0" in w for w in summary.warnings)
    assert summary.status == AssessmentStatus.PASS  # a version mismatch alone is not a regression


def test_summary_carries_baseline_and_current_meta():
    baseline = _snapshot()
    current = _snapshot()
    summary = compare(baseline, current, performance_thresholds={})
    assert summary.baseline_meta["tool_version"] == "0.1.0"
    assert summary.current_meta["project_path"] == "./p"


def test_all_categories_present():
    summary = compare(_snapshot(), _snapshot(), performance_thresholds={})
    names = {c.name for c in summary.categories}
    assert names == {"Functional", "Performance", "Database", "Discovery", "Assessment", "Browser", "Web Scenarios"}


def test_browser_not_assessed_when_missing_from_both_snapshots():
    summary = compare(_snapshot(), _snapshot(), performance_thresholds={})
    browser = next(c for c in summary.categories if c.name == "Browser")
    assert browser.status == AssessmentStatus.NOT_ASSESSED


def test_to_dict_round_trips_shape():
    summary = compare(_snapshot(), _snapshot(), performance_thresholds={})
    d = summary.to_dict()
    assert d["status"] == "pass"
    assert "categories" in d and "findings" in d
