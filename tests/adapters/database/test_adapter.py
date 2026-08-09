import socket

from universal_test.adapters.database.adapter import discover
from universal_test.adapters.database.profile import DatabaseCredentials, DatabaseProfile


def test_sqlite_success(sqlite_basic_path):
    profile = DatabaseProfile(engine="sqlite", readonly=True, path=str(sqlite_basic_path))
    result = discover(profile)
    assert result.info is not None
    assert result.not_assessed_reason is None


def test_sqlite_missing_file_is_not_assessed_not_a_crash(tmp_path):
    profile = DatabaseProfile(engine="sqlite", readonly=True, path=str(tmp_path / "nope.db"))
    result = discover(profile)
    assert result.info is None
    assert result.not_assessed_reason is not None


def _unused_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def test_postgresql_connection_failure_is_not_assessed_not_a_crash():
    profile = DatabaseProfile(
        engine="postgresql", readonly=True, host="127.0.0.1", port=_unused_port(), database="nope",
        connect_timeout_seconds=2.0,
    )
    result = discover(profile)
    assert result.info is None
    assert result.not_assessed_reason is not None


def test_mysql_connection_failure_is_not_assessed_not_a_crash():
    profile = DatabaseProfile(
        engine="mysql", readonly=True, host="127.0.0.1", port=_unused_port(), database="nope",
        connect_timeout_seconds=2.0,
    )
    result = discover(profile)
    assert result.info is None
    assert result.not_assessed_reason is not None


def test_credentials_never_appear_in_not_assessed_reason():
    creds = DatabaseCredentials(username="admin", password="TopSecretPassword99")
    profile = DatabaseProfile(
        engine="postgresql", readonly=True, host="127.0.0.1", port=_unused_port(), database="nope",
        credentials=creds, connect_timeout_seconds=2.0,
    )
    result = discover(profile)
    assert "TopSecretPassword99" not in (result.not_assessed_reason or "")
    assert "admin" not in (result.not_assessed_reason or "")


def test_result_to_dict_never_includes_credentials(sqlite_basic_path):
    creds = DatabaseCredentials(username="admin", password="TopSecretPassword99")
    profile = DatabaseProfile(engine="sqlite", readonly=True, path=str(sqlite_basic_path), credentials=creds)
    result = discover(profile)
    assert "TopSecretPassword99" not in str(result.profile.to_dict())
