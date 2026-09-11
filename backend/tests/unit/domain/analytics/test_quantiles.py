"""
tests/unit/domain/analytics/test_quantiles.py
============================================
Unit tests for quantile distribution and empirical linear rank interpolation.
"""

from decimal import Decimal

import pytest

from aurelius.domain.analytics.quantiles import (
    calculate_percentile,
    calculate_quantile_distribution,
)


def test_percentile_linear_interpolation_d1():
    """
    Validate quantile calculations on Dataset D1:
    x = [-0.04, -0.03, -0.02, -0.01, -0.005, +0.005, +0.01, +0.02, +0.03, +0.04] (N=10)
    Closed-form analytical values:
      p = 0.00 -> -0.040000
      p = 0.25 -> -0.017500
      p = 0.50 -> 0.000000
      p = 0.75 -> +0.017500
      p = 1.00 -> +0.040000
      IQR = Q75 - Q25 = 0.035000
    """
    d1 = [
        Decimal("-0.04"),
        Decimal("-0.03"),
        Decimal("-0.02"),
        Decimal("-0.01"),
        Decimal("-0.005"),
        Decimal("0.005"),
        Decimal("0.01"),
        Decimal("0.02"),
        Decimal("0.03"),
        Decimal("0.04"),
    ]

    p0 = calculate_percentile(d1, 0.0)
    p25 = calculate_percentile(d1, 0.25)
    p50 = calculate_percentile(d1, 0.50)
    p75 = calculate_percentile(d1, 0.75)
    p100 = calculate_percentile(d1, 1.0)

    assert p0 == Decimal("-0.040000")
    assert p25 == Decimal("-0.017500")
    assert p50 == Decimal("0.000000")
    assert p75 == Decimal("0.017500")
    assert p100 == Decimal("0.040000")
    assert (p75 - p25) == Decimal("0.035000")


def test_quantile_distribution_monotonicity():
    data = [Decimal(str(x)) for x in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]]
    qd = calculate_quantile_distribution(data)

    assert (
        qd.p1
        <= qd.p5
        <= qd.p10
        <= qd.p25
        <= qd.p50
        <= qd.p75
        <= qd.p90
        <= qd.p95
        <= qd.p99
    )
    assert qd.p50 == Decimal("55.000000")  # (50 + 60) / 2


def test_quantile_single_element_and_empty():
    single = [Decimal("42.5")]
    qd = calculate_quantile_distribution(single)
    assert qd.p1 == qd.p50 == qd.p99 == Decimal("42.500000")

    with pytest.raises(ValueError, match="empty sequence"):
        calculate_quantile_distribution([])
