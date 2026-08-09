"""Unit tests for `gui.runs.RunRegistry` (Final QA Known Issues H and I).

Exercises the registry directly (not over HTTP) so bounding and duplicate-run
rejection are verified independently of the transport layer.
"""

from __future__ import annotations

import threading
import time

import pytest

from universal_test.application.service import AssessmentRequest
from universal_test.gui.runs import RunAlreadyActiveError, RunRegistry


def _request(tmp_path, project="does-not-need-to-exist-for-these-tests") -> AssessmentRequest:
    return AssessmentRequest(project_path=str(tmp_path), run_functional=False)


def _block_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_completed_runs_are_bounded(tmp_path):
    registry = RunRegistry(max_completed_runs=3)
    for _ in range(10):
        run = registry.start(_request(tmp_path))
        assert _block_until(lambda: registry.get(run.id).done), "run never completed"

    remaining = [r for r in registry._runs.values()]  # noqa: SLF001 - white-box bound check
    assert len(remaining) <= 3
    assert all(r.done for r in remaining)


def test_active_run_is_never_pruned(tmp_path, monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def _slow_assessment(request, on_event=None, config=None):
        started.set()
        release.wait(timeout=5.0)
        raise RuntimeError("stop here, this test only cares about the run staying registered")

    monkeypatch.setattr("universal_test.gui.runs.run_assessment", _slow_assessment)

    registry = RunRegistry(max_completed_runs=1)
    active_run = registry.start(_request(tmp_path))
    assert _block_until(started.is_set)

    # Fill past the completed-run cap while the first run is still active.
    for _ in range(5):
        # Can't start a second run while one is active (Issue I) -- release,
        # let it finish (as an error), then start the next one to age out.
        release.set()
        assert _block_until(lambda: registry.get(active_run.id).done)
        release = threading.Event()
        active_run = registry.start(_request(tmp_path))
        started.wait(timeout=5.0)
        started.clear()

    assert registry.get(active_run.id) is not None
    release.set()


def test_second_start_is_rejected_while_first_is_active(tmp_path, monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def _slow_assessment(request, on_event=None, config=None):
        started.set()
        release.wait(timeout=5.0)
        return None

    monkeypatch.setattr("universal_test.gui.runs.run_assessment", _slow_assessment)

    registry = RunRegistry()
    first = registry.start(_request(tmp_path))
    assert _block_until(started.is_set)

    with pytest.raises(RunAlreadyActiveError):
        registry.start(_request(tmp_path))

    release.set()
    assert _block_until(lambda: registry.get(first.id).done)

    # Once the first run has finished, starting a new one succeeds again.
    second = registry.start(_request(tmp_path))
    assert second.id != first.id
