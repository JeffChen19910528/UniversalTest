from universal_test.discovery.engine import discover


def test_node_modules_excluded_from_language_counts(tmp_path):
    vendor = tmp_path / "node_modules" / "somelib"
    vendor.mkdir(parents=True)
    for i in range(20):
        (vendor / f"file{i}.js").write_text("module.exports = {};", encoding="utf-8")

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.py").write_text("print('hi')", encoding="utf-8")

    model = discover(tmp_path)
    languages = {d.name: d.file_count for d in model.languages}
    assert "JavaScript" not in languages
    assert languages.get("Python") == 1


def test_dot_git_and_venv_excluded(tmp_path):
    for excluded in (".git", ".venv", "__pycache__", "dist", "build", "bin", "obj", "target"):
        vendor = tmp_path / excluded
        vendor.mkdir()
        (vendor / "junk.py").write_text("x = 1", encoding="utf-8")

    (tmp_path / "main.py").write_text("print('ok')", encoding="utf-8")

    model = discover(tmp_path)
    assert model.file_count == 1
    languages = {d.name: d.file_count for d in model.languages}
    assert languages.get("Python") == 1
