"""
aurelius.domain.analytics.drawdowns
===================================
Pure domain mathematical functions for peak-to-trough drawdowns and recovery.

Financial Standards:
  - Calculated on provider-adjusted close (adj_close) to preserve
    split/dividend continuity.
  - Running peak: M_t = max_{0 <= s <= t} P_s.
  - Drawdown at session t: DD_t = (P_t - M_t) / M_t <= 0.0.
  - Deterministic tie-breaking for Maximum Drawdown (MDD):
      1. Trough date: Earliest date achieving the minimum drawdown value.
      2. Peak date: Earliest date achieving the peak value prior to or on the trough date.
  - Recovery:
      - First date strictly following the trough date on which price re-attains
        or exceeds the preceding peak price (P_t >= P_peak).
      - If price never reclaims the peak before period end: recovery_date = None, is_recovered = False.
  - Current Drawdown: Drawdown at the final observation of the series.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from aurelius.domain.entities.historical import DrawdownMetrics


def calculate_drawdown_series(prices: list[Decimal]) -> list[Decimal]:
    """
    Calculate running drawdown percentage from peak for each observation.
    All values are <= 0.0.
    """
    if not prices:
        return []

    running_peak = prices[0]
    drawdowns: list[Decimal] = []

    for p in prices:
        if p > running_peak:
            running_peak = p
        if running_peak <= 0:
            drawdowns.append(Decimal("0.0"))
        else:
            dd = (p - running_peak) / running_peak
            drawdowns.append(dd.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))

    return drawdowns


def compute_drawdown_metrics(
    prices: list[Decimal], dates: list[date]
) -> DrawdownMetrics:
    """
    Compute complete DrawdownMetrics domain entity on adjusted close series.
    Requires at least 1 price observation.
    """
    if not prices or len(prices) != len(dates):
        raise ValueError("Prices and dates must be non-empty and of equal length.")

    n = len(prices)
    if n == 1:
        return DrawdownMetrics(
            max_drawdown=Decimal("0.0"),
            max_drawdown_peak_date=dates[0],
            max_drawdown_trough_date=dates[0],
            recovery_date=dates[0],
            is_recovered=True,
            current_drawdown=Decimal("0.0"),
        )

    # Compute running peak and running peak index for each bar
    running_peaks: list[Decimal] = []
    peak_indices: list[int] = []

    current_peak = prices[0]
    current_peak_idx = 0

    for i, p in enumerate(prices):
        if p > current_peak:
            current_peak = p
            current_peak_idx = i
        running_peaks.append(current_peak)
        peak_indices.append(current_peak_idx)

    # Compute drawdowns
    drawdowns = calculate_drawdown_series(prices)

    # Identify maximum drawdown with deterministic tie-breaking (earliest trough)
    min_dd = Decimal("0.0")
    trough_idx = 0

    for i, dd in enumerate(drawdowns):
        if dd < min_dd:
            min_dd = dd
            trough_idx = i

    peak_idx = peak_indices[trough_idx]
    peak_price = running_peaks[trough_idx]
    peak_date = dates[peak_idx]
    trough_date = dates[trough_idx]

    # If min_dd == 0.0 (no decline ever occurred), peak and trough are at index 0
    if min_dd == Decimal("0.0"):
        return DrawdownMetrics(
            max_drawdown=Decimal("0.0"),
            max_drawdown_peak_date=dates[0],
            max_drawdown_trough_date=dates[0],
            recovery_date=dates[0],
            is_recovered=True,
            current_drawdown=Decimal("0.0"),
        )

    # Look for recovery strictly after trough_idx
    recovery_date: date | None = None
    is_recovered = False

    for j in range(trough_idx + 1, n):
        if prices[j] >= peak_price:
            recovery_date = dates[j]
            is_recovered = True
            break

    current_dd = drawdowns[-1]

    return DrawdownMetrics(
        max_drawdown=min_dd,
        max_drawdown_peak_date=peak_date,
        max_drawdown_trough_date=trough_date,
        recovery_date=recovery_date,
        is_recovered=is_recovered,
        current_drawdown=current_dd,
    )
