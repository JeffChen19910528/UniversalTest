from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.regression.discovery_compare import compare_discovery
from universal_test.regression.models import DiscoverySnapshot


def test_unchanged_is_pass_no_findings():
    snap = DiscoverySnapshot(languages=["Python"], frameworks=["FastAPI"])
    category = compare_discovery(snap, snap)
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_item_added_is_info_not_fail():
    baseline = DiscoverySnapshot(databases=[])
    current = DiscoverySnapshot(databases=["PostgreSQL"])
    category = compare_discovery(baseline, current)
    assert category.status == AssessmentStatus.PASS
    assert len(category.findings) == 1
    assert category.findings[0].severity == Severity.INFO
    assert category.findings[0].change.value == "added"


def test_item_removed_is_info_not_fail():
    baseline = DiscoverySnapshot(databases=["PostgreSQL"])
    current = DiscoverySnapshot(databases=[])
    category = compare_discovery(baseline, current)
    assert category.status == AssessmentStatus.PASS
    assert len(category.findings) == 1
    assert category.findings[0].severity == Severity.INFO
    assert category.findings[0].change.value == "removed"


def test_multiple_categories_compared_independently():
    baseline = DiscoverySnapshot(languages=["Python"], frameworks=["Django"], test_frameworks=["pytest"])
    current = DiscoverySnapshot(languages=["Python", "TypeScript"], frameworks=[], test_frameworks=["pytest"])
    category = compare_discovery(baseline, current)
    titles = [f.title for f in category.findings]
    assert any("TypeScript" in t for t in titles)
    assert any("Django" in t for t in titles)
    assert category.status == AssessmentStatus.PASS
