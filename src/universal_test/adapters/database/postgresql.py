"""PostgreSQL driver (optional `psycopg2-binary` dependency).

Connects with `default_transaction_read_only=on` set at the session level
(defense in depth on top of the "no execute(sql) method exists at all"
architectural guarantee — see `base.py`). System schemas (`pg_catalog`,
`information_schema`, `pg_toast*`) are excluded by default so an
application's own tables are never buried under Postgres internals
(Phase 6 brief §9).
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

_EXCLUDED_SCHEMAS_PREFIX = "pg_"
_EXCLUDED_SCHEMAS = {"information_schema"}


class PostgresqlDriver(DatabaseDriver):
    def __init__(self, profile: DatabaseProfile) -> None:
        try:
            import psycopg2
        except ImportError as exc:
            raise DatabaseDriverUnavailableError(
                "the 'psycopg2' driver is not installed; install with "
                "`pip install universal-test[database]` to assess PostgreSQL databases"
            ) from exc

        self._psycopg2 = psycopg2
        try:
            self._conn = psycopg2.connect(
                host=profile.host, port=profile.port, dbname=profile.database,
                user=profile.credentials.username, password=profile.credentials.password,
                connect_timeout=int(profile.connect_timeout_seconds),
                options="-c default_transaction_read_only=on",
            )
            self._conn.autocommit = True
            with self._conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {int(profile.query_timeout_seconds * 1000)}")
        except psycopg2.OperationalError as exc:
            message = str(exc).lower()
            if "timeout" in message:
                raise DatabaseTimeoutError(f"connecting to PostgreSQL timed out: {exc}") from exc
            raise DatabaseConnectionError(f"could not connect to PostgreSQL: {exc}") from exc

        self._database = profile.database

    def _query(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def get_server_version(self) -> str | None:
        rows = self._query("SELECT version()")
        return rows[0][0] if rows else None

    def get_database_name(self) -> str | None:
        return self._database

    def list_schemas(self) -> list[str]:
        rows = self._query(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT LIKE %s AND schema_name NOT IN %s ORDER BY schema_name",
            (f"{_EXCLUDED_SCHEMAS_PREFIX}%", tuple(_EXCLUDED_SCHEMAS)),
        )
        return [r[0] for r in rows]

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
            "SELECT tc.constraint_name, kcu.column_name FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
            "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s AND tc.table_name = %s "
            "ORDER BY kcu.ordinal_position",
            (schema, table),
        )
        if not rows:
            return None
        return PrimaryKey(name=rows[0][0], columns=[r[1] for r in rows])

    def list_foreign_keys(self, schema: str, table: str) -> list[ForeignKey]:
        rows = self._query(
            "SELECT tc.constraint_name, kcu.column_name, ccu.table_name, ccu.column_name, ccu.table_schema "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON tc.constraint_name = ccu.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s AND tc.table_name = %s "
            "ORDER BY tc.constraint_name, kcu.ordinal_position",
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
            "SELECT i.relname, a.attname, ix.indisunique "
            "FROM pg_class t "
            "JOIN pg_index ix ON t.oid = ix.indrelid "
            "JOIN pg_class i ON i.oid = ix.indexrelid "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey) "
            "JOIN pg_namespace n ON n.oid = t.relnamespace "
            "WHERE t.relkind = 'r' AND t.relname = %s AND n.nspname = %s "
            "ORDER BY i.relname, a.attnum",
            (table, schema),
        )
        grouped: dict[str, list] = {}
        unique: dict[str, bool] = {}
        for name, column, is_unique in rows:
            grouped.setdefault(name, []).append(column)
            unique[name] = bool(is_unique)
        return [DatabaseIndex(name=name, columns=cols, unique=unique[name]) for name, cols in grouped.items()]

    def get_safe_row_count(self, schema: str, table: str) -> RowCountEstimate:
        rows = self._query(
            "SELECT n_live_tup FROM pg_stat_user_tables WHERE schemaname = %s AND relname = %s",
            (schema, table),
        )
        if rows and rows[0][0] is not None:
            return RowCountEstimate(value=int(rows[0][0]), method="catalog_estimate", confidence=DetectionConfidence.INFERRED)
        return RowCountEstimate(value=None, method="unavailable", confidence=DetectionConfidence.UNKNOWN)

    def close(self) -> None:
        self._conn.close()
