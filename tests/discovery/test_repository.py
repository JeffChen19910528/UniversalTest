import subprocess

import pytest

from universal_test.discovery.engine import discover
from universal_test.discovery.repository import discover_repository


def _git(args, cwd):
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
        env=None,
    )


@pytest.fixture
def git_repo(tmp_path):
    _git(["init", "-q"], tmp_path)
    _git(["config", "user.email", "fixture@example.com"], tmp_path)
    _git(["config", "user.name", "Fixture"], tmp_path)
    (tmp_path / "README.md").write_text("fixture repo", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-q", "-m", "initial commit"], tmp_path)
    return tmp_path


def test_no_git_directory_reports_is_git_false(tmp_path):
    info = discover_repository(tmp_path)
    assert info.is_git is False


def test_git_repo_reports_branch_and_commit(git_repo):
    info = discover_repository(git_repo)
    assert info.is_git is True
    assert info.commit is not None and len(info.commit) == 40
    assert info.dirty is False


def test_git_repo_dirty_working_tree_detected(git_repo):
    (git_repo / "README.md").write_text("changed", encoding="utf-8")
    info = discover_repository(git_repo)
    assert info.dirty is True


def test_git_repo_never_modified_by_discovery(git_repo):
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    discover(git_repo)
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert before == after

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=git_repo, capture_output=True, text=True, check=True
    ).stdout
    assert status.strip() == ""
