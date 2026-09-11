"""
aurelius.domain.entities.historical
===================================
Domain entities for historical market analysis, return metrics, volatility,
drawdowns, moving averages, and benchmark performance comparison.

Financial Principles:
  1. Price Series Policy:
     - Raw Close: Used for SMA/EMA technical price-level indicators and period extremes.
     - Adjusted Close: Used for return series, volatility, and drawdowns.
       (`adj_close` represents a provider-specific historical adjustment intended
        to account for modeled corporate-action effects such as splits and dividends.
        AURELIUS does not claim that this is an exact investor-level corporate-action accounting series).
  2. Terminology:
     - The cumulative performance derived from provider-adjusted close is formally
       named `adjusted_price_return` (never "Total Return").
  3. Calendar-Time CAGR:
     - Annualized compounding is computed over elapsed calendar time:
       CAGR = (P_end / P_start) ** (365.2425 / calendar_days) - 1
  4. Win Rate:
     - positive_days / (positive_days + negative_days); zero-return days are excluded.
  5. Immutability:
     - All entities use ConfigDict(frozen=True).
"""

from datetime import date as PyDate
from datetime import datetime as PyDateTime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class HistoricalTimeHorizon(StrEnum):
    """
    Standard historical analysis time horizons.
    """

    ONE_MONTH = "1M"
    THREE_MONTHS = "3M"
    SIX_MONTHS = "6M"
    YEAR_TO_DATE = "YTD"
    ONE_YEAR = "1Y"
    THREE_YEARS = "3Y"
    FIVE_YEARS = "5Y"
    MAX = "MAX"
    CUSTOM = "CUSTOM"


class ReturnMetrics(BaseModel):
    """
    Return and performance analytics over a historical period.
    """

    model_config = ConfigDict(frozen=True)

    adjusted_price_return: Decimal = Field(
        ...,
        description="Period return calculated from provider-adjusted close (P_end / P_start - 1).",
    )
    cagr: Decimal | None = Field(
        default=None,
        description="Calendar-time Compound Annual Growth Rate for periods >= 365 calendar days.",
    )
    mean_daily_return: Decimal = Field(
        ..., description="Arithmetic mean of daily simple returns."
    )
    positive_days: int = Field(
        ..., description="Count of trading sessions with daily return > 0."
    )
    negative_days: int = Field(
        ..., description="Count of trading sessions with daily return < 0."
    )
    zero_days: int = Field(
        ..., description="Count of trading sessions with daily return == 0."
    )
    win_rate: Decimal | None = Field(
        default=None,
        description="Ratio of positive days to (positive + negative) days; None if no non-zero days.",
    )


class VolatilityMetrics(BaseModel):
    """
    Realized historical volatility metrics.
    """

    model_config = ConfigDict(frozen=True)

    daily_volatility: Decimal = Field(
        ...,
        description="Sample standard deviation (N-1 Bessel correction) of daily simple returns.",
    )
    annualized_volatility: Decimal = Field(
        ...,
        description="Annualized historical volatility (daily_volatility * sqrt(252)).",
    )
    trading_days_assumed: int = Field(
        default=252,
        description="Annualization session factor (standard US equity: 252).",
    )


class DrawdownMetrics(BaseModel):
    """
    Drawdown and peak-to-trough risk metrics calculated on adjusted close.
    """

    model_config = ConfigDict(frozen=True)

    max_drawdown: Decimal = Field(
        ..., description="Maximum percentage decline from a running peak (<= 0.0)."
    )
    max_drawdown_peak_date: PyDate = Field(
        ...,
        description="Date of the peak preceding the maximum drawdown trough.",
    )
    max_drawdown_trough_date: PyDate = Field(
        ..., description="Date on which the maximum drawdown trough occurred."
    )
    recovery_date: PyDate | None = Field(
        default=None,
        description="First date after trough on which price reclaimed the preceding peak, or None.",
    )
    is_recovered: bool = Field(
        ...,
        description="True if price has recovered back to or above the preceding peak.",
    )
    current_drawdown: Decimal = Field(
        ...,
        description="Drawdown percentage at the final observation of the period (<= 0.0).",
    )


