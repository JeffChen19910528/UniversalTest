import json

import pytest

from universal_test.cli.main import build_parser, main


def test_build_parser_requires_a_command():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


@pytest.mark.parametrize("command", ["report", "run"])
def test_each_stub_subcommand_routes_and_returns_success(tmp_path, command, capsys):
    exit_code = main([command, str(tmp_path)])
    assert exit_code == 0


def test_assess_command_with_no_output_flag_uses_the_reports_directory(tmp_path, monkeypatch, capsys):
    # 'assess' is implemented as of Phase 5 (not a stub); its default --format is
    # "all" and it writes to ./reports when --output isn't given (see
    # tests/cli/test_cli_assess_command.py for full behavioral coverage) --
    # verified here against a monkeypatched cwd so it can't touch the real repo's
    # reports/ directory.
    monkeypatch.chdir(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('hi')", encoding="utf-8")
    exit_code = main(["assess", str(project)])
    assert exit_code == 0
    assert (tmp_path / "reports" / "report.json").is_file()


def test_test_command_with_no_openapi_spec_present_is_a_clean_error(tmp_path):
    # 'test' is implemented as of Phase 3 (not a stub) -- with no spec to find,
    # it must fail clearly rather than silently succeed.
    exit_code = main(["test", str(tmp_path)])
    assert exit_code == 2


def test_performance_without_target_is_refused(tmp_path):
    exit_code = main(["performance", str(tmp_path)])
    assert exit_code == 2


def test_performance_with_target_but_no_endpoint_or_spec_is_a_clean_error(tmp_path):
    # 'performance' is implemented as of Phase 4 -- with no OpenAPI spec and no
    # --endpoint, it must refuse to guess which endpoint to load-test.
    exit_code = main(["performance", str(tmp_path), "--target", "http://localhost:8080", "--dry-run"])
    assert exit_code == 2


def test_performance_dry_run_still_requires_a_target(tmp_path):
    # Phase 4 brief: --target is required even for --dry-run (unlike 'test').
    exit_code = main(["performance", str(tmp_path), "--dry-run"])
    assert exit_code == 2


def test_invalid_project_path_config_error(tmp_path):
    missing_config = tmp_path / "nope.yaml"
    exit_code = main(["scan", str(tmp_path), "--config", str(missing_config)])
    assert exit_code == 2


def test_version_flag():
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["--version"])
    assert exc_info.value.code == 0


def test_scan_text_output_to_stdout(tmp_path, capsys):
    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")
    exit_code = main(["scan", str(tmp_path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Universal Test Framework" in out
    assert "Python" in out


def test_scan_json_output_is_valid(tmp_path, capsys):
    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")
    exit_code = main(["scan", str(tmp_path), "--format", "json"])
    assert exit_code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["file_count"] == 1


def test_scan_markdown_output(tmp_path, capsys):
    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")
    exit_code = main(["scan", str(tmp_path), "--format", "markdown"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.startswith("# Discovery Report")


def test_scan_writes_to_output_directory(tmp_path):
    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")
    output_dir = tmp_path / "out"
    exit_code = main(["scan", str(tmp_path), "--format", "json", "--output", str(output_dir)])
    assert exit_code == 0
    written = output_dir / "discovery.json"
    assert written.is_file()
    parsed = json.loads(written.read_text(encoding="utf-8"))
    assert parsed["file_count"] == 1


def test_scan_html_format_not_yet_supported(tmp_path):
    exit_code = main(["scan", str(tmp_path), "--format", "html"])
    assert exit_code == 2


def test_scan_nonexistent_path_returns_error(tmp_path):
    exit_code = main(["scan", str(tmp_path / "does-not-exist")])
    assert exit_code == 2
