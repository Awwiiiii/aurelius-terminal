"""
aurelius.domain.entities.market_overview
========================================
Core domain entities for market overview, benchmark tracking, and market movers.

Domain Principles:
  1. Decoupling: Canonical benchmark identities (e.g. 'SP500', 'VIX') are defined
     independently of provider-specific routing symbols (e.g. '^GSPC', '^VIX').
  2. Financial Semantics:
     - Volume is an integer count or None if missing. Never fabricated as zero.
     - Market cap is provider-reported or None if omitted. Never reconstructed.
     - VIX represents 30-day forward annualized implied volatility derived from
       S&P 500 options; it is NOT a currency-priced equity asset.
     - Price and percentage changes are represented as Decimal.
  3. Safe Session Telemetry:
     - Session state reflects indicative provider status. In the absence of an
       authoritative holiday calendar, unverified weekday sessions default to UNKNOWN.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.enums import Currency


class MarketSessionState(StrEnum):
    """
    Market session operational state.
    """

    REGULAR_OPEN = "REGULAR_OPEN"
    PRE_MARKET = "PRE_MARKET"
    AFTER_HOURS = "AFTER_HOURS"
    CLOSED = "CLOSED"
    WEEKEND = "WEEKEND"
    UNKNOWN = "UNKNOWN"


class DataFreshness(StrEnum):
    """
    Data timeliness classification.
    """

    REAL_TIME = "REAL_TIME"
    DELAYED = "DELAYED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class BenchmarkCategory(StrEnum):
    """
    Economic market segment classification for benchmarks.
    """

    LARGE_CAP_CORE = "LARGE_CAP_CORE"
    MEGA_CAP_VALUE = "MEGA_CAP_VALUE"
    TECH_GROWTH = "TECH_GROWTH"
    SMALL_CAP = "SMALL_CAP"
    VOLATILITY = "VOLATILITY"


class BenchmarkDefinition(BaseModel):
    """
    Canonical definition of a financial benchmark index, decoupled from provider symbols.
    """

    model_config = ConfigDict(frozen=True)

    benchmark_id: str = Field(
        ...,
        description="Canonical internal benchmark identifier (e.g. 'SP500', 'VIX').",
    )
    name: str = Field(..., description="Descriptive benchmark name.")
    category: BenchmarkCategory = Field(..., description="Economic market segment.")
    description: str = Field(
        ..., description="Financial purpose and methodology description."
    )
    is_currency_priced: bool = Field(
        default=True,
        description="False for volatility/sentiment indices (e.g. VIX) that quote in index points, not currency.",
    )


# Canonical benchmark registry (Pure Domain Configuration)
CANONICAL_BENCHMARKS: dict[str, BenchmarkDefinition] = {
    "SP500": BenchmarkDefinition(
        benchmark_id="SP500",
        name="S&P 500 Index",
        category=BenchmarkCategory.LARGE_CAP_CORE,
        description="Market-cap weighted index tracking 500 leading US public corporations.",
        is_currency_priced=True,
    ),
    "DOW": BenchmarkDefinition(
        benchmark_id="DOW",
        name="Dow Jones Industrial Average",
        category=BenchmarkCategory.MEGA_CAP_VALUE,
        description="Price-weighted index tracking 30 blue-chip US industrial corporations.",
        is_currency_priced=True,
    ),
    "NASDAQ": BenchmarkDefinition(
        benchmark_id="NASDAQ",
        name="Nasdaq Composite",
        category=BenchmarkCategory.TECH_GROWTH,
        description="Broad market-cap weighted index heavily tilted toward technology and growth equities.",
        is_currency_priced=True,
    ),
    "RUSSELL2000": BenchmarkDefinition(
        benchmark_id="RUSSELL2000",
        name="Russell 2000 Index",
        category=BenchmarkCategory.SMALL_CAP,
        description="Standard benchmark measuring small-cap US equity performance.",
        is_currency_priced=True,
    ),
    "VIX": BenchmarkDefinition(
        benchmark_id="VIX",
        name="CBOE Volatility Index",
        category=BenchmarkCategory.VOLATILITY,
        description="30-day forward annualized implied volatility derived from S&P 500 options. Not a currency price or equity security.",
        is_currency_priced=False,
    ),
}


class BenchmarkSnapshot(BaseModel):
    """
    Performance snapshot of a curated major market benchmark index.
    """

    model_config = ConfigDict(frozen=True)

    benchmark_id: str = Field(
        ...,
        description="Canonical internal benchmark identifier (e.g. 'SP500', 'VIX').",
    )
    name: str = Field(..., description="Descriptive benchmark name.")
    category: BenchmarkCategory = Field(..., description="Economic market segment.")
    provider_ticker: str = Field(
        ..., description="Provider routing symbol (e.g. '^GSPC')."
    )
    price: Decimal = Field(..., description="Current index level / value.")
    change: Decimal = Field(
        ..., description="Index point change from prior session close."
    )
    change_percent: Decimal = Field(
        ..., description="Index percentage change from prior session close."
    )
    previous_close: Decimal | None = Field(
        default=None, description="Prior session closing level."
    )
    day_high: Decimal | None = Field(
        default=None, description="Intraday high index level."
    )
    day_low: Decimal | None = Field(
        default=None, description="Intraday low index level."
    )
    currency: Currency = Field(
        default=Currency.UNKNOWN,
        description="Index currency. Set to UNKNOWN for non-currency indices such as VIX.",
    )
    is_currency_priced: bool = Field(
        default=True,
        description="False for non-currency indices (VIX) that quote in percentage/volatility points.",
    )
    provider: str = Field(..., description="Source market data provider identifier.")
    timestamp: datetime = Field(..., description="Quote observation timestamp (UTC).")


class MoverCategory(StrEnum):
    """
    Market mover ranking table category.
    """

    GAINERS = "GAINERS"
    LOSERS = "LOSERS"
    ACTIVE = "ACTIVE"


class MarketMoverItem(BaseModel):
    """
    Individual security item within a market mover ranking table.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Normalized ticker symbol (e.g. 'AAPL').")
    name: str = Field(..., description="Display name of the company or security.")
    price: Decimal = Field(..., description="Current traded price.")
    change: Decimal = Field(..., description="Point change from prior session close.")
    change_percent: Decimal = Field(
        ..., description="Percentage change from prior session close."
    )
    previous_close: Decimal | None = Field(
        default=None, description="Prior session closing price."
    )
    volume: int | None = Field(
        default=None,
        description="Reported whole-share trading volume, or None if unavailable. Never defaulted to zero.",
    )
    market_cap: Decimal | None = Field(
        default=None,
        description="Provider-reported market capitalization directly from provider feed, or None if omitted. Never calculated or estimated.",
    )
    exchange: str | None = Field(default=None, description="Primary listing exchange.")
    category: MoverCategory = Field(
        ...,
        description="Ranking classification for this table (GAINERS, LOSERS, ACTIVE).",
    )


