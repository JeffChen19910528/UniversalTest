from universal_test.discovery.engine import discover


def test_fastapi_detected(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    names = {d.name for d in model.frameworks}
    assert "FastAPI" in names


def test_react_detected(fixture_path):
    model = discover(fixture_path("node-react"))
    names = {d.name for d in model.frameworks}
    assert "React" in names
    # a React app's package.json should not also be mislabeled "Node.js" backend
    assert "Node.js" not in names


def test_aspnet_core_detected(fixture_path):
    model = discover(fixture_path("dotnet-api"))
    names = {d.name for d in model.frameworks}
    assert "ASP.NET Core" in names


def test_mixed_project_detects_both_frameworks(fixture_path):
    model = discover(fixture_path("mixed-project"))
    names = {d.name for d in model.frameworks}
    assert "FastAPI" in names
    assert "React" in names


def test_no_weak_framework_assertions_on_generic_project(fixture_path):
    model = discover(fixture_path("database-project"))
    # database-project has no web framework manifest evidence at all
    assert model.frameworks == []
