from universal_test.adapters.rest.request_data import generate_value


def test_string_uses_example_over_default():
    value, confident = generate_value({"type": "string", "example": "ex", "default": "def"})
    assert value == "ex" and confident


def test_string_uses_default_when_no_example():
    value, confident = generate_value({"type": "string", "default": "def"})
    assert value == "def" and confident


def test_string_uses_enum_first_value():
    value, confident = generate_value({"type": "string", "enum": ["b", "a"]})
    assert value == "b" and confident


def test_string_falls_back_to_safe_default():
    value, confident = generate_value({"type": "string"})
    assert value == "test string" and confident


def test_string_format_email():
    value, confident = generate_value({"type": "string", "format": "email"})
    assert value == "test@example.com" and confident


def test_integer_uses_minimum():
    value, confident = generate_value({"type": "integer", "minimum": 5})
    assert value == 5 and confident


def test_integer_defaults_to_zero():
    value, confident = generate_value({"type": "integer"})
    assert value == 0 and confident


def test_boolean_defaults_true():
    value, confident = generate_value({"type": "boolean"})
    assert value is True and confident


def test_array_with_no_min_items_is_empty():
    value, confident = generate_value({"type": "array", "items": {"type": "string"}})
    assert value == [] and confident


def test_array_with_min_items_builds_minimal_list():
    value, confident = generate_value({"type": "array", "items": {"type": "integer"}, "minItems": 2})
    assert value == [0, 0] and confident


def test_array_with_min_items_but_no_items_schema_is_unconfident():
    value, confident = generate_value({"type": "array", "minItems": 1})
    assert confident is False


def test_object_builds_required_fields_only():
    schema = {
        "type": "object",
        "required": ["name"],
        "properties": {"name": {"type": "string"}, "optional": {"type": "string"}},
    }
    value, confident = generate_value(schema)
    assert confident and value == {"name": "test string"}


def test_object_required_field_missing_schema_is_unconfident():
    schema = {"type": "object", "required": ["name"], "properties": {}}
    value, confident = generate_value(schema)
    assert confident is False


def test_one_of_without_example_is_unconfident():
    value, confident = generate_value({"oneOf": [{"type": "string"}, {"type": "integer"}]})
    assert confident is False


def test_all_of_merges_required_fields():
    schema = {
        "allOf": [
            {"properties": {"a": {"type": "string"}}, "required": ["a"]},
            {"properties": {"b": {"type": "integer"}}, "required": ["b"]},
        ]
    }
    value, confident = generate_value(schema)
    assert confident and value == {"a": "test string", "b": 0}


def test_none_schema_is_unconfident():
    value, confident = generate_value(None)
    assert confident is False
