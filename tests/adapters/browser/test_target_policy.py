import pytest

from universal_test.adapters.browser.errors import BrowserTargetError
from universal_test.adapters.browser.target_policy import is_same_origin, validate_target


@pytest.mark.parametrize("target", [
    "http://localhost:3000",
    "http://127.0.0.1:8080",
    "https://localhost",
    "http://[::1]:9000",
    "file:///C:/project/index.html",
])
def test_local_targets_allowed_by_default(target):
    validate_target(target, allow_external=False)


def test_external_target_rejected_without_flag():
    with pytest.raises(BrowserTargetError):
        validate_target("https://example.com", allow_external=False)


def test_external_target_allowed_with_flag():
    validate_target("https://example.com", allow_external=True)


def test_empty_target_rejected():
    with pytest.raises(BrowserTargetError):
        validate_target("", allow_external=False)


def test_unsupported_scheme_rejected():
    with pytest.raises(BrowserTargetError):
        validate_target("ftp://localhost/file", allow_external=False)


def test_is_same_origin():
    assert is_same_origin("http://localhost:3000", "http://localhost:3000/about")
    assert not is_same_origin("http://localhost:3000", "http://localhost:4000/about")
    assert not is_same_origin("http://localhost:3000", "https://evil.example.com")
