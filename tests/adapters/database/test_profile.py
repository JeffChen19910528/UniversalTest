import pytest

from universal_test.core.errors import ConfigurationError
from universal_test.adapters.database.profile import load_database_profile


def _write(tmp_path, content):
    path = tmp_path / "db.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_valid_sqlite_profile(tmp_path):
    path = _write(tmp_path, "database:\n  engine: sqlite\n  path: ./app.db\n  readonly: true\n")
    profile = load_database_profile(path)
    assert profile.engine == "sqlite"
    assert profile.readonly is True
    assert profile.path == "./app.db"


def test_valid_postgresql_profile_with_env_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_USER", "svc_account")
    monkeypatch.setenv("DB_PASSWORD", "hunter2")
    path = _write(tmp_path, """
database:
  engine: postgresql
  host: db.example.local
  port: 5432
  database: erp
  credentials:
    username_env: DB_USER
    password_env: DB_PASSWORD
  readonly: true
""")
    profile = load_database_profile(path)
    assert profile.credentials.username == "svc_account"
    assert profile.credentials.password == "hunter2"


def test_missing_readonly_true_is_rejected(tmp_path):
    path = _write(tmp_path, "database:\n  engine: sqlite\n  path: ./app.db\n")
    with pytest.raises(ConfigurationError, match="readonly"):
        load_database_profile(path)


def test_readonly_false_is_rejected(tmp_path):
    path = _write(tmp_path, "database:\n  engine: sqlite\n  path: ./app.db\n  readonly: false\n")
    with pytest.raises(ConfigurationError, match="readonly"):
        load_database_profile(path)


def test_unsupported_engine_is_rejected(tmp_path):
    path = _write(tmp_path, "database:\n  engine: oracle\n  readonly: true\n")
    with pytest.raises(ConfigurationError):
        load_database_profile(path)


def test_sqlite_without_path_is_rejected(tmp_path):
    path = _write(tmp_path, "database:\n  engine: sqlite\n  readonly: true\n")
    with pytest.raises(ConfigurationError, match="path"):
        load_database_profile(path)


def test_server_engine_without_host_is_rejected(tmp_path):
    path = _write(tmp_path, "database:\n  engine: postgresql\n  database: erp\n  readonly: true\n")
    with pytest.raises(ConfigurationError):
        load_database_profile(path)


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(ConfigurationError):
        load_database_profile(tmp_path / "does-not-exist.yaml")


def test_invalid_yaml_is_rejected(tmp_path):
    path = _write(tmp_path, "database: [unterminated")
    with pytest.raises(ConfigurationError):
        load_database_profile(path)


def test_missing_top_level_database_key_is_rejected(tmp_path):
    path = _write(tmp_path, "engine: sqlite\n")
    with pytest.raises(ConfigurationError):
        load_database_profile(path)


def test_profile_to_dict_never_includes_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_USER", "svc_account")
    monkeypatch.setenv("DB_PASSWORD", "SuperSecret123")
    path = _write(tmp_path, """
database:
  engine: postgresql
  host: db.example.local
  database: erp
  credentials:
    username_env: DB_USER
    password_env: DB_PASSWORD
  readonly: true
""")
    profile = load_database_profile(path)
    d = profile.to_dict()
    assert "SuperSecret123" not in str(d)
    assert "svc_account" not in str(d)
    assert d["credentials"] == "configured"


def test_credentials_not_configured_when_no_env_names_given(tmp_path):
    path = _write(tmp_path, "database:\n  engine: sqlite\n  path: ./app.db\n  readonly: true\n")
    profile = load_database_profile(path)
    assert profile.credentials.configured is False
    assert profile.to_dict()["credentials"] == "not configured"
