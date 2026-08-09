from universal_test.core.models.enums import AssessmentStatus, Severity
from universal_test.regression.database_compare import compare_database
from universal_test.regression.models import DatabaseSnapshot, DatabaseTableSnapshot


def _table(name, columns, schema="main", pk=None, fks=0, indexes=0) -> DatabaseTableSnapshot:
    return DatabaseTableSnapshot(schema=schema, name=name, columns=columns, primary_key=pk, foreign_key_count=fks, index_count=indexes)


def _snapshot(tables) -> DatabaseSnapshot:
    return DatabaseSnapshot(engine="sqlite", database_name="app.db", summary={}, tables=tables)


def test_missing_baseline_is_not_assessed():
    category = compare_database(None, _snapshot([]))
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_missing_current_is_not_assessed():
    category = compare_database(_snapshot([]), None)
    assert category.status == AssessmentStatus.NOT_ASSESSED


def test_unchanged_schema_is_pass_no_findings():
    tables = [_table("items", ["id", "name"], pk=["id"])]
    category = compare_database(_snapshot(tables), _snapshot(tables))
    assert category.status == AssessmentStatus.PASS
    assert category.findings == []


def test_table_added_is_info_never_fail():
    baseline = _snapshot([_table("items", ["id"])])
    current = _snapshot([_table("items", ["id"]), _table("orders", ["id", "item_id"])])
    category = compare_database(baseline, current)
    assert category.status == AssessmentStatus.PASS  # INFO severity never escalates status
    assert len(category.findings) == 1
    assert category.findings[0].severity == Severity.INFO
    assert "orders" in category.findings[0].title


def test_table_removed_is_info_never_fail():
    baseline = _snapshot([_table("items", ["id"]), _table("orders", ["id"])])
    current = _snapshot([_table("items", ["id"])])
    category = compare_database(baseline, current)
    assert category.status == AssessmentStatus.PASS
    assert any(f.change.value == "removed" for f in category.findings)
    assert all(f.severity == Severity.INFO for f in category.findings)


def test_column_added_is_info():
    baseline = _snapshot([_table("items", ["id", "name"])])
    current = _snapshot([_table("items", ["id", "name", "price"])])
    category = compare_database(baseline, current)
    assert category.status == AssessmentStatus.PASS
    assert any("price" in f.title for f in category.findings)


def test_column_removed_is_info():
    baseline = _snapshot([_table("items", ["id", "name", "price"])])
    current = _snapshot([_table("items", ["id", "name"])])
    category = compare_database(baseline, current)
    assert category.status == AssessmentStatus.PASS
    assert any("price" in f.title for f in category.findings)


def test_foreign_key_count_changed_is_info():
    baseline = _snapshot([_table("orders", ["id"], fks=0)])
    current = _snapshot([_table("orders", ["id"], fks=1)])
    category = compare_database(baseline, current)
    assert category.status == AssessmentStatus.PASS
    assert any("foreign key" in f.title.lower() for f in category.findings)


def test_index_count_changed_is_info():
    baseline = _snapshot([_table("orders", ["id"], indexes=1)])
    current = _snapshot([_table("orders", ["id"], indexes=2)])
    category = compare_database(baseline, current)
    assert category.status == AssessmentStatus.PASS
    assert any("index" in f.title.lower() for f in category.findings)
