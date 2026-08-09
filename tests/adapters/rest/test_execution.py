from universal_test.core.models.enums import ResultStatus
from universal_test.adapters.rest.adapter import run
from universal_test.adapters.rest.auth import AuthConfig
from .fixture_server import VALID_BEARER_TOKEN


def test_get_and_post_success(openapi_fixture_path, live_server):
    result = run(openapi_fixture_path("openapi-basic"), target=live_server.base_url)
    assert result.executed
    statuses = {r.id: r.status for r in result.run_result.results}
    assert set(statuses.values()) <= {ResultStatus.PASSED, ResultStatus.SKIPPED, ResultStatus.UNKNOWN}
    assert ResultStatus.PASSED in statuses.values()


def test_negative_validation_tests_pass_against_real_server(openapi_fixture_path, live_server):
    result = run(openapi_fixture_path("openapi-basic"), target=live_server.base_url)
    by_name = {tc.id: tc.name for tc in result.test_cases}
    for r in result.run_result.results:
        name = by_name[r.id]
        if "missing required body field" in name or "unsupported content type" in name:
            assert r.status == ResultStatus.PASSED, f"{name}: {r.message} / {[a.message for a in r.assertion_results]}"


def test_auth_required_without_credentials_is_skipped(openapi_fixture_path, live_server):
    result = run(openapi_fixture_path("openapi-auth"), target=live_server.base_url)
    assert result.executed
    assert all(r.status == ResultStatus.SKIPPED for r in result.run_result.results)
    assert "authentication required" in result.run_result.results[0].message


def test_auth_required_with_bearer_token_succeeds(openapi_fixture_path, live_server):
    auth_config = AuthConfig(bearer_token=VALID_BEARER_TOKEN)
    result = run(openapi_fixture_path("openapi-auth"), target=live_server.base_url, auth_config=auth_config)
    assert result.executed
    assert all(r.status == ResultStatus.PASSED for r in result.run_result.results)


def test_auth_required_with_wrong_bearer_token_fails_not_errors(openapi_fixture_path, live_server):
    auth_config = AuthConfig(bearer_token="wrong-token")
    result = run(openapi_fixture_path("openapi-auth"), target=live_server.base_url, auth_config=auth_config)
    assert result.executed
    # a wrong credential is an assertion failure (server said 401, we expected 200), not an ERROR
    assert all(r.status == ResultStatus.FAILED for r in result.run_result.results)


def test_schema_validation_pass_and_fail(openapi_fixture_path, live_server):
    result = run(openapi_fixture_path("openapi-schema"), target=live_server.base_url)
    assert result.executed
    by_name = {r.id: (tc.name, r) for tc, r in zip(result.test_cases, result.run_result.results)}
    good = next(name_result for name_result in by_name.values() if name_result[0] == "GET /widgets")
    broken = next(name_result for name_result in by_name.values() if name_result[0] == "GET /widgets-broken")
    assert good[1].status == ResultStatus.PASSED
    assert broken[1].status == ResultStatus.FAILED
    assert any(a.assertion.type == "json_schema_valid" and not a.passed for a in broken[1].assertion_results)


def test_connection_failure_is_an_error_not_a_failed_assertion(openapi_fixture_path):
    # nothing is listening on this port -- connection should be refused immediately
    result = run(openapi_fixture_path("openapi-basic"), target="http://127.0.0.1:1")
    assert result.executed
    assert all(r.status == ResultStatus.ERROR for r in result.run_result.results)
    assert all(r.evidence[0].data["type"] in ("NetworkError", "TargetError") for r in result.run_result.results)


def test_timeout_is_an_error_with_a_distinct_exception_type(openapi_fixture_path, live_server):
    result = run(
        openapi_fixture_path("openapi-basic"), target=live_server.base_url, timeout_seconds=0.05,
    )
    assert result.executed
    by_name = {r.id: (tc.name, r) for tc, r in zip(result.test_cases, result.run_result.results)}
    _, slow_result = next(nr for nr in by_name.values() if nr[0] == "GET /slow")
    assert slow_result.status == ResultStatus.ERROR
    assert slow_result.evidence[0].data["type"] == "RequestTimeoutError"


def test_target_override_wins_over_spec_servers(openapi_fixture_path, live_server, monkeypatch):
    # openapi-basic declares no `servers` at all; add one pointing somewhere unreachable
    # to prove --target is what's actually used, never the spec's own servers[].
    import universal_test.adapters.rest.normalizer as normalizer_module
    original = normalizer_module.parse_specification

    def _with_fake_server(path):
        spec = original(path)
        spec.servers = ["https://production.example.invalid"]
        return spec

    monkeypatch.setattr("universal_test.adapters.rest.adapter.parse_specification", _with_fake_server)

    result = run(openapi_fixture_path("openapi-basic"), target=live_server.base_url)
    assert result.executed
    assert any(r.status == ResultStatus.PASSED for r in result.run_result.results)
