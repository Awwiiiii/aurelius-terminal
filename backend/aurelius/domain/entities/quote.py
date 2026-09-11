"""
aurelius.domain.entities.quote
==============================
Quote domain entity representing a real-time or delayed market price snapshot.

Domain and Financial Principles:
  - Volume is modeled as `int` because reported market trading volume is a whole-share
    count aggregate from exchanges. This design choice reflects standard exchange and
    provider reporting conventions, while acknowledging that fractional shares can and
    do exist in internal brokerage accounting and trading platforms.
  - Delay semantics: Unofficial/free data providers like Yahoo Finance have known
    limitations regarding real-time feeds. While data is typically delayed by 15-20 minutes
    during market hours, certain quotes or indices may reflect near real-time depending
    on provider feeds and market status. We do not make an unconditional claim that every
    quote is delayed; instead, `is_delayed` represents known provider reporting limitations.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.enums import Currency, MarketState


class Quote(BaseModel):
    """
    A market quote snapshot for a single security.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Normalized ticker symbol (e.g. 'AAPL').")
    price: Decimal = Field(..., description="Current/last traded price.")
    timestamp: datetime = Field(..., description="Quote timestamp (UTC).")
    currency: Currency = Field(default=Currency.USD, description="Trading currency.")
    change: Decimal | None = Field(
        default=None, description="Absolute change from previous close."
    )
    change_percent: Decimal | None = Field(
        default=None, description="Percentage change from previous close."
    )
    volume: int | None = Field(
        default=None,
        description=(
            "Reported trading volume as an integer share count. Note: Reported exchange volume "
            "is aggregated in whole shares, though fractional shares can exist in retail trading."
        ),
    )
    open: Decimal | None = Field(
        default=None, description="Opening price for the current trading day."
    )
    high: Decimal | None = Field(default=None, description="Intraday high price.")
    low: Decimal | None = Field(default=None, description="Intraday low price.")
    previous_close: Decimal | None = Field(
        default=None, description="Closing price of the prior trading session."
    )
    market_state: MarketState = Field(
        default=MarketState.UNKNOWN, description="Market session state."
    )
    provider: str = Field(
        ..., description="Identifier of the data provider supplying the quote."
    )
    is_delayed: bool = Field(
        default=True,
        description=(
            "Indicates whether quote data is subject to provider delays (typically 15-20 minutes "
            "for unofficial/free feeds during market hours). Documented as a known provider limitation."
        ),
    )
