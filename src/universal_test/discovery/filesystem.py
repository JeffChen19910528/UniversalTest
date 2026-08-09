"""Read-only filesystem walking shared by every discovery detector.

Never writes, never executes anything found. Prunes vendor/generated
directories so their contents cannot pollute language/framework counts
(Phase 2 brief, constraint list item 1).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

EXCLUDED_DIR_NAMES = {
    "node_modules", ".git", "bin", "obj", "build", "dist", "target",
    "venv", ".venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".idea", ".vscode", "vendor", "Pods", ".gradle", ".terraform",
    ".tox", "egg-info", ".egg-info", "site-packages", ".next", ".nuxt",
}

# files larger than this are skipped when reading content (avoids scanning
# large binaries/lockfiles/data dumps for secrets or manifest content)
MAX_READ_BYTES = 512_000

TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec", "specs"}


@dataclass(frozen=True)
class ScannedFile:
    path: Path          # absolute path
    relative: str        # posix-style relative path from scan root
    extension: str        # lowercase, includes leading dot, "" if none


def _is_excluded_dir(name: str) -> bool:
    return name in EXCLUDED_DIR_NAMES or name.endswith(".egg-info")


def walk(root: Path) -> list[ScannedFile]:
    """Return every file under `root`, excluding vendor/generated directories.

    Read-only: uses os.walk for traversal only, never modifies anything.
    """
    root = root.resolve()
    files: list[ScannedFile] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _is_excluded_dir(d)]
        current = Path(dirpath)
        for filename in filenames:
            full = current / filename
            try:
                relative = full.relative_to(root).as_posix()
            except ValueError:
                continue
            files.append(ScannedFile(path=full, relative=relative, extension=full.suffix.lower()))
    return files


def find_test_directories(files: list[ScannedFile]) -> list[str]:
    seen: set[str] = set()
    for f in files:
        for part in Path(f.relative).parts[:-1]:
            if part.lower() in TEST_DIR_NAMES:
                # record the directory path up to and including this part
                idx = Path(f.relative).parts.index(part)
                dir_path = "/".join(Path(f.relative).parts[: idx + 1])
                seen.add(dir_path)
    return sorted(seen)


def read_text_safe(path: Path, max_bytes: int = MAX_READ_BYTES) -> str | None:
    """Read a small text file, returning None for binary/unreadable/oversized files."""
    try:
        if path.stat().st_size > max_bytes:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw:
        return None  # treat as binary
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("latin-1")
        except UnicodeDecodeError:
            return None


def find_by_name(files: list[ScannedFile], *names: str) -> list[ScannedFile]:
    lowered = {n.lower() for n in names}
    return [f for f in files if Path(f.relative).name.lower() in lowered]


def find_by_suffix(files: list[ScannedFile], *suffixes: str) -> list[ScannedFile]:
    lowered = tuple(s.lower() for s in suffixes)
    return [f for f in files if f.extension in lowered or f.relative.lower().endswith(lowered)]
