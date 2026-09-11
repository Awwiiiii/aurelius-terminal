"""
aurelius.services.market_overview_service
========================================
Service layer orchestrating market overview telemetry, canonical benchmark performance,
and market mover rankings with concurrency control and TTL caching.
"""

import asyncio
import logging
from datetime import UTC, datetime

from aurelius.domain.entities.market_overview import (
    BenchmarkSnapshot,
    DataFreshness,
    MarketMoverItem,
    MarketOverviewSnapshot,
    MarketSessionState,
    MarketStatus,
    MoverCategory,
)
from aurelius.providers.base import MarketDataProvider
from aurelius.providers.registry import get_market_data_provider

logger = logging.getLogger(__name__)


class MarketOverviewService:
    """
    Orchestrates market overview operations, providing in-memory TTL caching
    to protect downstream providers from rate-limiting during market-monitoring workflows.
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        cache_ttl_seconds: int = 60,
    ) -> None:
        self._provider = provider
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached_snapshot: MarketOverviewSnapshot | None = None
        self._cache_timestamp: datetime | None = None
        self._lock = asyncio.Lock()

    def _is_cache_valid(self) -> bool:
        if self._cached_snapshot is None or self._cache_timestamp is None:
            return False
        age = (datetime.now(UTC) - self._cache_timestamp).total_seconds()
        return age < self._cache_ttl_seconds

    async def get_overview_snapshot(
        self, force_refresh: bool = False
    ) -> MarketOverviewSnapshot:
        """
        Retrieve complete market overview snapshot. Serves from cache if age < TTL,
        unless force_refresh is requested.
        """
        if not force_refresh and self._is_cache_valid():
            assert self._cached_snapshot is not None
            return self._cached_snapshot.model_copy(update={"cached": True})

        async with self._lock:
            # Double-check inside lock
            if not force_refresh and self._is_cache_valid():
                assert self._cached_snapshot is not None
                return self._cached_snapshot.model_copy(update={"cached": True})

            logger.info(
                "Fetching fresh market overview snapshot from provider: %s",
                self._provider.name,
            )

            # Concurrent retrieval of telemetry, benchmarks, and movers
            status_task = self._provider.get_market_status("US")
            benchmarks_task = self._provider.get_benchmarks()
            gainers_task = self._provider.get_market_movers(
                MoverCategory.GAINERS, count=10
            )
            losers_task = self._provider.get_market_movers(
                MoverCategory.LOSERS, count=10
            )
            active_task = self._provider.get_market_movers(
                MoverCategory.ACTIVE, count=10
            )

            results = await asyncio.gather(
                status_task,
                benchmarks_task,
                gainers_task,
                losers_task,
                active_task,
                return_exceptions=True,
            )

            status_res, bench_res, gainers_res, losers_res, active_res = results

            # Safe handling of individual component failures
            if isinstance(status_res, Exception):
                logger.error("Failed to fetch market status: %s", status_res)
                market_status = MarketStatus(
                    region="US",
                    session_state=MarketSessionState.UNKNOWN,
                    session_message="Market session telemetry unavailable.",
                    is_indicative=True,
                )
            else:
                market_status = status_res

            benchmarks: list[BenchmarkSnapshot] = []
            if isinstance(bench_res, Exception):
                logger.error("Failed to fetch benchmarks: %s", bench_res)
            else:
                benchmarks = bench_res

            gainers: list[MarketMoverItem] = []
            if isinstance(gainers_res, Exception):
                logger.error("Failed to fetch gainers: %s", gainers_res)
            else:
                gainers = gainers_res

            losers: list[MarketMoverItem] = []
            if isinstance(losers_res, Exception):
                logger.error("Failed to fetch losers: %s", losers_res)
            else:
                losers = losers_res

            active: list[MarketMoverItem] = []
            if isinstance(active_res, Exception):
                logger.error("Failed to fetch active: %s", active_res)
            else:
                active = active_res

            now = datetime.now(UTC)
            snapshot = MarketOverviewSnapshot(
                market_status=market_status,
                benchmarks=benchmarks,
                gainers=gainers,
                losers=losers,
                active=active,
                fetched_at=now,
                freshness=DataFreshness.DELAYED,
                cached=False,
                provider=self._provider.name,
            )

            self._cached_snapshot = snapshot
            self._cache_timestamp = now
            return snapshot

    async def get_benchmarks(self) -> list[BenchmarkSnapshot]:
        """
        Get canonical benchmarks, pulling from cache if valid.
        """
        snapshot = await self.get_overview_snapshot()
        return snapshot.benchmarks

    async def get_market_movers(self, category: MoverCategory) -> list[MarketMoverItem]:
        """
        Get movers by category, pulling from cache if valid.
        """
        snapshot = await self.get_overview_snapshot()
        if category == MoverCategory.GAINERS:
            return snapshot.gainers
        if category == MoverCategory.LOSERS:
            return snapshot.losers
        return snapshot.active

    async def get_market_status(self) -> MarketStatus:
        """
        Get market status, pulling from cache if valid.
        """
        snapshot = await self.get_overview_snapshot()
        return snapshot.market_status


_service_instance: MarketOverviewService | None = None


def get_market_overview_service() -> MarketOverviewService:
    """
    FastAPI dependency returning shared singleton instance of MarketOverviewService.
    """
    global _service_instance
    if _service_instance is None:
        provider = get_market_data_provider()
        _service_instance = MarketOverviewService(provider=provider)
    return _service_instance


def reset_market_overview_service() -> None:
    """
    Reset singleton instance (useful for testing).
    """
    global _service_instance
    _service_instance = None
