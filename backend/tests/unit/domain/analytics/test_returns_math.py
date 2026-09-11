"""
Unit tests for pure returns mathematics:
- Simple daily returns
- Cumulative return series
- Calendar-time CAGR (>= 365 calendar days, None if < 365)
- Win rate with zero-return day exclusion
"""

from datetime import date
from decimal import Decimal

from aurelius.domain.analytics.returns import (
    calculate_calendar_cagr,
    calculate_cumulative_returns,
    calculate_simple_daily_returns,
    calculate_win_rate_counts,
    compute_return_metrics,
)


def test_simple_daily_returns_empty_and_single():
    assert calculate_simple_daily_returns([]) == []
    assert calculate_simple_daily_returns([Decimal("100.0")]) == [None]


def test_simple_daily_returns_calculation():
    prices = [Decimal("100.0"), Decimal("105.0"), Decimal("94.5"), Decimal("94.5")]
    returns = calculate_simple_daily_returns(prices)
    assert len(returns) == 4
    assert returns[0] is None
    assert returns[1] == Decimal("0.05000000")
    assert returns[2] == Decimal("-0.10000000")
    assert returns[3] == Decimal("0.00000000")


def test_cumulative_returns():
    prices = [Decimal("100.0"), Decimal("110.0"), Decimal("90.0")]
    cum = calculate_cumulative_returns(prices)
    assert cum[0] == Decimal("0.00000000")
    assert cum[1] == Decimal("0.10000000")
    assert cum[2] == Decimal("-0.10000000")


def test_calendar_cagr_under_one_year():
    # 364 days: must emit None
    cagr = calculate_calendar_cagr(
        start_price=Decimal("100.0"),
        end_price=Decimal("120.0"),
        calendar_days=364,
    )
    assert cagr is None


def test_calendar_cagr_multi_year():
    # Exactly 2 years = 730 calendar days, 100 -> 121 (10% annualized)
    # (121/100) ** (365.2425 / 730) - 1 ≈ 1.21 ** 0.500332 - 1 ≈ 0.100067
    cagr = calculate_calendar_cagr(
        start_price=Decimal("100.0"),
        end_price=Decimal("121.0"),
        calendar_days=730,
    )
    assert cagr is not None
    assert Decimal("0.09") < cagr < Decimal("0.11")


def test_win_rate_zero_day_exclusion():
    daily_returns: list[Decimal | None] = [
        None,
        Decimal("0.02"),
        Decimal("-0.01"),
        Decimal("0.00"),  # Zero day: must be excluded from denominator
        Decimal("0.03"),
    ]
    pos, neg, zero, win_rate = calculate_win_rate_counts(daily_returns)
    assert pos == 2
    assert neg == 1
    assert zero == 1
    # Denominator is 2 + 1 = 3 (zero excluded). Win rate = 2 / 3 ≈ 0.6667
    assert win_rate == Decimal("0.6667")


def test_win_rate_all_zero_days():
    daily_returns: list[Decimal | None] = [None, Decimal("0.00"), Decimal("0.00")]
    pos, neg, zero, win_rate = calculate_win_rate_counts(daily_returns)
    assert pos == 0
    assert neg == 0
    assert zero == 2
    assert win_rate is None


def test_compute_return_metrics():
    dates = [
        date(2023, 1, 1),
        date(2023, 1, 2),
        date(2023, 1, 3),
        date(2024, 1, 2),  # 366 calendar days
    ]
    prices = [Decimal("100.0"), Decimal("102.0"), Decimal("101.0"), Decimal("120.0")]

    metrics = compute_return_metrics(prices, dates)
    assert metrics.adjusted_price_return == Decimal("0.200000")
    assert metrics.cagr is not None
    assert metrics.positive_days == 2
    assert metrics.negative_days == 1
    assert metrics.zero_days == 0
    assert metrics.win_rate == Decimal("0.6667")
