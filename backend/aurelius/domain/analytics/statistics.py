"""
aurelius.domain.analytics.statistics
====================================
Pure domain mathematical algorithms for univariate descriptive statistics and
sample/population moments.

Financial Standards & Estimator Policy:
  1. Sample estimators with Bessel's correction (N - 1 denominator) are primary.
  2. Population estimators (N denominator) are maintained for reference.
  3. Small-sample contracts:
     - N = 0: Raises ValueError.
     - N = 1: Mean, median, min, max, range, and MAD are defined.
              Sample variance, sample std dev, skewness, and excess kurtosis are None.
     - N = 2: Sample variance and sample std dev are defined.
              Skewness (N < 3) and excess kurtosis (N < 4) are None.
     - N = 3: Skewness is defined. Excess kurtosis (N < 4) is None.
     - N >= 4: All statistics are defined.
  4. Constant / Zero-Variance Series:
     - If all observations are identical (s = 0), skewness and excess kurtosis are 0.0.
"""

import math
from decimal import ROUND_HALF_UP, Decimal

from aurelius.domain.analytics.quantiles import calculate_percentile
from aurelius.domain.entities.quantitative import DescriptiveStatistics


def calculate_mean(data: list[Decimal]) -> Decimal:
    """Arithmetic mean of observations: sum(x) / N."""
    if not data:
        raise ValueError("Cannot calculate mean of empty sequence.")
    return sum(data) / Decimal(len(data))


def calculate_median(data: list[Decimal]) -> Decimal:
    """Median observation."""
    if not data:
        raise ValueError("Cannot calculate median of empty sequence.")
    sorted_d = sorted(data)
    n = len(sorted_d)
    mid = n // 2
    if n % 2 == 1:
        return sorted_d[mid]
    return (sorted_d[mid - 1] + sorted_d[mid]) / Decimal("2")


def calculate_sample_variance(data: list[Decimal]) -> Decimal | None:
    """
    Sample variance with Bessel's correction (N - 1 denominator).
    Returns None if N < 2.
    """
    n = len(data)
    if n < 2:
        return None
    mean_val = calculate_mean(data)
    sum_sq = sum((x - mean_val) ** 2 for x in data)
    return sum_sq / Decimal(n - 1)


def calculate_population_variance(data: list[Decimal]) -> Decimal:
    """
    Population variance with N denominator.
    Returns 0.0 if N == 1.
    """
    n = len(data)
    if n == 0:
        raise ValueError("Cannot calculate population variance of empty sequence.")
    if n == 1:
        return Decimal("0.0")
    mean_val = calculate_mean(data)
    sum_sq = sum((x - mean_val) ** 2 for x in data)
    return sum_sq / Decimal(n)


def calculate_sample_std_dev(data: list[Decimal]) -> Decimal | None:
    """
    Sample standard deviation: sqrt(sample_variance).
    Returns None if N < 2.
    """
    s_var = calculate_sample_variance(data)
    if s_var is None:
        return None
    val_float = math.sqrt(float(s_var))
    return Decimal(str(round(val_float, 10))).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )


def calculate_population_std_dev(data: list[Decimal]) -> Decimal:
    """
    Population standard deviation: sqrt(population_variance).
    """
    p_var = calculate_population_variance(data)
    val_float = math.sqrt(float(p_var))
    return Decimal(str(round(val_float, 10))).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )


def calculate_mad(data: list[Decimal]) -> Decimal:
    """Mean Absolute Deviation from arithmetic mean: sum(|x - mean|) / N."""
    if not data:
        raise ValueError("Cannot calculate MAD of empty sequence.")
    mean_val = calculate_mean(data)
    return sum(abs(x - mean_val) for x in data) / Decimal(len(data))


def calculate_iqr(data: list[Decimal]) -> Decimal:
    """Interquartile Range: Q75 - Q25 using linear rank interpolation."""
    if not data:
        raise ValueError("Cannot calculate IQR of empty sequence.")
    q25 = calculate_percentile(data, 0.25)
    q75 = calculate_percentile(data, 0.75)
    return (q75 - q25).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def calculate_skewness(data: list[Decimal]) -> Decimal | None:
    """
    Fisher-Pearson sample skewness (G1).
    Returns None if N < 3.
    Returns 0.0 if sample variance is zero.
    """
    n = len(data)
    if n < 3:
        return None

    mean_val = calculate_mean(data)
    m2 = sum((x - mean_val) ** 2 for x in data) / Decimal(n)
    if m2 == Decimal("0.0"):
        return Decimal("0.0000")

    m3 = sum((x - mean_val) ** 3 for x in data) / Decimal(n)

    # Convert to float for fractional power calculation
    m2_float = float(m2)
    m3_float = float(m3)
    g1 = m3_float / (m2_float**1.5)

    # Unbiased adjustment factor: sqrt(n * (n - 1)) / (n - 2)
    adj = math.sqrt(float(n * (n - 1))) / float(n - 2)
    g1_unbiased = adj * g1

    return Decimal(str(round(g1_unbiased, 6))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def calculate_excess_kurtosis(data: list[Decimal]) -> Decimal | None:
    """
    Unbiased sample excess kurtosis (G2) relative to normal distribution (0.0 for Gaussian).
    Returns None if N < 4.
    Returns 0.0 if sample variance is zero.
    """
    n = len(data)
    if n < 4:
        return None

    mean_val = calculate_mean(data)
    m2 = sum((x - mean_val) ** 2 for x in data) / Decimal(n)
    if m2 == Decimal("0.0"):
        return Decimal("0.0000")

    m4 = sum((x - mean_val) ** 4 for x in data) / Decimal(n)

    m2_float = float(m2)
    m4_float = float(m4)
    g2 = (m4_float / (m2_float**2)) - 3.0

    # Unbiased adjustment: (n - 1) / ((n - 2) * (n - 3)) * ((n + 1) * g2 + 6)
    adj_factor = float(n - 1) / float((n - 2) * (n - 3))
    g2_unbiased = adj_factor * (float(n + 1) * g2 + 6.0)

    return Decimal(str(round(g2_unbiased, 6))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def compute_descriptive_statistics(data: list[Decimal]) -> DescriptiveStatistics:
    """
    Assemble complete descriptive statistical profile for an observed series.
    """
    if not data:
        raise ValueError("Cannot compute descriptive statistics of empty sequence.")

    n = len(data)
    mean_val = calculate_mean(data).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    median_val = calculate_median(data).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )

    raw_s_var = calculate_sample_variance(data)
    sample_var = (
        raw_s_var.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        if raw_s_var is not None
        else None
    )

    pop_var = calculate_population_variance(data).quantize(
        Decimal("0.00000001"), rounding=ROUND_HALF_UP
    )

    sample_std = calculate_sample_std_dev(data)
    pop_std = calculate_population_std_dev(data)

    min_val = min(data).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    max_val = max(data).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    range_val = (max_val - min_val).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )

    mad_val = calculate_mad(data).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    iqr_val = calculate_iqr(data)

    skew_val = calculate_skewness(data)
    kurt_val = calculate_excess_kurtosis(data)

    return DescriptiveStatistics(
        sample_size=n,
        mean=mean_val,
        median=median_val,
        sample_variance=sample_var,
        population_variance=pop_var,
        sample_std_dev=sample_std,
        population_std_dev=pop_std,
        min_value=min_val,
        max_value=max_val,
        range_value=range_val,
        mad=mad_val,
        iqr=iqr_val,
        skewness=skew_val,
        excess_kurtosis=kurt_val,
    )
