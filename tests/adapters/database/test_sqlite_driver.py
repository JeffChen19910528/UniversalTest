import sqlite3

import pytest

from universal_test.core.errors import DatabaseConnectionError
from universal_test.adapters.database.base import discover_database
from universal_test.adapters.database.models import DatabaseEngine
from universal_test.adapters.database.sqlite import SqliteDriver


def test_nonexistent_file_raises_connection_error(tmp_path):
    with pytest.raises(DatabaseConnectionError):
        SqliteDriver(str(tmp_path / "nope.db"))


def test_basic_fixture_discovery(sqlite_basic_path):
    driver = SqliteDriver(str(sqlite_basic_path))
    info = discover_database(DatabaseEngine.SQLITE, driver)
    driver.close()

    assert info.engine == DatabaseEngine.SQLITE
    assert len(info.schemas) == 1
    schema = info.schemas[0]
    table_names = {t.name for t in schema.tables}
    assert table_names == {"items"}
    items = next(t for t in schema.tables if t.name == "items")
    assert items.primary_key is not None
    assert items.primary_key.columns == ["id"]
    assert {c.name for c in items.columns} == {"id", "name", "price"}


def test_relations_fixture_foreign_keys_and_indexes(sqlite_relations_path):
    driver = SqliteDriver(str(sqlite_relations_path))
    info = discover_database(DatabaseEngine.SQLITE, driver)
    driver.close()

    schema = info.schemas[0]
    orders = next(t for t in schema.tables if t.name == "orders")
    assert len(orders.foreign_keys) == 1
    fk = orders.foreign_keys[0]
    assert fk.referenced_table == "customers"
    assert fk.columns == ["customer_id"]
    assert fk.referenced_columns == ["id"]

    index_names = {i.name for i in orders.indexes}
    assert "idx_orders_customer" in index_names

    customers = next(t for t in schema.tables if t.name == "customers")
    unique_indexes = [i for i in customers.indexes if i.unique]
    assert any(i.name == "idx_customers_email" for i in unique_indexes)


def test_relations_fixture_view_discovered(sqlite_relations_path):
    driver = SqliteDriver(str(sqlite_relations_path))
    info = discover_database(DatabaseEngine.SQLITE, driver)
    driver.close()

    schema = info.schemas[0]
    assert len(schema.views) == 1
    assert schema.views[0].name == "customer_orders"
    assert {c.name for c in schema.views[0].columns} == {"name", "total"}


def test_table_without_primary_key_reports_none(sqlite_relations_path):
    driver = SqliteDriver(str(sqlite_relations_path))
    info = discover_database(DatabaseEngine.SQLITE, driver)
    driver.close()

    audit_log = next(t for t in info.schemas[0].tables if t.name == "audit_log")
    assert audit_log.primary_key is None


def test_row_count_uses_catalog_estimate_after_analyze(sqlite_relations_path):
    driver = SqliteDriver(str(sqlite_relations_path))
    info = discover_database(DatabaseEngine.SQLITE, driver)
    driver.close()

    customers = next(t for t in info.schemas[0].tables if t.name == "customers")
    assert customers.row_count is not None
    assert customers.row_count.method == "catalog_estimate"
    assert customers.row_count.value == 2


def test_readonly_connection_rejects_writes(sqlite_basic_path):
    driver = SqliteDriver(str(sqlite_basic_path))
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        driver._conn.execute("DELETE FROM items")
    driver.close()


def test_no_execute_sql_method_exists_on_driver(sqlite_basic_path):
    driver = SqliteDriver(str(sqlite_basic_path))
    assert not hasattr(driver, "execute")
    assert not hasattr(driver, "execute_sql")
    assert not hasattr(driver, "query")
    driver.close()


def test_discovery_survives_one_table_metadata_failure(sqlite_basic_path, monkeypatch):
    driver = SqliteDriver(str(sqlite_basic_path))
    original = driver.list_columns

    def _boom(schema, table):
        if table == "items":
            raise RuntimeError("simulated failure")
        return original(schema, table)

    monkeypatch.setattr(driver, "list_columns", _boom)
    info = discover_database(DatabaseEngine.SQLITE, driver)
    driver.close()

    assert info.schemas[0].tables == []
    assert any("items" in w for w in info.warnings)
