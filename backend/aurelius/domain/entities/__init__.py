"""
aurelius.domain.entities
========================
Core financial domain entities for AURELIUS.

Milestone 1 Entities:
  - Security: Tradable asset metadata
  - Price, PriceChange: Point-in-time price observations using Decimal
  - Quote: Market price snapshot with integer volume
  - OHLCVBar, OHLCVSeries: Historical bar models with unadjusted raw OHLC and provider adj_close
  - Enums: AssetType, Currency, MarketInterval (restricted to 1d in M1), MarketState
"""

from aurelius.domain.entities.enums import (
    AssetType,
    Currency,
    MarketInterval,
    MarketState,
)
from aurelius.domain.entities.ohlcv import OHLCVBar, OHLCVSeries
from aurelius.domain.entities.price import Price, PriceChange
from aurelius.domain.entities.quote import Quote
from aurelius.domain.entities.security import Security

__all__ = [
    "AssetType",
    "Currency",
    "MarketInterval",
    "MarketState",
    "OHLCVBar",
    "OHLCVSeries",
    "Price",
    "PriceChange",
    "Quote",
    "Security",
]
