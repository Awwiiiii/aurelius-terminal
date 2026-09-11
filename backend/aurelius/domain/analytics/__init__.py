"""
aurelius.domain.analytics
=========================
Pure financial analytics mathematical algorithms for AURELIUS Milestone 4.

Modules:
  - returns: simple daily returns, cumulative returns, calendar-time CAGR, win rate
  - volatility: sample standard deviation (Bessel N-1), annualization, rolling volatility
  - drawdowns: running peak, drawdown series, deterministic MDD tie-breaking, recovery
  - indicators: zero-indexed warm-up SMA, EMA, period extremes
  - benchmark: inner date alignment, common base date rebasing, excess return, Pearson correlation
"""

from aurelius.domain.analytics.benchmark import align_and_compare_benchmark
from aurelius.domain.analytics.drawdowns import (
    calculate_drawdown_series,
    compute_drawdown_metrics,
)
from aurelius.domain.analytics.indicators import (
    calculate_ema,
    calculate_sma,
    compute_historical_extremes,
)
from aurelius.domain.analytics.returns import (
    calculate_calendar_cagr,
    calculate_cumulative_returns,
    calculate_simple_daily_returns,
    calculate_win_rate_counts,
    compute_return_metrics,
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
    "calculate_rolling_volatility",
    "calculate_sample_volatility",
    "calculate_simple_daily_returns",
    "calculate_sma",
    "calculate_win_rate_counts",
    "compute_drawdown_metrics",
    "compute_historical_extremes",
    "compute_return_metrics",
    "compute_volatility_metrics",
]
