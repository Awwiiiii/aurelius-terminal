"""
aurelius.providers.registry
===========================
Registry for managing and resolving market data provider implementations.

Design principles:
  - Enables loose coupling and runtime provider switching.
  - Acts as the dependency resolution target for FastAPI route handlers.
"""

from aurelius.domain.errors import ProviderError
from aurelius.providers.base import MarketDataProvider


class ProviderRegistry:
    """
    Registry holding instances of MarketDataProvider.
    """

    def __init__(self) -> None:
        self._providers: dict[str, MarketDataProvider] = {}
        self._default_provider_name: str | None = None

    def register(self, provider: MarketDataProvider, default: bool = False) -> None:
        """
        Register a market data provider instance.
        """
        self._providers[provider.name] = provider
        if default or self._default_provider_name is None:
            self._default_provider_name = provider.name

    def get(self, name: str | None = None) -> MarketDataProvider:
        """
        Resolve a provider by name, or return the default provider if name is None.
        """
        target_name = name or self._default_provider_name
        if target_name is None:
            raise ProviderError("No market data providers have been registered.")

        provider = self._providers.get(target_name)
        if provider is None:
            raise ProviderError(
                f"Provider '{target_name}' is not registered. Available: {list(self._providers.keys())}",
                provider=target_name,
            )
        return provider

    def clear(self) -> None:
        """
        Clear all registered providers (primarily for testing).
        """
        self._providers.clear()
        self._default_provider_name = None


# Global registry instance
provider_registry = ProviderRegistry()


def get_market_data_provider() -> MarketDataProvider:
    """
    FastAPI dependency that provides the default market data provider.
    """
    if provider_registry._default_provider_name is None:
        from aurelius.providers.yfinance_provider import (
            YFinanceProvider,  # noqa: PLC0415
        )

        provider_registry.register(YFinanceProvider(), default=True)
    return provider_registry.get()
