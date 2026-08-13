from universal_test.adapters.browser.assertions import build_browser_assertion_engine, selector_key
from universal_test.core.models.test_spec import AssertionSpec

CSS_BODY = {"type": "css", "value": "body"}
ROLE_BUTTON = {"type": "role", "role": "button", "value": "Start"}


def _context(elements=None, **extra):
    return {"url": "http://localhost/", "title": "Home", "elements": elements or {}, **extra}


def test_selector_key_distinguishes_role_from_css():
    assert selector_key(CSS_BODY) != selector_key(ROLE_BUTTON)
    assert selector_key(CSS_BODY) == selector_key(dict(CSS_BODY))


def test_visible_pass_and_fail():
    engine = build_browser_assertion_engine()
    ctx = _context(elements={selector_key(CSS_BODY): {"visible": True, "count": 1}})
    result = engine.evaluate(AssertionSpec("visible", {"selector": CSS_BODY}), ctx)
    assert result.passed

    ctx2 = _context(elements={selector_key(CSS_BODY): {"visible": False, "count": 1}})
    result2 = engine.evaluate(AssertionSpec("visible", {"selector": CSS_BODY}), ctx2)
    assert not result2.passed


def test_hidden_true_when_no_match():
    engine = build_browser_assertion_engine()
    ctx = _context(elements={})
    result = engine.evaluate(AssertionSpec("hidden", {"selector": CSS_BODY}), ctx)
    assert result.passed


def test_text_contains_and_equals():
    engine = build_browser_assertion_engine()
    ctx = _context(elements={selector_key(CSS_BODY): {"text": "Hello world"}})
    assert engine.evaluate(AssertionSpec("text_contains", {"selector": CSS_BODY, "value": "world"}), ctx).passed
    assert not engine.evaluate(AssertionSpec("text_equals", {"selector": CSS_BODY, "value": "Hello"}), ctx).passed


def test_url_equals_and_contains():
    engine = build_browser_assertion_engine()
    ctx = _context()
    assert engine.evaluate(AssertionSpec("url_equals", {"equals": "http://localhost/"}), ctx).passed
    assert engine.evaluate(AssertionSpec("url_contains", {"value": "localhost"}), ctx).passed
    assert not engine.evaluate(AssertionSpec("url_contains", {"value": "example.com"}), ctx).passed


def test_page_title_non_empty_default():
    engine = build_browser_assertion_engine()
    assert engine.evaluate(AssertionSpec("page_title", {}), _context(title="Something")).passed
    assert not engine.evaluate(AssertionSpec("page_title", {}), _context(title="")).passed
    assert engine.evaluate(AssertionSpec("page_title", {"equals": "Home"}), _context(title="Home")).passed
    assert engine.evaluate(AssertionSpec("page_title", {"contains": "Ho"}), _context(title="Home")).passed


def test_element_count():
    engine = build_browser_assertion_engine()
    ctx = _context(elements={selector_key(CSS_BODY): {"count": 3}})
    assert engine.evaluate(AssertionSpec("element_count", {"selector": CSS_BODY, "equals": 3}), ctx).passed
    assert engine.evaluate(AssertionSpec("element_count", {"selector": CSS_BODY, "min": 1, "max": 5}), ctx).passed
    assert not engine.evaluate(AssertionSpec("element_count", {"selector": CSS_BODY, "equals": 1}), ctx).passed


def test_attribute_equals_and_input_value():
    engine = build_browser_assertion_engine()
    ctx = _context(elements={selector_key(CSS_BODY): {"attributes": {"type": "text"}, "value": "hello"}})
    assert engine.evaluate(
        AssertionSpec("attribute_equals", {"selector": CSS_BODY, "name": "type", "equals": "text"}), ctx,
    ).passed
    assert engine.evaluate(AssertionSpec("input_value", {"selector": CSS_BODY, "equals": "hello"}), ctx).passed


def test_checked_enabled_disabled():
    engine = build_browser_assertion_engine()
    ctx = _context(elements={selector_key(CSS_BODY): {"checked": True, "enabled": True}})
    assert engine.evaluate(AssertionSpec("checked", {"selector": CSS_BODY}), ctx).passed
    assert engine.evaluate(AssertionSpec("enabled", {"selector": CSS_BODY}), ctx).passed
    assert not engine.evaluate(AssertionSpec("disabled", {"selector": CSS_BODY}), ctx).passed


def test_browser_engine_does_not_carry_rest_assertions():
    engine = build_browser_assertion_engine()
    assert not engine.is_registered("status_code")
    assert engine.is_registered("visible")
