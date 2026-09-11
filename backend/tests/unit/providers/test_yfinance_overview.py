"""
tests/unit/providers/test_yfinance_overview.py
=============================================
Unit tests for Market Overview data provider implementations, including
session telemetry fallbacks, benchmark normalization, and market movers.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from aurelius.domain.entities import (
    Currency,
    MarketSessionState,
    MoverCategory,
)
from aurelius.providers.yfinance_provider import YFinanceProvider


@pytest.fixture
def provider() -> YFinanceProvider:
    return YFinanceProvider()


@pytest.mark.asyncio
async def test_get_market_status_open(provider: YFinanceProvider) -> None:
    mock_market = MagicMock()
    mock_market.status = {
        "id": "us",
        "status": "open",
        "message": "U.S. markets close in 4 hours",
        "open": datetime(2026, 9, 11, 13, 30, tzinfo=UTC),
        "close": datetime(2026, 9, 11, 20, 0, tzinfo=UTC),
        "timezone": {"$text": "America/New_York"},
    }

    with patch("yfinance.Market", return_value=mock_market):
        status = await provider.get_market_status("US")

    assert status.region == "US"
    assert status.session_state == MarketSessionState.REGULAR_OPEN
    assert status.session_message == "U.S. markets close in 4 hours"
    assert status.is_indicative is True


@pytest.mark.asyncio
async def test_get_market_status_fallback_weekend(
    provider: YFinanceProvider,
) -> None:
    # Simulate an error from provider on Saturday
    sat_dt = datetime(2026, 9, 12, 14, 0, tzinfo=ZoneInfo("America/New_York"))

    with (
        patch("yfinance.Market", side_effect=RuntimeError("Provider offline")),
        patch("aurelius.providers.yfinance_provider.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = sat_dt
        status = await provider.get_market_status("US")

    assert status.session_state == MarketSessionState.WEEKEND
    assert "weekend" in (status.session_message or "").lower()


@pytest.mark.asyncio
async def test_get_market_status_fallback_weekday_unknown(
    provider: YFinanceProvider,
) -> None:
    # Simulate an error from provider on Wednesday: MUST return UNKNOWN without holiday calendar
    wed_dt = datetime(2026, 9, 9, 14, 0, tzinfo=ZoneInfo("America/New_York"))

    with (
        patch("yfinance.Market", side_effect=RuntimeError("Provider offline")),
        patch("aurelius.providers.yfinance_provider.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = wed_dt
        status = await provider.get_market_status("US")

    assert status.session_state == MarketSessionState.UNKNOWN
    assert status.is_indicative is True


@pytest.mark.asyncio
async def test_get_benchmarks_normalization(
    provider: YFinanceProvider,
) -> None:
    # Mock yf.Tickers for SP500 (^GSPC) and VIX (^VIX)
    mock_gspc = MagicMock()
    mock_gspc_fast = MagicMock()
    mock_gspc_fast.last_price = 5600.50
    mock_gspc_fast.previous_close = 5575.00
    mock_gspc_fast.day_high = 5610.00
    mock_gspc_fast.day_low = 5560.00
    mock_gspc.fast_info = mock_gspc_fast

    mock_vix = MagicMock()
    mock_vix_fast = MagicMock()
    mock_vix_fast.last_price = 15.75
    mock_vix_fast.previous_close = 16.50
    mock_vix_fast.day_high = 16.60
    mock_vix_fast.day_low = 15.50
    mock_vix.fast_info = mock_vix_fast

    mock_tickers_obj = MagicMock()
    mock_tickers_obj.tickers = {"^GSPC": mock_gspc, "^VIX": mock_vix}

    with patch("yfinance.Tickers", return_value=mock_tickers_obj):
        benchmarks = await provider.get_benchmarks(["SP500", "VIX"])

    assert len(benchmarks) == 2

    # SP500 verification
    sp500 = next(b for b in benchmarks if b.benchmark_id == "SP500")
    assert sp500.price == Decimal("5600.5")
    assert sp500.change == Decimal("25.5")
    assert sp500.currency == Currency.USD
    assert sp500.is_currency_priced is True

    # VIX verification: non-currency semantics
    vix = next(b for b in benchmarks if b.benchmark_id == "VIX")
    assert vix.price == Decimal("15.75")
    assert vix.change == Decimal("-0.75")
    assert vix.currency == Currency.UNKNOWN
    assert vix.is_currency_priced is False


@pytest.mark.asyncio
async def test_get_market_movers_filtering_and_semantics(
    provider: YFinanceProvider,
) -> None:
    mock_quotes = [
        # Valid gainer
        {
            "symbol": "GOOD",
            "shortName": "Good Company",
            "regularMarketPrice": 50.00,
            "regularMarketChange": 5.00,
            "regularMarketChangePercent": 11.11,
            "regularMarketPreviousClose": 45.00,
            "regularMarketVolume": 250000,
            "marketCap": 1500000000,
            "exchange": "NMS",
        },
        # Missing volume: volume is None, marketCap is None -> MUST NOT DEFAULT VOLUME TO 0
        {
            "symbol": "NOVOL",
            "shortName": "No Volume Corp",
            "regularMarketPrice": 12.00,
            "regularMarketChange": 1.20,
            "regularMarketChangePercent": 11.11,
            "regularMarketPreviousClose": 10.80,
            "regularMarketVolume": None,
            "marketCap": None,
            "exchange": "NYQ",
        },
        # Filtered out: penny stock (price < $2.00)
        {
            "symbol": "PENNY",
            "shortName": "Penny Stock",
            "regularMarketPrice": 0.85,
            "regularMarketChange": 0.20,
            "regularMarketChangePercent": 30.77,
            "regularMarketPreviousClose": 0.65,
            "regularMarketVolume": 500000,
            "exchange": "NCM",
        },
        # Filtered out: low reported volume (< 100k)
        {
            "symbol": "LOWVOL",
            "shortName": "Low Volume Stock",
            "regularMarketPrice": 25.00,
            "regularMarketChange": 2.50,
            "regularMarketChangePercent": 11.11,
            "regularMarketPreviousClose": 22.50,
            "regularMarketVolume": 5000,
            "exchange": "NMS",
        },
    ]

    with patch("yfinance.screen", return_value={"quotes": mock_quotes}):
        movers = await provider.get_market_movers(MoverCategory.GAINERS, count=10)

    symbols = [m.ticker for m in movers]
    assert "GOOD" in symbols
    assert "NOVOL" in symbols
    assert "PENNY" not in symbols
    assert "LOWVOL" not in symbols

    # Check volume semantics
    novol_item = next(m for m in movers if m.ticker == "NOVOL")
    assert novol_item.volume is None
    assert novol_item.volume != 0
    assert novol_item.market_cap is None

    good_item = next(m for m in movers if m.ticker == "GOOD")
    assert good_item.volume == 250000
    assert good_item.market_cap == Decimal("1500000000")
