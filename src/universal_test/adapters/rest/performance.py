"""Performance-testing orchestration for the REST adapter: endpoint
selection + deterministic request building, reusing Phase 3's OpenAPI
discovery/parsing and `test_generation.build_positive_request` — Phase 4
never re-implements request generation (brief §7).
"""

from __future__ import annotations

from pathlib import Path

from universal_test.core.errors import OpenApiError
from universal_test.testing.performance.models import PerformanceRequest
from universal_test.adapters.rest.auth import AuthConfig, build_auth_headers
from universal_test.adapters.rest.discovery_bridge import NoSpecFoundError, select_specification
from universal_test.adapters.rest.models import ApiEndpoint, ApiSpecification
from universal_test.adapters.rest.normalizer import parse_specification
from universal_test.adapters.rest.test_generation import build_positive_request
from universal_test.adapters.rest.url_utils import substitute_path_params


def select_endpoint(spec: ApiSpecification, method: str | None, path: str | None) -> ApiEndpoint:
    candidates = spec.endpoints
    if path:
        candidates = [e for e in candidates if e.path == path]
        if not candidates:
            raise OpenApiError(f"no endpoint found for path {path!r} in {spec.source_file}")
    if method:
        candidates = [e for e in candidates if e.method.value.upper() == method.upper()]
        if not candidates:
            where = f" and path {path!r}" if path else ""
            raise OpenApiError(f"no endpoint found for method {method!r}{where} in {spec.source_file}")

    if len(candidates) > 1:
        options = ", ".join(f"{e.method.value.upper()} {e.path}" for e in candidates)
        raise OpenApiError(
            f"multiple endpoints match; pass --endpoint and --method to pick one: {options}"
        )
    if not candidates:
        raise OpenApiError(
            f"{spec.source_file} declares no endpoints matching the given --endpoint/--method"
        )
    return candidates[0]


def build_performance_request(endpoint: ApiEndpoint) -> tuple[PerformanceRequest | None, list[str]]:
    request_dict, notes = build_positive_request(endpoint)
    if request_dict is None:
        return None, notes

    path = substitute_path_params(endpoint.path, request_dict["path_params"])
    request = PerformanceRequest(
        method=endpoint.method.value.upper(),
        path=path,
        query_params=request_dict["query_params"],
        headers=request_dict["headers"],
        json_body=request_dict["json"],
        content_type=request_dict["content_type"],
    )
    return request, notes


def resolve_performance_target(
    project_path: str | Path,
    *,
    openapi_override: str | None = None,
    endpoint_path: str | None = None,
    method: str | None = None,
) -> tuple[ApiSpecification | None, ApiEndpoint | None, PerformanceRequest, list[str]]:
    """Prefer the project's OpenAPI spec (per Phase 4 brief §6); fall back to an
    explicit `--endpoint`/`--method` only when no spec is discoverable at all.
    A `MultipleSpecsFoundError` from spec discovery is never swallowed here —
    the same "never silently pick one" rule from Phase 3 applies.
    """
    spec: ApiSpecification | None = None
    try:
        spec_path = select_specification(Path(project_path), openapi_override)
        spec = parse_specification(spec_path)
    except NoSpecFoundError:
        spec = None

    if spec is not None and spec.endpoints:
        endpoint = select_endpoint(spec, method, endpoint_path)
        request, notes = build_performance_request(endpoint)
        if request is None:
            raise OpenApiError(
                f"unable to construct a valid request for {endpoint.method.value.upper()} "
                f"{endpoint.path}: insufficient OpenAPI schema information "
                f"({'; '.join(notes)}); pick a simpler operation with --endpoint/--method"
            )
        return spec, endpoint, request, notes

    if not endpoint_path:
        raise OpenApiError(
            "no OpenAPI document was found; specify --endpoint <path> [--method GET] explicitly "
            "(universal-test does not scan for unknown APIs)"
        )
    resolved_method = (method or "GET").upper()
    request = PerformanceRequest(method=resolved_method, path=endpoint_path)
    return None, None, request, []


def resolve_auth_headers(
    spec: ApiSpecification | None, endpoint: ApiEndpoint | None, auth_config: AuthConfig,
) -> tuple[dict[str, str], dict[str, str]]:
    """Static (per-run, not per-request) auth headers/query for the performance executor.

    Mirrors the functional executor's scheme-aware resolution when an
    OpenAPI endpoint is known; falls back to applying a supplied credential
    directly (as a plain bearer/API-key header) when testing a manually
    specified `--endpoint` with no spec to look up a security scheme in —
    still never guesses whether auth is *required*, just uses what's given.
    """
    if endpoint is not None and spec is not None and endpoint.security:
        return build_auth_headers(endpoint.security, spec.security_schemes, auth_config)
    if auth_config.bearer_token:
        return {"Authorization": f"Bearer {auth_config.bearer_token}"}, {}
    if auth_config.api_key_value:
        header_name = auth_config.api_key_header_override or "X-API-Key"
        return {header_name: auth_config.api_key_value}, {}
    if auth_config.basic_username and auth_config.basic_password:
        import base64
        token = base64.b64encode(f"{auth_config.basic_username}:{auth_config.basic_password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}, {}
    return {}, {}
