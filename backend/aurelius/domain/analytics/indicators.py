"""
aurelius.domain.analytics.indicators
====================================
Pure domain mathematical functions for technical price indicators (SMA, EMA)
and historical period extremes.

Financial Standards:
  - Price Series Policy:
      Indicators and extremes are computed strictly on raw execution Close
      prices to reflect nominal traded levels and classical chart levels.
  - Zero-Indexed Warm-Up for Moving Averages (e.g. k=20):
      - observations 0..18 (first 19 observations): None
      - observation 19 (the 20th observation): first valid SMA20 = mean(P_0..P_19)
      - subsequent observations: rolling SMA20
  - EMA Warm-Up (k=20):
      - observations 0..18: None
      - observation 19: initialized using SMA20 over observations 0..19
      - observation 20 onward: recursive EMA formula:
          alpha = 2 / (k + 1) = 2 / 21
          EMA_t = P_t * alpha + EMA_{t-1} * (1 - alpha)
      (Does not require 21 observations; valid at observation 19).
  - Period Extremes:
      - Period high and low on raw Close with deterministic earliest-date tie breaking.
      - Distances to last close expressed as percentage:
          distance_from_high = (P_last - P_high) / P_high * 100 (<= 0%)
          distance_from_low = (P_last - P_low) / P_low * 100 (>= 0%)
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from aurelius.domain.entities.historical import HistoricalExtremes


def calculate_sma(prices: list[Decimal], window: int) -> list[Decimal | None]:
    """
    Calculate Simple Moving Average (SMA) over window k.

    Zero-indexed observation rules:
      - indices 0..(window-2): None
      - index (window-1): first valid SMA
      - index i >= window: rolling SMA
    """
    n = len(prices)
    if window < 1:
        raise ValueError("SMA window must be >= 1.")

    result: list[Decimal | None] = [None] * n
    if n < window:
        return result

    # First valid SMA at index (window - 1)
    window_sum = sum(prices[:window])
    window_dec = Decimal(window)
    result[window - 1] = (window_sum / window_dec).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

    # Rolling window for subsequent bars
    for i in range(window, n):
        window_sum += prices[i] - prices[i - window]
        result[i] = (window_sum / window_dec).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    return result


def calculate_ema(prices: list[Decimal], window: int = 20) -> list[Decimal | None]:
    """
    Calculate Exponential Moving Average (EMA) over window k.

    Zero-indexed observation rules:
      - indices 0..(window-2): None
      - index (window-1): initialized with SMA over first `window` observations
      - index i >= window: EMA_i = P_i * alpha + EMA_{i-1} * (1 - alpha)
        where alpha = 2 / (window + 1)
    """
    n = len(prices)
    if window < 1:
        raise ValueError("EMA window must be >= 1.")

    result: list[Decimal | None] = [None] * n
    if n < window:
        return result

    # Initialize at index (window - 1) with SMA
    sma_init = (sum(prices[:window]) / Decimal(window)).quantize(
        Decimal("0.00000001"), rounding=ROUND_HALF_UP
    )
    result[window - 1] = sma_init.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    # Multiplier alpha = 2 / (window + 1)
    alpha = Decimal("2") / Decimal(window + 1)
    one_minus_alpha = Decimal("1") - alpha

    current_ema = sma_init
    for i in range(window, n):
        current_ema = prices[i] * alpha + current_ema * one_minus_alpha
        result[i] = current_ema.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return result


def compute_historical_extremes(
    prices: list[Decimal], dates: list[date]
) -> HistoricalExtremes:
    """
    Compute HistoricalExtremes entity on raw Close series.
    Requires at least 1 price observation.
    """
    if not prices or len(prices) != len(dates):
        raise ValueError("Prices and dates must be non-empty and of equal length.")

    period_high = prices[0]
    period_high_date = dates[0]

    period_low = prices[0]
    period_low_date = dates[0]

    for p, d in zip(prices, dates, strict=True):
        if p > period_high:
            period_high = p
            period_high_date = d
        if p < period_low:
            period_low = p
            period_low_date = d

    last_price = prices[-1]

    if period_high > 0:
        dist_high = (
            (last_price - period_high) / period_high * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        dist_high = Decimal("0.0")

    if period_low > 0:
        dist_low = ((last_price - period_low) / period_low * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        dist_low = Decimal("0.0")

    return HistoricalExtremes(
        period_high=period_high,
        period_high_date=period_high_date,
        period_low=period_low,
        period_low_date=period_low_date,
        distance_from_high=dist_high,
        distance_from_low=dist_low,
    )
