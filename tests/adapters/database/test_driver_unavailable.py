"""Verifies graceful degradation when an optional database driver isn't
installed — simulated via `sys.modules[name] = None`, which makes Python's
import system raise `ImportError` for that module without requiring us to
actually uninstall anything from the test environment.
"""

import sys

import pytest

from universal_test.core.errors import DatabaseDriverUnavailableError
from universal_test.adapters.database.adapter import discover
from universal_test.adapters.database.mysql import MysqlDriver
from universal_test.adapters.database.postgresql import PostgresqlDriver
from universal_test.adapters.database.profile import DatabaseProfile
from universal_test.adapters.database.sqlserver import SqlServerDriver


@pytest.fixture
def hide_module(monkeypatch):
    def _hide(name: str):
        monkeypatch.setitem(sys.modules, name, None)
    return _hide


def test_postgresql_driver_unavailable(hide_module):
    hide_module("psycopg2")
    profile = DatabaseProfile(engine="postgresql", readonly=True, host="x", database="x")
    with pytest.raises(DatabaseDriverUnavailableError, match="psycopg2"):
        PostgresqlDriver(profile)


def test_mysql_driver_unavailable(hide_module):
    hide_module("mysql.connector")
    hide_module("mysql")
    profile = DatabaseProfile(engine="mysql", readonly=True, host="x", database="x")
    with pytest.raises(DatabaseDriverUnavailableError, match="mysql-connector-python"):
        MysqlDriver(profile)


def test_sqlserver_driver_unavailable(hide_module):
    hide_module("pyodbc")
    profile = DatabaseProfile(engine="sqlserver", readonly=True, host="x", database="x")
    with pytest.raises(DatabaseDriverUnavailableError, match="pyodbc"):
        SqlServerDriver(profile)


def test_discover_reports_not_assessed_not_a_crash_when_driver_missing(hide_module):
    hide_module("psycopg2")
    profile = DatabaseProfile(engine="postgresql", readonly=True, host="x", database="x")
    result = discover(profile)
    assert result.info is None
    assert "psycopg2" in result.not_assessed_reason
    assert "install" in result.not_assessed_reason.lower()


def test_discover_never_auto_installs_anything(hide_module, monkeypatch):
    # a missing driver must never trigger pip/subprocess -- verify no subprocess call happens
    import subprocess
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
    hide_module("psycopg2")
    profile = DatabaseProfile(engine="postgresql", readonly=True, host="x", database="x")
    discover(profile)
    assert calls == []
