"""
aurelius.domain.analytics.volatility
====================================
Pure domain mathematical functions for historical realized volatility.

Financial Standards:
  - Observation Counts: N prices produce N - 1 returns.
    Two price observations produce 1 return, which is insufficient for
    sample standard deviation (Bessel N-1 correction).
    A minimum of 3 price observations (2 returns) is strictly required for
    sample volatility.
  - Sample Standard Deviation:
      s = sqrt( (1 / (M - 1)) * sum((R_i - mean_R)^2) ), where M >= 2 returns.
  - Annualization:
      vol_annualized = s * sqrt(252).
  - Rolling Volatility:
      A k-day rolling window refers to k daily returns.
      Emits None until k returns are available (bar index k).
"""

import math
from decimal import ROUND_HALF_UP, Decimal

from aurelius.domain.analytics.returns import calculate_simple_daily_returns
from aurelius.domain.entities.historical import VolatilityMetrics

TRADING_DAYS_PER_YEAR = 252
SQRT_252 = math.sqrt(TRADING_DAYS_PER_YEAR)


def calculate_sample_volatility(
    returns: list[Decimal],
) -> tuple[Decimal, Decimal]:
    """
    Calculate daily sample standard deviation and annualized volatility from a list of returns.

    Requires at least 2 returns (derived from at least 3 price observations).
    Returns (daily_volatility, annualized_volatility).
    Raises ValueError if fewer than 2 returns are provided.
    """
    if len(returns) < 2:
        raise ValueError(
            f"At least 2 return observations required for sample volatility (got {len(returns)}). "
            "Minimum 3 price observations required."
        )

    m = len(returns)
    mean_r = sum(returns) / Decimal(m)

    variance = sum((r - mean_r) ** 2 for r in returns) / Decimal(m - 1)

    daily_vol_float = math.sqrt(float(variance))
    ann_vol_float = daily_vol_float * SQRT_252

    daily_vol = Decimal(str(round(daily_vol_float, 8))).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    ann_vol = Decimal(str(round(ann_vol_float, 8))).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )

    return daily_vol, ann_vol


def calculate_rolling_volatility(
    prices: list[Decimal], window_returns: int = 20
) -> list[Decimal | None]:
    """
    Calculate rolling annualized volatility over a sliding window of k daily returns.

    Policy:
      - Window size refers to `window_returns` returns (e.g. 20 returns).
      - For bar indices 0..window_returns-1: emits None (insufficient returns).
      - For bar index window_returns: first valid rolling volatility on returns 1..window_returns.
      - For bar index i >= window_returns: rolling volatility on returns i-window_returns+1..i.
    """
    n = len(prices)
    if n == 0:
        return []

    # Get daily returns (length n, returns[0] is None)
    daily_returns = calculate_simple_daily_returns(prices)

    # Extract only valid returns as (bar_index, return_value)
    # daily_returns[i] corresponds to bar i for i in 1..n-1
    res: list[Decimal | None] = [None] * n

    if window_returns < 2:
        raise ValueError("Rolling window must be at least 2 returns.")

    for i in range(window_returns, n):
        # Slice of returns for window: bars (i - window_returns + 1) to i
        window = [
            daily_returns[j]
            for j in range(i - window_returns + 1, i + 1)
            if daily_returns[j] is not None
        ]
        if len(window) == window_returns:
            _, ann_vol = calculate_sample_volatility(window)
            res[i] = ann_vol
        else:
            res[i] = None

    return res


def compute_volatility_metrics(prices: list[Decimal]) -> VolatilityMetrics:
    """
    Compute VolatilityMetrics domain entity on adjusted close series.
    Requires at least 3 price observations (2 returns).
    If fewer than 3 price observations, returns 0.0 metrics.
    """
    if len(prices) < 3:
        return VolatilityMetrics(
            daily_volatility=Decimal("0.0"),
            annualized_volatility=Decimal("0.0"),
            trading_days_assumed=TRADING_DAYS_PER_YEAR,
        )

    daily_returns = calculate_simple_daily_returns(prices)
    valid_returns = [r for r in daily_returns if r is not None]

    daily_vol, ann_vol = calculate_sample_volatility(valid_returns)

    return VolatilityMetrics(
        daily_volatility=daily_vol,
        annualized_volatility=ann_vol,
        trading_days_assumed=TRADING_DAYS_PER_YEAR,
    )
