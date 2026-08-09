from universal_test.discovery.engine import discover


def test_docker_and_compose_detected(fixture_path):
    model = discover(fixture_path("docker-project"))
    names = {d.name for d in model.infrastructure}
    assert "Docker" in names
    assert "Docker Compose" in names


def test_github_actions_detected(fixture_path):
    model = discover(fixture_path("node-react"))
    names = {d.name for d in model.infrastructure}
    assert "GitHub Actions" in names


def test_mixed_project_has_docker_and_actions(fixture_path):
    model = discover(fixture_path("mixed-project"))
    names = {d.name for d in model.infrastructure}
    assert "Docker" in names
    assert "GitHub Actions" in names


def test_no_infrastructure_on_plain_python_project(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    assert model.infrastructure == []
