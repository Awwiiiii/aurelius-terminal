"""
aurelius.domain.analytics.returns
=================================
Pure domain mathematical functions for price returns, calendar-time CAGR,
and win rates.

Financial Standards:
  - Returns are computed on provider-adjusted close (adj_close) to account
    for modeled corporate action effects (splits and dividends).
  - Terminology: The cumulative return is strictly named `adjusted_price_return`
    (never "Total Return").
  - Calendar-Time CAGR: Uses actual elapsed calendar days:
      CAGR = (P_end / P_start) ** (365.2425 / calendar_days) - 1
    Requires calendar_days >= 365. Emits None for horizons < 365 calendar days.
  - Win Rate: Calculated as positive_days / (positive_days + negative_days).
    Zero-return trading sessions are excluded from the win rate calculation.
    Emits None if positive_days + negative_days == 0.
"""

import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from aurelius.domain.entities.historical import ReturnMetrics


def calculate_simple_daily_returns(prices: list[Decimal]) -> list[Decimal | None]:
    """
    Compute daily simple returns: R_t = (P_t - P_{t-1}) / P_{t-1}.

    The initial observation returns None.
    """
    if not prices:
        return []

    returns: list[Decimal | None] = [None]
    for i in range(1, len(prices)):
        prev = prices[i - 1]
        curr = prices[i]
        if prev <= 0:
            returns.append(Decimal("0.0"))
        else:
            ret = (curr - prev) / prev
            returns.append(ret.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))
    return returns


def calculate_log_daily_returns(prices: list[Decimal]) -> list[Decimal | None]:
    """
    Compute daily logarithmic (continuously compounded) returns: r_t = ln(P_t / P_{t-1}).

    The initial observation returns None.
    Evaluates logarithm in 64-bit float and quantizes result to Decimal('0.00000001').
    """
    if not prices:
        return []

    returns: list[Decimal | None] = [None]
    for i in range(1, len(prices)):
        prev = prices[i - 1]
        curr = prices[i]
        if prev <= Decimal("0.0") or curr <= Decimal("0.0"):
            returns.append(Decimal("0.00000000"))
        else:
            ratio = float(curr / prev)
            log_ret = math.log(ratio)
            returns.append(
                Decimal(str(round(log_ret, 10))).quantize(
                    Decimal("0.00000001"), rounding=ROUND_HALF_UP
                )
            )
    return returns


def calculate_cumulative_returns(prices: list[Decimal]) -> list[Decimal]:
    """
    Compute compounded cumulative return series from base observation:
    CumR_t = (P_t - P_0) / P_0.
    """
    if not prices:
        return []

    base = prices[0]
    if base <= 0:
        return [Decimal("0.0") for _ in prices]

    cumulative: list[Decimal] = []
    for p in prices:
        cum_ret = (p - base) / base
        cumulative.append(
            cum_ret.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        )
    return cumulative


def calculate_calendar_cagr(
    start_price: Decimal, end_price: Decimal, calendar_days: int
) -> Decimal | None:
    """
    Compute calendar-time Compound Annual Growth Rate (CAGR):
    CAGR = (P_end / P_start) ** (365.2425 / calendar_days) - 1.

    Requirements:
      - calendar_days >= 365
      - start_price > 0 and end_price > 0
    Returns None if calendar_days < 365 or if non-positive prices.
    """
    if calendar_days < 365 or start_price <= 0 or end_price <= 0:
        return None

    try:
        ratio = float(end_price / start_price)
        exponent = 365.2425 / float(calendar_days)
        cagr_float = math.pow(ratio, exponent) - 1.0
        return Decimal(str(round(cagr_float, 8))).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
    except (ValueError, OverflowError, ZeroDivisionError):
        return None


def calculate_win_rate_counts(
    daily_returns: list[Decimal | None],
) -> tuple[int, int, int, Decimal | None]:
    """
    Count positive, negative, and zero return sessions, and compute win rate.

    Win rate = positive_days / (positive_days + negative_days).
    Zero-return days are excluded.
    Returns (pos, neg, zero, win_rate).
    """
    pos = 0
    neg = 0
    zero = 0

    for r in daily_returns:
        if r is None:
            continue
        if r > 0:
            pos += 1
        elif r < 0:
            neg += 1
        else:
            zero += 1

    denominator = pos + neg
    if denominator == 0:
        win_rate = None
    else:
        win_rate = (Decimal(pos) / Decimal(denominator)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    return pos, neg, zero, win_rate


def compute_return_metrics(prices: list[Decimal], dates: list[date]) -> ReturnMetrics:
    """
    Compute complete ReturnMetrics domain model on adjusted close series.
    Requires at least 1 price observation.
    """
    if not prices or len(prices) != len(dates):
        raise ValueError("Prices and dates must be non-empty and of equal length.")

    if len(prices) == 1:
        return ReturnMetrics(
            adjusted_price_return=Decimal("0.0"),
            cagr=None,
            mean_daily_return=Decimal("0.0"),
            positive_days=0,
            negative_days=0,
            zero_days=0,
            win_rate=None,
        )

    start_price = prices[0]
    end_price = prices[-1]
    if start_price <= 0:
        adj_return = Decimal("0.0")
    else:
        adj_return = ((end_price - start_price) / start_price).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

    calendar_days = (dates[-1] - dates[0]).days
    cagr = calculate_calendar_cagr(start_price, end_price, calendar_days)

    daily_returns = calculate_simple_daily_returns(prices)
    valid_returns = [r for r in daily_returns if r is not None]

    if valid_returns:
        mean_daily = (sum(valid_returns) / Decimal(len(valid_returns))).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        )
    else:
        mean_daily = Decimal("0.0")

    pos, neg, zero, win_rate = calculate_win_rate_counts(daily_returns)

    return ReturnMetrics(
        adjusted_price_return=adj_return,
        cagr=cagr,
        mean_daily_return=mean_daily,
        positive_days=pos,
        negative_days=neg,
        zero_days=zero,
        win_rate=win_rate,
    )