class HistoricalExtremes(BaseModel):
    """
    Historical extreme price observations and distances on raw Close.
    """

    model_config = ConfigDict(frozen=True)

    period_high: Decimal = Field(
        ..., description="Highest raw closing price during the period."
    )
    period_high_date: PyDate = Field(..., description="Date of the highest raw close.")
    period_low: Decimal = Field(
        ..., description="Lowest raw closing price during the period."
    )
    period_low_date: PyDate = Field(..., description="Date of the lowest raw close.")
    distance_from_high: Decimal = Field(
        ...,
        description="Percentage distance from period high to last close ((P_last - P_high) / P_high * 100 <= 0%).",
    )
    distance_from_low: Decimal = Field(
        ...,
        description="Percentage distance from period low to last close ((P_last - P_low) / P_low * 100 >= 0%).",
    )


class BenchmarkComparison(BaseModel):
    """
    Comparative performance against a canonical benchmark aligned on matched trading dates.
    """

    model_config = ConfigDict(frozen=True)

    benchmark_id: str = Field(
        ..., description="Canonical benchmark identifier (e.g. 'SP500')."
    )
    benchmark_name: str = Field(..., description="Descriptive benchmark name.")
    common_base_date: PyDate = Field(
        ...,
        description="Earliest matched trading date used as base 100.0 rebase point.",
    )
    security_return: Decimal = Field(
        ..., description="Security return over the matched date window."
    )
    benchmark_return: Decimal = Field(
        ..., description="Benchmark return over the matched date window."
    )
    excess_return: Decimal = Field(
        ..., description="Excess return (security_return - benchmark_return)."
    )
    correlation: Decimal = Field(
        ..., description="Pearson correlation coefficient between daily simple returns."
    )


class HistoricalBarPoint(BaseModel):
    """
    Single trading-day point within an analytical historical time series.
    """

    model_config = ConfigDict(frozen=True)

    date: PyDate = Field(..., description="Trading session date.")
    open: Decimal = Field(..., description="Raw execution open price.")
    high: Decimal = Field(..., description="Raw execution high price.")
    low: Decimal = Field(..., description="Raw execution low price.")
    close: Decimal = Field(..., description="Raw execution close price.")
    adj_close: Decimal = Field(..., description="Provider-adjusted close price.")
    volume: int = Field(..., description="Whole-share trading volume.")
    daily_return: Decimal | None = Field(
        default=None,
        description="Simple daily return on adj_close; None for initial bar.",
    )
    cumulative_return: Decimal = Field(
        ..., description="Compounded cumulative return on adj_close from base date."
    )
    drawdown: Decimal = Field(
        ..., description="Drawdown percentage from running peak on adj_close (<= 0.0)."
    )
    sma_20: Decimal | None = Field(
        default=None, description="20-day Simple Moving Average on raw Close."
    )
    sma_50: Decimal | None = Field(
        default=None, description="50-day Simple Moving Average on raw Close."
    )
    sma_200: Decimal | None = Field(
        default=None, description="200-day Simple Moving Average on raw Close."
    )
    ema_20: Decimal | None = Field(
        default=None, description="20-day Exponential Moving Average on raw Close."
    )
    rolling_vol_20: Decimal | None = Field(
        default=None, description="Rolling 20-return annualized volatility."
    )
    benchmark_cumulative_return: Decimal | None = Field(
        default=None,
        description="Matched benchmark cumulative return from common base date.",
    )


class HistoricalAnalysisSummary(BaseModel):
    """
    Composite domain model aggregating historical market analysis.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Normalized ticker symbol.")
    horizon: HistoricalTimeHorizon = Field(..., description="Configured time horizon.")
    start_date: PyDate = Field(
        ..., description="Earliest trading session date in series."
    )
    end_date: PyDate = Field(..., description="Latest trading session date in series.")
    calendar_days: int = Field(
        ..., description="Actual elapsed calendar days (end - start)."
    )
    trading_days: int = Field(
        ..., description="Count of actual executed trading sessions."
    )
    returns: ReturnMetrics = Field(..., description="Return metrics on adjusted close.")
    volatility: VolatilityMetrics = Field(
        ..., description="Realized volatility metrics."
    )
    drawdowns: DrawdownMetrics = Field(
        ..., description="Drawdown metrics on adjusted close."
    )
    extremes: HistoricalExtremes = Field(
        ..., description="Period extremes on raw close."
    )
    benchmark_comparison: BenchmarkComparison | None = Field(
        default=None, description="Comparative benchmark metrics if requested."
    )
    series: list[HistoricalBarPoint] = Field(
        default_factory=list, description="Ordered time series bar points for charting."
    )
    provider: str = Field(..., description="Source market data provider.")
    fetched_at: PyDateTime = Field(
        ..., description="Timestamp of analysis generation (UTC)."
    )
