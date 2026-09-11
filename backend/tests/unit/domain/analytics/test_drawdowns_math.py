"""
Unit tests for drawdown analytics:
- Running peak calculation
- Negative drawdown values (<= 0.0)
- Deterministic MDD tie-breaking (earliest trough date, earliest preceding peak)
- Recovery detection
"""

from datetime import date
from decimal import Decimal

from aurelius.domain.analytics.drawdowns import (
    calculate_drawdown_series,
    compute_drawdown_metrics,
)


def test_drawdown_series_all_non_positive():
    prices = [
        Decimal("100.0"),
        Decimal("110.0"),
        Decimal("105.0"),
        Decimal("115.0"),
        Decimal("92.0"),
    ]
    dds = calculate_drawdown_series(prices)
    for dd in dds:
        assert dd <= Decimal("0.0")
    # Peak at 110, drop to 105: (105-110)/110 = -5/110 ≈ -0.045455
    assert dds[2] == Decimal("-0.045455")
    # Peak at 115, drop to 92: (92-115)/115 = -23/115 = -0.20
    assert dds[4] == Decimal("-0.200000")


def test_deterministic_mdd_tie_breaking():
    # Two identical troughs of -20%
    dates = [
        date(2023, 1, 1),
        date(2023, 1, 2),  # Peak 1: 100
        date(2023, 1, 3),  # Trough 1: 80 (-20%)
        date(2023, 1, 4),  # Rebound to 100
        date(2023, 1, 5),  # Trough 2: 80 (-20%)
    ]
    prices = [
        Decimal("100.0"),
        Decimal("100.0"),
        Decimal("80.0"),
        Decimal("100.0"),
        Decimal("80.0"),
    ]
    metrics = compute_drawdown_metrics(prices, dates)
    assert metrics.max_drawdown == Decimal("-0.200000")
    # Must choose earliest trough: date(2023, 1, 3)
    assert metrics.max_drawdown_trough_date == date(2023, 1, 3)
    # Earliest peak: date(2023, 1, 1)
    assert metrics.max_drawdown_peak_date == date(2023, 1, 1)


def test_recovery_detection():
    # Peak at day 1 (100), Trough at day 2 (80), Recovery at day 4 (100)
    dates = [
        date(2023, 1, 1),
        date(2023, 1, 2),
        date(2023, 1, 3),
        date(2023, 1, 4),
        date(2023, 1, 5),
    ]
    prices = [
        Decimal("100.0"),
        Decimal("80.0"),
        Decimal("90.0"),
        Decimal("102.0"),  # Reclaims peak
        Decimal("98.0"),
    ]
    metrics = compute_drawdown_metrics(prices, dates)
    assert metrics.is_recovered is True
    assert metrics.recovery_date == date(2023, 1, 4)


def test_unrecovered_drawdown():
    dates = [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)]
    prices = [Decimal("100.0"), Decimal("75.0"), Decimal("80.0")]
    metrics = compute_drawdown_metrics(prices, dates)
    assert metrics.is_recovered is False
    assert metrics.recovery_date is None
    assert metrics.current_drawdown == Decimal("-0.200000")
