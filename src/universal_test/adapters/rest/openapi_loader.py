"""OpenAPI document loading + internal `$ref` resolution.

Deliberately does **not** fetch external `$ref`s over the network (a spec
that references `https://example.com/schema.json` is left unresolved with a
warning) — resolving discovery/test-generation input must stay offline and
never make an implicit outbound request before the user has configured a
target (skill.md §4.2 "safe by default").
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml

from universal_test.core.errors import OpenApiError

_MAX_REF_DEPTH = 40


def load_document(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OpenApiError(f"could not read OpenAPI document {path}: {exc}") from exc

    if path.suffix.lower() == ".json":
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            raise OpenApiError(f"invalid JSON in {path}: {exc}") from exc
    else:
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise OpenApiError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(doc, dict):
        raise OpenApiError(f"{path} does not contain a mapping at the top level")
    return doc


def _resolve_ref(ref: str, root: dict) -> object | None:
    if not ref.startswith("#/"):
        return None  # external ref — left unresolved deliberately (see module docstring)
    node: object = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def resolve_internal_refs(doc: dict, warnings: list[str] | None = None) -> dict:
    """Return a deep copy of `doc` with every internal `$ref` inlined.

    Bounded by `_MAX_REF_DEPTH` and tracks the in-progress resolution chain
    to detect cycles (common with recursive schemas) — a cyclic or
    unresolvable ref is left as a small marker dict plus a warning rather
    than recursing forever or raising.
    """
    warnings = warnings if warnings is not None else []

    def _walk(node: object, chain: tuple[str, ...], depth: int) -> object:
        if depth > _MAX_REF_DEPTH:
            warnings.append(f"$ref resolution exceeded max depth ({_MAX_REF_DEPTH}); truncated")
            return {"_unresolved": True}
        if isinstance(node, dict):
            if "$ref" in node and isinstance(node["$ref"], str):
                ref = node["$ref"]
                if ref in chain:
                    warnings.append(f"circular $ref detected: {' -> '.join(chain + (ref,))}")
                    return {"_circular_ref": ref}
                resolved = _resolve_ref(ref, doc)
                if resolved is None:
                    warnings.append(f"could not resolve $ref: {ref}")
                    return {"_unresolved_ref": ref}
                return _walk(copy.deepcopy(resolved), chain + (ref,), depth + 1)
            return {k: _walk(v, chain, depth + 1) for k, v in node.items()}
        if isinstance(node, list):
            return [_walk(item, chain, depth + 1) for item in node]
        return node

    result = _walk(doc, (), 0)
    assert isinstance(result, dict)
    return result
