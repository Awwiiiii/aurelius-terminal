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

from aurelius.domain.entities.company import CompanyProfile
from aurelius.domain.entities.enums import MarketInterval
from aurelius.domain.entities.ohlcv import OHLCVSeries
from aurelius.domain.entities.quote import Quote
from aurelius.domain.entities.search import SecuritySearchResult
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

    @abstractmethod
    async def search_securities(
        self, query: str, limit: int = 10
    ) -> list[SecuritySearchResult]:
        """
        Search for securities matching a text query (ticker, company name, asset).

        Accepts general text search queries (e.g. 'Apple', 'S&P 500', 'BRK.B').
        Sector/industry fields returned in results are provider-supplied classifications
        and must not be treated as authoritative GICS.

        Args:
            query: User search text query (1-60 characters).
            limit: Maximum number of results to return (1-50, default 10).

        Returns:
            List of matching SecuritySearchResult domain entities.

        Raises:
            InvalidSearchQueryError: If the query is empty, too long, or invalid.
            ProviderError: If the underlying search service fails.
        """
        ...

    @abstractmethod
    async def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        """
        Retrieve corporate identity, sector, industry, and description for an equity.

        Non-corporate instruments such as ETFs (e.g. SPY) and indices (e.g. ^GSPC)
        are valid securities but do not have corporate profiles. For non-corporate
        instruments, this method returns None. Returning None is normal behavior
        and must never be treated as an error or lookup failure.

        Provider sector and industry classifications are provider-supplied and
        must not be treated as authoritative GICS.

        Args:
            ticker: Normalized listing ticker symbol (e.g. 'AAPL').

        Returns:
            Validated CompanyProfile domain entity for corporate issuers, or None
            for non-corporate instruments or if corporate profile data is unavailable.

        Raises:
            InvalidTickerError: If the ticker format is invalid.
            DataNotFoundError: If the security does not exist.
            ProviderError: If the provider fails.
        """
        ...
