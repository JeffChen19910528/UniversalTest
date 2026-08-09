from universal_test.discovery.engine import discover


def test_pytest_detected(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    names = {d.name for d in model.test_frameworks}
    assert "pytest" in names


def test_jest_detected(fixture_path):
    model = discover(fixture_path("node-react"))
    names = {d.name for d in model.test_frameworks}
    assert "Jest" in names


def test_xunit_detected(fixture_path):
    model = discover(fixture_path("dotnet-api"))
    names = {d.name for d in model.test_frameworks}
    assert "xUnit" in names


def test_test_directories_found(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    assert "tests" in model.test_directories
