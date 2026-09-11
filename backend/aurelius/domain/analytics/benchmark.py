"""
aurelius.domain.analytics.benchmark
===================================
Pure domain mathematical functions for benchmark performance alignment,
rebasing, excess return, and Pearson correlation.

Financial Standards:
  - Inner Alignment:
      Security and benchmark series are matched on identical trading session dates.
  - Common Base Date:
      The earliest matched trading session is designated as the common base date (t_0).
      Both security and benchmark cumulative series are rebased to 100.0 at t_0.
  - Synchronized Returns:
      Security return and benchmark return are evaluated strictly across the matched window:
        security_return = (P_sec,end - P_sec,start) / P_sec,start
        benchmark_return = (P_bmk,end - P_bmk,start) / P_bmk,start
        excess_return = security_return - benchmark_return
  - Pearson Correlation (rho):
      Calculated between daily simple returns across matched trading dates:
        rho = Cov(R_sec, R_bmk) / (std(R_sec) * std(R_bmk))
      Requires at least 2 return pairs (3 matched dates). Returns Decimal("0.0") if insufficient
      observations or zero variance.
"""

import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from aurelius.domain.entities.historical import BenchmarkComparison
from aurelius.domain.entities.ohlcv import OHLCVBar


def align_and_compare_benchmark(
    security_bars: list[OHLCVBar],
    benchmark_bars: list[OHLCVBar],
    benchmark_id: str = "SP500",
    benchmark_name: str = "S&P 500 Index",
) -> tuple[BenchmarkComparison | None, dict[date, Decimal]]:
    """
    Perform inner date alignment and calculate comparative benchmark analytics.

    Returns:
      (BenchmarkComparison, dict of {date: benchmark_cumulative_return})
    If fewer than 2 matched trading dates exist, returns (None, {}).
    """
    # Build date-keyed map for benchmark bars (use adj_close if available, fallback to close)
    bmk_by_date = {}
    for bar in benchmark_bars:
        d = bar.timestamp.date() if hasattr(bar.timestamp, "date") else bar.timestamp
        bmk_by_date[d] = bar.adj_close if bar.adj_close is not None else bar.close

    sec_by_date = {}
    for bar in security_bars:
        d = bar.timestamp.date() if hasattr(bar.timestamp, "date") else bar.timestamp
        sec_by_date[d] = bar.adj_close if bar.adj_close is not None else bar.close

    # Find common dates in chronological order
    common_dates = sorted(set(sec_by_date.keys()) & set(bmk_by_date.keys()))

    if len(common_dates) < 2:
        return None, {}

    common_base_date = common_dates[0]
    sec_base = sec_by_date[common_base_date]
    bmk_base = bmk_by_date[common_base_date]

    if sec_base <= 0 or bmk_base <= 0:
        return None, {}

    # Calculate cumulative benchmark returns map for each matched date
    bmk_cumulative_map: dict[date, Decimal] = {}
    for d in common_dates:
        p = bmk_by_date[d]
        cum_ret = ((p - bmk_base) / bmk_base).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        bmk_cumulative_map[d] = cum_ret

    # Calculate period returns over matched window
    sec_end = sec_by_date[common_dates[-1]]
    bmk_end = bmk_by_date[common_dates[-1]]

    sec_return = ((sec_end - sec_base) / sec_base).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    bmk_return = ((bmk_end - bmk_base) / bmk_base).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    excess_return = (sec_return - bmk_return).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )

    # Calculate daily returns for correlation
    sec_returns: list[float] = []
    bmk_returns: list[float] = []

    for i in range(1, len(common_dates)):
        d_prev = common_dates[i - 1]
        d_curr = common_dates[i]

        s_prev = sec_by_date[d_prev]
        s_curr = sec_by_date[d_curr]
        b_prev = bmk_by_date[d_prev]
        b_curr = bmk_by_date[d_curr]

        if s_prev > 0 and b_prev > 0:
            sec_returns.append(float((s_curr - s_prev) / s_prev))
            bmk_returns.append(float((b_curr - b_prev) / b_prev))

    # Pearson correlation
    correlation = Decimal("0.0")
    if len(sec_returns) >= 2:
        m = len(sec_returns)
        mean_s = sum(sec_returns) / m
        mean_b = sum(bmk_returns) / m

        var_s = sum((x - mean_s) ** 2 for x in sec_returns)
        var_b = sum((y - mean_b) ** 2 for y in bmk_returns)

        denom = math.sqrt(var_s * var_b)
        if denom > 0:
            cov = sum(
                (x - mean_s) * (y - mean_b)
                for x, y in zip(sec_returns, bmk_returns, strict=True)
            )
            corr_val = cov / denom
            correlation = Decimal(str(round(corr_val, 4))).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

    comparison = BenchmarkComparison(
        benchmark_id=benchmark_id,
        benchmark_name=benchmark_name,
        common_base_date=common_base_date,
        security_return=sec_return,
        benchmark_return=bmk_return,
        excess_return=excess_return,
        correlation=correlation,
    )

    return comparison, bmk_cumulative_map
