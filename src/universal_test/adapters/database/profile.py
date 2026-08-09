"""Explicit database connection profile (Phase 6 brief §4/§6).

Discovering "SQL Server detected" in a project (Phase 2) never implies
permission to connect to it. A `DatabaseProfile` is the *only* way the
database adapter learns of a target, and it is only ever built from a
profile the user explicitly supplies (`--database-profile <path>`) — never
from anything found while scanning the project.

Credentials are read from named environment variables only (same
`*_env` convention as `adapters/rest/auth.py`) — never taken directly from
the profile YAML, so a credential is never sitting in a file that might get
committed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from universal_test.core.errors import ConfigurationError


@dataclass(frozen=True)
class DatabaseCredentials:
    username: str | None
    password: str | None

    @property
    def configured(self) -> bool:
        return self.username is not None or self.password is not None


@dataclass(frozen=True)
class DatabaseProfile:
    engine: str  # "sqlserver" | "postgresql" | "mysql" | "sqlite"
    readonly: bool
    host: str | None = None
    port: int | None = None
    database: str | None = None
    path: str | None = None  # sqlite only
    credentials: DatabaseCredentials = DatabaseCredentials(username=None, password=None)
    connect_timeout_seconds: float = 10.0
    query_timeout_seconds: float = 10.0

    def to_dict(self) -> dict:
        """Connection-identifying fields only — never credentials (Phase 6 brief §5)."""
        return {
            "engine": self.engine,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "path": self.path,
            "readonly": self.readonly,
            "credentials": "configured" if self.credentials.configured else "not configured",
        }


_SUPPORTED_ENGINES = {"sqlserver", "postgresql", "mysql", "sqlite"}


def load_database_profile(path: str | Path) -> DatabaseProfile:
    profile_path = Path(path)
    if not profile_path.is_file():
        raise ConfigurationError(f"--database-profile path does not exist or is not a file: {profile_path}")

    try:
        raw = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {profile_path}: {exc}") from exc

    if not isinstance(raw, dict) or "database" not in raw or not isinstance(raw["database"], dict):
        raise ConfigurationError(f"{profile_path} must contain a top-level 'database:' mapping")

    section = raw["database"]

    engine = section.get("engine")
    if engine not in _SUPPORTED_ENGINES:
        raise ConfigurationError(
            f"database.engine must be one of {sorted(_SUPPORTED_ENGINES)}, got {engine!r}"
        )

    # Safety default: readonly must be explicitly true. Missing/false is refused
    # rather than assumed safe (Phase 6 brief §6: "拒絕執行，而不是假設安全").
    if section.get("readonly") is not True:
        raise ConfigurationError(
            "database.readonly must be explicitly set to `true` in the profile; "
            "refusing to connect without an explicit read-only acknowledgement"
        )

    creds_section = section.get("credentials", {}) or {}
    if not isinstance(creds_section, dict):
        raise ConfigurationError("database.credentials must be a mapping")
    username = os.environ.get(creds_section["username_env"]) if creds_section.get("username_env") else None
    password = os.environ.get(creds_section["password_env"]) if creds_section.get("password_env") else None
    credentials = DatabaseCredentials(username=username, password=password)

    if engine == "sqlite":
        if not section.get("path"):
            raise ConfigurationError("database.path is required when database.engine is 'sqlite'")
    else:
        if not section.get("host") or not section.get("database"):
            raise ConfigurationError(
                f"database.host and database.database are required for engine {engine!r}"
            )

    return DatabaseProfile(
        engine=engine,
        readonly=True,
        host=section.get("host"),
        port=section.get("port"),
        database=section.get("database"),
        path=section.get("path"),
        credentials=credentials,
        connect_timeout_seconds=float(section.get("connect_timeout_seconds", 10.0)),
        query_timeout_seconds=float(section.get("query_timeout_seconds", 10.0)),
    )
