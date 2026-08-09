from universal_test.core.models.enums import Severity
from universal_test.core.models.evidence import Evidence
from universal_test.regression.models import (
    AssessmentCategorySnapshot,
    AssessmentSnapshot,
    BaselineSnapshot,
    ChangeType,
    DatabaseSnapshot,
    DatabaseTableSnapshot,
    DiscoverySnapshot,
    FunctionalSnapshot,
    FunctionalTestEntry,
    MetricDelta,
    PerformanceLevelSnapshot,
    PerformanceSnapshot,
    RegressionFinding,
    SourceInfo,
)


def _full_snapshot() -> BaselineSnapshot:
    return BaselineSnapshot(
        schema_version="1.0", tool_version="0.1.0", generated_at="2026-01-01T00:00:00Z",
        project_path="./p",
        source=SourceInfo(is_git=True, commit="abc", branch="main", dirty=True),
        discovery=DiscoverySnapshot(languages=["Python"], frameworks=["FastAPI"], databases=["PostgreSQL"]),
        functional=FunctionalSnapshot(
            target="http://x", generated_count=2, summary={"passed": 1, "failed": 1},
            tests=[FunctionalTestEntry(id="API-001", status="passed"), FunctionalTestEntry(id="API-002", status="failed")],
        ),
        performance=PerformanceSnapshot(
            target="http://x", endpoint="GET /y",
            levels=[PerformanceLevelSnapshot(concurrency=1, metrics={"p95_ms": 100.0, "rps": 50.0})],
        ),
        database=DatabaseSnapshot(
            engine="sqlite", database_name="app.db", summary={"tables": 1},
            tables=[DatabaseTableSnapshot(schema="main", name="items", columns=["id"], primary_key=["id"], foreign_key_count=0, index_count=1)],
        ),
        assessment=AssessmentSnapshot(overall_status="warning", categories=[AssessmentCategorySnapshot(name="Functional Health", status="warning")]),
    )


def test_baseline_snapshot_round_trips_through_dict():
    original = _full_snapshot()
    restored = BaselineSnapshot.from_dict(original.to_dict())

    assert restored.schema_version == original.schema_version
    assert restored.tool_version == original.tool_version
    assert restored.source.commit == "abc"
    assert restored.discovery.frameworks == ["FastAPI"]
    assert restored.functional.tests[0].id == "API-001"
    assert restored.performance.levels[0].concurrency == 1
    assert restored.database.tables[0].name == "items"
    assert restored.assessment.overall_status == "warning"


def test_baseline_snapshot_round_trips_with_no_functional_performance_database():
    original = BaselineSnapshot(
        schema_version="1.0", tool_version="0.1.0", generated_at="t", project_path="./p",
        source=SourceInfo(is_git=False, commit=None, branch=None, dirty=None),
        discovery=DiscoverySnapshot(), functional=None, performance=None, database=None,
        assessment=AssessmentSnapshot(overall_status="unknown", categories=[]),
    )
    restored = BaselineSnapshot.from_dict(original.to_dict())
    assert restored.functional is None
    assert restored.performance is None
    assert restored.database is None


def test_metric_delta_to_dict_shape():
    m = MetricDelta(
        name="P95", baseline_value=100.0, current_value=110.0, direction="lower_is_better",
        change=ChangeType.UNCHANGED, absolute_delta=10.0, percent_delta=10.0, threshold_percent=10.0,
    )
    d = m.to_dict()
    assert d["change"] == "unchanged"
    assert d["direction"] == "lower_is_better"


def test_regression_finding_to_dict_shape():
    f = RegressionFinding(
        id="X-1", category="Functional", change=ChangeType.REGRESSED, severity=Severity.HIGH,
        confidence=1.0, title="t", description="d", evidence=[Evidence("x", {"a": 1})],
    )
    d = f.to_dict()
    assert d["change"] == "regressed"
    assert d["severity"] == "high"
    assert d["evidence"][0]["type"] == "x"


def test_database_table_snapshot_qualified_name():
    t = DatabaseTableSnapshot(schema="main", name="orders", columns=[], primary_key=None, foreign_key_count=0, index_count=0)
    assert t.qualified_name == "main.orders"
