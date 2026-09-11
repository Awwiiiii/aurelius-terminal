"""
Unit tests for historical realized volatility mathematics:
- Observation counts: 2 prices = 1 return (insufficient); 3 prices = 2 returns (valid sample std)
- Annualization using sqrt(252)
- Rolling volatility over k returns
"""

from decimal import Decimal

import pytest

from aurelius.domain.analytics.volatility import (
    calculate_rolling_volatility,
    calculate_sample_volatility,
    compute_volatility_metrics,
)


def test_sample_volatility_observation_counts():
    # 1 return -> must raise ValueError
    with pytest.raises(ValueError, match="At least 2 return observations required"):
        calculate_sample_volatility([Decimal("0.01")])

    # 2 returns -> valid sample std dev
    returns = [Decimal("0.01"), Decimal("-0.01")]
    daily_vol, ann_vol = calculate_sample_volatility(returns)
    assert daily_vol > Decimal("0.0")
    # Bessel N-1 with mean=0: variance = (0.0001 + 0.0001) / 1 = 0.0002 -> std = sqrt(0.0002) ≈ 0.014142
    assert daily_vol == Decimal("0.014142")
    # Annualized = 0.0141421356 * sqrt(252) ≈ 0.224499
    assert ann_vol == Decimal("0.224499")


def test_compute_volatility_metrics_fewer_than_three_prices():
    # 2 prices = 1 return -> returns 0.0 metrics
    prices = [Decimal("100.0"), Decimal("102.0")]
    metrics = compute_volatility_metrics(prices)
    assert metrics.daily_volatility == Decimal("0.0")
    assert metrics.annualized_volatility == Decimal("0.0")


def test_rolling_volatility_window():
    # 25 prices -> 24 returns
    # With window=20:
    # bars 0..19 (first 20 bars, 0..19 returns) must be None
    # bar 20 (20th return) must be the first valid rolling vol
    prices = [Decimal("100.0") + Decimal(str(i * 0.5)) for i in range(25)]
    rolling = calculate_rolling_volatility(prices, window_returns=20)
    assert len(rolling) == 25
    for i in range(20):
        assert rolling[i] is None
    for i in range(20, 25):
        assert rolling[i] is not None
        assert rolling[i] > Decimal("0.0")
