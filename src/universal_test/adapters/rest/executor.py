"""HTTP execution for generated REST TestCases, via httpx.

Matches the `core.engine.Executor` signature exactly (`TestCase -> dict`) so
it plugs straight into the unmodified Phase 1 `TestEngine`/`Orchestrator`.

Safety/redaction:
- The request's own auth headers/query params are computed here and sent,
  but never returned in the context dict — only response data is. A
  `TestResult`/`Evidence` built from this context therefore can never
  contain the credential that was sent (skill.md §26, Phase 3 brief §11).
- Response headers and body are passed through `core.redaction` before
  being placed in the context, as defense in depth against a target
  echoing a secret back (e.g. reflecting an `Authorization` header in an
  error message).
"""

from __future__ import annotations

import time
from typing import Callable

import httpx

from universal_test.core.errors import NetworkError, RequestTimeoutError, TargetError
from universal_test.core.models.test_spec import TestCase
from universal_test.core.redaction import redact, redact_mapping
from universal_test.adapters.rest.auth import AuthConfig, build_auth_headers
from universal_test.adapters.rest.models import SecurityScheme
from universal_test.adapters.rest.url_utils import substitute_path_params

_MAX_BODY_CHARS = 5000


def make_executor(
    base_url: str,
    security_schemes: dict[str, SecurityScheme],
    auth_config: AuthConfig,
    timeout_seconds: float = 10.0,
) -> Callable[[TestCase], dict]:
    client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def executor(test_case: TestCase) -> dict:
        control = test_case.request.get("_control", {"execute": True})
        if not control.get("execute", True):
            return {"_not_executed": True}

        path = substitute_path_params(test_case.target.path or "", test_case.request.get("path_params", {}))
        query_params = dict(test_case.request.get("query_params", {}))
        headers = dict(test_case.request.get("headers", {}))
        body = test_case.request.get("json")
        raw_body = test_case.request.get("raw_body")
        content_type = test_case.request.get("content_type")

        auth_headers, auth_query = build_auth_headers(
            test_case.target.extra.get("security", []), security_schemes, auth_config,
        )
        headers.update(auth_headers)
        query_params.update(auth_query)
        if raw_body is not None and content_type:
            headers.setdefault("Content-Type", content_type)

        try:
            start = time.monotonic()
            if raw_body is not None:
                response = client.request(
                    test_case.target.method or "GET", path, params=query_params, headers=headers, content=raw_body,
                )
            elif body is not None:
                response = client.request(
                    test_case.target.method or "GET", path, params=query_params, headers=headers, json=body,
                )
            else:
                response = client.request(
                    test_case.target.method or "GET", path, params=query_params, headers=headers,
                )
            elapsed_ms = (time.monotonic() - start) * 1000
        except httpx.TimeoutException as exc:
            raise RequestTimeoutError(f"request to {path} timed out after {timeout_seconds}s") from exc
        except httpx.ConnectError as exc:
            raise NetworkError(f"could not connect to target for {path}: {exc}") from exc
        except httpx.RequestError as exc:
            raise TargetError(f"request to target failed for {path}: {exc}") from exc

        try:
            json_body = response.json()
        except ValueError:
            json_body = None

        return {
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
            "json": json_body,
            "headers": redact_mapping(dict(response.headers)),
            "body": redact(response.text[:_MAX_BODY_CHARS]),
        }

    executor.client = client  # type: ignore[attr-defined]  # explicit close() by the caller after a run
    return executor
