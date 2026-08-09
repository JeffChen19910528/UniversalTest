import pytest

from universal_test.core.assertions.engine import AssertionEngine
from universal_test.core.errors import AssertionEngineError
from universal_test.core.models.test_spec import AssertionSpec


@pytest.fixture
def engine() -> AssertionEngine:
    return AssertionEngine()


HTTP_CONTEXT = {
    "status_code": 201,
    "elapsed_ms": 42,
    "json": {"id": "abc", "items": [{"name": "widget"}], "nested": {"ok": True}},
    "headers": {"Content-Type": "application/json"},
    "body": '{"id": "abc"}',
}


def test_status_code_pass(engine):
    result = engine.evaluate(AssertionSpec("status_code", {"equals": 201}), HTTP_CONTEXT)
    assert result.passed


def test_status_code_fail(engine):
    result = engine.evaluate(AssertionSpec("status_code", {"equals": 200}), HTTP_CONTEXT)
    assert not result.passed
    assert result.evidence[0].type == "http_response"


def test_status_code_in(engine):
    result = engine.evaluate(
        AssertionSpec("status_code_in", {"values": [200, 201, 202]}), HTTP_CONTEXT
    )
    assert result.passed


def test_response_time_less_than(engine):
    ok = engine.evaluate(AssertionSpec("response_time_less_than", {"ms": 100}), HTTP_CONTEXT)
    too_slow = engine.evaluate(AssertionSpec("response_time_less_than", {"ms": 10}), HTTP_CONTEXT)
    assert ok.passed
    assert not too_slow.passed


def test_json_path_exists(engine):
    assert engine.evaluate(AssertionSpec("json_path_exists", {"path": "$.id"}), HTTP_CONTEXT).passed
    assert not engine.evaluate(
        AssertionSpec("json_path_exists", {"path": "$.missing"}), HTTP_CONTEXT
    ).passed
    assert engine.evaluate(
        AssertionSpec("json_path_exists", {"path": "$.items[0].name"}), HTTP_CONTEXT
    ).passed


def test_json_path_equals(engine):
    result = engine.evaluate(
        AssertionSpec("json_path_equals", {"path": "$.nested.ok", "equals": True}), HTTP_CONTEXT
    )
    assert result.passed


def test_json_schema_valid_minimal(engine):
    schema = {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}}
    result = engine.evaluate(AssertionSpec("json_schema_valid", {"schema": schema}), HTTP_CONTEXT)
    assert result.passed

    bad_context = {**HTTP_CONTEXT, "json": {"other": 1}}
    result = engine.evaluate(AssertionSpec("json_schema_valid", {"schema": schema}), bad_context)
    assert not result.passed


def test_json_schema_valid_uses_jsonschema_library(engine):
    schema = {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}}
    result = engine.evaluate(AssertionSpec("json_schema_valid", {"schema": schema}), HTTP_CONTEXT)
    assert result.evidence[0].data["validator"] == "jsonschema"


def test_json_schema_valid_reports_full_validation_errors(engine):
    # a constraint the Phase 1 minimal checker didn't support (string length) --
    # proves Phase 3's full jsonschema-backed validation is actually active.
    schema = {"type": "object", "properties": {"id": {"type": "string", "minLength": 10}}}
    result = engine.evaluate(AssertionSpec("json_schema_valid", {"schema": schema}), HTTP_CONTEXT)
    assert not result.passed  # HTTP_CONTEXT's json.id == "abc", shorter than minLength 10


def test_json_schema_valid_malformed_schema_is_reported_not_silently_passed(engine):
    malformed_schema = {"type": "not-a-real-type"}
    result = engine.evaluate(AssertionSpec("json_schema_valid", {"schema": malformed_schema}), HTTP_CONTEXT)
    assert not result.passed
    assert "schema_error" in result.evidence[0].data


def test_header_exists_and_equals(engine):
    assert engine.evaluate(AssertionSpec("header_exists", {"name": "content-type"}), HTTP_CONTEXT).passed
    result = engine.evaluate(
        AssertionSpec("header_equals", {"name": "Content-Type", "equals": "application/json"}),
        HTTP_CONTEXT,
    )
    assert result.passed


def test_body_contains_and_not_contains(engine):
    assert engine.evaluate(AssertionSpec("body_contains", {"value": "abc"}), HTTP_CONTEXT).passed
    assert engine.evaluate(AssertionSpec("body_not_contains", {"value": "zzz"}), HTTP_CONTEXT).passed


def test_row_count(engine):
    context = {"rows": [1, 2, 3]}
    assert engine.evaluate(AssertionSpec("row_count", {"equals": 3}), context).passed
    assert engine.evaluate(AssertionSpec("row_count", {"min": 1, "max": 5}), context).passed
    assert not engine.evaluate(AssertionSpec("row_count", {"min": 10}), context).passed


def test_value_equals_and_not_null(engine):
    context = {"status_code": 200, "json": {"a": None}}
    assert engine.evaluate(AssertionSpec("value_equals", {"path": "status_code", "equals": 200}), context).passed
    assert not engine.evaluate(AssertionSpec("value_not_null", {"path": "json.a"}), context).passed
    assert not engine.evaluate(AssertionSpec("value_not_null", {"path": "json.missing"}), context).passed


def test_unknown_assertion_type_raises(engine):
    with pytest.raises(AssertionEngineError):
        engine.evaluate(AssertionSpec("does_not_exist", {}), HTTP_CONTEXT)


def test_missing_required_param_raises(engine):
    with pytest.raises(AssertionEngineError):
        engine.evaluate(AssertionSpec("status_code", {}), HTTP_CONTEXT)


def test_custom_assertion_can_be_registered(engine):
    engine.register("always_pass", lambda params, context: (True, "ok", []))
    result = engine.evaluate(AssertionSpec("always_pass", {}), HTTP_CONTEXT)
    assert result.passed
