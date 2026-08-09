from universal_test.adapters.rest.auth import (
    AuthConfig,
    available_scheme_names,
    build_auth_headers,
    resolve_auth_from_env,
)
from universal_test.adapters.rest.models import SecurityScheme


def test_resolve_auth_from_env_reads_set_variable(monkeypatch):
    monkeypatch.setenv("MY_TOKEN", "abc123")
    config, warnings = resolve_auth_from_env(bearer_token_env="MY_TOKEN")
    assert config.bearer_token == "abc123"
    assert warnings == []


def test_resolve_auth_from_env_warns_on_unset_variable(monkeypatch):
    monkeypatch.delenv("DOES_NOT_EXIST", raising=False)
    config, warnings = resolve_auth_from_env(bearer_token_env="DOES_NOT_EXIST")
    assert config.bearer_token is None
    assert len(warnings) == 1
    assert "DOES_NOT_EXIST" in warnings[0]


def test_available_scheme_names_bearer():
    schemes = {"bearerAuth": SecurityScheme(name="bearerAuth", type="http", scheme="bearer")}
    assert available_scheme_names(AuthConfig(bearer_token="x"), schemes) == {"bearerAuth"}
    assert available_scheme_names(AuthConfig(), schemes) == set()


def test_available_scheme_names_api_key():
    schemes = {"apiKeyAuth": SecurityScheme(name="apiKeyAuth", type="apiKey", location="header", param_name="X-API-Key")}
    assert available_scheme_names(AuthConfig(api_key_value="k"), schemes) == {"apiKeyAuth"}


def test_available_scheme_names_basic_requires_both_fields():
    schemes = {"basicAuth": SecurityScheme(name="basicAuth", type="http", scheme="basic")}
    assert available_scheme_names(AuthConfig(basic_username="u"), schemes) == set()
    assert available_scheme_names(AuthConfig(basic_username="u", basic_password="p"), schemes) == {"basicAuth"}


def test_build_auth_headers_bearer():
    schemes = {"bearerAuth": SecurityScheme(name="bearerAuth", type="http", scheme="bearer")}
    headers, query = build_auth_headers(["bearerAuth"], schemes, AuthConfig(bearer_token="tok"))
    assert headers == {"Authorization": "Bearer tok"}
    assert query == {}


def test_build_auth_headers_api_key_header():
    schemes = {"apiKeyAuth": SecurityScheme(name="apiKeyAuth", type="apiKey", location="header", param_name="X-API-Key")}
    headers, query = build_auth_headers(["apiKeyAuth"], schemes, AuthConfig(api_key_value="secret"))
    assert headers == {"X-API-Key": "secret"}
    assert query == {}


def test_build_auth_headers_api_key_query():
    schemes = {"apiKeyAuth": SecurityScheme(name="apiKeyAuth", type="apiKey", location="query", param_name="api_key")}
    headers, query = build_auth_headers(["apiKeyAuth"], schemes, AuthConfig(api_key_value="secret"))
    assert headers == {}
    assert query == {"api_key": "secret"}


def test_build_auth_headers_basic():
    schemes = {"basicAuth": SecurityScheme(name="basicAuth", type="http", scheme="basic")}
    headers, _ = build_auth_headers(["basicAuth"], schemes, AuthConfig(basic_username="u", basic_password="p"))
    assert headers["Authorization"].startswith("Basic ")


def test_build_auth_headers_no_matching_credential_returns_empty():
    schemes = {"bearerAuth": SecurityScheme(name="bearerAuth", type="http", scheme="bearer")}
    headers, query = build_auth_headers(["bearerAuth"], schemes, AuthConfig())
    assert headers == {} and query == {}
