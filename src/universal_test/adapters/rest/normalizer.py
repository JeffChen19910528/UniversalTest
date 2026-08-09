"""Build a normalized `ApiSpecification` from a resolved OpenAPI 3.x document.

Only OpenAPI 3.x is supported. Swagger 2.0 documents are detected and
rejected with a clear `OpenApiError` rather than silently producing a wrong
or partial model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from universal_test.core.errors import OpenApiError
from universal_test.core.models.evidence import Evidence
from universal_test.adapters.rest.models import (
    ApiEndpoint,
    ApiSpecification,
    HttpMethod,
    ParameterModel,
    RequestBodyModel,
    ResponseModel,
    SchemaModel,
    SecurityScheme,
)
from universal_test.adapters.rest.openapi_loader import load_document, resolve_internal_refs

_PREFERRED_CONTENT_TYPES = ("application/json",)


def parse_specification(path: Path) -> ApiSpecification:
    raw = load_document(path)

    if "swagger" in raw and "openapi" not in raw:
        raise OpenApiError(
            f"{path} is a Swagger 2.0 document ('swagger: {raw.get('swagger')}'); "
            "only OpenAPI 3.x is supported in Phase 3"
        )
    openapi_version = raw.get("openapi")
    if not isinstance(openapi_version, str) or not openapi_version.startswith("3."):
        raise OpenApiError(f"{path} does not declare a supported 'openapi: 3.x' version")
    if "paths" not in raw or not isinstance(raw["paths"], dict):
        raise OpenApiError(f"{path} has no usable 'paths' section")

    warnings: list[str] = []
    doc = resolve_internal_refs(raw, warnings)

    info = doc.get("info", {}) if isinstance(doc.get("info"), dict) else {}
    spec = ApiSpecification(
        source_file=str(path),
        title=info.get("title"),
        version=info.get("version"),
        openapi_version=openapi_version,
        servers=[s["url"] for s in doc.get("servers", []) if isinstance(s, dict) and "url" in s],
        warnings=warnings,
    )

    components = doc.get("components", {}) if isinstance(doc.get("components"), dict) else {}
    security_schemes_raw = components.get("securitySchemes", {})
    if isinstance(security_schemes_raw, dict):
        for name, scheme_def in security_schemes_raw.items():
            if not isinstance(scheme_def, dict):
                continue
            spec.security_schemes[name] = SecurityScheme(
                name=name,
                type=scheme_def.get("type", "unknown"),
                scheme=scheme_def.get("scheme"),
                location=scheme_def.get("in"),
                param_name=scheme_def.get("name"),
            )

    global_security = _extract_security_names(doc.get("security"))

    paths = doc.get("paths", {})
    for raw_path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_level_params = path_item.get("parameters", [])
        for method in HttpMethod:
            operation = path_item.get(method.value)
            if not isinstance(operation, dict):
                continue
            try:
                endpoint = _build_endpoint(
                    method, raw_path, operation, path_level_params, global_security, path,
                )
            except Exception as exc:  # noqa: BLE001 - one malformed operation must not abort the whole spec
                warnings.append(f"skipped {method.value.upper()} {raw_path}: {type(exc).__name__}: {exc}")
                continue
            spec.endpoints.append(endpoint)

    if not spec.endpoints:
        warnings.append("no usable operations were found under 'paths'")

    return spec


def _extract_security_names(security_field: Any) -> list[str]:
    if not isinstance(security_field, list):
        return []
    names: list[str] = []
    for requirement in security_field:
        if isinstance(requirement, dict):
            names.extend(requirement.keys())
    return names


def _build_endpoint(
    method: HttpMethod, raw_path: str, operation: dict, path_level_params: list,
    global_security: list[str], source_path: Path,
) -> ApiEndpoint:
    parameters = [
        _build_parameter(p) for p in (list(path_level_params) + list(operation.get("parameters", [])))
        if isinstance(p, dict) and "name" in p and "in" in p
    ]

    request_body = None
    if isinstance(operation.get("requestBody"), dict):
        request_body = _build_request_body(operation["requestBody"])

    responses = []
    if isinstance(operation.get("responses"), dict):
        for status_code, response_def in operation["responses"].items():
            if isinstance(response_def, dict):
                responses.append(_build_response(str(status_code), response_def))

    if "security" in operation:
        security = _extract_security_names(operation.get("security"))
    else:
        security = global_security

    return ApiEndpoint(
        method=method,
        path=raw_path,
        operation_id=operation.get("operationId"),
        summary=operation.get("summary"),
        parameters=parameters,
        request_body=request_body,
        responses=responses,
        security=security,
        evidence=[Evidence("openapi_operation", {"file": str(source_path), "path": raw_path, "method": method.value})],
    )


def _build_parameter(p: dict) -> ParameterModel:
    schema = p.get("schema")
    return ParameterModel(
        name=p["name"],
        location=p["in"],
        required=bool(p.get("required", False)) or p["in"] == "path",
        schema=SchemaModel(schema) if isinstance(schema, dict) else None,
        example=p.get("example"),
    )


def _pick_content(content: dict) -> tuple[str | None, dict | None]:
    if not isinstance(content, dict) or not content:
        return None, None
    for preferred in _PREFERRED_CONTENT_TYPES:
        if preferred in content:
            return preferred, content[preferred]
    first_type = next(iter(content))
    return first_type, content[first_type]


def _build_request_body(body_def: dict) -> RequestBodyModel:
    content_type, media = _pick_content(body_def.get("content", {}))
    schema = media.get("schema") if isinstance(media, dict) else None
    return RequestBodyModel(
        required=bool(body_def.get("required", False)),
        content_type=content_type,
        schema=SchemaModel(schema) if isinstance(schema, dict) else None,
    )


def _build_response(status_code: str, response_def: dict) -> ResponseModel:
    content_type, media = _pick_content(response_def.get("content", {}))
    schema = media.get("schema") if isinstance(media, dict) else None
    return ResponseModel(
        status_code=status_code,
        content_type=content_type,
        schema=SchemaModel(schema) if isinstance(schema, dict) else None,
    )
