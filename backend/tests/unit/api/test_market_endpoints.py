"""
tests/unit/api/test_market_endpoints.py
=======================================
Unit tests for Market Data API endpoints (/api/v1/market/*) using dependency overrides.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aurelius.api.main import create_app
from aurelius.domain.entities import (
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
from aurelius.domain.errors import (
    DataNotFoundError,
    DataQualityError,
    InvalidTickerError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from aurelius.providers.base import MarketDataProvider
from aurelius.providers.registry import get_market_data_provider


class MockMarketDataProvider(MarketDataProvider):
    """
    Mock provider for isolated API endpoint testing.
    """

    @property
    def name(self) -> str:
        return "mock_provider"

    async def get_quote(self, ticker: str) -> Quote:
        if ticker == "INVALID":
            raise InvalidTickerError("Invalid ticker symbol", ticker=ticker)
        if ticker == "NOTFOUND":
            raise DataNotFoundError("Ticker not found", ticker=ticker)
        if ticker == "RATELIMIT":
            raise ProviderRateLimitError(
                "Rate limit exceeded", provider=self.name, ticker=ticker
            )
        if ticker == "UNAVAILABLE":
            raise ProviderUnavailableError(
                "Provider offline", provider=self.name, ticker=ticker
            )
        if ticker == "BADQUALITY":
            raise DataQualityError(
                "Invalid quote price", check="positive_price", ticker=ticker
            )

        return Quote(
            ticker=ticker,
            price=Decimal("185.64"),
            timestamp=datetime(2024, 1, 2, 16, 0, tzinfo=UTC),
            currency=Currency.USD,
            change=Decimal("-0.40"),
            change_percent=Decimal("-0.21"),
            volume=82488700,
            open=Decimal("187.15"),
            high=Decimal("188.44"),
            low=Decimal("183.89"),
            previous_close=Decimal("186.04"),
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
        if ticker == "NOTFOUND":
            raise DataNotFoundError("No historical data found", ticker=ticker)
        if start > end:
            raise DataQualityError(
                "Start date cannot be after end date",
                check="start_date_lte_end_date",
                ticker=ticker,
            )

        bars = [
            OHLCVBar(
                timestamp=start,
                open=Decimal("187.15"),
                high=Decimal("188.44"),
                low=Decimal("183.89"),
                close=Decimal("185.64"),
                volume=82488700,
                adj_close=Decimal("184.25"),
            )
        ]
        return OHLCVSeries(
            ticker=ticker,
            interval=interval,
            bars=bars,
            provider=self.name,
            is_adjusted=True,
        )

    async def get_security(self, ticker: str) -> Security:
        return Security(
            ticker=ticker,
            name="Mock Company",
            currency=Currency.USD,
            provider=self.name,
            fetched_at=datetime.now(UTC),
        )

    async def search_securities(
        self, query: str, limit: int = 10
    ) -> list[SecuritySearchResult]:
        return [
            SecuritySearchResult(
                ticker="AAPL",
                name="Apple Inc.",
                exchange="NASDAQ",
                exchange_display="NASDAQ",
                provider=self.name,
            )
        ]

    async def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        if ticker == "SPY":
            return None
        return CompanyProfile(
            lookup_ticker=ticker,
            company_name="Mock Company Inc.",
            description="A mock company description.",
            sector="Technology",
            industry="Consumer Electronics",
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
    mock_provider = MockMarketDataProvider()
    app.dependency_overrides[get_market_data_provider] = lambda: mock_provider
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_quote_success(client: TestClient) -> None:
    response = client.get("/api/v1/market/quote/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["price"] == "185.64"
    assert data["change"] == "-0.40"
    assert data["change_percent"] == "-0.21"
    assert data["volume"] == 82488700
    assert data["provider"] == "mock_provider"
    assert data["is_delayed"] is True


def test_get_quote_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/market/quote/NOTFOUND")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "DATA_NOT_FOUND"


def test_get_quote_rate_limit(client: TestClient) -> None:
    response = client.get("/api/v1/market/quote/RATELIMIT")
    assert response.status_code == 429
    data = response.json()
    assert data["error"] == "PROVIDER_RATE_LIMIT"


def test_get_quote_provider_unavailable(client: TestClient) -> None:
    response = client.get("/api/v1/market/quote/UNAVAILABLE")
    assert response.status_code == 503
    data = response.json()
    assert data["error"] == "PROVIDER_UNAVAILABLE"


def test_get_quote_data_quality_failure(client: TestClient) -> None:
    response = client.get("/api/v1/market/quote/BADQUALITY")
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "DATA_QUALITY_FAILURE"


def test_get_ohlcv_success(client: TestClient) -> None:
    response = client.get("/api/v1/market/ohlcv/AAPL?start=2024-01-02&end=2024-01-04")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["interval"] == "1d"
    assert data["is_adjusted"] is True
    assert len(data["bars"]) == 1
    bar = data["bars"][0]
    assert bar["timestamp"] == "2024-01-02"
    assert bar["open"] == "187.15"
    assert bar["high"] == "188.44"
    assert bar["low"] == "183.89"
    assert bar["close"] == "185.64"
    assert bar["volume"] == 82488700
    assert bar["adj_close"] == "184.25"


def test_get_ohlcv_missing_required_params(client: TestClient) -> None:
    response = client.get("/api/v1/market/ohlcv/AAPL")
    # Missing start and end date query params
    assert response.status_code == 422


def test_get_ohlcv_date_order_failure(client: TestClient) -> None:
    # start > end triggers DataQualityError
    response = client.get("/api/v1/market/ohlcv/AAPL?start=2024-01-10&end=2024-01-02")
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "DATA_QUALITY_FAILURE"
