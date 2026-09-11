"""
tests/unit/domain/analytics/test_rolling.py
===========================================
Unit tests for rolling statistics over W return observations and zero-indexed warm-up.
"""

from decimal import Decimal

import pytest

from aurelius.domain.analytics.rolling import (
    calculate_rolling_correlation,
    calculate_rolling_covariance,
    calculate_rolling_mean,
    calculate_rolling_std,
)


def test_rolling_statistics_warmup_and_values():
    """
    Test 10 observations with window W = 4:
      - indices 0, 1, 2: must be None
      - index 3: first valid calculation over 0..3
      - index 4..9: subsequent sliding window calculations
    """
    returns = [Decimal(str(i * 0.01)) for i in range(10)]
    w = 4

    r_mean = calculate_rolling_mean(returns, window=w)
    r_std = calculate_rolling_std(returns, window=w)

    assert len(r_mean) == 10
    assert len(r_std) == 10

    # Warm-up check (first W - 1 = 3 observations must be None)
    for j in range(3):
        assert r_mean[j] is None
        assert r_std[j] is None

    # First valid observation at index 3: mean of [0.0, 0.01, 0.02, 0.03] = 0.015
    assert r_mean[3] == Decimal("0.015000")
    assert r_std[3] is not None
    assert r_std[3] > Decimal("0.0")

    # Rolling covariance and correlation between x and y
    returns_y = [Decimal(str(i * 0.02)) for i in range(10)]
    r_cov = calculate_rolling_covariance(returns, returns_y, window=w)
    r_corr = calculate_rolling_correlation(returns, returns_y, window=w)

    for j in range(3):
        assert r_cov[j] is None
        assert r_corr[j] is None

    # Perfectly collinear y = 2x -> rolling correlation must be 1.0000
    for j in range(3, 10):
        assert r_corr[j] == Decimal("1.0000")


def test_rolling_invalid_window():
    returns = [Decimal("0.01")] * 5
    with pytest.raises(ValueError, match="at least 2"):
        calculate_rolling_std(returns, window=1)
