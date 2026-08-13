"""Ctrl+C / cancellation regression tests (Phase 9 hardening pass).

`browser_session()` is a `contextlib.contextmanager` with `finally` at
every layer (page listeners -> context.close() -> browser.close() ->
playwright.stop()). Python delivers `Ctrl+C` as a `KeyboardInterrupt`
raised at the next bytecode instruction -- indistinguishable, from the
exception-handling machinery's point of view, from raising it explicitly
inside the `with` block. These tests verify the *existing* cleanup
behavior holds under that specific exception type, without changing it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

playwright_sync_api = pytest.importorskip("playwright.sync_api")


def _chromium_launchable() -> bool:
    try:
        with playwright_sync_api.sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


if not _chromium_launchable():
    pytest.skip(
        "Chromium binary is not installed -- run `universal-test browser install` "
        "(or `python -m playwright install chromium`) to enable these tests",
        allow_module_level=True,
    )

from universal_test.adapters.browser.executor import browser_session
from universal_test.adapters.browser.local_server import serve_directory
from universal_test.adapters.browser.models import BrowserStep
from universal_test.core.models.test_spec import TestCase, TestTarget

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _smoke_case():
    return TestCase(
        id="cancel-smoke", name="cancel-smoke", type="browser",
        target=TestTarget(adapter="browser", extra={"steps": [BrowserStep("navigate").to_dict()]}),
        assertions=[],
    )


def test_keyboard_interrupt_during_session_still_propagates():
    """KeyboardInterrupt must never be silently swallowed by browser_session's
    cleanup machinery -- the caller (CLI) still needs to see it to print its
    own "cancelled" message and exit non-zero."""
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        with pytest.raises(KeyboardInterrupt):
            with browser_session(base_url, headless=True) as (executor, _shots):
                executor(_smoke_case())
                raise KeyboardInterrupt


def test_cleanup_completes_after_keyboard_interrupt_no_orphan_session():
    """After a KeyboardInterrupt unwinds through browser_session, a brand new
    session must still launch and run cleanly -- proving context.close()/
    browser.close()/playwright.stop() all actually ran (didn't leak a
    process/lock that would break the next launch)."""
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        with pytest.raises(KeyboardInterrupt):
            with browser_session(base_url, headless=True) as (executor, _shots):
                executor(_smoke_case())
                raise KeyboardInterrupt

        with browser_session(base_url, headless=True) as (executor2, _shots2):
            context = executor2(_smoke_case())
            assert context["url"].startswith(base_url)


def test_keyboard_interrupt_before_any_step_still_cleans_up():
    """Interrupt delivered before the executor is even called once (e.g. Ctrl+C
    right after browser launch) must still tear down cleanly."""
    with serve_directory(FIXTURES / "browser-static-basic") as base_url:
        with pytest.raises(KeyboardInterrupt):
            with browser_session(base_url, headless=True) as (_executor, _shots):
                raise KeyboardInterrupt

        with browser_session(base_url, headless=True) as (executor2, _shots2):
            context = executor2(_smoke_case())
            assert context["url"].startswith(base_url)
