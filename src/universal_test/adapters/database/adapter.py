"""Database adapter orchestration: profile -> connected driver -> `DatabaseInfo`.

Every failure mode (missing driver, connection refused, timeout, bad
credentials, metadata query failure) is caught here and turned into a
`not_assessed_reason` string rather than propagating — connectivity
problems are never the assessed *project's* fault (Phase 6 brief §16), so
the caller should report `NOT_ASSESSED`, never `FAIL`.
"""

from __future__ import annotations

from dataclasses import dataclass

from universal_test.core.errors import DatabaseConnectionError, DatabaseDriverUnavailableError, DatabaseTimeoutError
from universal_test.adapters.database.base import DatabaseDriver, discover_database
from universal_test.adapters.database.models import DatabaseEngine, DatabaseInfo
from universal_test.adapters.database.mysql import MysqlDriver
from universal_test.adapters.database.postgresql import PostgresqlDriver
from universal_test.adapters.database.profile import DatabaseProfile
from universal_test.adapters.database.sqlite import SqliteDriver
from universal_test.adapters.database.sqlserver import SqlServerDriver


@dataclass
class DatabaseDiscoveryResult:
    profile: DatabaseProfile
    info: DatabaseInfo | None
    not_assessed_reason: str | None


def _build_driver(profile: DatabaseProfile) -> DatabaseDriver:
    if profile.engine == "sqlite":
        return SqliteDriver(profile.path, profile.connect_timeout_seconds)
    if profile.engine == "postgresql":
        return PostgresqlDriver(profile)
    if profile.engine == "mysql":
        return MysqlDriver(profile)
    if profile.engine == "sqlserver":
        return SqlServerDriver(profile)
    raise DatabaseDriverUnavailableError(f"unsupported database engine: {profile.engine!r}")  # pragma: no cover


def discover(profile: DatabaseProfile) -> DatabaseDiscoveryResult:
    try:
        driver = _build_driver(profile)
    except (DatabaseDriverUnavailableError, DatabaseConnectionError, DatabaseTimeoutError) as exc:
        return DatabaseDiscoveryResult(profile=profile, info=None, not_assessed_reason=str(exc))

    try:
        info = discover_database(DatabaseEngine(profile.engine), driver)
    except Exception as exc:  # noqa: BLE001 - any unexpected metadata-query failure -> NOT_ASSESSED, not a crash
        return DatabaseDiscoveryResult(
            profile=profile, info=None,
            not_assessed_reason=f"database metadata discovery failed: {type(exc).__name__}: {exc}",
        )
    finally:
        try:
            driver.close()
        except Exception:  # noqa: BLE001 - closing must never mask the real result
            pass

    return DatabaseDiscoveryResult(profile=profile, info=info, not_assessed_reason=None)
