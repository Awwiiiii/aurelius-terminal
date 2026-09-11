"""
tests/unit/domain/analytics/test_alignment.py
============================================
Unit tests for multi-series inner date alignment and zero forward-filling policy.
"""

from datetime import date
from decimal import Decimal

from aurelius.domain.analytics.alignment import inner_align_date_series


def test_inner_align_date_series_intersection():
    d1 = date(2023, 1, 3)
    d2 = date(2023, 1, 4)
    d3 = date(2023, 1, 5)
    d4 = date(2023, 1, 6)

    # Series A has d1, d2, d3
    # Series B has d2, d3, d4
    # Common intersection must be [d2, d3] in chronological order
    series_map = {
        "AAPL": {d1: Decimal("150.0"), d2: Decimal("151.0"), d3: Decimal("152.0")},
        "MSFT": {d2: Decimal("240.0"), d3: Decimal("242.0"), d4: Decimal("245.0")},
    }

    common_dates, aligned = inner_align_date_series(series_map)

    assert common_dates == [d2, d3]
    assert aligned["AAPL"] == [Decimal("151.0"), Decimal("152.0")]
    assert aligned["MSFT"] == [Decimal("240.0"), Decimal("242.0")]


def test_inner_align_date_series_disjoint():
    d1 = date(2023, 1, 3)
    d2 = date(2023, 1, 4)

    series_map = {
        "AAPL": {d1: Decimal("150.0")},
        "MSFT": {d2: Decimal("240.0")},
    }

    common_dates, aligned = inner_align_date_series(series_map)
    assert common_dates == []
    assert aligned["AAPL"] == []
    assert aligned["MSFT"] == []
