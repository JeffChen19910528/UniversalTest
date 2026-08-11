"""DiscoveryEngine: ties every detector together into one read-only scan.

Never writes to, executes, or connects to anything in the scanned project
(skill.md §6, Phase 2 constraints). A detector raising an unexpected error is
recorded as a warning and does not abort the whole scan — one bad manifest
file must not prevent reporting everything else that *was* discovered.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from universal_test import __version__
from universal_test.core.errors import DiscoveryError
from universal_test.core.logging_setup import get_logger
from universal_test.discovery import (
    api,
    database,
    filesystem,
    framework,
    frontend,
    infrastructure,
    language,
    manifests,
    project_type,
    repository,
    secrets,
    test_framework,
)
from universal_test.discovery.models import ProjectModel

_logger = get_logger("discovery")


def discover(project_path: str | Path) -> ProjectModel:
    root = Path(project_path)
    if not root.exists():
        raise DiscoveryError(f"Project path does not exist: {root}")
    if not root.is_dir():
        raise DiscoveryError(f"Project path is not a directory: {root}")
    root = root.resolve()

    model = ProjectModel(
        root_path=str(root),
        tool_version=__version__,
        scanned_at=datetime.now(timezone.utc).isoformat(),
    )

    files = filesystem.walk(root)
    model.file_count = len(files)
    model.test_directories = filesystem.find_test_directories(files)

    model.repository = repository.discover_repository(root)

    bundle = manifests.load_manifests(root, files)
    model.warnings.extend(bundle.parse_warnings)

    for step_name, step in (
        ("languages", lambda: language.detect_languages(files, bundle)),
        ("project_types", lambda: project_type.detect_project_types(files, bundle)),
        ("build_systems", lambda: project_type.detect_build_systems(files, bundle)),
        ("frameworks", lambda: framework.detect_frameworks(files, bundle)),
        ("infrastructure", lambda: infrastructure.detect_infrastructure(files)),
        ("databases", lambda: database.detect_databases(files, bundle)),
        ("apis", lambda: api.detect_apis(files, bundle)),
        ("test_frameworks", lambda: test_framework.detect_test_frameworks(files, bundle)),
        ("frontend", lambda: frontend.detect_frontend(files, bundle, model.frameworks)),
        ("secrets", lambda: secrets.scan_for_secrets(files)),
    ):
        try:
            setattr(model, step_name, step())
        except Exception as exc:  # noqa: BLE001 - one detector failing must not abort the scan
            _logger.warning("discovery step %r failed: %s", step_name, exc)
            model.warnings.append(f"{step_name} detection failed: {type(exc).__name__}: {exc}")

    model.primary_language = language.primary_language(model.languages)

    return model
