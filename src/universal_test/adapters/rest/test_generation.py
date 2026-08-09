"""Conservative functional TestCase generation from an ApiSpecification.

Reuses `core.models.TestCase`/`AssertionSpec` and the existing
`AssertionEngine` assertion types — no new assertion types are introduced
here (Phase 3 brief §9). Generation never fabricates request data it isn't
confident about (§8) and never generates a deliberate "send request without
credentials" probe (that would be a security test, out of scope — §5, §29).

Every generated `TestCase.request` carries a `"_control"` key the REST
executor inspects: `{"execute": bool, "result_status": "skipped"|"unknown",
"reason": str}`. When `execute` is False the executor performs no HTTP call
at all and the adapter layer (see `adapter.py`) rewrites the resulting
`TestResult.status`/`message` accordingly after the (assertion-free, hence
naturally `UNKNOWN`) run — this reuses Phase 1's `TestEngine`/`Orchestrator`
unchanged rather than modifying Core for this one distinction.
"""

from __future__ import annotations

import copy

import jsonschema

from universal_test.core.models.test_spec import AssertionSpec, TestCase, TestTarget
from universal_test.adapters.rest.models import ApiEndpoint, ApiSpecification
from universal_test.adapters.rest.request_data import generate_value

_MAX_NEGATIVE_TESTS_PER_ENDPOINT = 3


class _IdCounter:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return f"API-{self._n:03d}"


def _schema_is_usable(schema_dict: dict | None) -> bool:
    if schema_dict is None:
        return False
    try:
        validator_cls = jsonschema.validators.validator_for(schema_dict)
        validator_cls.check_schema(schema_dict)
    except Exception:  # noqa: BLE001 - any schema-compilation failure means "not usable"
        return False
    return True


def _skip_case(
    ids: _IdCounter, endpoint: ApiEndpoint, suffix: str, reason: str, result_status: str,
) -> TestCase:
    return TestCase(
        id=ids.next(),
        name=f"{endpoint.method.value.upper()} {endpoint.path} [{suffix}]",
        type="functional",
        target=TestTarget(adapter="rest", method=endpoint.method.value.upper(), path=endpoint.path,
                           extra={"security": endpoint.security, "operation_id": endpoint.operation_id}),
        request={"_control": {"execute": False, "result_status": result_status, "reason": reason}},
        assertions=[],
    )


def _expected_status_assertion(endpoint: ApiEndpoint) -> AssertionSpec | None:
    successes = [r.status_code for r in endpoint.success_responses() if r.status_code.isdigit()]
    if not successes:
        return None
    codes = sorted(int(c) for c in successes)
    if len(codes) == 1:
        return AssertionSpec("status_code", {"equals": codes[0]})
    return AssertionSpec("status_code_in", {"values": codes})


def _expected_error_status_assertion(endpoint: ApiEndpoint) -> AssertionSpec | None:
    errors = [r.status_code for r in endpoint.error_responses() if r.status_code.isdigit()]
    if not errors:
        return None
    codes = sorted(int(c) for c in errors)
    if len(codes) == 1:
        return AssertionSpec("status_code", {"equals": codes[0]})
    return AssertionSpec("status_code_in", {"values": codes})


def build_positive_request(endpoint: ApiEndpoint) -> tuple[dict | None, list[str]]:
    """Return `(request_dict, notes)`. `request_dict is None` means "not confident".

    Public: reused by `testing/performance` (via the REST adapter) so
    performance testing sends the same validated, deterministic request
    shape as functional testing — never regenerating a different request
    per call (Phase 4 brief §7: "不要重新發明 request generation").
    """
    notes: list[str] = []
    path_params: dict = {}
    query_params: dict = {}
    headers: dict = {}

    for param in endpoint.parameters:
        if param.location == "path":
            value, confident = generate_value(param.schema)
            if not confident:
                notes.append(f"path parameter {param.name!r} has insufficient schema information")
                return None, notes
            path_params[param.name] = value
        elif param.required and param.location == "query":
            value, confident = generate_value(param.schema)
            if not confident:
                notes.append(f"required query parameter {param.name!r} has insufficient schema information")
                return None, notes
            query_params[param.name] = value
        elif param.required and param.location == "header":
            value, confident = generate_value(param.schema)
            if not confident:
                notes.append(f"required header parameter {param.name!r} has insufficient schema information")
                return None, notes
            headers[param.name] = value

    body = None
    content_type = None
    if endpoint.request_body and endpoint.request_body.required:
        body, confident = generate_value(endpoint.request_body.schema)
        if not confident:
            notes.append("required request body has insufficient schema information")
            return None, notes
        content_type = endpoint.request_body.content_type

    return {
        "path_params": path_params, "query_params": query_params, "headers": headers,
        "json": body, "content_type": content_type,
    }, notes


