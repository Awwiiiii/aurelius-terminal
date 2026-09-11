"""
tests/unit/domain/analytics/test_rolling_volatility_regression.py
================================================================
Regression test suite for M4.1 Historical Analysis stabilization:
1. Rolling volatility calculation & observation count semantics (window=20 returns).
2. Deterministic fixture validation (first point at exact observation 20).
3. Sparse / null-leading series handling.
4. API response serialization of rolling_vol_20.
"""

from datetime import date
from decimal import Decimal

from aurelius.api.v1.schemas.historical import HistoricalBarPointResponse
from aurelius.domain.analytics.volatility import (
    calculate_rolling_volatility,
    calculate_sample_volatility,
)
from aurelius.domain.entities.historical import HistoricalBarPoint


def test_deterministic_rolling_volatility_fixture():
    """
    Deterministic test with 25 observations.
    Given N prices, there are N-1 daily returns.
    With window=20 returns:
    - Observations 0..19 (first 20 bars, representing returns 0..18) must be None.
    - Observation 20 (21st bar, representing the 20th return) must be the first valid rolling vol.
    - Observations 21..24 must all be non-null.
    """
    # Create 25 price observations with known simple geometric changes
    # P_0 = 100, P_i = 100 * (1.01)^i
    prices = [Decimal(str(round(100.0 * (1.01**i), 4))) for i in range(25)]

    rolling = calculate_rolling_volatility(prices, window_returns=20)
    assert len(rolling) == 25

    # Check warm-up: exactly 20 observations must be None
    for i in range(20):
        assert rolling[i] is None, (
            f"Observation {i} expected None during warm-up, got {rolling[i]}"
        )

    # Check first valid observation at index 20
    assert rolling[20] is not None
    # For a constant return series ~0.01, standard deviation is near 0.0
    assert rolling[20] >= Decimal("0.0")

    # Check remaining observations
    for i in range(21, 25):
        assert rolling[i] is not None
        assert rolling[i] >= Decimal("0.0")


def test_rolling_volatility_manual_calculation_accuracy():
    """
    Verify numeric accuracy against manual calculation on a known varying sequence.
    """
    # Create 21 price points (producing exactly 20 returns)
    base = 100.0
    returns = [0.01 if i % 2 == 0 else -0.01 for i in range(20)]
    prices = [Decimal(str(base))]
    cur = base
    for r in returns:
        cur = cur * (1.0 + r)
        prices.append(Decimal(str(round(cur, 6))))

    assert len(prices) == 21
    rolling = calculate_rolling_volatility(prices, window_returns=20)
    assert len(rolling) == 21

    # Indices 0..19 must be None
    for i in range(20):
        assert rolling[i] is None

    # Index 20 is first valid observation
    assert rolling[20] is not None

    # Manual sample std dev calculation on returns:
    # 10 observations of +0.01, 10 observations of -0.01 -> mean = 0.0
    # sum of squares = 20 * (0.01^2) = 0.002
    # sample variance = 0.002 / 19 ≈ 0.00010526315789
    # sample std = sqrt(0.00010526315789) ≈ 0.0102597835
    # annualized = sample_std * sqrt(252) ≈ 0.0102597835 * 15.874507866387544 ≈ 0.162869
    dec_returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, 21)]
    manual_daily, manual_ann = calculate_sample_volatility(dec_returns)

    assert rolling[20] == manual_ann


def test_fewer_prices_than_window():
    """If total prices <= window_returns, all rolling volatility points must be None."""
    prices = [Decimal("100.0") + Decimal(str(i)) for i in range(15)]
    rolling = calculate_rolling_volatility(prices, window_returns=20)
    assert len(rolling) == 15
    assert all(r is None for r in rolling)


def test_api_schema_serialization_preserves_rolling_vol():
    """
    Verify HistoricalBarPoint and HistoricalBarPointResponse correctly serialize
    both None warm-up values and Decimal/string values.
    """
    d1 = date(2023, 1, 3)
    d2 = date(2023, 1, 4)

    point_warmup = HistoricalBarPoint(
        date=d1,
        open=Decimal("150.00"),
        high=Decimal("152.00"),
        low=Decimal("149.00"),
        close=Decimal("151.00"),
        adj_close=Decimal("151.00"),
        volume=1000000,
        daily_return=None,
        cumulative_return=Decimal("0.000000"),
        drawdown=Decimal("0.000000"),
        sma_20=None,
        sma_50=None,
        sma_200=None,
        ema_20=None,
        rolling_vol_20=None,
        benchmark_cumulative_return=None,
    )

    point_valid = HistoricalBarPoint(
        date=d2,
        open=Decimal("151.00"),
        high=Decimal("153.00"),
        low=Decimal("150.00"),
        close=Decimal("152.50"),
        adj_close=Decimal("152.50"),
        volume=1200000,
        daily_return=Decimal("0.009934"),
        cumulative_return=Decimal("0.009934"),
        drawdown=Decimal("0.000000"),
        sma_20=Decimal("150.25"),
        sma_50=None,
        sma_200=None,
        ema_20=Decimal("150.50"),
        rolling_vol_20=Decimal("0.185200"),
        benchmark_cumulative_return=None,
    )

    resp_warmup = HistoricalBarPointResponse.from_domain(point_warmup)
    resp_valid = HistoricalBarPointResponse.from_domain(point_valid)

    assert resp_warmup.rolling_vol_20 is None
    assert resp_valid.rolling_vol_20 == "0.185200"
