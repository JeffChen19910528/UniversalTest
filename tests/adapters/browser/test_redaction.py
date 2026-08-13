from universal_test.adapters.browser.redaction import redact_context, redact_text


def test_redact_text_removes_password():
    assert "hunter2" not in redact_text("password=hunter2")


def test_redact_context_removes_secrets_in_console_and_network_evidence():
    context = {
        "url": "http://localhost/",
        "console_errors": [{"level": "error", "text": "Authorization: Bearer abc123secret"}],
        "network_failures": [{"url": "http://localhost/api", "reason": "Set-Cookie: session=deadbeef"}],
        "elements": {"css:body": {"attributes": {"token": "supersecrettoken"}}},
    }
    redacted = redact_context(context)
    dumped = str(redacted)
    assert "abc123secret" not in dumped
    assert "deadbeef" not in dumped
    assert "supersecrettoken" not in dumped


def test_redact_context_never_carries_storage_keys():
    # The executor never reads localStorage/sessionStorage/cookies/IndexedDB into
    # context in the first place (spec section 41) -- this asserts the redaction
    # helper doesn't accidentally invite that by special-casing such keys as safe.
    context = {"localStorage": {"token": "secret"}}
    redacted = redact_context(context)
    assert "secret" not in str(redacted)
