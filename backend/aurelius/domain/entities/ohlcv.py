"""
aurelius.domain.entities.ohlcv
==============================
OHLCV (Open, High, Low, Close, Volume) domain entities.

Financial and Domain Principles:
  1. Volume is an integer (`int`):
     Reported market volume represents a count of whole shares traded on an exchange.
     While fractional shares can exist in broker-dealer internal book-keeping and fractional
     investing accounts, market aggregate volume reporting adheres to whole-share counts.

  2. Semantics of `is_adjusted`:
     Raw OHLC fields (`open`, `high`, `low`, `close`) ALWAYS remain raw, unadjusted
     historical transaction prices.
     The `is_adjusted` flag on `OHLCVSeries` indicates that provider-calculated adjusted
     closing prices are available and populated in the `adj_close` field of each bar.
     The `is_adjusted` flag does NOT imply that OHLC values themselves have been adjusted.

  3. Semantics and Limitation of `adj_close`:
     `adj_close` represents a provider-specific adjusted historical close (e.g. from
     Yahoo Finance), adjusted for corporate actions such as stock splits and cash dividends
     according to the provider's specific adjustment algorithm.
     `adj_close` must NOT automatically be interpreted as an exact investor total-return
     series, as it does not account for taxes, trade execution friction, cash dividend
     reinvestment timing differences, or special distributions that providers may handle
     differently.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.enums import MarketInterval


class OHLCVBar(BaseModel):
    """
    A single OHLCV bar representing trading activity over a specified period.

    For Milestone 1, bars represent daily aggregates where `timestamp` is a date.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: date = Field(..., description="Trading date for the bar.")
    open: Decimal = Field(..., description="Opening transaction price (unadjusted).")
    high: Decimal = Field(..., description="Highest transaction price (unadjusted).")
    low: Decimal = Field(..., description="Lowest transaction price (unadjusted).")
    close: Decimal = Field(..., description="Closing transaction price (unadjusted).")
    volume: int = Field(
        ...,
        description="Whole-share trading volume for the period. Note: fractional shares can exist in retail accounts, but market volume is reported in whole shares.",
    )
    adj_close: Decimal | None = Field(
        default=None,
        description=(
            "Provider-specific adjusted historical close price (accounting for splits and dividends). "
            "Must NOT automatically be interpreted as an exact investor total-return series."
        ),
    )


class OHLCVSeries(BaseModel):
    """
    A collection of OHLCV bars for a security across a time range.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Normalized ticker symbol.")
    interval: MarketInterval = Field(
        default=MarketInterval.DAILY,
        description="Bar aggregation interval (restricted to 1d in Milestone 1).",
    )
    bars: list[OHLCVBar] = Field(
        ..., description="Chronologically sorted list of OHLCV bars."
    )
    provider: str = Field(..., description="Data provider that supplied the bars.")
    is_adjusted: bool = Field(
        default=False,
        description=(
            "Explicit semantics: When True, indicates that provider-specific adjusted closing prices "
            "are populated in the `adj_close` field of each bar. Raw OHLC fields remain completely "
            "unadjusted. This flag does NOT imply that OHLC values themselves were modified."
        ),
    )
