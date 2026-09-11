"""
aurelius.api.v1.schemas.market
==============================
Pydantic response models for market data endpoints.

Financial serialization:
  - Price and monetary values are serialized as formatted strings to prevent
    binary float parsing loss in JSON consumers/clients (JavaScript Numbers).
  - Volume is serialized as an integer (`int`).
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.ohlcv import OHLCVBar, OHLCVSeries
from aurelius.domain.entities.quote import Quote


class QuoteResponse(BaseModel):
    """
    Market quote snapshot response.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Normalized security ticker symbol.")
    price: str = Field(..., description="Current/last traded price as string.")
    timestamp: datetime = Field(..., description="Quote observation timestamp in UTC.")
    currency: str = Field(..., description="Currency code (e.g. 'USD').")
    change: str | None = Field(
        default=None, description="Absolute change from prior session close."
    )
    change_percent: str | None = Field(
        default=None, description="Percentage change from prior session close."
    )
    volume: int | None = Field(
        default=None, description="Reported whole-share trading volume."
    )
    open: str | None = Field(default=None, description="Opening price for the day.")
    high: str | None = Field(default=None, description="Intraday high price.")
    low: str | None = Field(default=None, description="Intraday low price.")
    previous_close: str | None = Field(
        default=None, description="Prior session closing price."
    )
    market_state: str = Field(
        ..., description="Market session state (PRE, REGULAR, POST, CLOSED)."
    )
    provider: str = Field(..., description="Data provider identifier.")
    is_delayed: bool = Field(
        ..., description="Indicates if quote data is delayed by provider."
    )

    @classmethod
    def from_domain(cls, quote: Quote) -> "QuoteResponse":
        return cls(
            ticker=quote.ticker,
            price=str(quote.price),
            timestamp=quote.timestamp,
            currency=quote.currency.value,
            change=str(quote.change) if quote.change is not None else None,
            change_percent=str(quote.change_percent)
            if quote.change_percent is not None
            else None,
            volume=quote.volume,
            open=str(quote.open) if quote.open is not None else None,
            high=str(quote.high) if quote.high is not None else None,
            low=str(quote.low) if quote.low is not None else None,
            previous_close=str(quote.previous_close)
            if quote.previous_close is not None
            else None,
            market_state=quote.market_state.value,
            provider=quote.provider,
            is_delayed=quote.is_delayed,
        )


class OHLCVBarResponse(BaseModel):
    """
    Historical OHLCV bar response.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: date = Field(..., description="Date of the bar.")
    open: str = Field(..., description="Unadjusted open price as string.")
    high: str = Field(..., description="Unadjusted high price as string.")
    low: str = Field(..., description="Unadjusted low price as string.")
    close: str = Field(..., description="Unadjusted close price as string.")
    volume: int = Field(..., description="Whole-share trading volume.")
    adj_close: str | None = Field(
        default=None,
        description="Provider-specific adjusted close price. Does NOT imply raw OHLC was adjusted.",
    )

    @classmethod
    def from_domain(cls, bar: OHLCVBar) -> "OHLCVBarResponse":
        return cls(
            timestamp=bar.timestamp,
            open=str(bar.open),
            high=str(bar.high),
            low=str(bar.low),
            close=str(bar.close),
            volume=bar.volume,
            adj_close=str(bar.adj_close) if bar.adj_close is not None else None,
        )


class OHLCVResponse(BaseModel):
    """
    Collection of historical OHLCV bars response.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Normalized ticker symbol.")
    interval: str = Field(..., description="Bar time interval (e.g. '1d').")
    bars: list[OHLCVBarResponse] = Field(
        ..., description="Chronologically sorted OHLCV bars."
    )
    provider: str = Field(..., description="Data provider identifier.")
    is_adjusted: bool = Field(
        ...,
        description="Indicates whether adj_close is populated in bars. Raw OHLC remains unadjusted.",
    )

    @classmethod
    def from_domain(cls, series: OHLCVSeries) -> "OHLCVResponse":
        return cls(
            ticker=series.ticker,
            interval=series.interval.value,
            bars=[OHLCVBarResponse.from_domain(bar) for bar in series.bars],
            provider=series.provider,
            is_adjusted=series.is_adjusted,
        )
