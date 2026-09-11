"""
aurelius.providers.base
=======================
Abstract Base Class defining the contract for all market data providers in AURELIUS.

Design principles:
  - Decoupling: The domain and application layers interact ONLY with this abstract interface.
  - Asynchronous interface: All I/O operations are async. If an underlying provider library
    (e.g., yfinance) is synchronous/blocking, the concrete implementation must offload
    calls via `asyncio.to_thread` to preserve FastAPI event-loop responsiveness.
  - Validation: Implementations must return strictly validated domain models (`Quote`,
    `OHLCVSeries`, `Security`).
"""

from abc import ABC, abstractmethod
from datetime import date

from aurelius.domain.entities.enums import MarketInterval
from aurelius.domain.entities.ohlcv import OHLCVSeries
from aurelius.domain.entities.quote import Quote
from aurelius.domain.entities.security import Security


class MarketDataProvider(ABC):
    """
    Abstract interface for market data providers.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique provider identifier (e.g. 'yahoo_finance', 'fmp').
        """
        ...

    @abstractmethod
    async def get_quote(self, ticker: str) -> Quote:
        """
        Retrieve a current or delayed quote snapshot for a security.

        Args:
            ticker: Normalized ticker symbol (e.g. 'AAPL').

        Returns:
            Validated Quote domain entity.

        Raises:
            InvalidTickerError: If the ticker is malformed.
            DataNotFoundError: If the ticker or quote data does not exist.
            ProviderError: If the provider is unreachable or returns an error.
            DataQualityError: If returned data fails domain sanity checks.
        """
        ...

    @abstractmethod
    async def get_historical_bars(
        self,
        ticker: str,
        start: date,
        end: date,
        interval: MarketInterval = MarketInterval.DAILY,
    ) -> OHLCVSeries:
        """
        Retrieve historical OHLCV bars for a security over a date range.

        Args:
            ticker: Normalized ticker symbol.
            start: Start date (inclusive).
            end: End date (inclusive).
            interval: Bar aggregation interval (restricted to DAILY in M1).

        Returns:
            Validated OHLCVSeries domain entity.

        Raises:
            InvalidTickerError: If the ticker is malformed.
            DataNotFoundError: If no data exists for the given ticker or date range.
            ProviderError: If the provider fails or is unreachable.
            DataQualityError: If bars violate domain sanity or ordering rules.
        """
        ...

    @abstractmethod
    async def get_security(self, ticker: str) -> Security:
        """
        Retrieve metadata about a security.

        Args:
            ticker: Normalized ticker symbol.

        Returns:
            Validated Security domain entity.

        Raises:
            InvalidTickerError: If the ticker is malformed.
            DataNotFoundError: If the security does not exist.
            ProviderError: If the provider is unreachable.
        """
        ...
