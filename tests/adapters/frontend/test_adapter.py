import pytest

from universal_test.adapters.frontend.adapter import FrontendAdapter


def test_detect_true_for_frontend_project(fixture_path):
    adapter = FrontendAdapter()
    assert adapter.detect(fixture_path("react-vite-vitest")) is True


def test_detect_false_for_backend_project(fixture_path):
    adapter = FrontendAdapter()
    assert adapter.detect(fixture_path("backend-mentions-react")) is False


def test_describe_returns_adapter_info():
    adapter = FrontendAdapter()
    info = adapter.describe()
    assert info.name == "frontend"
    assert "discovery" in info.capabilities


def test_discover_returns_frontend_info(fixture_path):
    adapter = FrontendAdapter()
    result = adapter.discover(fixture_path("react-vite-vitest"))
    assert result.detected is True
    assert "build" in result.build_scripts


def test_generate_tests_returns_empty_list_not_a_crash(fixture_path):
    adapter = FrontendAdapter()
    info = adapter.discover(fixture_path("react-vite-vitest"))
    assert adapter.generate_tests(info) == []


def test_execute_raises_explicit_not_implemented():
    adapter = FrontendAdapter()
    with pytest.raises(NotImplementedError, match="Browser/UI test execution"):
        adapter.execute([])


def test_collect_metrics_returns_empty_dict():
    adapter = FrontendAdapter()
    assert adapter.collect_metrics(None) == {}
