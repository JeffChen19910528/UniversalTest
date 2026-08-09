"""CI environment detection (Phase 8 brief §6) — informational only.

Detecting `GITHUB_ACTIONS=true` or similar never changes safety behavior:
it is used exclusively to improve a log message (e.g. "Detected CI
environment: GitHub Actions"). It never sets `--yes` automatically, never
relaxes the interactive-confirmation gate, and never widens what a run is
allowed to do — the brief's explicit warning: "不要因為偵測到 CI 就自動放寬
safety". `--ci`/`--yes` remain the only things that change tool behavior;
this module only changes what gets logged.
"""

from __future__ import annotations

import os

_MARKERS: list[tuple[str, str]] = [
    ("GITHUB_ACTIONS", "GitHub Actions"),
    ("GITLAB_CI", "GitLab CI"),
    ("JENKINS_URL", "Jenkins"),
    ("TF_BUILD", "Azure Pipelines"),
    ("CIRCLECI", "CircleCI"),
    ("TRAVIS", "Travis CI"),
    ("BUILDKITE", "Buildkite"),
    ("CI", "generic CI"),  # checked last: many providers also set this alongside a specific marker
]


def detect_ci_environment(env: dict[str, str] | None = None) -> str | None:
    """Returns a human-readable CI provider name, or `None` if no known CI
    environment variable is set. Provider-specific markers are checked
    before the generic `CI` variable so a specific name is preferred over
    "generic CI" when both are present (which is the common case)."""
    environ = env if env is not None else os.environ
    for var, label in _MARKERS:
        if environ.get(var):
            return label
    return None
