"""Database driver contract + generic discovery walker.

`DatabaseDriver` is the **entire** surface any engine module may expose —
notice there is no `execute(sql)` method anywhere in this file. That is
deliberate: Phase 6 brief §7/§19 — "根本不提供 arbitrary SQL execution" — the
primary safety mechanism is that the capability simply doesn't exist, not a
SQL statement blocklist bolted on afterwards. Every concrete driver
(`sqlite.py`/`postgresql.py`/`mysql.py`/`sqlserver.py`) implements these
methods using its own fixed, parameterized, read-only metadata queries.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from universal_test.adapters.database.models import (
    DatabaseColumn,
    DatabaseEngine,
    DatabaseIndex,
    DatabaseInfo,
    DatabaseSchema,
    DatabaseTable,
    DatabaseView,
    ForeignKey,
    PrimaryKey,
    RowCountEstimate,
)

MAX_TABLES_PER_SCHEMA = 200  # safety cap: never let one unfamiliar schema explode a scan


class DatabaseDriver(ABC):
    """Read-only metadata access. No method here can mutate data or schema."""

    @abstractmethod
    def get_server_version(self) -> str | None: ...

    @abstractmethod
    def get_database_name(self) -> str | None: ...

    @abstractmethod
    def list_schemas(self) -> list[str]: ...

    @abstractmethod
    def list_tables(self, schema: str) -> list[str]: ...

    @abstractmethod
    def list_views(self, schema: str) -> list[str]: ...

    @abstractmethod
    def list_columns(self, schema: str, table: str) -> list[DatabaseColumn]: ...

    @abstractmethod
    def get_primary_key(self, schema: str, table: str) -> PrimaryKey | None: ...

    @abstractmethod
    def list_foreign_keys(self, schema: str, table: str) -> list[ForeignKey]: ...

    @abstractmethod
    def list_indexes(self, schema: str, table: str) -> list[DatabaseIndex]: ...

    @abstractmethod
    def get_safe_row_count(self, schema: str, table: str) -> RowCountEstimate: ...

    @abstractmethod
    def close(self) -> None: ...


def discover_database(engine: DatabaseEngine, driver: DatabaseDriver) -> DatabaseInfo:
    """Walk a connected driver's metadata into a normalized `DatabaseInfo`.

    One table/view's metadata failing doesn't abort the whole scan — same
    "one failure doesn't abort the batch" pattern as Phase 2's
    `discovery.engine` and Phase 3's spec-endpoint parsing.
    """
    warnings: list[str] = []
    schemas: list[DatabaseSchema] = []

    for schema_name in driver.list_schemas():
        table_names = driver.list_tables(schema_name)
        if len(table_names) > MAX_TABLES_PER_SCHEMA:
            warnings.append(
                f"schema {schema_name!r} has {len(table_names)} tables; only the first "
                f"{MAX_TABLES_PER_SCHEMA} were inspected"
            )
            table_names = table_names[:MAX_TABLES_PER_SCHEMA]

        tables: list[DatabaseTable] = []
        for table_name in table_names:
            try:
                tables.append(DatabaseTable(
                    schema=schema_name, name=table_name,
                    columns=driver.list_columns(schema_name, table_name),
                    primary_key=driver.get_primary_key(schema_name, table_name),
                    foreign_keys=driver.list_foreign_keys(schema_name, table_name),
                    indexes=driver.list_indexes(schema_name, table_name),
                    row_count=driver.get_safe_row_count(schema_name, table_name),
                ))
            except Exception as exc:  # noqa: BLE001 - one table's metadata failing must not abort the scan
                warnings.append(f"skipped metadata for {schema_name}.{table_name}: {type(exc).__name__}: {exc}")

        views: list[DatabaseView] = []
        for view_name in driver.list_views(schema_name):
            try:
                views.append(DatabaseView(
                    schema=schema_name, name=view_name,
                    columns=driver.list_columns(schema_name, view_name),
                ))
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"skipped metadata for view {schema_name}.{view_name}: {type(exc).__name__}: {exc}")

        schemas.append(DatabaseSchema(name=schema_name, tables=tables, views=views))

    return DatabaseInfo(
        engine=engine,
        server_version=driver.get_server_version(),
        database_name=driver.get_database_name(),
        schemas=schemas,
        warnings=warnings,
    )
