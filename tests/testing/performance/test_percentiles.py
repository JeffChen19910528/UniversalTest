import pytest

from universal_test.testing.performance.percentiles import compute_latency_stats, percentile


def test_percentile_zero_samples_raises():
    with pytest.raises(ValueError):
        percentile([], 50)


def test_percentile_one_sample_returns_it_for_any_percentile():
    assert percentile([42.0], 1) == 42.0
    assert percentile([42.0], 50) == 42.0
    assert percentile([42.0], 99) == 42.0


def test_percentile_two_samples():
    values = [10.0, 20.0]
    assert percentile(values, 50) == 10.0
    assert percentile(values, 90) == 20.0
    assert percentile(values, 99) == 20.0


def test_percentile_identical_values():
    values = [5.0] * 100
    assert percentile(values, 50) == 5.0
    assert percentile(values, 99) == 5.0


def test_percentile_small_dataset():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(values, 50) == 3.0  # rank = ceil(0.5*5) = 3 -> index 2
    assert percentile(values, 100) == 5.0


def test_percentile_large_dataset_matches_nearest_rank_definition():
    values = [float(i) for i in range(1, 1001)]  # 1..1000
    assert percentile(values, 50) == 500.0
    assert percentile(values, 90) == 900.0
    assert percentile(values, 95) == 950.0
    assert percentile(values, 99) == 990.0


def test_compute_latency_stats_zero_samples_is_none():
    assert compute_latency_stats([]) is None


def test_compute_latency_stats_one_sample():
    stats = compute_latency_stats([10.0])
    assert stats.min_ms == stats.max_ms == stats.p50_ms == stats.p99_ms == 10.0
    assert stats.mean_ms == 10.0


def test_compute_latency_stats_sorts_input():
    stats = compute_latency_stats([30.0, 10.0, 20.0])
    assert stats.min_ms == 10.0
    assert stats.max_ms == 30.0


def test_compute_latency_stats_mean():
    stats = compute_latency_stats([10.0, 20.0, 30.0])
    assert stats.mean_ms == 20.0