class MarketStatus(BaseModel):
    """
    Market operational session telemetry for a specific market region.
    """

    model_config = ConfigDict(frozen=True)

    region: str = Field(default="US", description="Market region code (e.g. 'US').")
    session_state: MarketSessionState = Field(..., description="Active session state.")
    exchange_timezone: str = Field(
        default="America/New_York", description="Primary listing timezone."
    )
    session_message: str | None = Field(
        default=None, description="Informational session duration or notice."
    )
    next_open: datetime | None = Field(
        default=None, description="Next session open timestamp (UTC) if known."
    )
    next_close: datetime | None = Field(
        default=None, description="Next session close timestamp (UTC) if known."
    )
    is_indicative: bool = Field(
        default=True,
        description="True if based on provider feed rather than exchange gateway.",
    )


class MarketOverviewSnapshot(BaseModel):
    """
    Composite domain model aggregating broad market telemetry.
    """

    model_config = ConfigDict(frozen=True)

    market_status: MarketStatus = Field(..., description="Market session status.")
    benchmarks: list[BenchmarkSnapshot] = Field(
        ..., description="Performance snapshots of major benchmarks."
    )
    gainers: list[MarketMoverItem] = Field(
        ..., description="Top session percentage gainers."
    )
    losers: list[MarketMoverItem] = Field(
        ..., description="Top session percentage losers."
    )
    active: list[MarketMoverItem] = Field(
        ..., description="Top session volume leaders."
    )
    fetched_at: datetime = Field(
        ..., description="Timestamp of snapshot creation (UTC)."
    )
    freshness: DataFreshness = Field(
        default=DataFreshness.DELAYED,
        description="Data timeliness classification.",
    )
    cached: bool = Field(
        default=False,
        description="True if served from the in-memory application cache.",
    )
    provider: str = Field(
        default="yahoo_finance",
        description="Source data provider identifier.",
    )
