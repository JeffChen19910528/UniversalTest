from universal_test.adapters.browser.models import BrowserSelector
from universal_test.adapters.browser.scenario_models import (
    ALL_ACTIONS,
    ScenarioStep,
    WebScenario,
    normalize_action,
)


def test_action_aliases_normalize():
    assert normalize_action("select_option") == "select"
    assert normalize_action("wait") == "wait_for"
    assert normalize_action("click") == "click"  # not an alias, passes through


def test_assert_actions_are_recognized():
    step = ScenarioStep(id="s1", action="assert_visible", selector=BrowserSelector("css", "#x"))
    assert step.is_assertion is True

    action_step = ScenarioStep(id="s2", action="click", selector=BrowserSelector("css", "#x"))
    assert action_step.is_assertion is False


def test_requires_selector():
    assert ScenarioStep(id="s", action="click").requires_selector() is True
    assert ScenarioStep(id="s", action="navigate").requires_selector() is False
    assert ScenarioStep(id="s", action="assert_url").requires_selector() is False
    assert ScenarioStep(id="s", action="assert_visible").requires_selector() is True


def test_step_round_trip_serialization():
    step = ScenarioStep(
        id="fill-user", action="fill", selector=BrowserSelector("label", "Username"), value="bob",
    )
    data = step.public_dict()
    restored = ScenarioStep.from_dict(data)
    assert restored.id == step.id
    assert restored.action == step.action
    assert restored.selector == step.selector
    assert restored.value == step.value


def test_scenario_round_trip_serialization():
    scenario = WebScenario(
        id="login-smoke", name="Login Smoke Test", description="desc", target="http://localhost:3000",
        steps=[ScenarioStep(id="open", action="navigate", url="/login")],
        timeout_seconds=60,
    )
    data = scenario.public_dict()
    restored = WebScenario.from_dict(data)
    assert restored.id == "login-smoke"
    assert restored.name == "Login Smoke Test"
    assert restored.timeout_seconds == 60
    assert len(restored.steps) == 1
    assert restored.steps[0].url == "/login"


def test_public_dict_never_includes_value_when_value_env_present():
    step = ScenarioStep(id="pw", action="fill", selector=BrowserSelector("label", "Password"), value_env="TEST_PASSWORD")
    data = step.public_dict()
    assert "value" not in data
    assert data["value_env"] == "TEST_PASSWORD"


def test_all_actions_includes_real_actions_and_assertions_and_aliases():
    for action in ("navigate", "click", "fill", "select_option", "wait", "assert_visible", "assert_url"):
        assert normalize_action(action) in ALL_ACTIONS or action in ALL_ACTIONS
