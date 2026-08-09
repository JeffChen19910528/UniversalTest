import pytest

from universal_test.core.errors import DiscoveryError
from universal_test.discovery.engine import discover


def test_empty_repository_does_not_crash(tmp_path):
    model = discover(tmp_path)
    assert model.file_count == 0
    assert model.languages == []
    assert model.primary_language is None
    assert model.project_types[0].name == "generic"
    assert model.secrets == []
    assert model.warnings == []


def test_unknown_project_with_unrelated_files(tmp_path):
    (tmp_path / "notes.txt").write_text("just some notes", encoding="utf-8")
    (tmp_path / "data.csv").write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    model = discover(tmp_path)
    assert model.languages == []
    assert model.project_types[0].name == "generic"
    assert model.frameworks == []


def test_malformed_pyproject_toml_does_not_abort_scan(tmp_path):
    (tmp_path / "pyproject.toml").write_text("this is [ not valid toml", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")

    model = discover(tmp_path)
    # scan completes and still finds the Python file by extension
    languages = {d.name for d in model.languages}
    assert "Python" in languages
    assert any("pyproject.toml" in w for w in model.warnings)


def test_malformed_package_json_does_not_abort_scan(tmp_path):
    (tmp_path / "package.json").write_text("{not valid json", encoding="utf-8")
    (tmp_path / "index.js").write_text("console.log('hi')", encoding="utf-8")

    model = discover(tmp_path)
    languages = {d.name for d in model.languages}
    assert "JavaScript" in languages
    assert any("package.json" in w for w in model.warnings)


def test_incomplete_project_missing_source_but_has_manifest(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "incomplete"}', encoding="utf-8")

    model = discover(tmp_path)
    types = {d.name for d in model.project_types}
    assert "node" in types
    assert model.languages == []  # manifest exists but no JS/TS source files at all


def test_nonexistent_path_raises_discovery_error(tmp_path):
    with pytest.raises(DiscoveryError):
        discover(tmp_path / "does-not-exist")


def test_path_is_a_file_not_a_directory_raises(tmp_path):
    file_path = tmp_path / "notadir.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(DiscoveryError):
        discover(file_path)
