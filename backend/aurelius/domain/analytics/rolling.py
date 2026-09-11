"""
aurelius.domain.analytics.rolling
=================================
Sliding window quantitative metrics over W return observations.

Warm-up Semantics:
  - Input: list of M return observations (indexed j = 0, ..., M - 1).
  - Window: W returns (W >= 2).
  - Indices 0 ... W - 2: emit None (insufficient returns).
  - Index W - 1: first valid calculation over returns 0 ... W - 1.
  - Indices j >= W: calculation over returns j - W + 1 ... j.
"""

from decimal import ROUND_HALF_UP, Decimal

from aurelius.domain.analytics.multivariate import (
    calculate_pearson_correlation,
    calculate_sample_covariance,
)
from aurelius.domain.analytics.statistics import (
    calculate_mean,
    calculate_sample_std_dev,
)


def calculate_rolling_mean(series: list[Decimal], window: int) -> list[Decimal | None]:
    """
    Rolling arithmetic mean over a sliding window of W return observations.
    """
    m = len(series)
    if window < 1:
        raise ValueError("Rolling window must be at least 1.")
    if m == 0:
        return []

    res: list[Decimal | None] = [None] * m
    for j in range(window - 1, m):
        w_slice = series[j - window + 1 : j + 1]
        m_val = calculate_mean(w_slice)
        res[j] = m_val.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return res


def calculate_rolling_std(series: list[Decimal], window: int) -> list[Decimal | None]:
    """
    Rolling sample standard deviation over a sliding window of W return observations.
    """
    m = len(series)
    if window < 2:
        raise ValueError("Rolling standard deviation window must be at least 2.")
    if m == 0:
        return []

    res: list[Decimal | None] = [None] * m
    for j in range(window - 1, m):
        w_slice = series[j - window + 1 : j + 1]
        s_val = calculate_sample_std_dev(w_slice)
        res[j] = s_val
    return res


def calculate_rolling_covariance(
    x: list[Decimal], y: list[Decimal], window: int
) -> list[Decimal | None]:
    """
    Rolling sample covariance over a sliding window of W return observation pairs.
    """
    m = len(x)
    if window < 2:
        raise ValueError("Rolling covariance window must be at least 2.")
    if m == 0 or len(y) != m:
        return []

    res: list[Decimal | None] = [None] * m
    for j in range(window - 1, m):
        x_slice = x[j - window + 1 : j + 1]
        y_slice = y[j - window + 1 : j + 1]
        cov_val = calculate_sample_covariance(x_slice, y_slice)
        res[j] = cov_val
    return res


def calculate_rolling_correlation(
    x: list[Decimal], y: list[Decimal], window: int
) -> list[Decimal | None]:
    """
    Rolling Pearson correlation over a sliding window of W return observation pairs.
    """
    m = len(x)
    if window < 2:
        raise ValueError("Rolling correlation window must be at least 2.")
    if m == 0 or len(y) != m:
        return []

    res: list[Decimal | None] = [None] * m
    for j in range(window - 1, m):
        x_slice = x[j - window + 1 : j + 1]
        y_slice = y[j - window + 1 : j + 1]
        corr_val = calculate_pearson_correlation(x_slice, y_slice)
        res[j] = corr_val
    return res
