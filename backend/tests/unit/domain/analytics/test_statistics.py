"""
tests/unit/domain/analytics/test_statistics.py
=============================================
Unit tests for univariate descriptive statistics, sample/population estimators,
and higher-order standardized moments against deterministic reference datasets.
"""

from decimal import Decimal

import pytest

from aurelius.domain.analytics.statistics import (
    compute_descriptive_statistics,
)


def test_dataset_d1_symmetric_reference():
    """
    Validate Dataset D1: 10-element symmetric vector:
    x = [-0.04, -0.03, -0.02, -0.01, -0.005, +0.005, +0.01, +0.02, +0.03, +0.04]
    Closed-form analytical expectations:
      - Mean = 0.000000
      - Median = 0.000000
      - Population Variance = 0.000605
      - Sample Variance = 0.00067222
      - Sample Std Dev = 0.025927
      - Skewness = 0.0000
      - Excess Kurtosis = -0.9191
      - Q25 = -0.0175, Q75 = +0.0175, IQR = 0.0350
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

    stats = compute_descriptive_statistics(d1)

    assert stats.sample_size == 10
    assert stats.mean == Decimal("0.000000")
    assert stats.median == Decimal("0.000000")
    assert stats.population_variance == Decimal("0.00060500")
    assert stats.sample_variance == Decimal("0.00067222")
    assert stats.sample_std_dev == Decimal("0.025927")
    assert stats.population_std_dev == Decimal("0.024597")
    assert stats.skewness == Decimal("0.0000")
    assert stats.excess_kurtosis == Decimal("-0.9191")
    assert stats.iqr == Decimal("0.035000")
    assert stats.min_value == Decimal("-0.040000")
    assert stats.max_value == Decimal("0.040000")
    assert stats.range_value == Decimal("0.080000")


def test_dataset_d2_asymmetric_fat_tailed_reference():
    """
    Validate Dataset D2: 12-element asymmetric vector:
    10 observations of +0.01 and 2 observations of -0.05
    Closed-form analytical expectations:
      - Mean = 0.000000
      - Median = 0.010000
      - Population Variance = 0.000500
      - Sample Variance = 0.00054545
      - Sample Std Dev = 0.023355
      - Skewness = -2.0552
      - Excess Kurtosis = 2.6400 (exact)
    """
    d2 = [Decimal("0.01")] * 10 + [Decimal("-0.05")] * 2

    stats = compute_descriptive_statistics(d2)

    assert stats.sample_size == 12
    assert stats.mean == Decimal("0.000000")
    assert stats.median == Decimal("0.010000")
    assert stats.population_variance == Decimal("0.00050000")
    assert stats.sample_variance == Decimal("0.00054545")
    assert stats.sample_std_dev == Decimal("0.023355")
    assert stats.skewness == Decimal("-2.0552")
    assert stats.excess_kurtosis == Decimal("2.6400")


def test_dataset_d4_small_sample_and_boundary_contracts():
    """
    Validate Dataset D4: Degenerate and boundary conditions.
    """
    # N = 0 -> raises ValueError
    with pytest.raises(ValueError, match="empty sequence"):
        compute_descriptive_statistics([])

    # N = 1 -> sample statistics, skewness, and kurtosis must be None
    n1 = [Decimal("0.05")]
    s1 = compute_descriptive_statistics(n1)
    assert s1.sample_size == 1
    assert s1.mean == Decimal("0.050000")
    assert s1.median == Decimal("0.050000")
    assert s1.sample_variance is None
    assert s1.sample_std_dev is None
    assert s1.skewness is None
    assert s1.excess_kurtosis is None
    assert s1.population_variance == Decimal("0.00000000")
    assert s1.population_std_dev == Decimal("0.000000")

    # N = 2 -> sample variance & std defined, skewness & kurtosis are None
    n2 = [Decimal("0.02"), Decimal("-0.02")]
    s2 = compute_descriptive_statistics(n2)
    assert s2.sample_size == 2
    assert s2.sample_variance is not None
    assert s2.sample_std_dev is not None
    assert s2.skewness is None
    assert s2.excess_kurtosis is None

    # N = 3 -> skewness defined, kurtosis is None
    n3 = [Decimal("0.01"), Decimal("0.02"), Decimal("0.04")]
    s3 = compute_descriptive_statistics(n3)
    assert s3.sample_size == 3
    assert s3.skewness is not None
    assert s3.excess_kurtosis is None

    # Constant series (all identical, s = 0)
    const_series = [Decimal("0.03")] * 6
    s_const = compute_descriptive_statistics(const_series)
    assert s_const.sample_variance == Decimal("0.00000000")
    assert s_const.sample_std_dev == Decimal("0.000000")
    assert s_const.skewness == Decimal("0.0000")
    assert s_const.excess_kurtosis == Decimal("0.0000")
    assert s_const.range_value == Decimal("0.000000")
    assert s_const.iqr == Decimal("0.000000")
