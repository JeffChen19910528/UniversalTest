"""Deterministic request-data generation from a JSON-Schema-shaped dict.

Phase 3 brief §8: prefer `example`/`default`/`enum`/documented `minimum` over
guessing, and return "not confident" (`False`) rather than inventing a value
when there isn't enough information — the caller is expected to skip
executing a test built from an unconfident value rather than sending a
made-up request.
"""

from __future__ import annotations

from typing import Any

from universal_test.adapters.rest.models import SchemaModel

_STRING_FORMAT_DEFAULTS = {
    "date": "2024-01-01",
    "date-time": "2024-01-01T00:00:00Z",
    "email": "test@example.com",
    "uuid": "00000000-0000-0000-0000-00000000",
    "uri": "https://example.com/resource",
    "hostname": "example.com",
    "ipv4": "203.0.113.1",
}

# a value we can always fall back to for a bare, unconstrained string
_DEFAULT_STRING = "test string"


def generate_value(schema: SchemaModel | dict | None, _depth: int = 0) -> tuple[Any, bool]:
    """Return `(value, confident)`. `confident is False` means: do not use this value."""
    if schema is None or _depth > 10:
        return None, False

    raw = schema.raw if isinstance(schema, SchemaModel) else schema
    if not isinstance(raw, dict):
        return None, False

    if "example" in raw:
        return raw["example"], True
    if "default" in raw:
        return raw["default"], True
    if "enum" in raw and isinstance(raw["enum"], list) and raw["enum"]:
        return raw["enum"][0], True

    schema_type = raw.get("type")

    if schema_type == "string":
        fmt = raw.get("format")
        return _STRING_FORMAT_DEFAULTS.get(fmt, _DEFAULT_STRING), True

    if schema_type == "integer":
        minimum = raw.get("minimum")
        return (int(minimum) if minimum is not None else 0), True

    if schema_type == "number":
        minimum = raw.get("minimum")
        return (float(minimum) if minimum is not None else 0.0), True

    if schema_type == "boolean":
        return True, True

    if schema_type == "array":
        return _generate_array(raw, _depth)

    if schema_type == "object" or (schema_type is None and "properties" in raw):
        return _generate_object(raw, _depth)

    if "allOf" in raw and isinstance(raw["allOf"], list):
        return _generate_all_of(raw["allOf"], _depth)

    # oneOf/anyOf without an example/default is genuinely ambiguous — don't guess which branch.
    return None, False


def _generate_array(raw: dict, depth: int) -> tuple[Any, bool]:
    min_items = raw.get("minItems", 0) or 0
    items_schema = raw.get("items")
    if min_items <= 0:
        return [], True
    if not isinstance(items_schema, dict):
        return None, False
    value, confident = generate_value(items_schema, depth + 1)
    if not confident:
        return None, False
    return [value] * min_items, True


def _generate_object(raw: dict, depth: int) -> tuple[Any, bool]:
    properties = raw.get("properties", {})
    required = raw.get("required", [])
    if not isinstance(properties, dict):
        properties = {}
    result: dict[str, Any] = {}
    for field_name in required:
        field_schema = properties.get(field_name)
        if field_schema is None:
            return None, False
        value, confident = generate_value(field_schema, depth + 1)
        if not confident:
            return None, False
        result[field_name] = value
    return result, True


def _generate_all_of(sub_schemas: list, depth: int) -> tuple[Any, bool]:
    merged_properties: dict[str, Any] = {}
    merged_required: list[str] = []
    for sub in sub_schemas:
        if not isinstance(sub, dict):
            return None, False
        merged_properties.update(sub.get("properties", {}) or {})
        merged_required.extend(sub.get("required", []) or [])
    return _generate_object({"properties": merged_properties, "required": merged_required}, depth)