def _positive_test_case(
    ids: _IdCounter, endpoint: ApiEndpoint, has_credentials: bool, spec_warnings: list[str],
) -> TestCase:
    if endpoint.security and not has_credentials:
        return _skip_case(
            ids, endpoint, "auth required",
            f"authentication required (scheme(s): {', '.join(endpoint.security)}) "
            "but no matching credentials were supplied",
            "skipped",
        )

    request, notes = build_positive_request(endpoint)
    if request is None:
        spec_warnings.extend(f"{endpoint.method.value.upper()} {endpoint.path}: {n}" for n in notes)
        return _skip_case(
            ids, endpoint, "insufficient data",
            "unable to construct a valid request from the available OpenAPI schema",
            "unknown",
        )

    status_assertion = _expected_status_assertion(endpoint)
    if status_assertion is None:
        spec_warnings.append(
            f"{endpoint.method.value.upper()} {endpoint.path}: no documented success response; "
            "cannot assert an expected status code"
        )
        return _skip_case(
            ids, endpoint, "no documented response",
            "OpenAPI declares no success (2xx) response for this operation",
            "unknown",
        )

    assertions = [status_assertion]
    success_response = next(
        (r for r in endpoint.success_responses() if r.status_code == str(_status_from_assertion(status_assertion))),
        None,
    ) or (endpoint.success_responses()[0] if endpoint.success_responses() else None)
    if success_response and success_response.schema and success_response.content_type == "application/json":
        if _schema_is_usable(success_response.schema.raw):
            assertions.append(AssertionSpec("json_schema_valid", {"schema": success_response.schema.raw}))
        else:
            spec_warnings.append(
                f"{endpoint.method.value.upper()} {endpoint.path}: response schema validation NOT_AVAILABLE "
                "(schema could not be compiled)"
            )

    return TestCase(
        id=ids.next(),
        name=f"{endpoint.method.value.upper()} {endpoint.path}",
        type="functional",
        target=TestTarget(adapter="rest", method=endpoint.method.value.upper(), path=endpoint.path,
                           extra={"security": endpoint.security, "operation_id": endpoint.operation_id}),
        request={**request, "_control": {"execute": True}},
        assertions=assertions,
    )


def _status_from_assertion(spec: AssertionSpec) -> int:
    return spec.params.get("equals") or (spec.params.get("values") or [0])[0]


def _negative_test_cases(
    ids: _IdCounter, endpoint: ApiEndpoint, baseline: dict, has_credentials: bool, spec_warnings: list[str],
) -> list[TestCase]:
    if endpoint.security and not has_credentials:
        return []  # can't meaningfully probe an endpoint we can't authenticate against

    error_assertion = _expected_error_status_assertion(endpoint)
    if error_assertion is None:
        spec_warnings.append(
            f"{endpoint.method.value.upper()} {endpoint.path}: no documented error response with a "
            "concrete status code; skipping negative tests"
        )
        return []

    cases: list[TestCase] = []

    non_path_required = [
        p for p in endpoint.parameters if p.required and p.location in ("query", "header")
    ]
    if non_path_required:
        target_param = non_path_required[0]
        request = copy.deepcopy(baseline)
        bucket = "query_params" if target_param.location == "query" else "headers"
        request[bucket].pop(target_param.name, None)
        cases.append(_variant_case(
            ids, endpoint, f"missing required {target_param.location} parameter '{target_param.name}'",
            request, error_assertion,
        ))

    if endpoint.request_body and endpoint.request_body.schema and isinstance(baseline.get("json"), dict):
        required_fields = endpoint.request_body.schema.raw.get("required", [])
        if required_fields:
            field = required_fields[0]
            request = copy.deepcopy(baseline)
            request["json"].pop(field, None)
            cases.append(_variant_case(
                ids, endpoint, f"missing required body field '{field}'", request, error_assertion,
            ))

            numeric_field = next(
                (f for f, s in (endpoint.request_body.schema.raw.get("properties", {}) or {}).items()
                 if isinstance(s, dict) and s.get("type") in ("integer", "number", "boolean")),
                None,
            )
            if numeric_field and numeric_field in baseline["json"]:
                request = copy.deepcopy(baseline)
                request["json"][numeric_field] = "not-a-valid-type"
                cases.append(_variant_case(ids, endpoint, "invalid field type", request, error_assertion))

        if baseline.get("content_type") == "application/json" and len(cases) < _MAX_NEGATIVE_TESTS_PER_ENDPOINT:
            request = copy.deepcopy(baseline)
            request["content_type"] = "text/plain"
            request["json"] = None
            request["raw_body"] = "unsupported content type payload"
            cases.append(_variant_case(ids, endpoint, "unsupported content type", request, error_assertion))

    return cases[:_MAX_NEGATIVE_TESTS_PER_ENDPOINT]


def _variant_case(
    ids: _IdCounter, endpoint: ApiEndpoint, label: str, request: dict, expected: AssertionSpec,
) -> TestCase:
    request["_control"] = {"execute": True}
    return TestCase(
        id=ids.next(),
        name=f"{endpoint.method.value.upper()} {endpoint.path} [{label}]",
        type="functional",
        target=TestTarget(adapter="rest", method=endpoint.method.value.upper(), path=endpoint.path,
                           extra={"security": endpoint.security, "operation_id": endpoint.operation_id}),
        request=request,
        assertions=[expected],
    )


def generate_test_cases(spec: ApiSpecification, available_auth_schemes: set[str]) -> list[TestCase]:
    ids = _IdCounter()
    cases: list[TestCase] = []

    for endpoint in spec.endpoints:
        has_credentials = (not endpoint.security) or bool(set(endpoint.security) & available_auth_schemes)

        positive = _positive_test_case(ids, endpoint, has_credentials, spec.warnings)
        cases.append(positive)

        if positive.request.get("_control", {}).get("execute"):
            cases.extend(_negative_test_cases(ids, endpoint, positive.request, has_credentials, spec.warnings))

    return cases
