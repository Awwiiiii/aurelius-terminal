"""
tests/unit/api/test_quantitative_endpoints.py
=============================================
Unit tests for quantitative analytics endpoints:
  - GET /api/v1/analytics/distribution/{ticker}
  - GET /api/v1/analytics/compare
  - GET /api/v1/analytics/rolling
using FastAPI dependency overrides.
"""

from datetime import date
from decimal import Decimal
from typing import Literal

import pytest
from fastapi.testclient import TestClient

from aurelius.api.main import create_app
from aurelius.domain.entities.historical import HistoricalTimeHorizon
from aurelius.domain.entities.quantitative import (
    DescriptiveStatistics,
    HistogramBin,
    MultiAssetCorrelationMatrix,
    QuantileDistribution,
    ReturnDistributionSummary,
    RollingQuantitativeSeries,
    RollingStatisticPoint,
)
from aurelius.services.quantitative_analytics_service import (
    QuantitativeAnalyticsService,
    get_quantitative_analytics_service,
)


def _build_mock_distribution(ticker: str = "AAPL") -> ReturnDistributionSummary:
    stats = DescriptiveStatistics(
        sample_size=10,
        mean=Decimal("0.001200"),
        median=Decimal("0.001000"),
        sample_variance=Decimal("0.00045000"),
        population_variance=Decimal("0.00040500"),
        sample_std_dev=Decimal("0.021213"),
        population_std_dev=Decimal("0.020125"),
        min_value=Decimal("-0.035000"),
        max_value=Decimal("0.042000"),
        range_value=Decimal("0.077000"),
        mad=Decimal("0.015000"),
        iqr=Decimal("0.025000"),
        skewness=Decimal("-0.1500"),
        excess_kurtosis=Decimal("0.4500"),
    )
    quantiles = QuantileDistribution(
        p1=Decimal("-0.034000"),
        p5=Decimal("-0.030000"),
        p10=Decimal("-0.022000"),
        p25=Decimal("-0.012000"),
        p50=Decimal("0.001000"),
        p75=Decimal("0.013000"),
        p90=Decimal("0.025000"),
        p95=Decimal("0.032000"),
        p99=Decimal("0.040000"),
    )
    bins = [
        HistogramBin(
            bin_start=Decimal("-0.040000"),
            bin_end=Decimal("0.000000"),
            bin_mid=Decimal("-0.020000"),
            count=4,
            frequency=Decimal("0.400000"),
        ),
        HistogramBin(
            bin_start=Decimal("0.000000"),
            bin_end=Decimal("0.050000"),
            bin_mid=Decimal("0.025000"),
            count=6,
            frequency=Decimal("0.600000"),
        ),
    ]
    return ReturnDistributionSummary(
        ticker=ticker,
        horizon="1Y",
        return_type="SIMPLE",
        sample_size=10,
        positive_count=6,
        positive_pct=Decimal("0.6000"),
        negative_count=4,
        negative_pct=Decimal("0.4000"),
        zero_count=0,
        zero_pct=Decimal("0.0000"),
        statistics=stats,
        quantiles=quantiles,
        histogram=bins,
    )


def _build_mock_matrix(tickers: list[str]) -> MultiAssetCorrelationMatrix:
    corr = [
        [Decimal("1.0000"), Decimal("0.8500")],
        [Decimal("0.8500"), Decimal("1.0000")],
    ]
    cov = [
        [Decimal("0.00045000"), Decimal("0.00035000")],
        [Decimal("0.00035000"), Decimal("0.00040000")],
    ]
    return MultiAssetCorrelationMatrix(
        tickers=tickers,
        horizon="1Y",
        common_dates_count=100,
        start_date=date(2023, 1, 3),
        end_date=date(2023, 12, 29),
        correlation_matrix=corr,
        covariance_matrix=cov,
    )


def _build_mock_rolling(
    ticker_a: str, ticker_b: str | None, metric: str, window: int
) -> RollingQuantitativeSeries:
    pts = [
        RollingStatisticPoint(date=date(2023, 1, 10), value=None),
        RollingStatisticPoint(date=date(2023, 1, 11), value=Decimal("0.245000")),
    ]
    return RollingQuantitativeSeries(
        ticker_a=ticker_a,
        ticker_b=ticker_b,
        metric_name=metric,
        window=window,
        series=pts,
    )


class MockQuantitativeService(QuantitativeAnalyticsService):
    def __init__(self) -> None:
        pass

    async def get_return_distribution(
        self,
        ticker: str,
        horizon: HistoricalTimeHorizon = HistoricalTimeHorizon.ONE_YEAR,
        return_type: Literal["SIMPLE", "LOG"] = "SIMPLE",
        custom_start: date | None = None,
        custom_end: date | None = None,
        force_refresh: bool = False,
    ) -> ReturnDistributionSummary:
        return _build_mock_distribution(ticker=ticker)

    async def compare_assets(
        self,
        tickers: list[str],
        horizon: HistoricalTimeHorizon = HistoricalTimeHorizon.ONE_YEAR,
        custom_start: date | None = None,
        custom_end: date | None = None,
        force_refresh: bool = False,
    ) -> MultiAssetCorrelationMatrix:
        return _build_mock_matrix(tickers=tickers)

    async def get_rolling_series(
        self,
        ticker_a: str,
        ticker_b: str | None = None,
        metric: Literal["VOLATILITY", "CORRELATION", "MEAN"] = "VOLATILITY",
        window: int = 20,
        horizon: HistoricalTimeHorizon = HistoricalTimeHorizon.ONE_YEAR,
        custom_start: date | None = None,
        custom_end: date | None = None,
        force_refresh: bool = False,
    ) -> RollingQuantitativeSeries:
        return _build_mock_rolling(ticker_a, ticker_b, metric, window)


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_quantitative_analytics_service] = lambda: (
        MockQuantitativeService()
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_distribution_endpoint(client: TestClient):
    resp = client.get(
        "/api/v1/analytics/distribution/AAPL?horizon=1Y&return_type=SIMPLE"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "AAPL"
    assert data["return_type"] == "SIMPLE"
    assert "statistics" in data
    assert data["statistics"]["mean"] == "0.001200"
    assert data["statistics"]["skewness"] == "-0.1500"
    assert "quantiles" in data
    assert data["quantiles"]["p50"] == "0.001000"
    assert len(data["histogram"]) == 2


def test_compare_assets_endpoint(client: TestClient):
    resp = client.get("/api/v1/analytics/compare?tickers=AAPL,MSFT&horizon=1Y")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tickers"] == ["AAPL", "MSFT"]
    assert data["correlation_matrix"][0][1] == "0.8500"
    assert data["covariance_matrix"][0][0] == "0.00045000"

    # Fewer than 2 tickers -> 400 Bad Request
    resp_bad = client.get("/api/v1/analytics/compare?tickers=AAPL")
    assert resp_bad.status_code == 400


def test_rolling_series_endpoint(client: TestClient):
    resp = client.get(
        "/api/v1/analytics/rolling?ticker_a=AAPL&metric=VOLATILITY&window=20"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker_a"] == "AAPL"
    assert data["metric_name"] == "VOLATILITY"
    assert data["window"] == 20
    assert len(data["series"]) == 2
    assert data["series"][0]["value"] is None
    assert data["series"][1]["value"] == "0.245000"

    # CORRELATION without ticker_b -> 400 Bad Request
    resp_bad = client.get("/api/v1/analytics/rolling?ticker_a=AAPL&metric=CORRELATION")
    assert resp_bad.status_code == 400
