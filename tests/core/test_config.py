import pytest

from universal_test.core.configuration.config import load_config
from universal_test.core.errors import ConfigurationError


def test_defaults_are_safe_with_no_config_at_all():
    config = load_config()
    assert config.performance.enabled is False
    assert config.performance.target is None
    assert config.database.enabled is False
    assert config.security.enabled is False
    assert config.ai.enabled is False
    assert config.functional.enabled is True


def test_load_config_from_project_path(tmp_path):
    (tmp_path / "universal-test.yaml").write_text(
        """
project:
  name: example-project
performance:
  enabled: true
  target: http://localhost:8080
  concurrency: [1, 10, 50]
""",
        encoding="utf-8",
    )
    config = load_config(project_path=tmp_path)
    assert config.project.name == "example-project"
    assert config.performance.enabled is True
    assert config.performance.target == "http://localhost:8080"
    assert config.performance.concurrency == [1, 10, 50]


def test_no_config_file_present_falls_back_to_defaults(tmp_path):
    config = load_config(project_path=tmp_path)
    assert config.functional.enabled is True
    assert config.performance.enabled is False


def test_explicit_missing_config_path_raises(tmp_path):
    with pytest.raises(ConfigurationError):
        load_config(config_path=tmp_path / "does-not-exist.yaml")


def test_invalid_yaml_raises(tmp_path):
    bad = tmp_path / "universal-test.yaml"
    bad.write_text("project: [unterminated", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(config_path=bad)


def test_non_mapping_section_raises(tmp_path):
    bad = tmp_path / "universal-test.yaml"
    bad.write_text("performance: not-a-mapping\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(config_path=bad)


def test_overrides_take_highest_priority(tmp_path):
    (tmp_path / "universal-test.yaml").write_text(
        "performance:\n  enabled: false\n", encoding="utf-8"
    )
    config = load_config(
        project_path=tmp_path, overrides={"performance": {"enabled": True, "target": "http://x"}}
    )
    assert config.performance.enabled is True
    assert config.performance.target == "http://x"


def test_unknown_keys_are_ignored_not_fatal(tmp_path):
    bad = tmp_path / "universal-test.yaml"
    bad.write_text("totally_unknown_section:\n  foo: bar\n", encoding="utf-8")
    config = load_config(config_path=bad)
    assert config.functional.enabled is True


def test_regression_performance_thresholds_have_safe_non_zero_defaults():
    config = load_config()
    assert config.regression.performance["p95_percent"] == 10.0
    assert config.regression.performance["error_rate_absolute"] == 1.0


def test_regression_thresholds_overridable_via_config_file(tmp_path):
    (tmp_path / "universal-test.yaml").write_text(
        "regression:\n  performance:\n    p95_percent: 25\n    rps_percent: 5\n", encoding="utf-8"
    )
    config = load_config(project_path=tmp_path)
    assert config.regression.performance["p95_percent"] == 25
    assert config.regression.performance["rps_percent"] == 5


def test_regression_partial_threshold_override_keeps_other_defaults(tmp_path):
    # overriding just one threshold must not silently drop the rest of the defaults
    (tmp_path / "universal-test.yaml").write_text(
        "regression:\n  performance:\n    p95_percent: 25\n", encoding="utf-8"
    )
    config = load_config(project_path=tmp_path)
    assert config.regression.performance["p95_percent"] == 25
    assert config.regression.performance["p50_percent"] == 10.0
    assert config.regression.performance["error_rate_absolute"] == 1.0


def test_quality_gate_default_policy():
    config = load_config()
    assert config.quality_gate.fail_on == {
        "regression": ["critical", "high"], "functional": ["failure"], "performance": ["threshold"],
    }
    assert config.quality_gate.warn_on == {
        "regression": ["medium"], "database": ["schema_change"], "discovery": ["change"],
    }


def test_quality_gate_custom_policy_replaces_a_whole_category(tmp_path):
    (tmp_path / "universal-test.yaml").write_text(
        "quality_gate:\n  fail_on:\n    regression: [critical]\n", encoding="utf-8"
    )
    config = load_config(project_path=tmp_path)
    assert config.quality_gate.fail_on["regression"] == ["critical"]


def test_quality_gate_nested_policy_merge_keeps_other_categories(tmp_path):
    # overriding fail_on.regression must not silently drop fail_on.functional/performance
    (tmp_path / "universal-test.yaml").write_text(
        "quality_gate:\n  fail_on:\n    regression: [critical]\n", encoding="utf-8"
    )
    config = load_config(project_path=tmp_path)
    assert config.quality_gate.fail_on["functional"] == ["failure"]
    assert config.quality_gate.fail_on["performance"] == ["threshold"]
    assert config.quality_gate.warn_on == {
        "regression": ["medium"], "database": ["schema_change"], "discovery": ["change"],
    }


def test_quality_gate_can_add_opt_in_rules_like_database_not_assessed(tmp_path):
    (tmp_path / "universal-test.yaml").write_text(
        "quality_gate:\n  fail_on:\n    database: [not_assessed]\n", encoding="utf-8"
    )
    config = load_config(project_path=tmp_path)
    assert config.quality_gate.fail_on["database"] == ["not_assessed"]
    assert config.quality_gate.fail_on["regression"] == ["critical", "high"]  # untouched default


def test_quality_gate_invalid_policy_non_dict_raises(tmp_path):
    (tmp_path / "universal-test.yaml").write_text(
        "quality_gate:\n  fail_on: not-a-mapping\n", encoding="utf-8"
    )
    with pytest.raises(ConfigurationError):
        load_config(project_path=tmp_path)


def test_quality_gate_invalid_policy_non_list_value_raises(tmp_path):
    (tmp_path / "universal-test.yaml").write_text(
        "quality_gate:\n  fail_on:\n    regression: high\n", encoding="utf-8"
    )
    with pytest.raises(ConfigurationError):
        load_config(project_path=tmp_path)


def test_quality_gate_invalid_policy_non_string_list_item_raises(tmp_path):
    (tmp_path / "universal-test.yaml").write_text(
        "quality_gate:\n  fail_on:\n    regression: [1, 2]\n", encoding="utf-8"
    )
    with pytest.raises(ConfigurationError):
        load_config(project_path=tmp_path)


# --- V1 hardening audit: empty-value edge cases ------------------------------


def test_completely_empty_config_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "universal-test.yaml"
    path.write_text("", encoding="utf-8")
    config = load_config(config_path=path)
    assert config.functional.enabled is True
    assert config.quality_gate.fail_on["regression"] == ["critical", "high"]


def test_empty_mapping_config_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "universal-test.yaml"
    path.write_text("{}", encoding="utf-8")
    config = load_config(config_path=path)
    assert config.functional.enabled is True


def test_null_section_value_falls_back_to_section_defaults(tmp_path):
    # "quality_gate:" with nothing after the colon parses as None, not {}
    path = tmp_path / "universal-test.yaml"
    path.write_text("quality_gate:\n", encoding="utf-8")
    config = load_config(config_path=path)
    assert config.quality_gate.fail_on["regression"] == ["critical", "high"]
