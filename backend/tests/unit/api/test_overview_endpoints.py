"""
tests/unit/api/test_overview_endpoints.py
=========================================
Unit tests for Market Overview API endpoints (/api/v1/market/overview,
/benchmarks, /movers, /status) using FastAPI dependency overrides.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from aurelius.api.main import create_app
from aurelius.domain.entities import (
    BenchmarkCategory,
    BenchmarkSnapshot,
    Currency,
    DataFreshness,
    MarketMoverItem,
    MarketOverviewSnapshot,
    MarketSessionState,
    MarketStatus,
    MoverCategory,
)
from aurelius.services.market_overview_service import (
    MarketOverviewService,
    get_market_overview_service,
)


class MockMarketOverviewService(MarketOverviewService):
    """
    Mock service returning predefined market overview data for endpoint testing.
    """

    def __init__(self) -> None:  # noqa: D107
        pass

    async def get_overview_snapshot(
        self, force_refresh: bool = False
    ) -> MarketOverviewSnapshot:
        now = datetime(2026, 9, 11, 18, 0, tzinfo=UTC)
        status = MarketStatus(
            region="US",
            session_state=MarketSessionState.REGULAR_OPEN,
            session_message="Regular trading session active.",
            is_indicative=True,
        )
        benchmarks = [
            BenchmarkSnapshot(
                benchmark_id="SP500",
                name="S&P 500 Index",
                category=BenchmarkCategory.LARGE_CAP_CORE,
                provider_ticker="^GSPC",
                price=Decimal("5600.25"),
                change=Decimal("25.50"),
                change_percent=Decimal("0.46"),
                currency=Currency.USD,
                is_currency_priced=True,
                provider="mock_provider",
                timestamp=now,
            ),
            BenchmarkSnapshot(
                benchmark_id="VIX",
                name="CBOE Volatility Index",
                category=BenchmarkCategory.VOLATILITY,
                provider_ticker="^VIX",
                price=Decimal("15.73"),
                change=Decimal("-0.82"),
                change_percent=Decimal("-4.95"),
                currency=Currency.UNKNOWN,
                is_currency_priced=False,
                provider="mock_provider",
                timestamp=now,
            ),
        ]
        gainers = [
            MarketMoverItem(
                ticker="NVDA",
                name="NVIDIA Corporation",
                price=Decimal("120.50"),
                change=Decimal("6.25"),
                change_percent=Decimal("5.47"),
                volume=45000000,
                market_cap=Decimal("2960000000000"),
                exchange="NMS",
                category=MoverCategory.GAINERS,
            ),
            # Missing volume item: volume is None
            MarketMoverItem(
                ticker="NOVOL",
                name="No Volume Corp",
                price=Decimal("10.00"),
                change=Decimal("1.00"),
                change_percent=Decimal("11.11"),
                volume=None,
                market_cap=None,
                exchange="NMS",
                category=MoverCategory.GAINERS,
            ),
        ]
        losers = [
            MarketMoverItem(
                ticker="INTC",
                name="Intel Corporation",
                price=Decimal("19.50"),
                change=Decimal("-1.25"),
                change_percent=Decimal("-6.02"),
                volume=30000000,
                market_cap=Decimal("83000000000"),
                exchange="NMS",
                category=MoverCategory.LOSERS,
            )
        ]
        active = [
            MarketMoverItem(
                ticker="NVDA",
                name="NVIDIA Corporation",
                price=Decimal("120.50"),
                change=Decimal("6.25"),
                change_percent=Decimal("5.47"),
                volume=45000000,
                market_cap=Decimal("2960000000000"),
                exchange="NMS",
                category=MoverCategory.ACTIVE,
            )
        ]

        return MarketOverviewSnapshot(
            market_status=status,
            benchmarks=benchmarks,
            gainers=gainers,
            losers=losers,
            active=active,
            fetched_at=now,
            freshness=DataFreshness.DELAYED,
            cached=not force_refresh,
            provider="mock_provider",
        )

    async def get_benchmarks(self) -> list[BenchmarkSnapshot]:
        snap = await self.get_overview_snapshot()
        return snap.benchmarks

    async def get_market_movers(self, category: MoverCategory) -> list[MarketMoverItem]:
        snap = await self.get_overview_snapshot()
        if category == MoverCategory.GAINERS:
            return snap.gainers
        if category == MoverCategory.LOSERS:
            return snap.losers
        return snap.active

    async def get_market_status(self) -> MarketStatus:
        snap = await self.get_overview_snapshot()
        return snap.market_status


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_market_overview_service] = lambda: (
        MockMarketOverviewService()
    )
    return TestClient(app)


def test_get_market_overview_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/market/overview")
    assert response.status_code == 200
    data = response.json()

    # Session Status
    status = data["market_status"]
    assert status["region"] == "US"
    assert status["session_state"] == "REGULAR_OPEN"
    assert status["is_indicative"] is True

    # Benchmarks
    benchmarks = data["benchmarks"]
    assert len(benchmarks) == 2
    sp500 = next(b for b in benchmarks if b["benchmark_id"] == "SP500")
    assert sp500["price"] == "5600.25"
    assert sp500["is_currency_priced"] is True

    vix = next(b for b in benchmarks if b["benchmark_id"] == "VIX")
    assert vix["price"] == "15.73"
    assert vix["is_currency_priced"] is False
    assert vix["currency"] == "UNKNOWN"

    # Movers
    gainers = data["gainers"]
    assert len(gainers) == 2
    nvda = next(g for g in gainers if g["ticker"] == "NVDA")
    assert nvda["volume"] == 45000000
    assert nvda["market_cap"] == "2960000000000"

    novol = next(g for g in gainers if g["ticker"] == "NOVOL")
    assert novol["volume"] is None
    assert novol["market_cap"] is None

    # Legitimate cross-category overlap
    active = data["active"]
    assert any(a["ticker"] == "NVDA" for a in active)

    assert data["cached"] is True
    assert data["freshness"] == "DELAYED"


def test_get_market_overview_force_refresh(client: TestClient) -> None:
    response = client.get("/api/v1/market/overview?force_refresh=true")
    assert response.status_code == 200
    data = response.json()
    assert data["cached"] is False


def test_get_benchmarks_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/market/benchmarks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert any(b["benchmark_id"] == "VIX" for b in data)


def test_get_movers_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/market/movers?category=LOSERS")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "INTC"


def test_get_status_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/market/status")
    assert response.status_code == 200
    data = response.json()
    assert data["session_state"] == "REGULAR_OPEN"
    assert data["region"] == "US"
