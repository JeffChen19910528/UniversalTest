"""Tiny URL-building helpers shared by the functional executor and the
performance executor, so path-parameter substitution behaves identically
in both (Phase 3 `executor.py` and Phase 4 `performance_executor.py`).
"""

from __future__ import annotations


def substitute_path_params(path: str, path_params: dict) -> str:
    for name, value in path_params.items():
        path = path.replace("{" + name + "}", str(value))
    return path
