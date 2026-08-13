import math

from universal_test.core.configuration.config import (
    MAX_BROWSER_TEST_TIMEOUT_SECONDS,
    MAX_BROWSER_TIMEOUT_SECONDS,
    BrowserConfig,
    load_config,
)


def test_browser_config_defaults_are_safe():
    config = BrowserConfig()
    assert config.enabled is False
    assert config.allow_external is False
    assert config.screenshots is False
    assert config.headless is True


def test_browser_config_timeouts_hard_capped():
    config = BrowserConfig(
        navigation_timeout_seconds=999999, action_timeout_seconds=999999, test_timeout_seconds=999999,
    )
    assert config.navigation_timeout_seconds <= MAX_BROWSER_TIMEOUT_SECONDS
    assert config.action_timeout_seconds <= MAX_BROWSER_TIMEOUT_SECONDS
    assert config.test_timeout_seconds <= MAX_BROWSER_TIMEOUT_SECONDS * 5


def test_load_config_with_browser_section(tmp_path):
    config_file = tmp_path / "universal-test.yaml"
    config_file.write_text(
        "browser:\n  enabled: true\n  allow_external: true\n  navigation_timeout_seconds: 5\n",
        encoding="utf-8",
    )
    config = load_config(config_path=config_file)
    assert config.browser.enabled is True
    assert config.browser.allow_external is True
    assert config.browser.navigation_timeout_seconds == 5


def test_load_config_without_browser_section_is_safe_default():
    config = load_config()
    assert config.browser.enabled is False


def test_browser_config_rejects_zero_and_negative_timeouts():
    config = BrowserConfig(navigation_timeout_seconds=0, action_timeout_seconds=-5, test_timeout_seconds=-1)
    assert config.navigation_timeout_seconds >= 1.0
    assert config.action_timeout_seconds >= 1.0
    assert config.test_timeout_seconds >= 1.0


def test_browser_config_rejects_nan_timeout():
    config = BrowserConfig(
        navigation_timeout_seconds=float("nan"), action_timeout_seconds=float("nan"),
        test_timeout_seconds=float("nan"),
    )
    assert math.isfinite(config.navigation_timeout_seconds)
    assert math.isfinite(config.action_timeout_seconds)
    assert math.isfinite(config.test_timeout_seconds)
    # NaN falls back to the documented safe default, not an arbitrary clamp.
    assert config.navigation_timeout_seconds == 15.0
    assert config.action_timeout_seconds == 10.0
    assert config.test_timeout_seconds == 60.0


def test_browser_config_rejects_infinite_timeout():
    # +infinity is not a "very large but valid" duration -- treated the same
    # as NaN (an invalid, non-representable value) and falls back to the
    # documented safe default, never an unbounded wait.
    config = BrowserConfig(
        navigation_timeout_seconds=float("inf"), action_timeout_seconds=float("inf"),
        test_timeout_seconds=float("inf"),
    )
    assert math.isfinite(config.navigation_timeout_seconds)
    assert math.isfinite(config.action_timeout_seconds)
    assert math.isfinite(config.test_timeout_seconds)
    assert config.navigation_timeout_seconds == 15.0
    assert config.action_timeout_seconds == 10.0
    assert config.test_timeout_seconds == 60.0
    # Regardless of default-vs-clamp semantics, infinity must never survive.
    assert config.navigation_timeout_seconds <= MAX_BROWSER_TIMEOUT_SECONDS
    assert config.test_timeout_seconds <= MAX_BROWSER_TEST_TIMEOUT_SECONDS


def test_browser_config_test_timeout_hard_capped_independently():
    config = BrowserConfig(test_timeout_seconds=999999)
    assert config.test_timeout_seconds == MAX_BROWSER_TEST_TIMEOUT_SECONDS


def test_load_config_cannot_bypass_hard_cap_via_yaml(tmp_path):
    config_file = tmp_path / "universal-test.yaml"
    config_file.write_text(
        "browser:\n  test_timeout_seconds: 999999\n  navigation_timeout_seconds: -1\n",
        encoding="utf-8",
    )
    config = load_config(config_path=config_file)
    assert config.browser.test_timeout_seconds == MAX_BROWSER_TEST_TIMEOUT_SECONDS
    assert config.browser.navigation_timeout_seconds >= 1.0
