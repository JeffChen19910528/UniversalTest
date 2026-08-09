from universal_test.discovery.engine import discover


def test_openapi_file_detected(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    openapi = [d for d in model.apis if d.kind == "openapi"]
    assert openapi
    assert openapi[0].name == "OpenAPI/Swagger"


def test_no_api_evidence_without_any_marker(fixture_path):
    model = discover(fixture_path("dotnet-api"))
    kinds = {d.kind for d in model.apis}
    assert "openapi" not in kinds
    assert "graphql" not in kinds
