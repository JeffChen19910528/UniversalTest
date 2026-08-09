"""Normalized, engine-independent database model (Phase 6 brief §12).

The assessment layer only ever sees these dataclasses — never a raw
`pyodbc`/`psycopg2`/`mysql.connector`/`sqlite3` cursor or row object. Every
engine driver (`sqlserver.py`/`postgresql.py`/`mysql.py`/`sqlite.py`) is
responsible for building this model from its own metadata queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from universal_test.core.models.enums import DetectionConfidence
from universal_test.core.models.evidence import Evidence


class DatabaseEngine(str, Enum):
    SQLSERVER = "sqlserver"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"


@dataclass(frozen=True)
class DatabaseColumn:
    name: str
    data_type: str
    nullable: bool
    default: str | None = None
    ordinal_position: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "data_type": self.data_type, "nullable": self.nullable,
            "default": self.default, "ordinal_position": self.ordinal_position,
        }


@dataclass(frozen=True)
class PrimaryKey:
    name: str | None
    columns: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "columns": self.columns}


@dataclass(frozen=True)
class ForeignKey:
    name: str | None
    columns: list[str]
    referenced_table: str
    referenced_columns: list[str]
    referenced_schema: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "columns": self.columns,
            "referenced_schema": self.referenced_schema,
            "referenced_table": self.referenced_table, "referenced_columns": self.referenced_columns,
        }


@dataclass(frozen=True)
class DatabaseIndex:
    name: str
    columns: list[str]
    unique: bool

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "columns": self.columns, "unique": self.unique}


@dataclass(frozen=True)
class RowCountEstimate:
    """A row count that was safe to obtain — see `Phase 6 brief §15`: prefer a
    catalog/metadata-based estimate over `SELECT COUNT(*)`, which can be
    expensive on a large, unfamiliar table. `value is None` means "could not
    be safely determined" (never "the table is empty").
    """

    value: int | None
    method: str  # e.g. "catalog_estimate", "exact_count_skipped", "unavailable"
    confidence: DetectionConfidence

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "method": self.method, "confidence": self.confidence.value}


@dataclass
class DatabaseTable:
    schema: str
    name: str
    columns: list[DatabaseColumn] = field(default_factory=list)
    primary_key: PrimaryKey | None = None
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    indexes: list[DatabaseIndex] = field(default_factory=list)
    row_count: RowCountEstimate | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "name": self.name,
            "columns": [c.to_dict() for c in self.columns],
            "primary_key": self.primary_key.to_dict() if self.primary_key else None,
            "foreign_keys": [fk.to_dict() for fk in self.foreign_keys],
            "indexes": [i.to_dict() for i in self.indexes],
            "row_count": self.row_count.to_dict() if self.row_count else None,
        }


@dataclass
class DatabaseView:
    schema: str
    name: str
    columns: list[DatabaseColumn] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "name": self.name, "columns": [c.to_dict() for c in self.columns]}


@dataclass
class DatabaseSchema:
    name: str
    tables: list[DatabaseTable] = field(default_factory=list)
    views: list[DatabaseView] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tables": [t.to_dict() for t in self.tables],
            "views": [v.to_dict() for v in self.views],
        }


@dataclass
class DatabaseInfo:
    engine: DatabaseEngine
    server_version: str | None
    database_name: str | None
    schemas: list[DatabaseSchema] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine.value,
            "server_version": self.server_version,
            "database_name": self.database_name,
            "schemas": [s.to_dict() for s in self.schemas],
            "evidence": [e.to_dict() for e in self.evidence],
            "warnings": self.warnings,
        }
