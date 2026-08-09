"""Locate OpenAPI/Swagger candidate files in a project.

Reuses `discovery.filesystem` (same vendor-directory exclusions as `scan`)
and the same filename heuristic as `discovery.api` so `scan` and `test`
agree on what counts as a candidate spec file. Never picks one arbitrarily
when multiple exist — see `select_specification`.
"""

from __future__ import annotations

from pathlib import Path

from universal_test.core.errors import OpenApiError
from universal_test.discovery.api import OPENAPI_NAME_HINTS
from universal_test.discovery.filesystem import ScannedFile, read_text_safe, walk


class MultipleSpecsFoundError(OpenApiError):
    """Raised when multiple OpenAPI/Swagger candidates exist and none was selected."""

    def __init__(self, candidates: list[str]):
        self.candidates = candidates
        super().__init__(
            "multiple OpenAPI/Swagger candidate files were found: "
            f"{', '.join(candidates)}. Re-run with --openapi <path> to select one."
        )


class NoSpecFoundError(OpenApiError):
    """Raised when no OpenAPI/Swagger candidate file could be found."""


def find_openapi_candidates(project_path: Path) -> list[ScannedFile]:
    files = walk(project_path)
    candidates = [
        f for f in files
        if f.extension in (".yaml", ".yml", ".json")
        and any(hint in Path(f.relative).name.lower() for hint in OPENAPI_NAME_HINTS)
    ]
    confirmed = []
    for f in candidates:
        text = read_text_safe(f.path)
        if text and ("openapi:" in text or '"openapi"' in text or "swagger:" in text or '"swagger"' in text):
            confirmed.append(f)
    # prefer content-confirmed candidates; fall back to filename-only matches only if nothing was confirmed
    return confirmed if confirmed else candidates


def select_specification(project_path: Path, explicit_openapi: str | None) -> Path:
    """Return the single spec file to use, or raise if the choice is ambiguous.

    `explicit_openapi` (the CLI `--openapi` flag) always wins and is used
    as-is without re-scanning — the same principle the Phase 3 brief states
    for `--target` taking priority over any `servers` entry in the spec
    applies here too: an explicit selection is never second-guessed against
    discovery.
    """
    if explicit_openapi:
        explicit_path = Path(explicit_openapi)
        if not explicit_path.is_file():
            raise OpenApiError(f"--openapi path does not exist or is not a file: {explicit_path}")
        return explicit_path

    candidates = find_openapi_candidates(Path(project_path))
    if not candidates:
        raise NoSpecFoundError(
            "no OpenAPI/Swagger document was found under the project path; "
            "pass --openapi <path> to specify one explicitly"
        )
    if len(candidates) > 1:
        sorted_relatives = sorted(f.relative for f in candidates)
        raise MultipleSpecsFoundError(sorted_relatives)

    return candidates[0].path
