"""Playwright-backed executor (spec §9, §13, §19-§21, §26-§27, §47).

`browser_session()` is the entry point: a context manager that lazily
imports Playwright (raising `BrowserUnavailableError` if it isn't
installed), launches exactly one isolated browser + browser context for
the whole run (fresh cookies/storage, no reuse across runs), and yields an
`Executor` (`Callable[[TestCase], dict]`) matching `core/engine/test_engine.py`'s
contract exactly -- so `Orchestrator.run_test_cases()` can run it unmodified.

The returned context dict is plain, JSON-serializable data (no live
Playwright handles) -- see `_build_context()` for its exact shape. It is
redacted (`adapters.browser.redaction.redact_context`) before being handed
back to the caller, so no console/network evidence needs redacting again
downstream.

Cleanup is guaranteed via `finally` at every layer (browser, context,
playwright driver) so a `KeyboardInterrupt`/assertion exception/timeout
never leaks a process (spec §47/§48).

## TestCase wall-clock timeout (Phase 9 hardening)

Each call to the executor (one `TestCase`) gets a hard wall-clock budget
(`test_timeout_seconds`, from `BrowserConfig.test_timeout_seconds`). This is
enforced without any watchdog thread or signal -- Playwright's sync API is
explicitly single-threaded (calling it from a second thread is unsupported
and unsafe), so the only safe mechanism is to compute the *remaining*
budget before every blocking Playwright call and pass it as that call's own
`timeout=` argument (every navigation/action/wait Playwright API accepts
one). `_remaining_ms()` is the single choke point: it raises
`BrowserTimeoutError` immediately, *before* issuing another Playwright call,
once the deadline has passed, and otherwise returns `min(configured_step_
timeout, time_left)`. This guarantees no single step can be given more time
than the TestCase has left, so the total wall-clock time spent inside
Playwright calls cannot exceed `test_timeout_seconds` by more than the
(negligible) non-blocking Python work between calls -- exactly the "small
scheduling/cleanup overhead" the hardening brief allows for, never the sum
of every step's own full timeout.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

from universal_test.adapters.browser.assertions import selector_key
from universal_test.adapters.browser.errors import (
    BrowserNetworkError,
    BrowserSelectorError,
    BrowserTargetError,
    BrowserTimeoutError,
    BrowserUnavailableError,
)
from universal_test.adapters.browser.redaction import redact_context
from universal_test.adapters.browser.target_policy import is_same_origin, validate_target
from universal_test.core.models.test_spec import TestCase

Executor = Callable[[TestCase], dict]

_ATTRIBUTE_ACTIONS = {"click", "fill", "select", "check", "uncheck", "press"}

DEFAULT_TEST_TIMEOUT_SECONDS = 60.0
_MIN_TIMEOUT_MS = 1.0  # Playwright rejects timeout<=0; use a minimal, near-instant slice instead.


def _remaining_ms(deadline: float, cap_ms: float, *, action: str) -> float:
    """Returns the timeout (in ms) the next Playwright call may use: never
    more than `cap_ms` (that call's own configured timeout), and never more
    than what's left of the TestCase's wall-clock budget. Raises
    `BrowserTimeoutError` outright, without issuing another Playwright call,
    once the budget is already exhausted -- the mechanism that makes the
    TestCase timeout a true hard ceiling rather than the sum of every step's
    own timeout.
    """
    remaining = (deadline - time.monotonic()) * 1000
    if remaining <= 0:
        raise BrowserTimeoutError(
            f"TestCase exceeded its configured test-case timeout before step {action!r} could run "
            "(TestCase wall-clock budget exhausted)"
        )
    return min(cap_ms, remaining)


def _import_playwright():
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserUnavailableError(
            "Playwright is not installed; install with `pip install universal-test[browser]` "
            "and then run `universal-test browser install` to download a browser binary."
        ) from exc
    return sync_playwright, PlaywrightError, PlaywrightTimeoutError


def _locate(page, selector: dict[str, Any]):
    kind = selector.get("type")
    value = selector.get("value", "")
    if kind == "role":
        return page.get_by_role(selector.get("role", "button"), name=value)
    if kind == "label":
        return page.get_by_label(value)
    if kind == "text":
        return page.get_by_text(value)
    if kind == "placeholder":
        return page.get_by_placeholder(value)
    if kind == "test_id":
        return page.get_by_test_id(value)
    if kind == "css":
        return page.locator(value)
    raise BrowserSelectorError(f"unsupported selector type: {kind!r}")


def _resolve_element_state(
    page, selector: dict[str, Any], attribute_name: str | None, PlaywrightError, *,
    deadline: float, action_timeout_ms: float,
) -> dict:
    locator = _locate(page, selector)
    _remaining_ms(deadline, action_timeout_ms, action="resolve_element:count")  # raises if budget exhausted
    try:
        count = locator.count()
    except PlaywrightError:
        return {"count": 0, "visible": False, "text": None, "value": None, "checked": None, "enabled": None, "attributes": {}}
    if count == 0:
        return {"count": 0, "visible": False, "text": None, "value": None, "checked": None, "enabled": None, "attributes": {}}

    first = locator.first
    state: dict[str, Any] = {"count": count, "attributes": {}}
    for key, fn, wants_timeout in (
        ("visible", first.is_visible, False),
        ("text", first.text_content, True),
        ("value", first.input_value, True),
        ("checked", first.is_checked, True),
        ("enabled", first.is_enabled, True),
    ):
        try:
            if wants_timeout:
                state[key] = fn(timeout=_remaining_ms(deadline, action_timeout_ms, action=f"resolve_element:{key}"))
            else:
                state[key] = fn()  # is_visible() never waits/blocks -- no timeout param to bound
        except PlaywrightError:
            state[key] = None
    if attribute_name:
        try:
            state["attributes"][attribute_name] = first.get_attribute(
                attribute_name, timeout=_remaining_ms(deadline, action_timeout_ms, action="resolve_element:attribute"),
            )
        except PlaywrightError:
            state["attributes"][attribute_name] = None
    return state


def _require_single_match(
    locator, selector: dict[str, Any], PlaywrightError, *, deadline: float, action_timeout_ms: float,
) -> None:
    _remaining_ms(deadline, action_timeout_ms, action="require_single_match")
    try:
        count = locator.count()
    except PlaywrightError as exc:
        raise BrowserSelectorError(f"could not resolve selector {selector!r}: {exc}") from exc
    if count == 0:
        raise BrowserSelectorError(f"selector matched no elements: {selector!r}")
    if count > 1:
        raise BrowserSelectorError(
            f"selector matched {count} elements ambiguously: {selector!r} -- narrow the selector "
            "rather than acting on an arbitrary match (spec section 14)"
        )


def _run_steps(
    page, target: str, steps: list[dict], *, allow_external: bool, PlaywrightError, PlaywrightTimeoutError,
    deadline: float, navigation_timeout_ms: float, action_timeout_ms: float,
) -> None:
    for step in steps:
        action = step.get("action")
        selector = step.get("selector")
        value = step.get("value")
        try:
            if action == "navigate":
                # A step's navigate value may be relative (e.g. "login.html"/"/login",
                # preferred for scenario portability, spec section 41) -- resolve it
                # against the authorized target origin before ever comparing origins
                # or calling page.goto(), since Playwright requires an absolute URL
                # (no context base_url is set -- fresh, unconfigured context per run).
                url = urljoin(target, value) if value else target
                if not is_same_origin(target, url) and not allow_external:
                    raise BrowserTargetError(
                        f"step navigates to {url!r}, which is outside the authorized origin "
                        f"{target!r}; pass --allow-external to permit cross-origin navigation"
                    )
                page.goto(url, timeout=_remaining_ms(deadline, navigation_timeout_ms, action=action))
            elif action == "wait_for":
                if selector:
                    locator = _locate(page, selector)
                    locator.wait_for(
                        state=value or "visible", timeout=_remaining_ms(deadline, action_timeout_ms, action=action),
                    )
                else:
                    page.wait_for_load_state(
                        value or "load", timeout=_remaining_ms(deadline, action_timeout_ms, action=action),
                    )
            elif action in _ATTRIBUTE_ACTIONS:
                if not selector:
                    raise BrowserSelectorError(f"step {action!r} requires a selector")
                locator = _locate(page, selector)
                _require_single_match(
                    locator, selector, PlaywrightError, deadline=deadline, action_timeout_ms=action_timeout_ms,
                )
                step_timeout_ms = _remaining_ms(deadline, action_timeout_ms, action=action)
                if action == "click":
                    locator.click(timeout=step_timeout_ms)
                elif action == "fill":
                    locator.fill(value or "", timeout=step_timeout_ms)
                elif action == "select":
                    locator.select_option(value, timeout=step_timeout_ms)
                elif action == "check":
                    locator.check(timeout=step_timeout_ms)
                elif action == "uncheck":
                    locator.uncheck(timeout=step_timeout_ms)
                elif action == "press":
                    locator.press(value or "", timeout=step_timeout_ms)
            else:
                raise BrowserSelectorError(f"unsupported action: {action!r}")
        except BrowserTimeoutError:
            raise  # our own TestCase-budget signal -- never re-wrapped as a Playwright/network error
        except PlaywrightTimeoutError as exc:
            raise BrowserTimeoutError(f"step {action!r} timed out: {exc}") from exc
        except PlaywrightError as exc:
            message = str(exc)
            if "net::" in message or "ERR_CONNECTION" in message or "ERR_NAME_NOT_RESOLVED" in message:
                raise BrowserNetworkError(f"step {action!r} failed at the network layer: {exc}") from exc
            raise BrowserSelectorError(f"step {action!r} failed: {exc}") from exc


def _build_context(
    page, target: str, console_messages: list[dict], page_errors: list[dict],
    network_failures: list[dict], test_case: TestCase, PlaywrightError, *,
    deadline: float, action_timeout_ms: float,
) -> dict:
    body_state = _resolve_element_state(
        page, {"type": "css", "value": "body"}, None, PlaywrightError,
        deadline=deadline, action_timeout_ms=action_timeout_ms,
    )
    context: dict[str, Any] = {
        "url": page.url,
        "title": page.title(),
        "body_visible": bool(body_state.get("visible")),
        "console_errors": [m for m in console_messages if m.get("level") == "error"],
        "console_warnings": [m for m in console_messages if m.get("level") == "warning"],
        "page_errors": list(page_errors),
        "network_failures": list(network_failures),
        "elements": {},
    }
    for spec in test_case.assertions:
        selector = spec.params.get("selector")
        if not selector:
            continue
        key = selector_key(selector)
        if key in context["elements"]:
            continue
        attribute_name = spec.params.get("name") if spec.type == "attribute_equals" else None
        context["elements"][key] = _resolve_element_state(
            page, selector, attribute_name, PlaywrightError,
            deadline=deadline, action_timeout_ms=action_timeout_ms,
        )
    return context


@contextlib.contextmanager
def browser_session(
    target: str,
    *,
    browser_name: str = "chromium",
    headless: bool = True,
    navigation_timeout_seconds: float = 15.0,
    action_timeout_seconds: float = 10.0,
    test_timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS,
    allow_external: bool = False,
    screenshot_dir: str | Path | None = None,
):
    """Yields `(executor, screenshots)`: `executor` matches `Executor`;
    `screenshots` is a list that accumulates screenshot paths taken while
    the session is open (spec §24), populated only if `screenshot_dir`
    is given.

    `test_timeout_seconds` is a true hard wall-clock ceiling applied fresh
    to *each* `TestCase` the returned executor runs (a session may run
    several sequentially) -- see the module docstring's "TestCase
    wall-clock timeout" section for how it's enforced.
    """
    sync_playwright, PlaywrightError, PlaywrightTimeoutError = _import_playwright()
    validate_target(target, allow_external=allow_external)

    playwright = sync_playwright().start()
    screenshots: list[str] = []
    try:
        browser_type = getattr(playwright, browser_name, None)
        if browser_type is None:
            raise BrowserTargetError(f"unsupported browser: {browser_name!r}")
        try:
            browser = browser_type.launch(headless=headless)
        except PlaywrightError as exc:
            raise BrowserUnavailableError(
                f"could not launch {browser_name}: {exc}. Run `universal-test browser install` first."
            ) from exc

        try:
            # Fresh context per run -- no cookies/localStorage/sessionStorage/cache
            # reuse across runs (spec §9), never any browser permission pre-granted
            # (spec §23: microphone/camera/geolocation/notifications/clipboard).
            context = browser.new_context()
            context.set_default_navigation_timeout(navigation_timeout_seconds * 1000)
            context.set_default_timeout(action_timeout_seconds * 1000)
            try:
                page = context.new_page()
                console_messages: list[dict] = []
                page_errors: list[dict] = []
                network_failures: list[dict] = []
                page.on("console", lambda msg: console_messages.append({"level": msg.type, "text": msg.text}))
                page.on("pageerror", lambda exc: page_errors.append({"message": str(exc)}))

                def _on_request_failed(request):
                    failure = request.failure
                    reason = failure.get("errorText") if isinstance(failure, dict) else str(failure) if failure else None
                    network_failures.append({"url": request.url, "reason": reason})

                page.on("requestfailed", _on_request_failed)

                def _executor(test_case: TestCase) -> dict:
                    # Fresh hard wall-clock budget for *this* TestCase -- computed once,
                    # here, at the moment execution actually starts (never at session
                    # construction time, so queueing/earlier-test-case time never eats
                    # into it). `test_timeout_seconds_override` (Phase 11) lets a caller
                    # that runs several TestCases through this same executor -- e.g.
                    # `ScenarioRunner`, one synthesized TestCase per scenario step --
                    # cascade a shrinking *scenario*-level budget into each call, so a
                    # child step's effective timeout never exceeds what's left of the
                    # scenario, the same "child never exceeds remaining parent budget"
                    # rule this session-level timeout already enforces one level up.
                    # Absent (every Phase 9/10 caller), behavior is unchanged.
                    override = test_case.target.extra.get("test_timeout_seconds_override")
                    effective_test_timeout = override if override is not None else test_timeout_seconds
                    deadline = time.monotonic() + effective_test_timeout
                    navigation_timeout_ms = navigation_timeout_seconds * 1000
                    action_timeout_ms = action_timeout_seconds * 1000

                    steps = test_case.target.extra.get("steps", [])
                    try:
                        _run_steps(
                            page, target, steps, allow_external=allow_external,
                            PlaywrightError=PlaywrightError, PlaywrightTimeoutError=PlaywrightTimeoutError,
                            deadline=deadline, navigation_timeout_ms=navigation_timeout_ms,
                            action_timeout_ms=action_timeout_ms,
                        )
                    finally:
                        if screenshot_dir is not None:
                            path = Path(screenshot_dir) / f"{test_case.id}.png"
                            # Best-effort even if the TestCase budget is already spent --
                            # a small fixed floor so `page.screenshot` isn't handed a
                            # ~0ms timeout, but this never extends the TestCase result
                            # itself (screenshot capture is cleanup, not a scored step).
                            shot_timeout_ms = max(1000.0, (deadline - time.monotonic()) * 1000)
                            with contextlib.suppress(Exception):
                                page.screenshot(path=str(path), timeout=shot_timeout_ms)
                                screenshots.append(str(path))
                    context_dict = _build_context(
                        page, target, console_messages, page_errors, network_failures, test_case, PlaywrightError,
                        deadline=deadline, action_timeout_ms=action_timeout_ms,
                    )
                    return redact_context(context_dict)

                yield _executor, screenshots
            finally:
                context.close()
        finally:
            browser.close()
    finally:
        playwright.stop()
