"""Local-only HTTP server for the GUI (Post-V1 GUI brief §18-19).

Binds to `127.0.0.1` only (never `0.0.0.0`), never requires administrator
privileges, never touches firewall/system configuration, and never
executes project code itself — it only calls the same Application Service
Layer the CLI uses. `dataclasses.asdict`-style JSON responses are built by
hand (via each domain model's existing `to_dict()`) rather than a generic
serializer, so nothing accidentally leaks a field a report renderer
wouldn't already show.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from universal_test import __version__
from universal_test.adapters.rest.discovery_bridge import (
    MultipleSpecsFoundError,
    NoSpecFoundError,
    select_specification,
)
from universal_test.adapters.rest.normalizer import parse_specification
from universal_test.application.service import AssessmentRequest
from universal_test.core.errors import ConfigurationError, DiscoveryError, OpenApiError
from universal_test.core.logging_setup import get_logger
from universal_test.discovery import discover
from universal_test.gui.runs import RunAlreadyActiveError, RunRegistry

_logger = get_logger("gui")

STATIC_DIR = Path(__file__).parent / "static"
_STATIC_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}

LOOPBACK_HOST = "127.0.0.1"


def find_free_port(preferred: int = 8765, host: str = LOOPBACK_HOST) -> int:
    """Finds an available localhost port, trying `preferred` first (GUI brief
    §18's "找到可用 localhost port"). Binds only to the loopback interface at
    every stage — never `0.0.0.0` (brief §18/§19).
    """
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return sock.getsockname()[1]
    raise RuntimeError("could not find a free localhost port")  # pragma: no cover - practically unreachable


def _pick_path(*, directory: bool, filetypes: list[tuple[str, str]] | None = None) -> str | None:
    """Opens a native folder/file picker via Tkinter, running on the same
    machine as the browser (this is a localhost desktop tool, not a remote
    web app) — this is how a browser-based UI gets a real native folder
    picker without relying on nonstandard HTML5 directory upload behavior.
    """
    import tkinter
    from tkinter import filedialog

    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if directory:
            selected = filedialog.askdirectory(parent=root)
        else:
            selected = filedialog.askopenfilename(parent=root, filetypes=filetypes or [("All files", "*.*")])
    finally:
        root.destroy()
    return selected or None


class GuiRequestHandler(BaseHTTPRequestHandler):
    registry: RunRegistry

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
        pass  # keep console ASCII-safe and quiet (GUI brief §20); use --verbose CLI logging elsewhere for diagnostics

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/" or path == "":
                self._serve_static("index.html")
            elif path.startswith("/static/"):
                self._serve_static(path[len("/static/"):])
            elif path == "/api/version":
                self._json({"version": __version__})
            elif path.startswith("/api/assess/") and path.endswith("/stream"):
                run_id = path.split("/")[3]
                self._stream_events(run_id)
            elif path.startswith("/api/assess/") and path.endswith("/result"):
                run_id = path.split("/")[3]
                self._assess_result(run_id)
            else:
                self._json({"error": "not_found"}, status=404)
        except Exception:  # noqa: BLE001 - never let an unexpected error kill the server thread
            self._internal_error()

    def do_POST(self) -> None:  # noqa: N802 - stdlib method name
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            body = self._read_json_body()
            if path == "/api/pick-folder":
                self._pick_folder()
            elif path == "/api/pick-file":
                self._pick_file(body)
            elif path == "/api/validate-project":
                self._validate_project(body)
            elif path == "/api/perf/endpoints":
                self._perf_endpoints(body)
            elif path == "/api/assess":
                self._start_assess(body)
            elif path == "/api/open/report":
                self._open_report(body)
            elif path == "/api/open/folder":
                self._open_folder(body)
            else:
                self._json({"error": "not_found"}, status=404)
        except Exception:  # noqa: BLE001
            self._internal_error()

    # -- helpers -----------------------------------------------------------

    def _internal_error(self) -> None:
        """Logs the full (redacted) traceback server-side and returns only an
        opaque `error_id` to the browser -- an unhandled exception can
        legitimately contain a password, connection string, or token
        (e.g. from a driver's error message), and this is a localhost HTTP
        response, not a server-side log file (Final QA Known Issue E).
        """
        error_id = uuid.uuid4().hex[:12]
        # The shared logger's RedactingFormatter (core/logging_setup.py)
        # scrubs secrets from the formatted message before it is ever written
        # anywhere, so the full traceback is safe to log here.
        _logger.error("GUI request failed [error_id=%s]\n%s", error_id, traceback.format_exc())
        self._json({"error": "internal_error", "error_id": error_id}, status=500)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, relative: str) -> None:
        candidate = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in candidate.parents and candidate != STATIC_DIR.resolve():
            self._json({"error": "forbidden"}, status=403)
            return
        if not candidate.is_file():
            self._json({"error": "not_found"}, status=404)
            return
        content_type = _STATIC_CONTENT_TYPES.get(candidate.suffix, "application/octet-stream")
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _pick_folder(self) -> None:
        try:
            selected = _pick_path(directory=True)
        except Exception:
            self._json({"path": None, "error": "folder_picker_unavailable"})
            return
        self._json({"path": selected})

    def _pick_file(self, body: dict) -> None:
        kind = body.get("kind", "any")
        filetypes = {
            "baseline": [("Baseline JSON", "*.json"), ("All files", "*.*")],
            "database_profile": [("YAML", "*.yaml *.yml"), ("All files", "*.*")],
        }.get(kind, [("All files", "*.*")])
        try:
            selected = _pick_path(directory=False, filetypes=filetypes)
        except Exception:
            self._json({"path": None, "error": "file_picker_unavailable"})
            return
        self._json({"path": selected})

    def _validate_project(self, body: dict) -> None:
        path = body.get("path", "")
        p = Path(path)
        if not path:
            self._json({"valid": False, "reason": "empty_path"})
            return
        if not p.is_dir():
            self._json({"valid": False, "reason": "not_a_directory"})
            return
        try:
            next(p.iterdir())
        except StopIteration:
            self._json({"valid": False, "reason": "empty_directory"})
            return
        except OSError:
            self._json({"valid": False, "reason": "not_a_directory"})
            return
        self._json({"valid": True})

    def _perf_endpoints(self, body: dict) -> None:
        """Lists the OpenAPI operations a performance test could target, so
        the GUI never re-implements OpenAPI parsing itself (Final QA Known
        Issue G) -- it only renders what this endpoint already parsed.
        """
        project_path = body.get("project_path") or ""
        if not project_path or not Path(project_path).is_dir():
            self._json({"endpoints": [], "reason": "invalid_project_path"})
            return
        try:
            spec_path = select_specification(Path(project_path), body.get("openapi_override") or None)
        except NoSpecFoundError:
            self._json({"endpoints": [], "reason": "no_openapi_spec_found"})
            return
        except MultipleSpecsFoundError as exc:
            self._json({"endpoints": [], "reason": "multiple_specs_found", "candidates": exc.candidates})
            return

        try:
            spec = parse_specification(spec_path)
        except OpenApiError as exc:
            self._json({"endpoints": [], "reason": "spec_parse_error", "detail": str(exc)})
            return

        endpoints = [
            {"method": e.method.value.upper(), "path": e.path, "summary": e.summary}
            for e in spec.endpoints
        ]
        self._json({"endpoints": endpoints})

    def _start_assess(self, body: dict) -> None:
        try:
            request = _request_from_json(body)
        except (ValueError, ConfigurationError) as exc:
            self._json({"error": "invalid_request", "detail": str(exc)}, status=400)
            return
        try:
            run = self.registry.start(request)
        except RunAlreadyActiveError:
            self._json({"error": "assessment_already_running"}, status=409)
            return
        self._json({"run_id": run.id})

    def _stream_events(self, run_id: str) -> None:
        run = self.registry.get(run_id)
        if run is None:
            self._json({"error": "not_found"}, status=404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        with run.lock:
            already = list(run.events)
            already_done = run.done
        for event in already:
            self._write_sse(event.to_dict())
        if already_done:
            self._write_sse({"name": "done"})
            return

        while True:
            event = run.queue.get()
            if event is None:
                self._write_sse({"name": "done"})
                return
            try:
                self._write_sse(event.to_dict())
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

    def _write_sse(self, payload: dict) -> None:
        data = f"data: {json.dumps(payload)}\n\n".encode("utf-8")
        self.wfile.write(data)
        self.wfile.flush()

    def _assess_result(self, run_id: str) -> None:
        run = self.registry.get(run_id)
        if run is None:
            self._json({"error": "not_found"}, status=404)
            return
        with run.lock:
            done, outcome, error, error_id = run.done, run.outcome, run.error, run.error_id
        if not done:
            self._json({"status": "running"})
            return
        if error is not None:
            self._json({"status": "error", "error": error, "error_id": error_id})
            return
        self._json({"status": "complete", "result": _outcome_to_dict(run)})

    def _open_report(self, body: dict) -> None:
        run = self.registry.get(body.get("run_id", ""))
        fmt = body.get("format", "html")
        if run is None or run.outcome is None:
            self._json({"opened": False, "error": "no_result"})
            return
        target_path = run.outcome.report_paths.get(fmt)
        if not target_path:
            self._json({"opened": False, "error": "format_not_available"})
            return
        opened = _open_with_os(target_path)
        self._json({"opened": opened, "path": target_path})

    def _open_folder(self, body: dict) -> None:
        run = self.registry.get(body.get("run_id", ""))
        if run is None or run.outcome is None or not run.outcome.report_paths:
            self._json({"opened": False, "error": "no_result"})
            return
        any_report = next(iter(run.outcome.report_paths.values()))
        folder = str(Path(any_report).parent)
        opened = _open_with_os(folder)
        self._json({"opened": opened, "path": folder})


def _open_with_os(path: str) -> bool:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606 - opening a report/folder this same process just wrote, not arbitrary input
        else:
            import subprocess

            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, path])
        return True
    except OSError:
        return False


def _request_from_json(body: dict) -> AssessmentRequest:
    path = body.get("project_path")
    if not path:
        raise ValueError("project_path is required")
    if not Path(path).is_dir():
        raise ValueError(f"project_path does not exist or is not a directory: {path}")

    target = body.get("target") or None
    concurrency = body.get("perf_concurrency")
    if isinstance(concurrency, str):
        concurrency = [int(p.strip()) for p in concurrency.split(",") if p.strip()]

    return AssessmentRequest(
        project_path=path,
        target=target,
        run_functional=bool(body.get("run_functional", True)),
        run_performance=bool(body.get("run_performance", False)),
        performance_confirmed=bool(body.get("performance_confirmed", False)),
        run_database=bool(body.get("run_database", False)),
        database_profile_path=body.get("database_profile_path") or None,
        baseline_path=body.get("baseline_path") or None,
        output_dir=body.get("output_dir") or None,
        report_formats=body.get("report_formats") or ["json", "markdown", "html"],
        openapi_override=body.get("openapi_override") or None,
        timeout_seconds=float(body.get("timeout_seconds", 10.0)),
        perf_endpoint=body.get("perf_endpoint") or None,
        perf_method=body.get("perf_method") or None,
        perf_profile=body.get("perf_profile") or "load",
        perf_concurrency=concurrency,
        perf_max_concurrency=body.get("perf_max_concurrency"),
        perf_requests=body.get("perf_requests"),
        perf_duration=body.get("perf_duration"),
        perf_stop_error_rate=body.get("perf_stop_error_rate"),
        perf_stop_p95_ms=body.get("perf_stop_p95_ms"),
        bearer_token_env=body.get("bearer_token_env") or None,
        api_key_env=body.get("api_key_env") or None,
        api_key_header=body.get("api_key_header") or None,
        basic_auth_user_env=body.get("basic_auth_user_env") or None,
        basic_auth_pass_env=body.get("basic_auth_pass_env") or None,
    )


def _outcome_to_dict(run) -> dict:
    outcome = run.outcome
    return {
        "assessment": outcome.assessment.to_dict(),
        "regression": outcome.regression.to_dict() if outcome.regression else None,
        "quality_gate": outcome.quality_gate.to_dict(),
        "functional_not_run_reason": outcome.functional_not_run_reason,
        "performance_not_run_reason": outcome.performance_not_run_reason,
        "report_paths": outcome.report_paths,
    }


def make_server(host: str = LOOPBACK_HOST, port: int = 0) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("the GUI server only ever binds to a loopback address")  # brief §18/§19 hard rule

    handler_cls = type("BoundGuiRequestHandler", (GuiRequestHandler,), {"registry": RunRegistry()})
    server = ThreadingHTTPServer((host, port), handler_cls)
    return server
