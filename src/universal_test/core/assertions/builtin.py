"""Builtin assertion evaluators (skill.md §9).

Every evaluator has the signature `(params: dict, context: dict) -> tuple[bool,
str, list[Evidence]]` and reads only from the generic `context` dict an
adapter's `execute()` produces (status_code, elapsed_ms, json, headers, body,
rows). No HTTP/DB-specific imports here — that keeps the assertion engine
usable by every adapter.
"""

from __future__ import annotations

from typing import Any, Callable

from universal_test.core.assertions.path import MISSING, resolve_path
from universal_test.core.models.evidence import Evidence

try:
    import jsonschema
except ImportError:  # pragma: no cover - jsonschema is a declared dependency as of Phase 3
    jsonschema = None  # Core keeps working with the minimal fallback checker below.

Evaluator = Callable[[dict, dict], tuple[bool, str, list[Evidence]]]


def status_code(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    expected = params["equals"]
    actual = context.get("status_code")
    passed = actual == expected
    ev = [Evidence("http_response", {"status_code": actual})]
    return passed, f"expected status_code={expected}, got {actual}", ev


def status_code_in(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    expected = list(params["values"])
    actual = context.get("status_code")
    passed = actual in expected
    ev = [Evidence("http_response", {"status_code": actual})]
    return passed, f"expected status_code in {expected}, got {actual}", ev


def response_time_less_than(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    threshold = params["ms"]
    actual = context.get("elapsed_ms")
    passed = actual is not None and actual < threshold
    ev = [Evidence("timing", {"elapsed_ms": actual, "threshold_ms": threshold})]
    return passed, f"expected elapsed_ms < {threshold}, got {actual}", ev


def json_path_exists(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    path = params["path"]
    value = resolve_path(context.get("json"), path)
    passed = value is not MISSING
    ev = [Evidence("json_path", {"path": path, "found": passed})]
    return passed, f"expected json path {path!r} to exist", ev


def json_path_equals(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    path, expected = params["path"], params["equals"]
    actual = resolve_path(context.get("json"), path)
    found = actual is not MISSING
    passed = found and actual == expected
    ev = [Evidence("json_path", {"path": path, "value": None if not found else actual})]
    return passed, f"expected json path {path!r} == {expected!r}, got {actual if found else 'MISSING'}", ev


def json_schema_valid(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    """Full JSON Schema validation via the `jsonschema` library (Phase 3+), falling
    back to a minimal type/required-field checker if `jsonschema` is unavailable.

    A malformed *schema* itself (as opposed to invalid response data) is not
    an API failure — callers that generate this assertion (adapters/rest)
    are expected to pre-validate the schema at generation time and skip
    creating this assertion when the schema can't be compiled, recording
    "schema validation NOT_AVAILABLE" as spec-level evidence instead
    (see ARCHITECTURE.md). If an uncompilable schema reaches this evaluator
    anyway, it is reported as a schema error rather than a silent pass.
    """
    schema = params["schema"]
    data = context.get("json")

    if jsonschema is not None:
        try:
            validator_cls = jsonschema.validators.validator_for(schema)
            validator_cls.check_schema(schema)
            validator = validator_cls(schema)
            errors = [e.message for e in validator.iter_errors(data)]
        except jsonschema.exceptions.SchemaError as exc:
            ev = [Evidence("json_schema", {"schema_error": str(exc)})]
            return False, f"schema itself is invalid, cannot validate: {exc}", ev
        passed = not errors
        ev = [Evidence("json_schema", {"errors": errors, "validator": "jsonschema"})]
        return passed, "schema valid" if passed else f"schema violations: {errors}", ev

    errors = []
    _check_minimal_schema(data, schema, "$", errors)
    passed = not errors
    ev = [Evidence("json_schema", {"errors": errors, "validator": "minimal_fallback"})]
    return passed, "schema valid" if passed else f"schema violations: {errors}", ev


def _check_minimal_schema(data: Any, schema: dict, path: str, errors: list[str]) -> None:
    expected_type = schema.get("type")
    type_map = {
        "object": dict, "array": list, "string": str,
        "number": (int, float), "integer": int, "boolean": bool, "null": type(None),
    }
    if expected_type and not isinstance(data, type_map.get(expected_type, object)):
        errors.append(f"{path}: expected type {expected_type}, got {type(data).__name__}")
        return
    if expected_type == "object" and isinstance(data, dict):
        for required_field in schema.get("required", []):
            if required_field not in data:
                errors.append(f"{path}: missing required field {required_field!r}")
        for key, sub_schema in schema.get("properties", {}).items():
            if key in data:
                _check_minimal_schema(data[key], sub_schema, f"{path}.{key}", errors)


def header_exists(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    name = params["name"]
    headers = {k.lower(): v for k, v in context.get("headers", {}).items()}
    passed = name.lower() in headers
    ev = [Evidence("header", {"name": name, "present": passed})]
    return passed, f"expected header {name!r} to be present", ev


def header_equals(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    name, expected = params["name"], params["equals"]
    headers = {k.lower(): v for k, v in context.get("headers", {}).items()}
    actual = headers.get(name.lower())
    passed = actual == expected
    ev = [Evidence("header", {"name": name, "value": actual})]
    return passed, f"expected header {name!r} == {expected!r}, got {actual!r}", ev


def body_contains(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    needle = params["value"]
    body = context.get("body") or ""
    passed = needle in body
    ev = [Evidence("body", {"contains": needle, "found": passed})]
    return passed, f"expected body to contain {needle!r}", ev


def body_not_contains(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    needle = params["value"]
    body = context.get("body") or ""
    passed = needle not in body
    ev = [Evidence("body", {"not_contains": needle, "found": needle in body})]
    return passed, f"expected body to not contain {needle!r}", ev


def row_count(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    rows = context.get("rows", [])
    actual = len(rows)
    if "equals" in params:
        passed = actual == params["equals"]
        expectation = f"== {params['equals']}"
    else:
        minimum = params.get("min", 0)
        maximum = params.get("max")
        passed = actual >= minimum and (maximum is None or actual <= maximum)
        expectation = f">= {minimum}" + (f" and <= {maximum}" if maximum is not None else "")
    ev = [Evidence("rows", {"row_count": actual})]
    return passed, f"expected row_count {expectation}, got {actual}", ev


def value_equals(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    path, expected = params["path"], params["equals"]
    actual = resolve_path(context, path)
    found = actual is not MISSING
    passed = found and actual == expected
    ev = [Evidence("value", {"path": path, "value": None if not found else actual})]
    return passed, f"expected {path!r} == {expected!r}, got {actual if found else 'MISSING'}", ev


def value_not_null(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    path = params["path"]
    actual = resolve_path(context, path)
    passed = actual is not MISSING and actual is not None
    ev = [Evidence("value", {"path": path, "is_null": actual is None or actual is MISSING})]
    return passed, f"expected {path!r} to be non-null", ev


BUILTIN_ASSERTIONS: dict[str, Evaluator] = {
    "status_code": status_code,
    "status_code_in": status_code_in,
    "response_time_less_than": response_time_less_than,
    "json_path_exists": json_path_exists,
    "json_path_equals": json_path_equals,
    "json_schema_valid": json_schema_valid,
    "header_exists": header_exists,
    "header_equals": header_equals,
    "body_contains": body_contains,
    "body_not_contains": body_not_contains,
    "row_count": row_count,
    "value_equals": value_equals,
    "value_not_null": value_not_null,
}
