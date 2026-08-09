from universal_test.core.models.enums import DetectionConfidence
from universal_test.discovery.engine import discover


def test_python_fastapi_language_detected(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    names = {d.name: d for d in model.languages}
    assert "Python" in names
    assert names["Python"].confidence == DetectionConfidence.DETECTED
    assert model.primary_language == "Python"


def test_python_fastapi_project_type(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    types = {d.name for d in model.project_types}
    assert "python" in types


def test_node_react_language_and_frontend_type(fixture_path):
    model = discover(fixture_path("node-react"))
    languages = {d.name for d in model.languages}
    assert "JavaScript" in languages
    types = {d.name for d in model.project_types}
    assert "node" in types
    assert "frontend" in types


def test_dotnet_api_language_and_project_type(fixture_path):
    model = discover(fixture_path("dotnet-api"))
    languages = {d.name for d in model.languages}
    assert "C#" in languages
    types = {d.name for d in model.project_types}
    assert "dotnet" in types


def test_mixed_project_detects_both_languages(fixture_path):
    model = discover(fixture_path("mixed-project"))
    languages = {d.name for d in model.languages}
    assert "Python" in languages
    assert "JavaScript" in languages
    types = {d.name for d in model.project_types}
    assert "python" in types
    assert "node" in types
    assert "frontend" in types


def test_build_systems_detected(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    build_systems = {d.name for d in model.build_systems}
    assert "pip" in build_systems

    model = discover(fixture_path("dotnet-api"))
    build_systems = {d.name for d in model.build_systems}
    assert "dotnet sdk" in build_systems
