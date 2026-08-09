"""Minimal dotted/bracket path resolver used by json_path_* and value_* assertions.

Supports a practical subset of JSONPath: `$.a.b`, `a.b`, `items[0].name`.
Not a full JSONPath implementation — adapters/tests needing more should
resolve the value themselves and use `value_equals`/`value_not_null` on the
resolved value.
"""

from __future__ import annotations

import re
from typing import Any

_SENTINEL = object()
_TOKEN_PATTERN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def resolve_path(data: Any, path: str) -> Any:
    """Resolve `path` against `data`. Returns `_SENTINEL` (falsy-safe) if not found."""
    cleaned = path.strip()
    if cleaned.startswith("$"):
        cleaned = cleaned[1:]
    if cleaned.startswith("."):
        cleaned = cleaned[1:]
    if not cleaned:
        return data

    current = data
    for match in _TOKEN_PATTERN.finditer(cleaned):
        key, index = match.group(1), match.group(2)
        if index is not None:
            if not isinstance(current, (list, tuple)) or int(index) >= len(current):
                return _SENTINEL
            current = current[int(index)]
        else:
            if not isinstance(current, dict) or key not in current:
                return _SENTINEL
            current = current[key]
    return current


def path_exists(data: Any, path: str) -> bool:
    return resolve_path(data, path) is not _SENTINEL


MISSING = _SENTINEL
