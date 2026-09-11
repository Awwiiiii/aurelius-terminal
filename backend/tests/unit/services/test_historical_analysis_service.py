"""
Unit tests for HistoricalAnalysisService:
- Horizon date resolution
- Mock provider data analysis
- Warm-up and indicator calculations
- Caching and cache invalidation
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from aurelius.domain.entities.enums import MarketInterval
from aurelius.domain.entities.historical import HistoricalTimeHorizon
from aurelius.domain.entities.ohlcv import OHLCVBar, OHLCVSeries
from aurelius.services.historical_analysis_service import HistoricalAnalysisService


def _create_mock_bars(ticker: str, start_dt: date, num_days: int) -> list[OHLCVBar]:
    bars = []
    curr = start_dt
    for i in range(num_days):
        # Skip weekends to simulate trading sessions
        while curr.weekday() >= 5:
            curr += timedelta(days=1)
        price = Decimal(str(100 + i))
        bars.append(
            OHLCVBar(
                timestamp=curr,
                open=price,
                high=price + Decimal("1.0"),
                low=price - Decimal("1.0"),
                close=price,
                adj_close=price,
                volume=1000000 + i * 1000,
            )
        )
        curr += timedelta(days=1)
    return bars


def test_horizon_date_resolution():
    as_of = date(2023, 6, 15)

    s, e = HistoricalAnalysisService.resolve_horizon_dates(
        HistoricalTimeHorizon.ONE_MONTH, as_of_date=as_of
    )
    assert e == as_of
    assert s == as_of - timedelta(days=30)

    s, e = HistoricalAnalysisService.resolve_horizon_dates(
        HistoricalTimeHorizon.YEAR_TO_DATE, as_of_date=as_of
    )
    assert s == date(2023, 1, 1)

    s, e = HistoricalAnalysisService.resolve_horizon_dates(
        HistoricalTimeHorizon.CUSTOM,
        custom_start=date(2022, 1, 1),
        custom_end=date(2022, 12, 31),
        as_of_date=as_of,
    )
    assert s == date(2022, 1, 1)
    assert e == date(2022, 12, 31)

    with pytest.raises(ValueError, match="Custom horizon requires"):
        HistoricalAnalysisService.resolve_horizon_dates(HistoricalTimeHorizon.CUSTOM)

    with pytest.raises(ValueError, match="cannot be after"):
        HistoricalAnalysisService.resolve_horizon_dates(
            HistoricalTimeHorizon.CUSTOM,
            custom_start=date(2023, 1, 2),
            custom_end=date(2023, 1, 1),
        )


@pytest.mark.asyncio
async def test_service_analyze_security_with_mock_provider():
    provider = AsyncMock()
    provider.name = "mock_provider"

    # Generate 100 bars
    bars = _create_mock_bars("AAPL", date(2023, 1, 1), 100)
    series = OHLCVSeries(
        ticker="AAPL",
        interval=MarketInterval.DAILY,
        bars=bars,
        is_adjusted=True,
        provider="mock_provider",
    )

    bmk_bars = _create_mock_bars("^GSPC", date(2023, 1, 1), 100)
    bmk_series = OHLCVSeries(
        ticker="^GSPC",
        interval=MarketInterval.DAILY,
        bars=bmk_bars,
        is_adjusted=True,
        provider="mock_provider",
    )

    async def get_bars_mock(ticker, start, end, interval):
        if ticker == "AAPL":
            return series
        return bmk_series

    provider.get_historical_bars.side_effect = get_bars_mock

    service = HistoricalAnalysisService(provider=provider, cache_ttl_seconds=300)

    summary = await service.analyze_security(
        ticker="AAPL",
        horizon=HistoricalTimeHorizon.ONE_MONTH,
        include_benchmark=True,
    )

    assert summary.ticker == "AAPL"
    assert summary.horizon == HistoricalTimeHorizon.ONE_MONTH
    assert len(summary.series) > 0
    assert summary.returns.adjusted_price_return is not None
    assert summary.volatility.daily_volatility is not None
    assert summary.drawdowns.max_drawdown is not None
    assert summary.extremes.period_high is not None
    assert summary.benchmark_comparison is not None
    assert summary.provider == "mock_provider"

    # Check caching: subsequent call shouldn't call provider again
    call_count = provider.get_historical_bars.call_count
    cached_summary = await service.analyze_security(
        ticker="AAPL",
        horizon=HistoricalTimeHorizon.ONE_MONTH,
        include_benchmark=True,
    )
    assert provider.get_historical_bars.call_count == call_count
    assert cached_summary.ticker == summary.ticker
