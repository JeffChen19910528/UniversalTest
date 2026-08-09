"""In-memory registry of assessment runs started from the GUI.

One `Run` per "開始專案健檢" click. The HTTP layer never touches
`application.service` internals directly — it only starts a `Run` and
polls/streams its event queue, keeping the HTTP handler a thin transport
shim (GUI brief §11: "GUI 只負責 rendering").
"""

from __future__ import annotations

import queue
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any

from universal_test.application.events import ProgressEvent
from universal_test.application.service import AssessmentOutcome, AssessmentRequest, run_assessment
from universal_test.core.logging_setup import get_logger

_logger = get_logger("gui")


@dataclass
class Run:
    id: str
    request: AssessmentRequest
    events: list[ProgressEvent] = field(default_factory=list)
    queue: "queue.Queue[ProgressEvent | None]" = field(default_factory=queue.Queue)
    outcome: AssessmentOutcome | None = None
    error: str | None = None
    error_id: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    done: bool = False


_DEFAULT_MAX_COMPLETED_RUNS = 20


class RunAlreadyActiveError(Exception):
    """Raised by `RunRegistry.start()` when a run is already in flight.

    A long-running GUI process is meant for one user driving one assessment
    at a time (brief §11); this is the server-side backstop behind the
    frontend's "disable Start while running" UX (Final QA Known Issue I) --
    it also protects a user who fires two requests before the button
    actually disables in the DOM.
    """


class RunRegistry:
    """Bounded, in-memory registry of assessment runs (Final QA Known Issue
    H). Without bounding, a long-lived GUI process would accumulate one
    `Run` (events, queue, request, outcome) per assessment forever. Only
    *completed* runs are ever evicted -- an active run is never touched
    regardless of how many other runs finish while it's still going.
    """

    def __init__(self, max_completed_runs: int = _DEFAULT_MAX_COMPLETED_RUNS) -> None:
        self._runs: dict[str, Run] = {}
        self._lock = threading.Lock()
        self._max_completed_runs = max_completed_runs

    def has_active_run(self) -> bool:
        with self._lock:
            return self._has_active_run_locked()

    def _has_active_run_locked(self) -> bool:
        return any(not r.done for r in self._runs.values())

    def start(self, request: AssessmentRequest) -> Run:
        run_id = uuid.uuid4().hex
        run = Run(id=run_id, request=request)
        with self._lock:
            if self._has_active_run_locked():
                raise RunAlreadyActiveError("an assessment is already running")
            self._runs[run_id] = run
            self._prune_completed_locked()

        def on_event(event: ProgressEvent) -> None:
            with run.lock:
                run.events.append(event)
            run.queue.put(event)

        def worker() -> None:
            try:
                outcome = run_assessment(request, on_event=on_event)
                with run.lock:
                    run.outcome = outcome
            except Exception:  # noqa: BLE001 - surfaced to the GUI as a friendly error, never crashes the server
                # The exception (message, type, or traceback) can legitimately
                # contain a secret -- e.g. a driver surfacing a connection
                # string, or a header value in an HTTP client error. Only an
                # opaque error_id crosses the HTTP boundary to the browser;
                # the full (redacted-at-format-time) detail goes to the
                # server-side log only (Final QA Known Issue E).
                error_id = uuid.uuid4().hex[:12]
                _logger.error("GUI assessment run %s failed [error_id=%s]\n%s", run.id, error_id, traceback.format_exc())
                with run.lock:
                    run.error = "An unexpected error occurred while running the assessment."
                    run.error_id = error_id
                run.queue.put(_error_event(error_id))
            finally:
                with run.lock:
                    run.done = True
                run.queue.put(None)
                with self._lock:
                    self._prune_completed_locked()

        threading.Thread(target=worker, name=f"assess-{run_id}", daemon=True).start()
        return run

    def get(self, run_id: str) -> Run | None:
        with self._lock:
            return self._runs.get(run_id)

    def _prune_completed_locked(self) -> None:
        """Evicts the oldest completed runs beyond `_max_completed_runs`.

        Insertion order in `self._runs` (a plain dict, ordered since 3.7)
        doubles as recency order since run IDs are never reused. An active
        run is never a candidate: `r.done` is only ever read here, never
        mutated, so a run mid-flight is always retained regardless of age.
        """
        completed_ids = [rid for rid, r in self._runs.items() if r.done]
        overflow = len(completed_ids) - self._max_completed_runs
        if overflow <= 0:
            return
        for rid in completed_ids[:overflow]:
            del self._runs[rid]


def _error_event(error_id: str) -> ProgressEvent:
    return ProgressEvent(
        stage="pipeline", phase="failed",
        message="An unexpected error occurred while running the assessment.",
        detail={"error_id": error_id},
    )
