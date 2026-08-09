import json

from universal_test.discovery.engine import discover
from universal_test.discovery.serializers import to_json, to_markdown, to_text


def test_secret_pattern_detected_without_leaking_value(fixture_path):
    model = discover(fixture_path("dotnet-api"))
    assert model.secrets, "expected at least one potential secret in the fixture appsettings.json"
    finding = model.secrets[0]
    assert finding.file.endswith("appsettings.json")
    assert finding.pattern_type in ("password", "connection_string")


def test_placeholder_values_are_not_flagged(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    # API_KEY=REPLACE_ME is a placeholder and must not be flagged
    api_key_findings = [s for s in model.secrets if s.pattern_type == "api_key"]
    assert api_key_findings == []


def test_real_looking_connection_string_is_flagged(fixture_path):
    model = discover(fixture_path("python-fastapi"))
    conn_findings = [s for s in model.secrets if s.pattern_type == "connection_string"]
    assert conn_findings


def test_secret_values_never_appear_in_any_serialized_output(fixture_path):
    model = discover(fixture_path("dotnet-api"))
    assert model.secrets  # sanity: fixture does contain a flaggable pattern

    for rendered in (to_text(model), to_markdown(model), to_json(model)):
        assert "Sup3rSecretPw" not in rendered

    parsed = json.loads(to_json(model))
    for finding in parsed["secrets"]:
        assert finding["value"] == "[REDACTED]"
