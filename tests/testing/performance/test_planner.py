import pytest

from universal_test.core.errors import ConfigurationError
from universal_test.testing.performance.models import LoadProfileType
from universal_test.testing.performance.planner import (
    DEFAULT_REQUESTS_PER_LEVEL,
    MAX_CONCURRENCY,
    MAX_LEVELS,
    MAX_REQUESTS_PER_LEVEL,
    build_load_profile,
)


def test_baseline_forces_concurrency_one():
    profile, warnings = build_load_profile("baseline", concurrency=[5, 10])
    assert profile.concurrency_levels == [1]
    assert warnings  # warns that --concurrency was ignored


def test_load_default_concurrency():
    profile, _ = build_load_profile("load")
    assert profile.concurrency_levels == [1, 10]


def test_load_explicit_concurrency():
    profile, _ = build_load_profile("load", concurrency=[1, 5, 25])
    assert profile.concurrency_levels == [1, 5, 25]


def test_custom_requires_concurrency():
    with pytest.raises(ConfigurationError):
        build_load_profile("custom")


def test_custom_with_concurrency():
    profile, _ = build_load_profile("custom", concurrency=[3, 7])
    assert profile.concurrency_levels == [3, 7]


def test_stress_auto_generates_steps_within_cap():
    profile, _ = build_load_profile("stress", max_concurrency=20)
    assert profile.concurrency_levels == [1, 2, 5, 10, 20]
    assert profile.profile_type == LoadProfileType.STRESS


def test_stress_defaults_a_stop_condition_when_none_given():
    profile, warnings = build_load_profile("stress")
    assert profile.stop_on_error_rate_percent is not None
    assert warnings


def test_stress_respects_explicit_stop_condition():
    profile, warnings = build_load_profile("stress", stop_on_p95_ms=200)
    assert profile.stop_on_p95_ms == 200
    assert not any("defaulting" in w for w in warnings)


def test_requests_default_when_neither_given():
    profile, _ = build_load_profile("load")
    assert profile.requests_per_level == DEFAULT_REQUESTS_PER_LEVEL
    assert profile.duration_seconds_per_level is None


def test_duration_used_when_requests_not_given():
    profile, _ = build_load_profile("load", duration=5.0)
    assert profile.duration_seconds_per_level == 5.0
    assert profile.requests_per_level is None


def test_both_requests_and_duration_prefers_requests_with_warning():
    profile, warnings = build_load_profile("load", requests=10, duration=5.0)
    assert profile.requests_per_level == 10
    assert profile.duration_seconds_per_level is None
    assert any("takes precedence" in w for w in warnings)


def test_concurrency_zero_or_negative_rejected():
    with pytest.raises(ConfigurationError):
        build_load_profile("custom", concurrency=[0])
    with pytest.raises(ConfigurationError):
        build_load_profile("custom", concurrency=[-1])


def test_concurrency_exceeding_max_rejected():
    with pytest.raises(ConfigurationError):
        build_load_profile("custom", concurrency=[MAX_CONCURRENCY + 1])


def test_too_many_levels_rejected():
    with pytest.raises(ConfigurationError):
        build_load_profile("custom", concurrency=list(range(1, MAX_LEVELS + 2)))


def test_requests_exceeding_max_rejected():
    with pytest.raises(ConfigurationError):
        build_load_profile("load", requests=MAX_REQUESTS_PER_LEVEL + 1)


def test_requests_zero_or_negative_rejected():
    with pytest.raises(ConfigurationError):
        build_load_profile("load", requests=0)


def test_duration_zero_or_negative_rejected():
    with pytest.raises(ConfigurationError):
        build_load_profile("load", duration=0)


def test_unknown_profile_type_rejected():
    with pytest.raises(ConfigurationError):
        build_load_profile("nonsense")


def test_stress_max_concurrency_exceeding_hard_cap_rejected():
    with pytest.raises(ConfigurationError):
        build_load_profile("stress", max_concurrency=MAX_CONCURRENCY + 1)
