import builtins

import pytest

from universal_test.adapters.browser import errors
from universal_test.adapters.browser.adapter import run
from universal_test.core.errors import AdapterError, ExecutionError, NetworkError, RequestTimeoutError, TargetError


def test_error_classes_subclass_existing_core_errors():
    assert issubclass(errors.BrowserUnavailableError, AdapterError)
    assert issubclass(errors.BrowserTargetError, TargetError)
    assert issubclass(errors.BrowserTimeoutError, RequestTimeoutError)
    assert issubclass(errors.BrowserSelectorError, ExecutionError)
    assert issubclass(errors.BrowserPermissionRequiredError, AdapterError)
    assert issubclass(errors.BrowserNetworkError, NetworkError)


def test_missing_playwright_reports_not_assessed_not_a_crash(monkeypatch, tmp_path):
    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "playwright.sync_api" or name.startswith("playwright"):
            raise ImportError("simulated: playwright not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    result = run(str(tmp_path), target="http://localhost:9999")

    assert result.executed is False
    assert result.not_assessed_reason is not None
    assert "playwright" in result.not_assessed_reason.lower() or "browser install" in result.not_assessed_reason.lower()


def test_dry_run_never_imports_playwright(monkeypatch, tmp_path):
    real_import = builtins.__import__

    def _fail_on_playwright(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise AssertionError("dry-run must never import playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fail_on_playwright)

    result = run(str(tmp_path), target="http://localhost:9999", dry_run=True)
    assert result.executed is False
    assert len(result.test_cases) == 1


def test_no_target_reported_explicitly(tmp_path):
    result = run(str(tmp_path))
    assert result.executed is False
    assert result.no_target_reason is not None
    assert result.test_cases == []


def test_external_target_rejected_before_any_browser_launch(monkeypatch, tmp_path):
    real_import = builtins.__import__

    def _fail_on_playwright(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise AssertionError("must reject target before importing playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fail_on_playwright)

    result = run(str(tmp_path), target="https://example.com", allow_external=False)
    assert result.executed is False
    assert result.no_target_reason is not None
