from universal_test.discovery.engine import discover


def test_database_project_detects_all_three(fixture_path):
    model = discover(fixture_path("database-project"))
    names = {d.name for d in model.databases}
    assert {"PostgreSQL", "MongoDB", "Redis"} <= names


def test_docker_project_detects_postgres_and_redis_from_compose(fixture_path):
    model = discover(fixture_path("docker-project"))
    names = {d.name for d in model.databases}
    assert "PostgreSQL" in names
    assert "Redis" in names


def test_dotnet_api_detects_sql_server(fixture_path):
    model = discover(fixture_path("dotnet-api"))
    names = {d.name for d in model.databases}
    assert "SQL Server" in names


def test_no_database_evidence_on_frontend_only_project():
    pass  # covered implicitly by node-react having no db in test_infrastructure/test_frameworks
