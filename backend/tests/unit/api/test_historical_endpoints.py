"""
tests/unit/api/test_historical_endpoints.py
===========================================
Unit tests for Historical Market Analysis endpoints:
  - GET /api/v1/market/history/{ticker}/analysis
  - GET /api/v1/market/history/{ticker}/metrics
using FastAPI dependency overrides.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from aurelius.api.main import create_app
from aurelius.domain.entities.historical import (
    BenchmarkComparison,
    DrawdownMetrics,
    HistoricalAnalysisSummary,
    HistoricalBarPoint,
    HistoricalExtremes,
    HistoricalTimeHorizon,
    ReturnMetrics,
    VolatilityMetrics,
)
from aurelius.services.historical_analysis_service import (
    HistoricalAnalysisService,
    get_historical_analysis_service,
)


def _build_mock_summary(
    ticker: str = "AAPL",
    horizon: HistoricalTimeHorizon = HistoricalTimeHorizon.ONE_YEAR,
):
    d1 = date(2023, 1, 3)
    d2 = date(2023, 1, 4)
    return HistoricalAnalysisSummary(
        ticker=ticker,
        horizon=horizon,
        start_date=d1,
        end_date=d2,
        calendar_days=1,
        trading_days=2,
        returns=ReturnMetrics(
            adjusted_price_return=Decimal("0.020000"),
            cagr=None,
            mean_daily_return=Decimal("0.02000000"),
            positive_days=1,
            negative_days=0,
            zero_days=0,
            win_rate=Decimal("1.0000"),
        ),
        volatility=VolatilityMetrics(
            daily_volatility=Decimal("0.015000"),
            annualized_volatility=Decimal("0.238118"),
            trading_days_assumed=252,
        ),
        drawdowns=DrawdownMetrics(
            max_drawdown=Decimal("-0.050000"),
            max_drawdown_peak_date=d1,
            max_drawdown_trough_date=d2,
            recovery_date=None,
            is_recovered=False,
            current_drawdown=Decimal("-0.050000"),
        ),
        extremes=HistoricalExtremes(
            period_high=Decimal("150.00"),
            period_high_date=d1,
            period_low=Decimal("140.00"),
            period_low_date=d2,
            distance_from_high=Decimal("-6.67"),
            distance_from_low=Decimal("0.00"),
        ),
        benchmark_comparison=BenchmarkComparison(
            benchmark_id="SP500",
            benchmark_name="S&P 500 Index",
            common_base_date=d1,
            security_return=Decimal("0.020000"),
            benchmark_return=Decimal("0.010000"),
            excess_return=Decimal("0.010000"),
            correlation=Decimal("0.8500"),
        ),
        series=[
            HistoricalBarPoint(
                date=d1,
                open=Decimal("148.00"),
                high=Decimal("150.00"),
                low=Decimal("147.00"),
                close=Decimal("149.00"),
                adj_close=Decimal("149.00"),
                volume=50000000,
                daily_return=None,
                cumulative_return=Decimal("0.000000"),
                drawdown=Decimal("0.000000"),
                sma_20=None,
                sma_50=None,
                sma_200=None,
                ema_20=None,
                rolling_vol_20=None,
                benchmark_cumulative_return=Decimal("0.000000"),
            ),
            HistoricalBarPoint(
                date=d2,
                open=Decimal("149.00"),
                high=Decimal("152.00"),
                low=Decimal("148.50"),
                close=Decimal("151.98"),
                adj_close=Decimal("151.98"),
                volume=52000000,
                daily_return=Decimal("0.020000"),
                cumulative_return=Decimal("0.020000"),
                drawdown=Decimal("0.000000"),
                sma_20=None,
                sma_50=None,
                sma_200=None,
                ema_20=None,
                rolling_vol_20=None,
                benchmark_cumulative_return=Decimal("0.010000"),
            ),
        ],
        provider="test_provider",
        fetched_at=datetime(2026, 9, 11, 18, 0, tzinfo=UTC),
    )


class MockHistoricalService(HistoricalAnalysisService):
    def __init__(self) -> None:
        pass

    async def analyze_security(
        self,
        ticker: str,
        horizon: HistoricalTimeHorizon = HistoricalTimeHorizon.ONE_YEAR,
        custom_start: date | None = None,
        custom_end: date | None = None,
        benchmark_ticker: str = "^GSPC",
        include_benchmark: bool = True,
        force_refresh: bool = False,
    ) -> HistoricalAnalysisSummary:
        return _build_mock_summary(ticker=ticker, horizon=horizon)


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_historical_analysis_service] = lambda: (
        MockHistoricalService()
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_historical_analysis_default(client: TestClient):
    response = client.get("/api/v1/market/history/AAPL/analysis")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["horizon"] == "1Y"
    assert "returns" in data
    assert data["returns"]["adjusted_price_return"] == "0.020000"
    assert "volatility" in data
    assert data["volatility"]["annualized_volatility"] == "0.238118"
    assert "drawdowns" in data
    assert data["drawdowns"]["max_drawdown"] == "-0.050000"
    assert "extremes" in data
    assert data["extremes"]["period_high"] == "150.00"
    assert "benchmark_comparison" in data
    assert data["benchmark_comparison"]["excess_return"] == "0.010000"
    assert len(data["series"]) == 2


def test_get_historical_analysis_horizon_param(client: TestClient):
    response = client.get("/api/v1/market/history/MSFT/analysis?horizon=6M")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "MSFT"
    assert data["horizon"] == "6M"


def test_get_historical_metrics(client: TestClient):
    response = client.get("/api/v1/market/history/AAPL/metrics?horizon=3M")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["horizon"] == "3M"
    assert "returns" in data
    assert "volatility" in data
    assert "drawdowns" in data
    assert "series" not in data  # Metrics-only endpoint omits bar series
