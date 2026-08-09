"""httpx-based `PerformanceExecutor` for `testing.performance.PerformanceRunner`.

Per the runner's contract (see `testing/performance/runner.py`), this
callable must never raise — every transport failure is caught and encoded
as a `PerformanceSample` with the matching `ErrorType` instead.

A single `httpx.Client` (one connection pool) is shared across every worker
thread the runner spawns — httpx clients are documented as thread-safe for
concurrent requests, so this avoids paying connection-setup cost per request
without needing any extra locking here.
"""

from __future__ import annotations

import time
from typing import Callable

import httpx

from universal_test.testing.performance.models import ErrorType, PerformanceRequest, PerformanceSample


def make_performance_executor(
    base_url: str,
    request_timeout_seconds: float,
    auth_headers: dict[str, str] | None = None,
    auth_query: dict[str, str] | None = None,
) -> tuple[Callable[[PerformanceRequest], PerformanceSample], Callable[[], None]]:
    """Returns `(executor, close)`. Call `close()` once after the run finishes.

    `auth_headers`/`auth_query` are pre-resolved once by the caller (see
    `adapters/rest/performance.py::resolve_auth_headers`) rather than
    computed per request — the same static credential is reused for every
    sample in the run, same as the functional executor.
    """
    client = httpx.Client(base_url=base_url, timeout=request_timeout_seconds)
    auth_headers = auth_headers or {}
    auth_query = auth_query or {}

    def executor(request: PerformanceRequest) -> PerformanceSample:
        path = request.path  # already fully resolved (see PerformanceRequest docstring)
        headers = {**request.headers, **auth_headers}
        query_params = {**request.query_params, **auth_query}
        if request.content_type and request.content_type != "application/json":
            headers.setdefault("Content-Type", request.content_type)

        start_time = time.time()
        start = time.perf_counter()
        try:
            if request.json_body is not None:
                response = client.request(request.method, path, params=query_params, headers=headers, json=request.json_body)
            else:
                response = client.request(request.method, path, params=query_params, headers=headers)
            duration_ms = (time.perf_counter() - start) * 1000
        except httpx.TimeoutException:
            return PerformanceSample(
                start_time=start_time, duration_ms=(time.perf_counter() - start) * 1000,
                status_code=None, error_type=ErrorType.TIMEOUT,
            )
        except httpx.ConnectError:
            return PerformanceSample(
                start_time=start_time, duration_ms=(time.perf_counter() - start) * 1000,
                status_code=None, error_type=ErrorType.NETWORK_ERROR,
            )
        except httpx.RequestError:
            return PerformanceSample(
                start_time=start_time, duration_ms=(time.perf_counter() - start) * 1000,
                status_code=None, error_type=ErrorType.TARGET_ERROR,
            )

        error_type = ErrorType.HTTP_ERROR if response.status_code >= 400 else ErrorType.NONE
        return PerformanceSample(
            start_time=start_time, duration_ms=duration_ms, status_code=response.status_code, error_type=error_type,
        )

    return executor, client.close
