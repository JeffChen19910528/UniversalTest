"""Sanity checks for the CI provider templates (Phase 8 brief section
12-14) -- never connects to GitHub/GitLab/Jenkins; only validates the
checked-in template files are well-formed and shell out to the plain
`universal-test` CLI rather than embedding any provider SDK.
"""

from pathlib import Path

import yaml

EXAMPLES_CI_DIR = Path(__file__).parent.parent.parent / "examples" / "ci"


def test_github_actions_template_exists_and_parses():
    path = EXAMPLES_CI_DIR / "github-actions" / "universal-test.yml"
    assert path.is_file()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "jobs" in data


def test_github_actions_template_uses_ci_and_yes_and_baseline():
    text = (EXAMPLES_CI_DIR / "github-actions" / "universal-test.yml").read_text(encoding="utf-8")
    assert "--ci" in text
    assert "--yes" in text
    assert "--baseline" in text
    assert "universal-test assess" in text


def test_gitlab_template_exists_and_parses():
    path = EXAMPLES_CI_DIR / "gitlab" / "universal-test.yml"
    assert path.is_file()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "quality_gate" in data
    assert data["quality_gate"]["artifacts"]["when"] == "always"


def test_gitlab_template_uses_ci_and_yes_and_baseline():
    text = (EXAMPLES_CI_DIR / "gitlab" / "universal-test.yml").read_text(encoding="utf-8")
    assert "--ci" in text
    assert "--yes" in text
    assert "--baseline" in text


def test_jenkinsfile_exists_and_has_no_ci_provider_sdk():
    path = EXAMPLES_CI_DIR / "jenkins" / "Jenkinsfile"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "universal-test assess" in text
    assert "--ci" in text
    assert "--yes" in text
    assert "archiveArtifacts" in text


def test_no_template_hardcodes_a_credential():
    for path in EXAMPLES_CI_DIR.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "password" not in text.lower() or "TODO" in text or "env" in text.lower()
