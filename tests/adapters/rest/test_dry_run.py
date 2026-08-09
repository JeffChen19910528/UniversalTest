import universal_test.adapters.rest.adapter as adapter_module
from universal_test.adapters.rest.adapter import run
from universal_test.adapters.rest.serializers import dry_run_to_json, dry_run_to_markdown, dry_run_to_text


def test_dry_run_never_calls_make_executor(openapi_fixture_path, monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("make_executor must not be called during --dry-run")

    monkeypatch.setattr(adapter_module, "make_executor", _boom)

    result = run(openapi_fixture_path("openapi-basic"), target="http://127.0.0.1:9/should-not-be-hit", dry_run=True)

    assert result.executed is False
    assert result.run_result is None
    assert len(result.test_cases) >= 2


def test_dry_run_lists_discovered_and_generated_counts(openapi_fixture_path):
    result = run(openapi_fixture_path("openapi-basic"), dry_run=True)
    text = dry_run_to_text(result)
    assert f"Discovered: {len(result.specification.endpoints)} endpoints" in text
    assert f"Generated: {len(result.test_cases)} test cases" in text
    assert "No HTTP requests executed." in text


def test_dry_run_json_and_markdown_render(openapi_fixture_path):
    result = run(openapi_fixture_path("openapi-basic"), dry_run=True)
    assert "generated_test_cases" in dry_run_to_json(result)
    assert dry_run_to_markdown(result).startswith("# Dry Run")


def test_dry_run_shows_expected_status_per_case(openapi_fixture_path):
    result = run(openapi_fixture_path("openapi-basic"), dry_run=True)
    positive_get = next(tc for tc in result.test_cases if tc.name == "GET /users")
    assert any(a.type == "status_code" and a.params["equals"] == 200 for a in positive_get.assertions)
