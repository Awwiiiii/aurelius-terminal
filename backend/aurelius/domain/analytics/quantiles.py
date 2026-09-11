"""
aurelius.domain.analytics.quantiles
===================================
Pure domain mathematical algorithms for empirical quantile estimation.

Methodology:
  Standard linear interpolation between adjacent ranks (Method 7 / numpy standard):
    rank = p * (n - 1)
    i = floor(rank), f = rank - i
    Q(p) = x_{(i)} + f * (x_{(i+1)} - x_{(i)})
  where x_{(0)} <= x_{(1)} <= ... <= x_{(n-1)} is the sorted sequence.
"""

import math
from decimal import ROUND_HALF_UP, Decimal

from aurelius.domain.entities.quantitative import QuantileDistribution


def calculate_percentile(data: list[Decimal], p: float) -> Decimal:
    """
    Compute empirical percentile p in [0.0, 1.0] using linear rank interpolation.
    """
    if not data:
        raise ValueError("Cannot calculate percentile of empty sequence.")
    if not (0.0 <= p <= 1.0):
        raise ValueError(f"Percentile p must be in [0.0, 1.0], got {p}.")

    n = len(data)
    if n == 1:
        return data[0].quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    sorted_data = sorted(data)
    rank = p * (n - 1)
    i = math.floor(rank)
    f = Decimal(str(rank - i))

    if i >= n - 1:
        return sorted_data[-1].quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    lower = sorted_data[i]
    upper = sorted_data[i + 1]
    val = lower + f * (upper - lower)
    return val.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def calculate_quantile_distribution(data: list[Decimal]) -> QuantileDistribution:
    """
    Compute standard institutional quantile ladder (p1, p5, p10, p25, p50, p75, p90, p95, p99).
    """
    if not data:
        raise ValueError("Cannot calculate quantile distribution of empty sequence.")

    return QuantileDistribution(
        p1=calculate_percentile(data, 0.01),
        p5=calculate_percentile(data, 0.05),
        p10=calculate_percentile(data, 0.10),
        p25=calculate_percentile(data, 0.25),
        p50=calculate_percentile(data, 0.50),
        p75=calculate_percentile(data, 0.75),
        p90=calculate_percentile(data, 0.90),
        p95=calculate_percentile(data, 0.95),
        p99=calculate_percentile(data, 0.99),
    )
