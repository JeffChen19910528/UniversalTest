import pytest

from universal_test.core.errors import OpenApiError
from universal_test.adapters.rest.discovery_bridge import MultipleSpecsFoundError, select_specification
from universal_test.adapters.rest.normalizer import parse_specification


def test_discovery_finds_and_parses_basic_spec(openapi_fixture_path):
    project = openapi_fixture_path("openapi-basic")
    spec_path = select_specification(project, explicit_openapi=None)
    spec = parse_specification(spec_path)

    assert spec.openapi_version.startswith("3.")
    methods_and_paths = {(e.method.value, e.path) for e in spec.endpoints}
    assert ("get", "/users") in methods_and_paths
    assert ("post", "/users") in methods_and_paths


def test_multiple_specs_without_explicit_selection_raises(openapi_fixture_path):
    project = openapi_fixture_path("openapi-multiple")
    with pytest.raises(MultipleSpecsFoundError) as exc_info:
        select_specification(project, explicit_openapi=None)
    assert "openapi.yaml" in str(exc_info.value)
    assert "swagger.json" in str(exc_info.value)


def test_multiple_specs_with_explicit_selection_succeeds(openapi_fixture_path):
    project = openapi_fixture_path("openapi-multiple")
    explicit = str(project / "swagger.json")
    spec_path = select_specification(project, explicit_openapi=explicit)
    spec = parse_specification(spec_path)
    assert spec.title == "Multiple Fixture API (secondary)"


def test_invalid_spec_missing_paths_raises_openapi_error(openapi_fixture_path):
    project = openapi_fixture_path("openapi-invalid")
    spec_path = select_specification(project, explicit_openapi=None)
    with pytest.raises(OpenApiError):
        parse_specification(spec_path)


def test_nonexistent_explicit_openapi_path_raises(tmp_path):
    with pytest.raises(OpenApiError):
        select_specification(tmp_path, explicit_openapi=str(tmp_path / "nope.yaml"))


def test_auth_spec_captures_security_scheme(openapi_fixture_path):
    project = openapi_fixture_path("openapi-auth")
    spec_path = select_specification(project, explicit_openapi=None)
    spec = parse_specification(spec_path)
    assert "bearerAuth" in spec.security_schemes
    secure_endpoint = next(e for e in spec.endpoints if e.path == "/secure")
    assert secure_endpoint.security == ["bearerAuth"]
