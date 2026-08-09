import json

from universal_test.discovery.engine import discover
from universal_test.discovery.serializers import to_json, to_markdown, to_text


def test_to_json_is_valid_and_round_trips(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    parsed = json.loads(to_json(model))
    assert parsed["primary_language"] == "Python"
    assert parsed["root_path"] == model.root_path


def test_to_text_contains_key_sections(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    text = to_text(model)
    assert "Languages" in text
    assert "Python" in text
    assert "Potential Secrets" in text
    assert "not a security audit" in text


def test_to_markdown_contains_tables(fixture_path):
    model = discover(fixture_path("dotnet-api"))
    md = to_markdown(model)
    assert "# Discovery Report" in md
    assert "| Language | Confidence | Files |" in md
    assert "C#" in md
