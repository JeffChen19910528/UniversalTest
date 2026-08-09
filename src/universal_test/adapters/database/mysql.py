"""MySQL driver (optional `mysql-connector-python` dependency).

The session is switched to `SET SESSION TRANSACTION READ ONLY` right after
connecting — defense in depth on top of the architectural guarantee that no
`execute(sql)` capability is exposed at all (see `base.py`). In MySQL a
"schema" and a "database" are the same thing, so `list_schemas()` returns
just the one connected database rather than enumerating every database the
credential could see (Phase 6 brief §10 implies scoping to the configured
database, matching PostgreSQL's default-schema-scoping principle in §9).
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


class MysqlDriver(DatabaseDriver):
    def __init__(self, profile: DatabaseProfile) -> None:
        try:
            import mysql.connector
            from mysql.connector import errorcode
        except ImportError as exc:
            raise DatabaseDriverUnavailableError(
                "the 'mysql-connector-python' driver is not installed; install with "
                "`pip install universal-test[database]` to assess MySQL databases"
            ) from exc

        self._mysql = mysql.connector
        try:
            self._conn = mysql.connector.connect(
                host=profile.host, port=profile.port or 3306, database=profile.database,
                user=profile.credentials.username, password=profile.credentials.password,
                connection_timeout=int(profile.connect_timeout_seconds),
            )
            cur = self._conn.cursor()
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            cur.execute(f"SET SESSION MAX_EXECUTION_TIME={int(profile.query_timeout_seconds * 1000)}")
            cur.close()
        except mysql.connector.Error as exc:
            if exc.errno == errorcode.CR_CONN_HOST_ERROR or "timed out" in str(exc).lower():
                raise DatabaseTimeoutError(f"connecting to MySQL timed out: {exc}") from exc
            raise DatabaseConnectionError(f"could not connect to MySQL: {exc}") from exc

        self._database = profile.database

    def _query(self, sql: str, params: tuple = ()) -> list[tuple]:
        cur = self._conn.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()

    def get_server_version(self) -> str | None:
        rows = self._query("SELECT VERSION()")
        return rows[0][0] if rows else None

    def get_database_name(self) -> str | None:
        return self._database

    def list_schemas(self) -> list[str]:
        return [self._database] if self._database else []

    def list_tables(self, schema: str) -> list[str]:
        rows = self._query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name",
            (schema,),
        )
        return [r[0] for r in rows]

    def list_views(self, schema: str) -> list[str]:
        rows = self._query(
            "SELECT table_name FROM information_schema.views WHERE table_schema = %s ORDER BY table_name",
            (schema,),
        )
        return [r[0] for r in rows]

    def list_columns(self, schema: str, table: str) -> list[DatabaseColumn]:
        rows = self._query(
            "SELECT column_name, data_type, is_nullable, column_default, ordinal_position "
            "FROM information_schema.columns WHERE table_schema = %s AND table_name = %s "
            "ORDER BY ordinal_position",
            (schema, table),
        )
        return [
            DatabaseColumn(name=r[0], data_type=r[1], nullable=(r[2] == "YES"), default=r[3], ordinal_position=r[4])
            for r in rows
        ]

    def get_primary_key(self, schema: str, table: str) -> PrimaryKey | None:
        rows = self._query(
            "SELECT column_name FROM information_schema.key_column_usage "
            "WHERE table_schema = %s AND table_name = %s AND constraint_name = 'PRIMARY' "
            "ORDER BY ordinal_position",
            (schema, table),
        )
        if not rows:
            return None
        return PrimaryKey(name="PRIMARY", columns=[r[0] for r in rows])

    def list_foreign_keys(self, schema: str, table: str) -> list[ForeignKey]:
        rows = self._query(
            "SELECT constraint_name, column_name, referenced_table_name, referenced_column_name "
            "FROM information_schema.key_column_usage "
            "WHERE table_schema = %s AND table_name = %s AND referenced_table_name IS NOT NULL "
            "ORDER BY constraint_name, ordinal_position",
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
                referenced_schema=schema,
            ))
        return result

    def list_indexes(self, schema: str, table: str) -> list[DatabaseIndex]:
        rows = self._query(
            "SELECT index_name, column_name, non_unique FROM information_schema.statistics "
            "WHERE table_schema = %s AND table_name = %s ORDER BY index_name, seq_in_index",
            (schema, table),
        )
        grouped: dict[str, list] = {}
        unique: dict[str, bool] = {}
        for name, column, non_unique in rows:
            grouped.setdefault(name, []).append(column)
            unique[name] = not bool(non_unique)
        return [DatabaseIndex(name=name, columns=cols, unique=unique[name]) for name, cols in grouped.items()]

    def get_safe_row_count(self, schema: str, table: str) -> RowCountEstimate:
        rows = self._query(
            "SELECT table_rows FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
            (schema, table),
        )
        if rows and rows[0][0] is not None:
            return RowCountEstimate(value=int(rows[0][0]), method="catalog_estimate", confidence=DetectionConfidence.INFERRED)
        return RowCountEstimate(value=None, method="unavailable", confidence=DetectionConfidence.UNKNOWN)

    def close(self) -> None:
        self._conn.close()
