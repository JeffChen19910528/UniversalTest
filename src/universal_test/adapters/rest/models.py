"""Normalized, technology-independent OpenAPI model (Phase 3 brief §2).

Core never imports this module or any OpenAPI-parser-specific type — it only
ever sees `core.models.TestCase`/`TestResult`, which `test_generation.py`
builds *from* this model. This module is REST-adapter-private normalization,
analogous to `discovery.models.ProjectModel` for the discovery layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from universal_test.core.models.evidence import Evidence


class HttpMethod(str, Enum):
    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"
    HEAD = "head"
    OPTIONS = "options"


@dataclass(frozen=True)
class SchemaModel:
    """A JSON-Schema-shaped dict, already internal-$ref-resolved."""

    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.raw


@dataclass(frozen=True)
class ParameterModel:
    name: str
    location: str  # "path" | "query" | "header" | "cookie"
    required: bool
    schema: SchemaModel | None = None
    example: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "in": self.location, "required": self.required,
            "schema": self.schema.to_dict() if self.schema else None, "example": self.example,
        }


@dataclass(frozen=True)
class RequestBodyModel:
    required: bool
    content_type: str | None
    schema: SchemaModel | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required, "content_type": self.content_type,
            "schema": self.schema.to_dict() if self.schema else None,
        }


@dataclass(frozen=True)
class ResponseModel:
    status_code: str  # "200", "404", "4XX", "default"
    content_type: str | None
    schema: SchemaModel | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status_code": self.status_code, "content_type": self.content_type,
            "schema": self.schema.to_dict() if self.schema else None,
        }


@dataclass(frozen=True)
class SecurityScheme:
    name: str
    type: str  # "http" | "apiKey" | "oauth2" | "openIdConnect"
    scheme: str | None = None  # e.g. "bearer", "basic" (for type == "http")
    location: str | None = None  # "header" | "query" | "cookie" (for type == "apiKey")
    param_name: str | None = None  # header/query/cookie name (for type == "apiKey")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "type": self.type, "scheme": self.scheme,
            "in": self.location, "param_name": self.param_name,
        }


@dataclass(frozen=True)
class ApiEndpoint:
    method: HttpMethod
    path: str
    operation_id: str | None = None
    summary: str | None = None
    parameters: list[ParameterModel] = field(default_factory=list)
    request_body: RequestBodyModel | None = None
    responses: list[ResponseModel] = field(default_factory=list)
    security: list[str] = field(default_factory=list)  # names into ApiSpecification.security_schemes
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def id(self) -> str:
        base = self.operation_id or f"{self.method.value}_{self.path}"
        return base.replace("/", "_").replace("{", "").replace("}", "").strip("_")

    def success_responses(self) -> list[ResponseModel]:
        return [r for r in self.responses if r.status_code.isdigit() and r.status_code.startswith("2")]

    def error_responses(self) -> list[ResponseModel]:
        return [
            r for r in self.responses
            if (r.status_code.isdigit() and r.status_code[0] in ("4", "5"))
            or r.status_code.upper() in ("4XX", "5XX", "DEFAULT")
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "method": self.method.value,
            "path": self.path,
            "operation_id": self.operation_id,
            "summary": self.summary,
            "parameters": [p.to_dict() for p in self.parameters],
            "request_body": self.request_body.to_dict() if self.request_body else None,
            "responses": [r.to_dict() for r in self.responses],
            "security": self.security,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class ApiSpecification:
    source_file: str
    title: str | None = None
    version: str | None = None
    openapi_version: str | None = None
    servers: list[str] = field(default_factory=list)  # informational only; never auto-used as target
    endpoints: list[ApiEndpoint] = field(default_factory=list)
    security_schemes: dict[str, SecurityScheme] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "title": self.title,
            "version": self.version,
            "openapi_version": self.openapi_version,
            "servers": self.servers,
            "endpoints": [e.to_dict() for e in self.endpoints],
            "security_schemes": {k: v.to_dict() for k, v in self.security_schemes.items()},
            "warnings": self.warnings,
        }
