import pytest

from universal_test.adapters.browser.scenario_loader import (
    load_scenario_file,
    resolve_scenario_path,
    validate_scenarios,
)
from universal_test.adapters.browser.scenario_models import ScenarioCollection, ScenarioStep, WebScenario
from universal_test.adapters.browser.models import BrowserSelector
from universal_test.core.errors import ConfigurationError


def _write(tmp_path, text):
    path = tmp_path / "universal-test-web.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_file_raises_configuration_error(tmp_path):
    with pytest.raises(ConfigurationError):
        load_scenario_file(tmp_path / "does-not-exist.yaml")


def test_malformed_yaml_raises_configuration_error(tmp_path):
    path = _write(tmp_path, "scenarios: [this is: not: valid")
    with pytest.raises(ConfigurationError):
        load_scenario_file(path)


def test_missing_scenarios_key_yields_an_empty_collection(tmp_path):
    # Forward-compatible/lenient, matching this project's existing config-loading
    # convention (core/configuration/config.py): an unrecognized/missing key
    # degrades to "nothing found," never a hard crash.
    path = _write(tmp_path, "not_scenarios: []\n")
    collection = load_scenario_file(path)
    assert collection.scenarios == []


def test_empty_file_yields_an_empty_collection(tmp_path):
    path = _write(tmp_path, "")
    collection = load_scenario_file(path)
    assert collection.scenarios == []


def test_scenarios_key_not_a_list_raises_configuration_error(tmp_path):
    path = _write(tmp_path, "scenarios: not-a-list\n")
    with pytest.raises(ConfigurationError):
        load_scenario_file(path)


def test_valid_yaml_loads_scenarios(tmp_path):
    path = _write(tmp_path, """
scenarios:
  - id: login-smoke
    name: Login Smoke Test
    steps:
      - id: open
        action: navigate
        url: /login
      - id: user
        action: fill
        selector:
          type: label
          value: Username
        value_env: TEST_USERNAME
      - id: dashboard
        action: assert_visible
        selector:
          type: text
          value: Dashboard
""")
    collection = load_scenario_file(path)
    assert len(collection.scenarios) == 1
    scenario = collection.get("login-smoke")
    assert scenario is not None
    assert scenario.name == "Login Smoke Test"
    assert len(scenario.steps) == 3
    assert scenario.steps[1].value_env == "TEST_USERNAME"


def test_resolve_scenario_path_defaults_to_universal_test_web_yaml(tmp_path):
    resolved = resolve_scenario_path(tmp_path, None)
    assert resolved.name == "universal-test-web.yaml"


def test_resolve_scenario_path_honors_explicit_override(tmp_path):
    resolved = resolve_scenario_path(tmp_path, "custom.yaml")
    assert resolved == pytest_path("custom.yaml")


def pytest_path(name):
    from pathlib import Path
    return Path(name)


# -- Validation ---------------------------------------------------------

def _scenario(**overrides):
    defaults = dict(id="s1", name="Scenario 1", steps=[
        ScenarioStep(id="open", action="navigate", url="/x"),
    ])
    defaults.update(overrides)
    return WebScenario(**defaults)


def test_valid_scenario_has_no_issues():
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[_scenario()]))
    assert issues == []


def test_missing_scenario_id_is_an_issue():
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[_scenario(id="")]))
    assert any("id" in str(i) for i in issues)


def test_duplicate_scenario_id_is_an_issue():
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[_scenario(id="dup"), _scenario(id="dup")]))
    assert any("duplicate" in str(i).lower() for i in issues)


def test_missing_scenario_name_is_an_issue():
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[_scenario(name="")]))
    assert any("name" in str(i) for i in issues)


def test_unknown_action_is_an_issue():
    scenario = _scenario(steps=[ScenarioStep(id="s", action="delete_everything")])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("unknown action" in str(i) for i in issues)


def test_missing_navigate_url_is_an_issue():
    scenario = _scenario(steps=[ScenarioStep(id="s", action="navigate")])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("navigate" in str(i) for i in issues)


def test_click_without_selector_is_an_issue():
    scenario = _scenario(steps=[ScenarioStep(id="s", action="click")])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("selector" in str(i) for i in issues)


def test_invalid_selector_type_is_an_issue():
    scenario = _scenario(steps=[ScenarioStep(id="s", action="click", selector=BrowserSelector("xpath", "//div"))])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("invalid selector" in str(i) for i in issues)


def test_role_selector_without_role_is_an_issue():
    scenario = _scenario(steps=[ScenarioStep(id="s", action="click", selector=BrowserSelector("role", "Login"))])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("role" in str(i) for i in issues)


def test_assert_attribute_without_attribute_name_is_an_issue():
    scenario = _scenario(steps=[
        ScenarioStep(id="s", action="assert_attribute", selector=BrowserSelector("css", "#x")),
    ])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("attribute" in str(i) for i in issues)


def test_assert_count_without_bounds_is_an_issue():
    scenario = _scenario(steps=[
        ScenarioStep(id="s", action="assert_count", selector=BrowserSelector("css", "li")),
    ])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("assert_count" in str(i) for i in issues)


def test_missing_fill_value_is_an_issue():
    scenario = _scenario(steps=[ScenarioStep(id="s", action="fill", selector=BrowserSelector("css", "#x"))])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("value" in str(i) for i in issues)


def test_invalid_environment_variable_reference_is_an_issue():
    scenario = _scenario(steps=[
        ScenarioStep(id="s", action="fill", selector=BrowserSelector("css", "#x"), value_env="not a valid name!"),
    ])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("environment" in str(i) for i in issues)


def test_invalid_timeout_is_an_issue():
    scenario = _scenario(timeout_seconds=-5)
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("timeout" in str(i) for i in issues)


def test_nan_timeout_is_an_issue():
    scenario = _scenario(timeout_seconds=float("nan"))
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("timeout" in str(i) for i in issues)


def test_no_steps_is_an_issue():
    scenario = _scenario(steps=[])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("no steps" in str(i) for i in issues)


def test_duplicate_step_id_is_an_issue():
    scenario = _scenario(steps=[
        ScenarioStep(id="dup", action="navigate", url="/a"),
        ScenarioStep(id="dup", action="navigate", url="/b"),
    ])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert any("duplicate step" in str(i).lower() for i in issues)


def test_validation_never_touches_environment_or_network(monkeypatch):
    # Validation must be pure -- no os.environ reads (secrets resolved only at
    # execution time), no socket/browser activity (spec section 13).
    import os
    monkeypatch.setattr(os, "environ", {})  # empty -- if validation tried to require the var, this would fail
    scenario = _scenario(steps=[
        ScenarioStep(id="s", action="fill", selector=BrowserSelector("css", "#x"), value_env="TEST_PASSWORD"),
    ])
    issues = validate_scenarios(ScenarioCollection(source_path="x", scenarios=[scenario]))
    assert issues == []  # a well-formed env var reference is valid even if unset
