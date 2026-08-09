"""SQLite driver — stdlib `sqlite3` only, no optional dependency.

Opened via the read-only URI mode (`file:<path>?mode=ro`) so the connection
itself is incapable of writing, independent of which queries this module
happens to issue (Phase 6 brief §11: "不得直接用 writable connection 打開
production database").
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote

from universal_test.core.errors import DatabaseConnectionError
from universal_test.core.models.enums import DetectionConfidence
from universal_test.adapters.database.base import DatabaseDriver
from universal_test.adapters.database.models import (
    DatabaseColumn,
    DatabaseIndex,
    ForeignKey,
    PrimaryKey,
    RowCountEstimate,
)

_MAIN_SCHEMA = "main"


class SqliteDriver(DatabaseDriver):
    def __init__(self, path: str, connect_timeout_seconds: float = 10.0) -> None:
        db_path = Path(path)
        if not db_path.is_file():
            raise DatabaseConnectionError(f"SQLite database file does not exist: {db_path}")
        uri = f"file:{quote(str(db_path.resolve()))}?mode=ro"
        try:
            self._conn = sqlite3.connect(uri, uri=True, timeout=connect_timeout_seconds)
        except sqlite3.Error as exc:
            raise DatabaseConnectionError(f"could not open SQLite database read-only: {exc}") from exc
        self._path = db_path

    def get_server_version(self) -> str | None:
        return f"SQLite {sqlite3.sqlite_version}"

    def get_database_name(self) -> str | None:
        return self._path.name

    def list_schemas(self) -> list[str]:
        return [_MAIN_SCHEMA]

    def list_tables(self, schema: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]

    def list_views(self, schema: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]

    def list_columns(self, schema: str, table: str) -> list[DatabaseColumn]:
        rows = self._conn.execute(f"PRAGMA table_info({self._quote_ident(table)})").fetchall()
        return [
            DatabaseColumn(
                name=row[1], data_type=row[2] or "unknown", nullable=(row[3] == 0),
                default=row[4], ordinal_position=row[0],
            )
            for row in rows
        ]

    def get_primary_key(self, schema: str, table: str) -> PrimaryKey | None:
        rows = self._conn.execute(f"PRAGMA table_info({self._quote_ident(table)})").fetchall()
        pk_columns = [(row[5], row[1]) for row in rows if row[5] and row[5] > 0]
        if not pk_columns:
            return None
        pk_columns.sort(key=lambda item: item[0])
        return PrimaryKey(name=None, columns=[name for _, name in pk_columns])

    def list_foreign_keys(self, schema: str, table: str) -> list[ForeignKey]:
        rows = self._conn.execute(f"PRAGMA foreign_key_list({self._quote_ident(table)})").fetchall()
        grouped: dict[int, list] = {}
        for row in rows:
            grouped.setdefault(row[0], []).append(row)
        result = []
        for fk_id, fk_rows in grouped.items():
            fk_rows.sort(key=lambda r: r[1])
            result.append(ForeignKey(
                name=None,
                columns=[r[3] for r in fk_rows],
                referenced_table=fk_rows[0][2],
                referenced_columns=[r[4] for r in fk_rows],
            ))
        return result

    def list_indexes(self, schema: str, table: str) -> list[DatabaseIndex]:
        rows = self._conn.execute(f"PRAGMA index_list({self._quote_ident(table)})").fetchall()
        indexes = []
        for row in rows:
            index_name, unique = row[1], bool(row[2])
            col_rows = self._conn.execute(f"PRAGMA index_info({self._quote_ident(index_name)})").fetchall()
            columns = [c[2] for c in sorted(col_rows, key=lambda c: c[0])]
            indexes.append(DatabaseIndex(name=index_name, columns=columns, unique=unique))
        return indexes

    def get_safe_row_count(self, schema: str, table: str) -> RowCountEstimate:
        try:
            has_stats = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_stat1'"
            ).fetchone()
            if has_stats:
                row = self._conn.execute(
                    "SELECT stat FROM sqlite_stat1 WHERE tbl=?", (table,)
                ).fetchone()
                if row and row[0]:
                    estimate = int(str(row[0]).split()[0])
                    return RowCountEstimate(value=estimate, method="catalog_estimate", confidence=DetectionConfidence.INFERRED)
        except (sqlite3.Error, ValueError):
            pass
        return RowCountEstimate(value=None, method="unavailable", confidence=DetectionConfidence.UNKNOWN)

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _quote_ident(identifier: str) -> str:
        # PRAGMA statements can't use parameter binding for identifiers; double-quoting
        # (with embedded quotes escaped) is SQLite's standard identifier-quoting rule.
        return '"' + identifier.replace('"', '""') + '"'
