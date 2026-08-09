"""SQL Server driver (optional `pyodbc` dependency — also requires an
OS-level Microsoft ODBC Driver for SQL Server to be installed; a missing
*Python* package is reported the same way as a missing OS driver, since
both mean the same thing to the user: "this database can't be assessed
here").

Uses `sys.*` catalog views for foreign keys/indexes (more reliable than
`INFORMATION_SCHEMA` for SQL Server) and excludes built-in system schemas
so an application's own tables aren't buried under SQL Server internals
(same principle as PostgreSQL's system-schema exclusion, Phase 6 brief §8).
"""

from __future__ import annotations

from universal_test.core.errors import DatabaseConnectionError, DatabaseDriverUnavailableError, DatabaseTimeoutError
from universal_test.core.models.enums import DetectionConfidence
from universal_test.adapters.database.base import DatabaseDriver
from universal_test.adapters.database.models import (
    DatabaseColumn,
    DatabaseIndex,
    ForeignKey,
    PrimaryKey,
    RowCountEstimate,
)
from universal_test.adapters.database.profile import DatabaseProfile

_EXCLUDED_SCHEMAS = {
    "sys", "INFORMATION_SCHEMA", "guest", "db_owner", "db_accessadmin",
    "db_securityadmin", "db_ddladmin", "db_backupoperator", "db_datareader",
    "db_datawriter", "db_denydatareader", "db_denydatawriter",
}


class SqlServerDriver(DatabaseDriver):
    def __init__(self, profile: DatabaseProfile) -> None:
        try:
            import pyodbc
        except ImportError as exc:
            raise DatabaseDriverUnavailableError(
                "the 'pyodbc' driver is not installed (or no ODBC Driver for SQL Server is "
                "available on this machine); install with `pip install universal-test[database]` "
                "plus the Microsoft ODBC Driver to assess SQL Server databases"
            ) from exc

        self._pyodbc = pyodbc
        server = f"{profile.host},{profile.port}" if profile.port else profile.host
        conn_str = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={server};DATABASE={profile.database};"
            f"UID={profile.credentials.username};PWD={profile.credentials.password};"
            "Encrypt=yes;TrustServerCertificate=yes;"
        )
        try:
            self._conn = pyodbc.connect(conn_str, timeout=int(profile.connect_timeout_seconds))
            self._conn.timeout = int(profile.query_timeout_seconds)
        except pyodbc.Error as exc:
            message = str(exc).lower()
            if "timeout" in message:
                raise DatabaseTimeoutError(f"connecting to SQL Server timed out: {exc}") from exc
            raise DatabaseConnectionError(f"could not connect to SQL Server: {exc}") from exc

        self._database = profile.database

    def _query(self, sql: str, params: tuple = ()) -> list[tuple]:
        cur = self._conn.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()

    def get_server_version(self) -> str | None:
        rows = self._query("SELECT @@VERSION")
        return str(rows[0][0]) if rows else None

    def get_database_name(self) -> str | None:
        return self._database

    def list_schemas(self) -> list[str]:
        rows = self._query("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name")
        return [r[0] for r in rows if r[0] not in _EXCLUDED_SCHEMAS]

    def list_tables(self, schema: str) -> list[str]:
        rows = self._query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = ? AND table_type = 'BASE TABLE' ORDER BY table_name",
            (schema,),
        )
        return [r[0] for r in rows]

    def list_views(self, schema: str) -> list[str]:
        rows = self._query(
            "SELECT table_name FROM information_schema.views WHERE table_schema = ? ORDER BY table_name",
            (schema,),
        )
        return [r[0] for r in rows]

    def list_columns(self, schema: str, table: str) -> list[DatabaseColumn]:
        rows = self._query(
            "SELECT column_name, data_type, is_nullable, column_default, ordinal_position "
            "FROM information_schema.columns WHERE table_schema = ? AND table_name = ? "
            "ORDER BY ordinal_position",
            (schema, table),
        )
        return [
            DatabaseColumn(name=r[0], data_type=r[1], nullable=(r[2] == "YES"), default=r[3], ordinal_position=r[4])
            for r in rows
        ]

    def get_primary_key(self, schema: str, table: str) -> PrimaryKey | None:
        rows = self._query(
            "SELECT tc.constraint_name, kcu.column_name FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name "
            "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = ? AND tc.table_name = ? "
            "ORDER BY kcu.ordinal_position",
            (schema, table),
        )
        if not rows:
            return None
        return PrimaryKey(name=rows[0][0], columns=[r[1] for r in rows])

    def list_foreign_keys(self, schema: str, table: str) -> list[ForeignKey]:
        rows = self._query(
            "SELECT fk.name, c1.name, OBJECT_NAME(fkc.referenced_object_id), c2.name, s2.name "
            "FROM sys.foreign_keys fk "
            "JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id "
            "JOIN sys.columns c1 ON fkc.parent_object_id = c1.object_id AND fkc.parent_column_id = c1.column_id "
            "JOIN sys.columns c2 ON fkc.referenced_object_id = c2.object_id AND fkc.referenced_column_id = c2.column_id "
            "JOIN sys.tables t ON fk.parent_object_id = t.object_id "
            "JOIN sys.schemas s ON t.schema_id = s.schema_id "
            "JOIN sys.tables t2 ON fkc.referenced_object_id = t2.object_id "
            "JOIN sys.schemas s2 ON t2.schema_id = s2.schema_id "
            "WHERE s.name = ? AND t.name = ? ORDER BY fk.name, fkc.constraint_column_id",
            (schema, table),
        )
        grouped: dict[str, list] = {}
        for row in rows:
            grouped.setdefault(row[0], []).append(row)
        result = []
        for name, group in grouped.items():
            result.append(ForeignKey(
                name=name, columns=[r[1] for r in group],
                referenced_table=group[0][2], referenced_columns=[r[3] for r in group],
                referenced_schema=group[0][4],
            ))
        return result

    def list_indexes(self, schema: str, table: str) -> list[DatabaseIndex]:
        rows = self._query(
            "SELECT i.name, c.name, i.is_unique FROM sys.indexes i "
            "JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id "
            "JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id "
            "JOIN sys.tables t ON i.object_id = t.object_id "
            "JOIN sys.schemas s ON t.schema_id = s.schema_id "
            "WHERE s.name = ? AND t.name = ? AND i.name IS NOT NULL "
            "ORDER BY i.name, ic.key_ordinal",
            (schema, table),
        )
        grouped: dict[str, list] = {}
        unique: dict[str, bool] = {}
        for name, column, is_unique in rows:
            grouped.setdefault(name, []).append(column)
            unique[name] = bool(is_unique)
        return [DatabaseIndex(name=name, columns=cols, unique=unique[name]) for name, cols in grouped.items()]

    def get_safe_row_count(self, schema: str, table: str) -> RowCountEstimate:
        rows = self._query(
            "SELECT SUM(p.rows) FROM sys.partitions p "
            "JOIN sys.tables t ON p.object_id = t.object_id "
            "JOIN sys.schemas s ON t.schema_id = s.schema_id "
            "WHERE s.name = ? AND t.name = ? AND p.index_id IN (0, 1)",
            (schema, table),
        )
        if rows and rows[0][0] is not None:
            return RowCountEstimate(value=int(rows[0][0]), method="catalog_estimate", confidence=DetectionConfidence.INFERRED)
        return RowCountEstimate(value=None, method="unavailable", confidence=DetectionConfidence.UNKNOWN)

    def close(self) -> None:
        self._conn.close()
