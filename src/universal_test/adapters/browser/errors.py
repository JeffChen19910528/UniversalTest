"""Browser-adapter exception hierarchy.

Every class here subclasses an existing `core.errors` type so `TestEngine`'s
generic `except Exception` -> `ResultStatus.ERROR` path (skill.md-derived
failure-classification rule, `core/engine/test_engine.py`) keeps working
without any Core change. `BrowserUnavailableError` is the one deliberate
exception: it must never reach `TestEngine` at all -- `adapters/browser/
adapter.py` catches it *before* constructing the executor and reports
`NOT_ASSESSED`, never `ERROR` (spec §25: "browser binary missing" is not
an application defect).
"""

from __future__ import annotations

from universal_test.core.errors import AdapterError, ExecutionError, NetworkError, RequestTimeoutError, TargetError


class BrowserUnavailableError(AdapterError):
    """Playwright (or the requested browser binary) is not installed.

    Never surfaces as a test failure -- callers must catch this before
    execution and report `NOT_ASSESSED` with the missing-dependency reason
    named, the same pattern `DatabaseDriverUnavailableError` established.
    """


class BrowserTargetError(TargetError):
    """The configured target is invalid or disallowed by the target safety
    policy (not localhost/127.0.0.1/::1/file:// and `--allow-external` was
    not set) -- raised before any navigation occurs."""


class BrowserTimeoutError(RequestTimeoutError):
    """A navigation, action, or assertion wait exceeded its bounded timeout."""


class BrowserSelectorError(ExecutionError):
    """A step's selector matched zero or more-than-one element ambiguously.

    Per spec §14, an ambiguous selector must never silently click an
    arbitrary matching element -- it is a test-definition/execution
    problem, reported explicitly rather than guessed around.
    """


class BrowserPermissionRequiredError(AdapterError):
    """A step would require a browser permission (microphone/camera/
    geolocation/notifications/clipboard) that was not explicitly granted.
    Permissions are never auto-granted merely because static analysis
    detected the underlying API (spec §23)."""


class BrowserNetworkError(NetworkError):
    """The target could not be reached at the network layer -- distinct
    from an assertion failure: infrastructure, not application, evidence."""
