"""Git repository discovery: read-only inspection commands only.

Only ever runs `git rev-parse` / `git status --porcelain` — commands that
inspect state and cannot mutate the repository. Never `git pull/fetch/reset/
checkout/clean` etc.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from universal_test.discovery.models import RepositoryInfo

_GIT_TIMEOUT_SECONDS = 10


def _run_git(args: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return False, ""
    except subprocess.TimeoutExpired:
        return False, ""
    if result.returncode != 0:
        return False, ""
    return True, result.stdout.strip()


def discover_repository(root: Path) -> RepositoryInfo:
    if not (root / ".git").exists():
        return RepositoryInfo(is_git=False)

    ok, toplevel = _run_git(["rev-parse", "--show-toplevel"], root)
    if not ok:
        return RepositoryInfo(
            is_git=True,
            note="'.git' directory present but the git executable is unavailable "
                 "or the repository could not be inspected",
        )

    _, branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    _, commit = _run_git(["rev-parse", "HEAD"], root)
    status_ok, status_output = _run_git(["status", "--porcelain"], root)

    return RepositoryInfo(
        is_git=True,
        root=toplevel or None,
        branch=branch or None,
        commit=commit or None,
        dirty=(bool(status_output) if status_ok else None),
    )
