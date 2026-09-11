"""
tests.unit.providers.test_yfinance_search
=========================================
Unit tests for YFinanceProvider search_securities, get_company_profile,
and enhanced get_security metadata normalization using mocked yfinance payloads.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from aurelius.domain.entities.enums import AssetType, Currency
from aurelius.domain.errors import InvalidSearchQueryError
from aurelius.providers.yfinance_provider import YFinanceProvider


@pytest.fixture
def provider() -> YFinanceProvider:
    return YFinanceProvider()


@pytest.mark.asyncio
async def test_search_securities_success(provider: YFinanceProvider) -> None:
    mock_search = MagicMock()
    mock_search.quotes = [
        {
            "symbol": "AAPL",
            "shortname": "Apple Inc.",
            "longname": "Apple Inc.",
            "typeDisp": "Equity",
            "exchDisp": "NASDAQ",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "score": 12500.5,
        },
        {
            "symbol": "SPY",
            "shortname": "SPDR S&P 500 ETF Trust",
            "typeDisp": "ETF",
            "exchDisp": "NYSE Arca",
            "score": 9800.0,
        },
        {
            "symbol": "^GSPC",
            "shortname": "S&P 500",
            "typeDisp": "Index",
            "exchDisp": "SNP",
        },
    ]

    with patch("yfinance.Search", return_value=mock_search):
        results = await provider.search_securities("Apple", limit=5)

    assert len(results) == 3
    assert results[0].ticker == "AAPL"
    assert results[0].name == "Apple Inc."
    assert results[0].asset_type == AssetType.EQUITY
    assert results[0].exchange_display == "NASDAQ"
    assert results[0].provider == "yahoo_finance"

    assert results[1].ticker == "SPY"
    assert results[1].asset_type == AssetType.ETF
    assert results[1].exchange_display == "NYSE Arca"

    assert results[2].ticker == "^GSPC"
    assert results[2].asset_type == AssetType.INDEX


@pytest.mark.asyncio
async def test_search_securities_invalid_query(provider: YFinanceProvider) -> None:
    with pytest.raises(InvalidSearchQueryError):
        await provider.search_securities("")

    with pytest.raises(InvalidSearchQueryError):
        await provider.search_securities("a" * 61)

    with pytest.raises(InvalidSearchQueryError):
        await provider.search_securities("<script>")


@pytest.mark.asyncio
async def test_search_securities_empty_with_ticker_fallback(
    provider: YFinanceProvider,
) -> None:
    mock_search = MagicMock()
    mock_search.quotes = []

    mock_ticker = MagicMock()
    mock_ticker.info = {
        "symbol": "MSFT",
        "longName": "Microsoft Corporation",
        "quoteType": "EQUITY",
        "currency": "USD",
        "exchange": "NMS",
        "fullExchangeName": "NasdaqGS",
        "sector": "Technology",
        "industry": "Software - Infrastructure",
    }

    with (
        patch("yfinance.Search", return_value=mock_search),
        patch("yfinance.Ticker", return_value=mock_ticker),
    ):
        results = await provider.search_securities("MSFT")

    assert len(results) == 1
    assert results[0].ticker == "MSFT"
    assert results[0].name == "Microsoft Corporation"
    assert results[0].asset_type == AssetType.EQUITY


@pytest.mark.asyncio
async def test_get_company_profile_equity_success(provider: YFinanceProvider) -> None:
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "symbol": "AAPL",
        "longName": "Apple Inc.",
        "quoteType": "EQUITY",
        "longBusinessSummary": "Designs, manufactures, and markets smartphones.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "website": "https://www.apple.com",
        "country": "United States",
        "city": "Cupertino",
        "state": "CA",
        "address1": "One Apple Park Way",
        "fullTimeEmployees": 161000,
    }

    with patch("yfinance.Ticker", return_value=mock_ticker):
        profile = await provider.get_company_profile("AAPL")

    assert profile is not None
    assert profile.lookup_ticker == "AAPL"
    assert profile.company_name == "Apple Inc."
    assert profile.sector == "Technology"
    assert profile.industry == "Consumer Electronics"
    assert profile.website == "https://www.apple.com"
    assert profile.city == "Cupertino"
    assert profile.country == "United States"
    assert profile.employees == 161000
    assert profile.provider == "yahoo_finance"


@pytest.mark.asyncio
async def test_get_company_profile_etf_returns_none(
    provider: YFinanceProvider,
) -> None:
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "symbol": "SPY",
        "shortName": "SPDR S&P 500 ETF Trust",
        "quoteType": "ETF",
        "fundFamily": "SPDR State Street Global Advisors",
    }

    with patch("yfinance.Ticker", return_value=mock_ticker):
        profile = await provider.get_company_profile("SPY")

    # Non-corporate instruments must return None cleanly, not raise errors
    assert profile is None


@pytest.mark.asyncio
async def test_get_company_profile_index_returns_none(
    provider: YFinanceProvider,
) -> None:
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "symbol": "^GSPC",
        "shortName": "S&P 500",
        "quoteType": "INDEX",
    }

    with patch("yfinance.Ticker", return_value=mock_ticker):
        profile = await provider.get_company_profile("^GSPC")

    assert profile is None


@pytest.mark.asyncio
async def test_get_security_currency_unfabricated(provider: YFinanceProvider) -> None:
    mock_ticker = MagicMock()
    # No currency key in info!
    mock_ticker.info = {
        "symbol": "MYSTERY",
        "shortName": "Mystery Asset",
        "quoteType": "EQUITY",
        "exchange": "XYZ",
    }

    with patch("yfinance.Ticker", return_value=mock_ticker):
        sec = await provider.get_security("MYSTERY")

    # Must NOT default to USD
    assert sec.currency == Currency.UNKNOWN
    assert sec.provider == "yahoo_finance"
    assert isinstance(sec.fetched_at, datetime)
