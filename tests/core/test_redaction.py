from universal_test.core.redaction import redact, redact_mapping


def test_redacts_key_value_password():
    assert "***REDACTED***" in redact("password=hunter2")
    assert "hunter2" not in redact("password=hunter2")


def test_redacts_api_key_with_colon():
    text = 'api_key: "sk-abc123"'
    out = redact(text)
    assert "sk-abc123" not in out
    assert "***REDACTED***" in out


def test_redacts_connection_string_credentials():
    text = "postgres://admin:s3cret@db.internal:5432/app"
    out = redact(text)
    assert "s3cret" not in out
    assert "admin" not in out
    assert "db.internal:5432/app" in out


def test_redacts_private_key_block():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIBogIBAAJ...\n-----END RSA PRIVATE KEY-----"
    out = redact(text)
    assert "MIIBogIBAAJ" not in out


def test_leaves_non_secret_text_untouched():
    text = "GET /api/users returned 200"
    assert redact(text) == text


def test_redact_mapping_recurses():
    data = {
        "outer": {"password": "abc123"},
        "list": [{"token": "xyz"}],
        "safe": "value",
    }
    out = redact_mapping(data)
    assert "abc123" not in str(out)
    assert "xyz" not in str(out)
    assert out["safe"] == "value"


# --- V1 hardening audit finding: Set-Cookie/Cookie were not redacted at all ---


def test_redacts_set_cookie_header_value_in_mapping():
    headers = {"Set-Cookie": "sessionid=abc123XYZ; HttpOnly; Path=/"}
    out = redact_mapping(headers)
    assert "abc123XYZ" not in str(out)


def test_redacts_cookie_header_value_in_mapping():
    headers = {"Cookie": "sessionid=abc123XYZ"}
    out = redact_mapping(headers)
    assert "abc123XYZ" not in str(out)


def test_redacts_cookie_case_insensitive_key():
    for key in ("cookie", "Cookie", "COOKIE", "set-cookie", "Set-Cookie", "SET-COOKIE"):
        out = redact_mapping({key: "sessionid=abc123XYZ"})
        assert "abc123XYZ" not in str(out), f"leaked for key {key!r}"


def test_redacts_cookie_in_free_text():
    assert "abc123XYZ" not in redact("Cookie: sessionid=abc123XYZ")
    assert "abc123XYZ" not in redact("Set-Cookie: sessionid=abc123XYZ; Path=/")
