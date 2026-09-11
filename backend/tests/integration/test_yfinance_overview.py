"""
tests/integration/test_yfinance_overview.py
===========================================
Integration tests for YFinanceProvider market overview methods with real network calls.
Marked with @pytest.mark.integration.
"""

from decimal import Decimal

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


@pytest.mark.integration
async def test_live_market_status(provider: YFinanceProvider) -> None:
    status = await provider.get_market_status("US")
    assert status.region == "US"
    assert isinstance(status.session_state, MarketSessionState)
    assert status.is_indicative is True


@pytest.mark.integration
async def test_live_benchmarks(provider: YFinanceProvider) -> None:
    benchmarks = await provider.get_benchmarks()
    assert len(benchmarks) >= 5

    benchmark_map = {b.benchmark_id: b for b in benchmarks}
    assert "SP500" in benchmark_map
    assert "VIX" in benchmark_map

    sp500 = benchmark_map["SP500"]
    assert sp500.price > Decimal("0")
    assert sp500.is_currency_priced is True
    assert sp500.currency == Currency.USD

    vix = benchmark_map["VIX"]
    assert vix.price > Decimal("0")
    assert vix.is_currency_priced is False
    assert vix.currency == Currency.UNKNOWN


@pytest.mark.integration
async def test_live_market_movers(provider: YFinanceProvider) -> None:
    gainers = await provider.get_market_movers(MoverCategory.GAINERS, count=5)
    assert len(gainers) > 0
    for item in gainers:
        assert item.price > Decimal("0")
        assert item.category == MoverCategory.GAINERS
        if item.volume is not None:
            assert isinstance(item.volume, int)
        if item.market_cap is not None:
            assert isinstance(item.market_cap, Decimal)

    active = await provider.get_market_movers(MoverCategory.ACTIVE, count=5)
    assert len(active) > 0
    for item in active:
        assert item.price > Decimal("0")
        assert item.category == MoverCategory.ACTIVE
        if item.volume is not None:
            assert isinstance(item.volume, int)
