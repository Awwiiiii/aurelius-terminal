"""
tests/unit/services/test_market_overview_service.py
==================================================
Unit tests for MarketOverviewService caching, concurrency lock, and partial failure handling.
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from aurelius.domain.entities import (
    BenchmarkCategory,
    BenchmarkSnapshot,
    Currency,
    MarketMoverItem,
    MarketSessionState,
    MarketStatus,
    MoverCategory,
)
from aurelius.providers.base import MarketDataProvider
from aurelius.services.market_overview_service import MarketOverviewService


@pytest.fixture
def mock_provider() -> MagicMock:
    provider = MagicMock(spec=MarketDataProvider)
    provider.name = "mock_provider"

    # Default mock returns
    provider.get_market_status = AsyncMock(
        return_value=MarketStatus(
            region="US",
            session_state=MarketSessionState.REGULAR_OPEN,
            session_message="Regular session",
            is_indicative=True,
        )
    )
    provider.get_benchmarks = AsyncMock(
        return_value=[
            BenchmarkSnapshot(
                benchmark_id="SP500",
                name="S&P 500 Index",
                category=BenchmarkCategory.LARGE_CAP_CORE,
                provider_ticker="^GSPC",
                price=Decimal("5600.00"),
                change=Decimal("10.00"),
                change_percent=Decimal("0.18"),
                currency=Currency.USD,
                is_currency_priced=True,
                provider="mock_provider",
                timestamp=datetime.now(UTC),
            )
        ]
    )
    provider.get_market_movers = AsyncMock(
        return_value=[
            MarketMoverItem(
                ticker="TEST",
                name="Test Corp",
                price=Decimal("100.00"),
                change=Decimal("5.00"),
                change_percent=Decimal("5.26"),
                volume=1000000,
                market_cap=Decimal("10000000000"),
                category=MoverCategory.GAINERS,
            )
        ]
    )
    return provider


@pytest.mark.asyncio
async def test_cache_hit_and_ttl(mock_provider: MagicMock) -> None:
    service = MarketOverviewService(provider=mock_provider, cache_ttl_seconds=60)

    # First call: cache miss
    snap1 = await service.get_overview_snapshot()
    assert snap1.cached is False
    assert mock_provider.get_market_status.call_count == 1
    assert mock_provider.get_benchmarks.call_count == 1

    # Second call: cache hit
    snap2 = await service.get_overview_snapshot()
    assert snap2.cached is True
    assert mock_provider.get_market_status.call_count == 1
    assert mock_provider.get_benchmarks.call_count == 1


@pytest.mark.asyncio
async def test_force_refresh(mock_provider: MagicMock) -> None:
    service = MarketOverviewService(provider=mock_provider, cache_ttl_seconds=60)

    # First call: cache miss
    snap1 = await service.get_overview_snapshot()
    assert snap1.cached is False

    # Second call with force_refresh: cache bypassed
    snap2 = await service.get_overview_snapshot(force_refresh=True)
    assert snap2.cached is False
    assert mock_provider.get_market_status.call_count == 2


@pytest.mark.asyncio
async def test_concurrency_cache_stampede(mock_provider: MagicMock) -> None:
    service = MarketOverviewService(provider=mock_provider, cache_ttl_seconds=60)

    # Launch 5 concurrent requests
    results = await asyncio.gather(*[service.get_overview_snapshot() for _ in range(5)])

    assert len(results) == 5
    # The provider should only have been called once due to lock
    assert mock_provider.get_market_status.call_count == 1
    assert mock_provider.get_benchmarks.call_count == 1


@pytest.mark.asyncio
async def test_partial_failure_resilience(mock_provider: MagicMock) -> None:
    # Status and movers fail with exceptions
    mock_provider.get_market_status = AsyncMock(
        side_effect=RuntimeError("Status API failed")
    )
    mock_provider.get_market_movers = AsyncMock(
        side_effect=RuntimeError("Movers API failed")
    )

    service = MarketOverviewService(provider=mock_provider, cache_ttl_seconds=60)
    snap = await service.get_overview_snapshot()

    # Should not crash; status falls back to UNKNOWN and movers default to empty lists
    assert snap.market_status.session_state == MarketSessionState.UNKNOWN
    assert snap.gainers == []
    assert snap.losers == []
    assert snap.active == []
    assert len(snap.benchmarks) == 1
