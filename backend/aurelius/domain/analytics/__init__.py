"""
aurelius.domain.analytics
=========================
Pure financial and quantitative analytics mathematical algorithms for AURELIUS.

Milestone 4 Modules:
  - returns: simple/log daily returns, cumulative returns, calendar-time CAGR, win rate
  - volatility: sample standard deviation (Bessel N-1), annualization, rolling volatility
  - drawdowns: running peak, drawdown series, deterministic MDD tie-breaking, recovery
  - indicators: zero-indexed warm-up SMA, EMA, period extremes
  - benchmark: inner date alignment, common base date rebasing, excess return, Pearson correlation

Milestone 5 Modules:
  - statistics: univariate moments (mean, median, sample/pop variance & std dev, MAD, IQR, skewness, excess kurtosis)
  - quantiles: linear rank interpolation quantile distribution
  - distribution: Freedman-Diaconis frequency histogram binning and directional breakdowns
  - multivariate: pairwise sample/pop covariance, Pearson correlation, beta, tracking error, correlation matrix
  - rolling: sliding window statistics over W returns
  - alignment: multi-series inner date synchronization without forward-filling
"""

from aurelius.domain.analytics.alignment import inner_align_date_series
from aurelius.domain.analytics.benchmark import align_and_compare_benchmark
from aurelius.domain.analytics.distribution import (
    calculate_freedman_diaconis_histogram,
    compute_distribution_breakdown,
)
from aurelius.domain.analytics.drawdowns import (
    calculate_drawdown_series,
    compute_drawdown_metrics,
)
from aurelius.domain.analytics.indicators import (
    calculate_ema,
    calculate_sma,
    compute_historical_extremes,
)
from aurelius.domain.analytics.multivariate import (
    calculate_market_beta,
    calculate_pearson_correlation,
    calculate_population_covariance,
    calculate_sample_covariance,
    calculate_tracking_error,
    compute_correlation_matrix,
    compute_pairwise_statistics,
)
from aurelius.domain.analytics.quantiles import (
    calculate_percentile,
    calculate_quantile_distribution,
)
from aurelius.domain.analytics.returns import (
    calculate_calendar_cagr,
    calculate_cumulative_returns,
    calculate_log_daily_returns,
    calculate_simple_daily_returns,
    calculate_win_rate_counts,
    compute_return_metrics,
)
from aurelius.domain.analytics.rolling import (
    calculate_rolling_correlation,
    calculate_rolling_covariance,
    calculate_rolling_mean,
    calculate_rolling_std,
)
from aurelius.domain.analytics.statistics import (
    calculate_excess_kurtosis,
    calculate_iqr,
    calculate_mad,
    calculate_mean,
    calculate_median,
    calculate_population_std_dev,
    calculate_population_variance,
    calculate_sample_std_dev,
    calculate_sample_variance,
    calculate_skewness,
    compute_descriptive_statistics,
)
from aurelius.domain.analytics.volatility import (
    calculate_rolling_volatility,
    calculate_sample_volatility,
    compute_volatility_metrics,
)

__all__ = [
    "align_and_compare_benchmark",
    "calculate_calendar_cagr",
    "calculate_cumulative_returns",
    "calculate_drawdown_series",
    "calculate_ema",
    "calculate_excess_kurtosis",
    "calculate_freedman_diaconis_histogram",
    "calculate_iqr",
    "calculate_log_daily_returns",
    "calculate_mad",
    "calculate_market_beta",
    "calculate_mean",
    "calculate_median",
    "calculate_pearson_correlation",
    "calculate_percentile",
    "calculate_population_covariance",
    "calculate_population_std_dev",
    "calculate_population_variance",
    "calculate_quantile_distribution",
    "calculate_rolling_correlation",
    "calculate_rolling_covariance",
    "calculate_rolling_mean",
    "calculate_rolling_std",
    "calculate_rolling_volatility",
    "calculate_sample_covariance",
    "calculate_sample_std_dev",
    "calculate_sample_variance",
    "calculate_sample_volatility",
    "calculate_simple_daily_returns",
    "calculate_skewness",
    "calculate_sma",
    "calculate_tracking_error",
    "calculate_win_rate_counts",
    "compute_correlation_matrix",
    "compute_descriptive_statistics",
    "compute_distribution_breakdown",
    "compute_drawdown_metrics",
    "compute_historical_extremes",
    "compute_pairwise_statistics",
    "compute_return_metrics",
    "compute_volatility_metrics",
    "inner_align_date_series",
]
