"""
tests.unit.api.test_search_endpoints
====================================
Unit tests for search and company/security detail endpoints:
  - GET /api/v1/market/search
  - GET /api/v1/market/security/{ticker}
  - GET /api/v1/market/company/{ticker}
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aurelius.api.main import create_app
from aurelius.domain.entities import (
    AssetType,
    BenchmarkSnapshot,
    CompanyProfile,
    Currency,
    MarketInterval,
    MarketMoverItem,
    MarketSessionState,
    MarketState,
    MarketStatus,
    MoverCategory,
    OHLCVBar,
    OHLCVSeries,
    Quote,
    Security,
    SecuritySearchResult,
)
from aurelius.domain.errors import DataNotFoundError
from aurelius.domain.validation import validate_search_query, validate_ticker
from aurelius.providers.base import MarketDataProvider
from aurelius.providers.registry import get_market_data_provider


class MockSearchMarketDataProvider(MarketDataProvider):
    """Mock provider with search and company profile support."""

    @property
    def name(self) -> str:
        return "mock_provider"

    async def get_quote(self, ticker: str) -> Quote:
        norm = validate_ticker(ticker)
        return Quote(
            ticker=norm,
            price=Decimal("150.00"),
            timestamp=datetime.now(UTC),
            currency=Currency.USD,
            market_state=MarketState.REGULAR,
            provider=self.name,
            is_delayed=True,
        )

    async def get_historical_bars(
        self,
        ticker: str,
        start: date,
        end: date,
        interval: MarketInterval = MarketInterval.DAILY,
    ) -> OHLCVSeries:
        norm = validate_ticker(ticker)
        return OHLCVSeries(
            ticker=norm,
            interval=MarketInterval.DAILY,
            bars=[
                OHLCVBar(
                    timestamp=start,
                    open=Decimal("100"),
                    high=Decimal("110"),
                    low=Decimal("95"),
                    close=Decimal("105"),
                    volume=1000,
                )
            ],
            provider=self.name,
        )

    async def get_security(self, ticker: str) -> Security:
        norm = validate_ticker(ticker)
        if norm == "NOTFOUND":
            raise DataNotFoundError("Security not found", ticker=norm)
        if norm == "SPY":
            return Security(
                ticker="SPY",
                name="SPDR S&P 500 ETF Trust",
                asset_type=AssetType.ETF,
                currency=Currency.USD,
                exchange="PCX",
                exchange_display="NYSE Arca",
                timezone="America/New_York",
                provider=self.name,
                fetched_at=datetime.now(UTC),
            )
        if norm == "^GSPC":
            return Security(
                ticker="^GSPC",
                name="S&P 500",
                asset_type=AssetType.INDEX,
                currency=Currency.UNKNOWN,
                exchange="SNP",
                exchange_display="S&P Indices",
                timezone="America/New_York",
                provider=self.name,
                fetched_at=datetime.now(UTC),
            )
        return Security(
            ticker=norm,
            name="Apple Inc.",
            asset_type=AssetType.EQUITY,
            currency=Currency.USD,
            exchange="NMS",
            exchange_display="NASDAQ",
            timezone="America/New_York",
            country="United States",
            sector="Technology",
            industry="Consumer Electronics",
            provider=self.name,
            fetched_at=datetime.now(UTC),
        )

    async def search_securities(
        self, query: str, limit: int = 10
    ) -> list[SecuritySearchResult]:
        cleaned = validate_search_query(query)
        if "empty" in cleaned.lower():
            return []
        return [
            SecuritySearchResult(
                ticker="AAPL",
                name="Apple Inc.",
                exchange="NMS",
                exchange_display="NASDAQ",
                asset_type=AssetType.EQUITY,
                currency=Currency.USD,
                provider=self.name,
            ),
            SecuritySearchResult(
                ticker="SPY",
                name="SPDR S&P 500 ETF Trust",
                exchange="PCX",
                exchange_display="NYSE Arca",
                asset_type=AssetType.ETF,
                currency=Currency.USD,
                provider=self.name,
            ),
        ]

    async def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        norm = validate_ticker(ticker)
        if norm in ("SPY", "^GSPC"):
            return None
        if norm == "NOTFOUND":
            raise DataNotFoundError("Security not found", ticker=norm)
        return CompanyProfile(
            lookup_ticker=norm,
            company_name="Apple Inc.",
            description="Designs, manufactures, and markets consumer technology.",
            sector="Technology",
            industry="Consumer Electronics",
            country="United States",
            city="Cupertino",
            state="California",
            website="https://www.apple.com",
            employees=161000,
            provider=self.name,
            fetched_at=datetime.now(UTC),
        )

    async def get_market_status(self, region: str = "US") -> MarketStatus:
        return MarketStatus(
            region=region,
            session_state=MarketSessionState.REGULAR_OPEN,
            is_indicative=True,
        )

    async def get_benchmarks(
        self, benchmark_ids: list[str] | None = None
    ) -> list[BenchmarkSnapshot]:
        return []

    async def get_market_movers(
        self, category: MoverCategory, count: int = 10
    ) -> list[MarketMoverItem]:
        return []


@pytest.fixture
def client() -> Any:
    app = create_app()
    mock_provider = MockSearchMarketDataProvider()
    app.dependency_overrides[get_market_data_provider] = lambda: mock_provider
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_search_securities_success(client: TestClient) -> None:
    response = client.get("/api/v1/market/search?q=Apple")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Apple"
    assert data["count"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["ticker"] == "AAPL"
    assert data["results"][0]["asset_type"] == "EQUITY"
    assert data["results"][0]["exchange_display"] == "NASDAQ"


def test_search_securities_with_spaces(client: TestClient) -> None:
    # Space in query must be accepted
    response = client.get("/api/v1/market/search?q=Apple Inc.")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Apple Inc."
    assert data["count"] >= 1


def test_search_securities_invalid_query_symbols(client: TestClient) -> None:
    # Query with script tags should fail domain validation
    response = client.get("/api/v1/market/search?q=<script>")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "INVALID_SEARCH_QUERY"


def test_get_security_detail_equity(client: TestClient) -> None:
    response = client.get("/api/v1/market/security/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["security"]["ticker"] == "AAPL"
    assert data["security"]["asset_type"] == "EQUITY"
    assert data["security"]["timezone"] == "America/New_York"
    assert data["is_operating_company"] is True
    assert data["company_profile"] is not None
    assert data["company_profile"]["company_name"] == "Apple Inc."
    assert data["company_profile"]["sector"] == "Technology"
    assert data["company_profile"]["employees"] == 161000


def test_get_security_detail_etf_polymorphic(client: TestClient) -> None:
    # Non-corporate instrument must return 200 OK cleanly with company_profile: null
    response = client.get("/api/v1/market/security/SPY")
    assert response.status_code == 200
    data = response.json()
    assert data["security"]["ticker"] == "SPY"
    assert data["security"]["asset_type"] == "ETF"
    assert data["is_operating_company"] is False
    assert data["company_profile"] is None


def test_get_security_detail_index_special_ticker(client: TestClient) -> None:
    # Caret ticker for indices must be accepted cleanly
    response = client.get("/api/v1/market/security/^GSPC")
    assert response.status_code == 200
    data = response.json()
    assert data["security"]["ticker"] == "^GSPC"
    assert data["security"]["asset_type"] == "INDEX"
    assert data["is_operating_company"] is False
    assert data["company_profile"] is None


def test_get_company_profile_corporate_success(client: TestClient) -> None:
    response = client.get("/api/v1/market/company/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["is_operating_company"] is True
    assert data["company_profile"] is not None
    assert data["company_profile"]["lookup_ticker"] == "AAPL"
    assert data["message"] is None


def test_get_company_profile_non_corporate_etf(client: TestClient) -> None:
    # Must NOT 404 for ETFs! Returns 200 OK with company_profile: null and explanatory message
    response = client.get("/api/v1/market/company/SPY")
    assert response.status_code == 200
    data = response.json()
    assert data["is_operating_company"] is False
    assert data["company_profile"] is None
    assert "not an operating company" in data["message"]


def test_get_security_invalid_ticker(client: TestClient) -> None:
    response = client.get("/api/v1/market/security/BAD$$TICKER")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "INVALID_TICKER"


def test_get_security_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/market/security/NOTFOUND")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "DATA_NOT_FOUND"
