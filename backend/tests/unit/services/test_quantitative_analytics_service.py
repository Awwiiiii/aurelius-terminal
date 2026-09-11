"""
tests/unit/services/test_quantitative_analytics_service.py
==========================================================
Unit tests for QuantitativeAnalyticsService:
  - Single-asset empirical return distribution
  - Multi-asset inner alignment and correlation matrix
  - Rolling metric calculations
  - Cache hit and bypass behavior
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from aurelius.domain.entities.enums import MarketInterval
from aurelius.domain.entities.historical import HistoricalTimeHorizon
from aurelius.domain.entities.ohlcv import OHLCVBar, OHLCVSeries
from aurelius.services.quantitative_analytics_service import (
    QuantitativeAnalyticsService,
)


def _generate_mock_bars(
    symbol: str,
    start_dt: date,
    num_days: int,
    start_price: float = 100.0,
    step: float = 1.0,
) -> list[OHLCVBar]:
    bars = []
    curr = start_dt
    for i in range(num_days):
        while curr.weekday() >= 5:
            curr += timedelta(days=1)
        p = Decimal(str(round(start_price + (i * step), 4)))
        bars.append(
            OHLCVBar(
                timestamp=curr,
                open=p,
                high=p + Decimal("0.5"),
                low=p - Decimal("0.5"),
                close=p,
                adj_close=p,
                volume=50000,
            )
        )
        curr += timedelta(days=1)
    return bars


@pytest.mark.asyncio
async def test_get_return_distribution_service():
    mock_provider = AsyncMock()
    bars = _generate_mock_bars("AAPL", date(2023, 1, 1), 60)
    mock_provider.get_historical_bars.return_value = OHLCVSeries(
        ticker="AAPL",
        provider="mock",
        interval=MarketInterval.DAILY,
        bars=bars,
    )

    service = QuantitativeAnalyticsService(provider=mock_provider, cache_ttl_seconds=60)
    summary = await service.get_return_distribution(
        ticker="AAPL",
        horizon=HistoricalTimeHorizon.CUSTOM,
        custom_start=date(2023, 1, 5),
        custom_end=date(2023, 3, 20),
        return_type="SIMPLE",
    )

    assert summary.ticker == "AAPL"
    assert summary.sample_size > 0
    assert summary.statistics.mean is not None
    assert summary.statistics.median is not None
    assert len(summary.histogram) > 0

    # Cache hit test
    summary_cached = await service.get_return_distribution(
        ticker="AAPL",
        horizon=HistoricalTimeHorizon.CUSTOM,
        custom_start=date(2023, 1, 5),
        custom_end=date(2023, 3, 20),
        return_type="SIMPLE",
    )
    assert mock_provider.get_historical_bars.call_count == 1
    assert summary_cached == summary

    # Force refresh bypasses cache
    await service.get_return_distribution(
        ticker="AAPL",
        horizon=HistoricalTimeHorizon.CUSTOM,
        custom_start=date(2023, 1, 5),
        custom_end=date(2023, 3, 20),
        return_type="SIMPLE",
        force_refresh=True,
    )
    assert mock_provider.get_historical_bars.call_count == 2


@pytest.mark.asyncio
async def test_compare_assets_service():
    mock_provider = AsyncMock()
    bars_a = _generate_mock_bars(
        "AAPL", date(2023, 1, 1), 50, start_price=150.0, step=1.0
    )
    bars_b = _generate_mock_bars(
        "MSFT", date(2023, 1, 1), 50, start_price=300.0, step=2.0
    )

    async def _mock_fetch(symbol, **kwargs):
        if symbol == "AAPL":
            return OHLCVSeries(
                ticker="AAPL",
                provider="mock",
                interval=MarketInterval.DAILY,
                bars=bars_a,
            )
        return OHLCVSeries(
            ticker="MSFT", provider="mock", interval=MarketInterval.DAILY, bars=bars_b
        )

    mock_provider.get_historical_bars.side_effect = _mock_fetch
    service = QuantitativeAnalyticsService(provider=mock_provider)

    res = await service.compare_assets(
        tickers=["AAPL", "MSFT"],
        horizon=HistoricalTimeHorizon.CUSTOM,
        custom_start=date(2023, 1, 5),
        custom_end=date(2023, 3, 10),
    )

    assert res.tickers == ["AAPL", "MSFT"]
    assert len(res.correlation_matrix) == 2
    assert res.correlation_matrix[0][0] == Decimal("1.0000")
    assert res.correlation_matrix[1][1] == Decimal("1.0000")
    assert res.common_dates_count > 0


@pytest.mark.asyncio
async def test_get_rolling_series_service():
    mock_provider = AsyncMock()
    bars = _generate_mock_bars(
        "AAPL", date(2023, 1, 1), 80, start_price=150.0, step=0.5
    )
    mock_provider.get_historical_bars.return_value = OHLCVSeries(
        ticker="AAPL",
        provider="mock",
        interval=MarketInterval.DAILY,
        bars=bars,
    )

    service = QuantitativeAnalyticsService(provider=mock_provider)
    rolling = await service.get_rolling_series(
        ticker_a="AAPL",
        metric="VOLATILITY",
        window=20,
        horizon=HistoricalTimeHorizon.CUSTOM,
        custom_start=date(2023, 2, 1),
        custom_end=date(2023, 4, 1),
    )

    assert rolling.ticker_a == "AAPL"
    assert rolling.metric_name == "VOLATILITY"
    assert rolling.window == 20
    assert len(rolling.series) > 0
