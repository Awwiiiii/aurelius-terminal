"""
aurelius.providers
==================
External data provider abstraction layer.

Exports:
  - MarketDataProvider: Abstract interface
  - ProviderRegistry: Provider lifecycle registry
  - provider_registry: Global registry instance
  - get_market_data_provider: FastAPI dependency provider
  - YFinanceProvider: Yahoo Finance provider implementation
"""

from aurelius.providers.base import MarketDataProvider
from aurelius.providers.registry import (
    ProviderRegistry,
    get_market_data_provider,
    provider_registry,
)
from aurelius.providers.yfinance_provider import YFinanceProvider

__all__ = [
    "MarketDataProvider",
    "ProviderRegistry",
    "YFinanceProvider",
    "get_market_data_provider",
    "provider_registry",
]
