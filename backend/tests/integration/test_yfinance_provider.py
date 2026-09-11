"""
tests/integration/test_yfinance_provider.py
===========================================
Integration tests for YFinanceProvider with real network calls.

Marked with @pytest.mark.integration so they can be run selectively.
Uses documented historical dates rather than current intraday prices.
"""

from datetime import date
from decimal import Decimal

import pytest

from aurelius.domain.entities import MarketInterval
from aurelius.domain.errors import DataNotFoundError, InvalidTickerError
from aurelius.providers.yfinance_provider import YFinanceProvider


@pytest.mark.integration
async def test_yfinance_fetch_historical_known_value() -> None:
    provider = YFinanceProvider()
    # 2024-01-02 is a fixed historical US trading day for AAPL
    start = date(2024, 1, 2)
    end = date(2024, 1, 2)

    series = await provider.get_historical_bars(
        "AAPL", start=start, end=end, interval=MarketInterval.DAILY
    )

    assert series.ticker == "AAPL"
    assert series.interval == MarketInterval.DAILY
    assert len(series.bars) >= 1

    bar = series.bars[0]
    assert bar.timestamp == start
    # Historical known close for AAPL on 2024-01-02 is ~185.64
    assert Decimal("180.00") <= bar.close <= Decimal("190.00")
    assert bar.high >= bar.low
    assert bar.high >= bar.open
    assert bar.high >= bar.close
    assert bar.low <= bar.open
    assert bar.low <= bar.close
    assert isinstance(bar.volume, int)
    assert bar.volume > 0
    assert bar.adj_close is not None
    assert bar.adj_close > Decimal("0")


@pytest.mark.integration
async def test_yfinance_fetch_quote() -> None:
    provider = YFinanceProvider()
    quote = await provider.get_quote("MSFT")

    assert quote.ticker == "MSFT"
    assert quote.price > Decimal("0")
    assert quote.provider == "yahoo_finance"
    if quote.volume is not None:
        assert isinstance(quote.volume, int)
        assert quote.volume >= 0


@pytest.mark.integration
async def test_yfinance_invalid_ticker() -> None:
    provider = YFinanceProvider()
    with pytest.raises(InvalidTickerError):
        await provider.get_quote("INVALID$$TICKER")


@pytest.mark.integration
async def test_yfinance_nonexistent_ticker() -> None:
    provider = YFinanceProvider()
    # Ticker format valid, but security doesn't exist
    with pytest.raises(DataNotFoundError):
        await provider.get_historical_bars(
            "ZZZZ",
            start=date(2024, 1, 2),
            end=date(2024, 1, 5),
        )
