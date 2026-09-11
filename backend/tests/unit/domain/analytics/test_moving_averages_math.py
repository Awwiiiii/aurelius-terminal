"""
Unit tests for moving averages and indicators:
- Zero-indexed warm-up on raw Close:
  - SMA20: observations 0..18 emit None; observation 19 is first SMA20; observation 20 is rolling SMA20.
  - EMA20: observations 0..18 emit None; observation 19 is seeded with SMA20; observation 20 onward is recursive EMA.
  - Does NOT require 21 observations.
- Period extremes: high, low, distance_from_high <= 0%, distance_from_low >= 0%.
"""

from datetime import date
from decimal import Decimal

from aurelius.domain.analytics.indicators import (
    calculate_ema,
    calculate_sma,
    compute_historical_extremes,
)


def test_sma20_zero_indexed_warmup():
    prices = [Decimal(str(100 + i)) for i in range(25)]
    sma = calculate_sma(prices, window=20)
    assert len(sma) == 25
    # First 19 observations (indices 0..18) must be None
    for i in range(19):
        assert sma[i] is None, f"Observation {i} should be None"

    # Observation 19 (the 20th observation) is the first valid SMA
    # Mean of 100..119 = 109.5
    assert sma[19] == Decimal("109.5000")
    # Observation 20: Mean of 101..120 = 110.5
    assert sma[20] == Decimal("110.5000")


def test_ema20_zero_indexed_warmup():
    prices = [Decimal(str(100 + i)) for i in range(25)]
    ema = calculate_ema(prices, window=20)
    assert len(ema) == 25
    # First 19 observations (indices 0..18) must be None
    for i in range(19):
        assert ema[i] is None, f"Observation {i} should be None"

    # Observation 19 must be valid, initialized using SMA20 (109.5)
    assert ema[19] == Decimal("109.5000")

    # Observation 20: EMA_20 = P_20 * (2/21) + EMA_19 * (19/21)
    # P_20 = 120.0
    # 120 * (2/21) + 109.5 * (19/21) = (240 + 2080.5) / 21 = 2320.5 / 21 = 110.5000
    assert ema[20] == Decimal("110.5000")


def test_historical_extremes():
    dates = [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)]
    prices = [Decimal("100.0"), Decimal("120.0"), Decimal("90.0"), Decimal("105.0")]
    extremes = compute_historical_extremes(prices, dates)
    assert extremes.period_high == Decimal("120.0")
    assert extremes.period_high_date == date(2023, 1, 2)
    assert extremes.period_low == Decimal("90.0")
    assert extremes.period_low_date == date(2023, 1, 3)
    # Last price = 105.0
    # distance from high = (105 - 120) / 120 * 100 = -15 / 120 * 100 = -12.50%
    assert extremes.distance_from_high == Decimal("-12.50")
    # distance from low = (105 - 90) / 90 * 100 = 15 / 90 * 100 ≈ +16.67%
    assert extremes.distance_from_low == Decimal("16.67")
