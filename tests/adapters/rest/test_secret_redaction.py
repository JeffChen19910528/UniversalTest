import json

from universal_test.adapters.rest.adapter import run
from universal_test.adapters.rest.auth import AuthConfig
from universal_test.adapters.rest.serializers import run_to_json, run_to_markdown, run_to_text
from .fixture_server import SESSION_COOKIE_VALUE, VALID_BEARER_TOKEN


def test_bearer_token_never_appears_in_test_case_or_result(openapi_fixture_path, live_server):
    auth_config = AuthConfig(bearer_token=VALID_BEARER_TOKEN)
    result = run(openapi_fixture_path("openapi-auth"), target=live_server.base_url, auth_config=auth_config)

    for tc in result.test_cases:
        assert VALID_BEARER_TOKEN not in json.dumps(tc.to_dict())
    for r in result.run_result.results:
        assert VALID_BEARER_TOKEN not in json.dumps(r.to_dict())
        assert VALID_BEARER_TOKEN not in r.message


def test_bearer_token_never_appears_in_serialized_output(openapi_fixture_path, live_server):
    auth_config = AuthConfig(bearer_token=VALID_BEARER_TOKEN)
    result = run(openapi_fixture_path("openapi-auth"), target=live_server.base_url, auth_config=auth_config)

    for rendered in (run_to_text(result), run_to_markdown(result), run_to_json(result)):
        assert VALID_BEARER_TOKEN not in rendered
        assert "Authorization" not in rendered  # the header name itself isn't echoed either


def test_wrong_credentials_do_not_leak_into_failure_message(openapi_fixture_path, live_server):
    auth_config = AuthConfig(bearer_token="super-secret-wrong-token")
    result = run(openapi_fixture_path("openapi-auth"), target=live_server.base_url, auth_config=auth_config)

    for r in result.run_result.results:
        assert "super-secret-wrong-token" not in r.message
        assert "super-secret-wrong-token" not in json.dumps(r.to_dict())


def test_api_key_never_appears_in_output(openapi_fixture_path, live_server):
    auth_config = AuthConfig(api_key_value="my-secret-api-key-value")
    # openapi-auth fixture only declares bearerAuth; this proves the value simply never
    # gets attached/leaked even when present in config but unused by the target spec.
    result = run(openapi_fixture_path("openapi-basic"), target=live_server.base_url, auth_config=auth_config)
    for rendered in (run_to_text(result), run_to_json(result)):
        assert "my-secret-api-key-value" not in rendered


def test_set_cookie_response_header_never_appears_in_output(openapi_fixture_path, live_server):
    # V1 hardening audit finding: a real Set-Cookie response header from a live
    # target was not redacted at all before this fix (core/redaction.py).
    result = run(openapi_fixture_path("cookie-project"), target=live_server.base_url)
    for r in result.run_result.results:
        assert SESSION_COOKIE_VALUE not in json.dumps(r.to_dict())
    for rendered in (run_to_text(result), run_to_json(result), run_to_markdown(result)):
        assert SESSION_COOKIE_VALUE not in rendered
