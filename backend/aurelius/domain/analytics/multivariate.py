"""
aurelius.domain.analytics.multivariate
======================================
Pure domain mathematical algorithms for bivariate and multivariate statistics:
sample/population covariance, Pearson linear correlation, market beta, tracking error,
and multi-asset correlation matrices.

Standards:
  - Requires matched observation pairs (K >= 2).
  - Zero-Variance Boundary: If variance of either series is zero, correlation is mathematically
    undefined; emits None and marks is_degenerate = True.
  - Pearson correlation bounded strictly in [-1.0000, 1.0000].
"""

import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from aurelius.domain.analytics.statistics import (
    calculate_mean,
    calculate_sample_std_dev,
    calculate_sample_variance,
)
from aurelius.domain.entities.quantitative import PairwiseCorrelation

TRADING_DAYS_PER_YEAR = 252
SQRT_252 = math.sqrt(TRADING_DAYS_PER_YEAR)


def calculate_sample_covariance(x: list[Decimal], y: list[Decimal]) -> Decimal | None:
    """
    Sample covariance between x and y with K - 1 denominator.
    Returns None if K < 2 or len(x) != len(y).
    """
    k = len(x)
    if k < 2 or len(y) != k:
        return None

    mean_x = calculate_mean(x)
    mean_y = calculate_mean(y)

    cov_sum = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y, strict=True))
    cov = cov_sum / Decimal(k - 1)
    return cov.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def calculate_population_covariance(
    x: list[Decimal], y: list[Decimal]
) -> Decimal | None:
    """
    Population covariance between x and y with K denominator.
    Returns None if K == 0 or len(x) != len(y).
    """
    k = len(x)
    if k == 0 or len(y) != k:
        return None

    mean_x = calculate_mean(x)
    mean_y = calculate_mean(y)

    cov_sum = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y, strict=True))
    cov = cov_sum / Decimal(k)
    return cov.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def calculate_pearson_correlation(x: list[Decimal], y: list[Decimal]) -> Decimal | None:
    """
    Pearson linear correlation coefficient rho in [-1.0000, 1.0000].
    Returns None if K < 2, or if sample standard deviation of x or y is zero.
    """
    k = len(x)
    if k < 2 or len(y) != k:
        return None

    sx = calculate_sample_std_dev(x)
    sy = calculate_sample_std_dev(y)

    if sx is None or sy is None or sx == Decimal("0.0") or sy == Decimal("0.0"):
        return None

    s_cov = calculate_sample_covariance(x, y)
    if s_cov is None:
        return None

    corr_float = float(s_cov) / (float(sx) * float(sy))
    # Bound to [-1.0, 1.0] to absorb any floating-point edge drift
    corr_clamped = max(-1.0, min(1.0, corr_float))

    return Decimal(str(round(corr_clamped, 6))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def calculate_market_beta(
    asset_returns: list[Decimal], benchmark_returns: list[Decimal]
) -> Decimal | None:
    """
    Market Beta: Cov(R_i, R_m) / Var(R_m).
    Returns None if K < 2 or benchmark variance is zero.
    """
    if len(asset_returns) < 2 or len(benchmark_returns) != len(asset_returns):
        return None

    bmk_var = calculate_sample_variance(benchmark_returns)
    if bmk_var is None or bmk_var == Decimal("0.0"):
        return None

    cov = calculate_sample_covariance(asset_returns, benchmark_returns)
    if cov is None:
        return None

    beta = cov / bmk_var
    return beta.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_tracking_error(
    asset_returns: list[Decimal], benchmark_returns: list[Decimal]
) -> Decimal | None:
    """
    Annualized Tracking Error: sample std dev of active returns (R_i - R_m) * sqrt(252).
    Returns None if K < 2.
    """
    if len(asset_returns) < 2 or len(benchmark_returns) != len(asset_returns):
        return None

    active_diffs = [
        r_a - r_b for r_a, r_b in zip(asset_returns, benchmark_returns, strict=True)
    ]
    daily_te_std = calculate_sample_std_dev(active_diffs)
    if daily_te_std is None:
        return None

    ann_te_float = float(daily_te_std) * SQRT_252
    return Decimal(str(round(ann_te_float, 8))).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )


def compute_pairwise_statistics(
    ticker_a: str,
    ticker_b: str,
    dates: list[date],
    x: list[Decimal],
    y: list[Decimal],
) -> PairwiseCorrelation:
    """
    Compute PairwiseCorrelation domain entity over matched date pairs.
    """
    k = len(dates)
    if k == 0 or len(x) != k or len(y) != k:
        return PairwiseCorrelation(
            ticker_a=ticker_a,
            ticker_b=ticker_b,
            matched_observations=0,
            start_date=date.today(),
            end_date=date.today(),
            sample_covariance=None,
            population_covariance=None,
            correlation=None,
            beta_a_to_b=None,
            tracking_error=None,
            is_degenerate=True,
        )

    s_cov = calculate_sample_covariance(x, y)
    p_cov = calculate_population_covariance(x, y)
    corr = calculate_pearson_correlation(x, y)
    beta = calculate_market_beta(x, y)
    te = calculate_tracking_error(x, y)

    is_degen = corr is None or k < 2

    return PairwiseCorrelation(
        ticker_a=ticker_a,
        ticker_b=ticker_b,
        matched_observations=k,
        start_date=dates[0],
        end_date=dates[-1],
        sample_covariance=s_cov,
        population_covariance=p_cov,
        correlation=corr,
        beta_a_to_b=beta,
        tracking_error=te,
        is_degenerate=is_degen,
    )


def compute_correlation_matrix(
    tickers: list[str], returns_map: dict[str, list[Decimal]]
) -> tuple[list[list[Decimal | None]], list[list[Decimal | None]]]:
    """
    Build symmetric pairwise Pearson correlation and sample covariance matrices.
    """
    n = len(tickers)
    corr_matrix: list[list[Decimal | None]] = [[None] * n for _ in range(n)]
    cov_matrix: list[list[Decimal | None]] = [[None] * n for _ in range(n)]

    for i in range(n):
        for j in range(i, n):
            t_i = tickers[i]
            t_j = tickers[j]
            x = returns_map[t_i]
            y = returns_map[t_j]

            if i == j:
                # Diagonal
                s_var = calculate_sample_variance(x)
                cov_val = (
                    s_var.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
                    if s_var is not None
                    else None
                )
                corr_val = (
                    Decimal("1.0000")
                    if s_var is not None and s_var > Decimal("0.0")
                    else None
                )
            else:
                cov_val = calculate_sample_covariance(x, y)
                corr_val = calculate_pearson_correlation(x, y)

            cov_matrix[i][j] = cov_val
            cov_matrix[j][i] = cov_val
            corr_matrix[i][j] = corr_val
            corr_matrix[j][i] = corr_val

    return corr_matrix, cov_matrix
