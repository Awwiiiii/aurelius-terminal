"""
aurelius.api.v1.schemas.overview
================================
Pydantic response models for market overview, benchmarks, movers, and session telemetry.

Financial serialization principles:
  - Price and monetary values are serialized as formatted strings to prevent
    binary float parsing loss in JavaScript clients.
  - Volume is serialized as an integer (`int`) or `None` if omitted/missing.
  - Market capitalization is serialized as provider-reported string or `None`.
  - Non-currency benchmarks (e.g. VIX) include `is_currency_priced: False`.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.market_overview import (
    BenchmarkSnapshot,
    MarketMoverItem,
    MarketOverviewSnapshot,
    MarketStatus,
)


class BenchmarkResponse(BaseModel):
    """
    Market benchmark index performance response.
    """

    model_config = ConfigDict(frozen=True)

    benchmark_id: str = Field(
        ...,
        description="Canonical internal benchmark identifier (e.g. 'SP500', 'VIX').",
    )
    name: str = Field(..., description="Descriptive benchmark name.")
    category: str = Field(..., description="Economic market segment.")
    provider_ticker: str = Field(
        ..., description="Provider routing symbol (e.g. '^GSPC')."
    )
    price: str = Field(..., description="Current index level / value.")
    change: str = Field(..., description="Index point change from prior session close.")
    change_percent: str = Field(
        ..., description="Index percentage change from prior session close."
    )
    previous_close: str | None = Field(
        default=None, description="Prior session closing level."
    )
    day_high: str | None = Field(default=None, description="Intraday high index level.")
    day_low: str | None = Field(default=None, description="Intraday low index level.")
    currency: str = Field(
        ..., description="Index currency code or UNKNOWN for non-currency indices."
    )
    is_currency_priced: bool = Field(
        ...,
        description="False for volatility/sentiment indices (e.g. VIX) that quote in points, not currency.",
    )
    provider: str = Field(..., description="Data provider identifier.")
    timestamp: datetime = Field(..., description="Quote observation timestamp (UTC).")

    @classmethod
    def from_domain(cls, b: BenchmarkSnapshot) -> "BenchmarkResponse":
        return cls(
            benchmark_id=b.benchmark_id,
            name=b.name,
            category=b.category.value,
            provider_ticker=b.provider_ticker,
            price=str(b.price),
            change=str(b.change),
            change_percent=str(b.change_percent),
            previous_close=str(b.previous_close)
            if b.previous_close is not None
            else None,
            day_high=str(b.day_high) if b.day_high is not None else None,
            day_low=str(b.day_low) if b.day_low is not None else None,
            currency=b.currency.value,
            is_currency_priced=b.is_currency_priced,
            provider=b.provider,
            timestamp=b.timestamp,
        )


class MarketMoverResponse(BaseModel):
    """
    Market mover item response.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Normalized ticker symbol.")
    name: str = Field(..., description="Company or security display name.")
    price: str = Field(..., description="Current traded price as string.")
    change: str = Field(..., description="Point change from prior session close.")
    change_percent: str = Field(
        ..., description="Percentage change from prior session close."
    )
    previous_close: str | None = Field(
        default=None, description="Prior session closing price."
    )
    volume: int | None = Field(
        default=None,
        description="Reported whole-share trading volume, or None if unavailable.",
    )
    market_cap: str | None = Field(
        default=None,
        description="Provider-reported market capitalization directly from provider feed, or None if omitted.",
    )
    exchange: str | None = Field(default=None, description="Primary listing exchange.")
    category: str = Field(
        ..., description="Ranking classification (GAINERS, LOSERS, ACTIVE)."
    )

    @classmethod
    def from_domain(cls, m: MarketMoverItem) -> "MarketMoverResponse":
        return cls(
            ticker=m.ticker,
            name=m.name,
            price=str(m.price),
            change=str(m.change),
            change_percent=str(m.change_percent),
            previous_close=str(m.previous_close)
            if m.previous_close is not None
            else None,
            volume=m.volume,
            market_cap=str(m.market_cap) if m.market_cap is not None else None,
            exchange=m.exchange,
            category=m.category.value,
        )


class MarketStatusResponse(BaseModel):
    """
    Market session operational telemetry response.
    """

    model_config = ConfigDict(frozen=True)

    region: str = Field(..., description="Market region code (e.g. 'US').")
    session_state: str = Field(..., description="Active session state.")
    exchange_timezone: str = Field(..., description="Listing timezone.")
    session_message: str | None = Field(
        default=None, description="Informational notice or time remaining."
    )
    next_open: datetime | None = Field(
        default=None, description="Next session open timestamp (UTC) if known."
    )
    next_close: datetime | None = Field(
        default=None, description="Next session close timestamp (UTC) if known."
    )
    is_indicative: bool = Field(
        ...,
        description="True if based on provider feed rather than direct exchange gateway.",
    )

    @classmethod
    def from_domain(cls, s: MarketStatus) -> "MarketStatusResponse":
        return cls(
            region=s.region,
            session_state=s.session_state.value,
            exchange_timezone=s.exchange_timezone,
            session_message=s.session_message,
            next_open=s.next_open,
            next_close=s.next_close,
            is_indicative=s.is_indicative,
        )


class MarketOverviewResponse(BaseModel):
    """
    Composite market overview snapshot response.
    """

    model_config = ConfigDict(frozen=True)

    market_status: MarketStatusResponse = Field(
        ..., description="Operational session telemetry."
    )
    benchmarks: list[BenchmarkResponse] = Field(
        ..., description="Curated major market benchmark snapshots."
    )
    gainers: list[MarketMoverResponse] = Field(
        ..., description="Top session percentage gainers."
    )
    losers: list[MarketMoverResponse] = Field(
        ..., description="Top session percentage losers."
    )
    active: list[MarketMoverResponse] = Field(
        ..., description="Top session volume leaders."
    )
    fetched_at: datetime = Field(
        ..., description="Snapshot observation timestamp in UTC."
    )
    freshness: str = Field(..., description="Timeliness classification.")
    cached: bool = Field(
        ..., description="True if served from the in-memory application cache."
    )
    provider: str = Field(..., description="Source market data provider.")

    @classmethod
    def from_domain(cls, snap: MarketOverviewSnapshot) -> "MarketOverviewResponse":
        return cls(
            market_status=MarketStatusResponse.from_domain(snap.market_status),
            benchmarks=[BenchmarkResponse.from_domain(b) for b in snap.benchmarks],
            gainers=[MarketMoverResponse.from_domain(g) for g in snap.gainers],
            losers=[MarketMoverResponse.from_domain(loser) for loser in snap.losers],
            active=[MarketMoverResponse.from_domain(a) for a in snap.active],
            fetched_at=snap.fetched_at,
            freshness=snap.freshness.value,
            cached=snap.cached,
            provider=snap.provider,
        )
