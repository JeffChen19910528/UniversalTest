"""Browser-specific assertion evaluators (spec §15).

Same `(params, context) -> (bool, str, list[Evidence])` shape as
`core/assertions/builtin.py` -- registered onto a dedicated `AssertionEngine`
instance in `adapter.py`, never mutating the shared REST/DB registry.
Evaluators read only the plain-dict `context` the executor produces (see
`executor.py`'s docstring for its shape); none of them touch Playwright.
"""

from __future__ import annotations

from typing import Any

from universal_test.core.models.evidence import Evidence


def selector_key(selector: dict[str, Any]) -> str:
    """Canonical key both the executor (when pre-resolving element state)
    and these evaluators (when reading it back) derive from a selector spec,
    so the two always agree without sharing a live object."""
    if not selector:
        return ""
    if selector.get("type") == "role":
        return f"role:{selector.get('role', '')}:{selector.get('value', '')}"
    return f"{selector.get('type', '')}:{selector.get('value', '')}"


def _element(params: dict, context: dict) -> dict:
    selector = params.get("selector") or {}
    key = selector_key(selector)
    return context.get("elements", {}).get(key, {})


def visible(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    element = _element(params, context)
    passed = bool(element.get("visible"))
    ev = [Evidence("browser_element", {"selector": params.get("selector"), "visible": element.get("visible")})]
    return passed, f"expected element to be visible, visible={element.get('visible')}", ev


def hidden(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    element = _element(params, context)
    passed = not element.get("visible") or element.get("count", 0) == 0
    ev = [Evidence("browser_element", {"selector": params.get("selector"), "visible": element.get("visible")})]
    return passed, f"expected element to be hidden, visible={element.get('visible')}", ev


def text_contains(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    element = _element(params, context)
    needle = params["value"]
    text = element.get("text") or ""
    passed = needle in text
    ev = [Evidence("browser_element", {"selector": params.get("selector"), "text": text})]
    return passed, f"expected element text to contain {needle!r}, got {text!r}", ev


def text_equals(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    element = _element(params, context)
    expected = params["value"]
    text = element.get("text") or ""
    passed = text.strip() == expected
    ev = [Evidence("browser_element", {"selector": params.get("selector"), "text": text})]
    return passed, f"expected element text == {expected!r}, got {text!r}", ev


def url_equals(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    expected = params["equals"]
    actual = context.get("url")
    passed = actual == expected
    ev = [Evidence("browser_page", {"url": actual})]
    return passed, f"expected url == {expected!r}, got {actual!r}", ev


def url_contains(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    needle = params["value"]
    actual = context.get("url") or ""
    passed = needle in actual
    ev = [Evidence("browser_page", {"url": actual})]
    return passed, f"expected url to contain {needle!r}, got {actual!r}", ev


def page_title(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    actual = context.get("title") or ""
    ev = [Evidence("browser_page", {"title": actual})]
    if "equals" in params:
        passed = actual == params["equals"]
        return passed, f"expected title == {params['equals']!r}, got {actual!r}", ev
    if "contains" in params:
        passed = params["contains"] in actual
        return passed, f"expected title to contain {params['contains']!r}, got {actual!r}", ev
    passed = bool(actual.strip())
    return passed, f"expected a non-empty title, got {actual!r}", ev


def element_count(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    element = _element(params, context)
    actual = element.get("count", 0)
    ev = [Evidence("browser_element", {"selector": params.get("selector"), "count": actual})]
    if "equals" in params:
        passed = actual == params["equals"]
        return passed, f"expected element_count == {params['equals']}, got {actual}", ev
    minimum = params.get("min", 0)
    maximum = params.get("max")
    passed = actual >= minimum and (maximum is None or actual <= maximum)
    expectation = f">= {minimum}" + (f" and <= {maximum}" if maximum is not None else "")
    return passed, f"expected element_count {expectation}, got {actual}", ev


def attribute_equals(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    element = _element(params, context)
    name, expected = params["name"], params["equals"]
    actual = (element.get("attributes") or {}).get(name)
    passed = actual == expected
    ev = [Evidence("browser_element", {"selector": params.get("selector"), "attribute": name, "value": actual})]
    return passed, f"expected attribute {name!r} == {expected!r}, got {actual!r}", ev


def input_value(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    element = _element(params, context)
    expected = params["equals"]
    actual = element.get("value")
    passed = actual == expected
    ev = [Evidence("browser_element", {"selector": params.get("selector"), "value": actual})]
    return passed, f"expected input value == {expected!r}, got {actual!r}", ev


def checked(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    element = _element(params, context)
    passed = element.get("checked") is True
    ev = [Evidence("browser_element", {"selector": params.get("selector"), "checked": element.get("checked")})]
    return passed, f"expected element to be checked, checked={element.get('checked')}", ev


def enabled(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    element = _element(params, context)
    passed = element.get("enabled") is True
    ev = [Evidence("browser_element", {"selector": params.get("selector"), "enabled": element.get("enabled")})]
    return passed, f"expected element to be enabled, enabled={element.get('enabled')}", ev


def disabled(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    element = _element(params, context)
    passed = element.get("enabled") is False
    ev = [Evidence("browser_element", {"selector": params.get("selector"), "enabled": element.get("enabled")})]
    return passed, f"expected element to be disabled, enabled={element.get('enabled')}", ev


def console_summary(params: dict, context: dict) -> tuple[bool, str, list[Evidence]]:
    """Always-included diagnostic assertion (spec §19-§20, §29, §58): records
    console/page-error/network-failure counts as evidence without treating
    them as a defect by default -- `console.warn` and third-party resource
    failures must never auto-fail a test. Only fails if the test explicitly
    configures `max_console_errors`.
    """
    console_errors = context.get("console_errors", [])
    page_errors = context.get("page_errors", [])
    ev = [Evidence("browser_diagnostics", {
        "console_error_count": len(console_errors),
        "console_warning_count": len(context.get("console_warnings", [])),
        "page_error_count": len(page_errors),
        "network_failure_count": len(context.get("network_failures", [])),
    })]
    max_errors = params.get("max_console_errors")
    passed = True if max_errors is None else len(console_errors) <= max_errors
    message = f"console_error_count={len(console_errors)}, page_error_count={len(page_errors)}"
    return passed, message, ev


BROWSER_ASSERTIONS = {
    "visible": visible,
    "hidden": hidden,
    "text_contains": text_contains,
    "text_equals": text_equals,
    "url_equals": url_equals,
    "url_contains": url_contains,
    "page_title": page_title,
    "element_count": element_count,
    "attribute_equals": attribute_equals,
    "input_value": input_value,
    "checked": checked,
    "enabled": enabled,
    "disabled": disabled,
    "console_summary": console_summary,
}


def build_browser_assertion_engine():
    """A fresh `AssertionEngine` carrying only browser assertion types --
    never the shared REST/DB default, so vocabularies never leak into each
    other (spec §15)."""
    from universal_test.core.assertions.engine import AssertionEngine

    engine = AssertionEngine(register_builtins=False)
    for name, evaluator in BROWSER_ASSERTIONS.items():
        engine.register(name, evaluator)
    return engine
