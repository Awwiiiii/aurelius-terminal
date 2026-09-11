"""
aurelius.api.v1.historical
==========================
API endpoints for historical market analysis, return metrics, volatility,
drawdowns, moving averages, and benchmark comparison.

Endpoints:
  - GET /api/v1/market/history/{ticker}/analysis
  - GET /api/v1/market/history/{ticker}/metrics
"""

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from aurelius.api.v1.schemas.historical import (
    BenchmarkComparisonResponse,
    DrawdownMetricsResponse,
    HistoricalAnalysisResponse,
    HistoricalExtremesResponse,
    ReturnMetricsResponse,
    VolatilityMetricsResponse,
)
from aurelius.domain.entities.historical import HistoricalTimeHorizon
from aurelius.services.historical_analysis_service import (
    DEFAULT_BENCHMARK_TICKER,
    HistoricalAnalysisService,
    get_historical_analysis_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market/history", tags=["Historical Market Analysis"])


class HistoricalMetricsOnlyResponse(BaseModel):
    """Metrics-only response omitting the full time-series bar array."""

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Normalized ticker symbol.")
    horizon: str = Field(..., description="Configured time horizon.")
    start_date: str = Field(..., description="Earliest trading session date.")
    end_date: str = Field(..., description="Latest trading session date.")
    calendar_days: int = Field(..., description="Actual elapsed calendar days.")
    trading_days: int = Field(
        ..., description="Count of actual executed trading sessions."
    )
    returns: ReturnMetricsResponse = Field(
        ..., description="Return metrics on adjusted close."
    )
    volatility: VolatilityMetricsResponse = Field(
        ..., description="Realized volatility metrics."
    )
    drawdowns: DrawdownMetricsResponse = Field(
        ..., description="Drawdown metrics on adjusted close."
    )
    extremes: HistoricalExtremesResponse = Field(
        ..., description="Period extremes on raw close."
    )
    benchmark_comparison: BenchmarkComparisonResponse | None = Field(
        default=None, description="Comparative benchmark metrics."
    )


@router.get(
    "/{ticker}/analysis",
    response_model=HistoricalAnalysisResponse,
    summary="Get complete historical market analysis",
    description=(
        "Returns comprehensive historical analysis for a security over a configured time horizon, "
        "including daily return series, cumulative return series, calendar-time CAGR, win rate, "
        "realized volatility, running drawdowns, SMA/EMA indicators on raw Close, and inner-aligned "
        "benchmark comparison against S&P 500 (^GSPC)."
    ),
)
async def get_historical_analysis(
    ticker: Annotated[
        str,
        Path(
            description="Normalized ticker symbol (e.g. 'AAPL', 'MSFT', 'SPY').",
            examples=["AAPL"],
        ),
    ],
    service: Annotated[
        HistoricalAnalysisService,
        Depends(get_historical_analysis_service),
    ],
    horizon: Annotated[
        HistoricalTimeHorizon,
        Query(
            description="Standard analysis horizon (1M, 3M, 6M, YTD, 1Y, 3Y, 5Y, MAX, CUSTOM).",
        ),
    ] = HistoricalTimeHorizon.ONE_YEAR,
    start_date: Annotated[
        date | None,
        Query(
            description="Explicit start date (required if horizon=CUSTOM). Format: YYYY-MM-DD.",
        ),
    ] = None,
    end_date: Annotated[
        date | None,
        Query(
            description="Explicit end date (required if horizon=CUSTOM). Format: YYYY-MM-DD.",
        ),
    ] = None,
    benchmark: Annotated[
        str,
        Query(
            description="Benchmark ticker for comparative performance (default: ^GSPC).",
        ),
    ] = DEFAULT_BENCHMARK_TICKER,
    include_benchmark: Annotated[
        bool,
        Query(
            description="Whether to perform benchmark alignment and comparative metrics.",
        ),
    ] = True,
    force_refresh: Annotated[
        bool,
        Query(
            description="Force provider bypass and refresh cache immediately.",
        ),
    ] = False,
) -> HistoricalAnalysisResponse:
    """
    Execute historical market analysis across specified horizon.
    """
    summary = await service.analyze_security(
        ticker=ticker,
        horizon=horizon,
        custom_start=start_date,
        custom_end=end_date,
        benchmark_ticker=benchmark,
        include_benchmark=include_benchmark,
        force_refresh=force_refresh,
    )
    return HistoricalAnalysisResponse.from_domain(summary)


@router.get(
    "/{ticker}/metrics",
    response_model=HistoricalMetricsOnlyResponse,
    summary="Get historical performance metrics summary",
    description=(
        "Returns summary risk, return, and volatility metrics without the full time-series bar array."
    ),
)
async def get_historical_metrics(
    ticker: Annotated[
        str,
        Path(
            description="Normalized ticker symbol (e.g. 'AAPL').",
            examples=["AAPL"],
        ),
    ],
    service: Annotated[
        HistoricalAnalysisService,
        Depends(get_historical_analysis_service),
    ],
    horizon: Annotated[
        HistoricalTimeHorizon,
        Query(
            description="Standard analysis horizon (1M, 3M, 6M, YTD, 1Y, 3Y, 5Y, MAX, CUSTOM).",
        ),
    ] = HistoricalTimeHorizon.ONE_YEAR,
    start_date: Annotated[
        date | None,
        Query(description="Explicit start date (for CUSTOM)."),
    ] = None,
    end_date: Annotated[
        date | None,
        Query(description="Explicit end date (for CUSTOM)."),
    ] = None,
    benchmark: Annotated[
        str,
        Query(description="Benchmark ticker."),
    ] = DEFAULT_BENCHMARK_TICKER,
    include_benchmark: Annotated[
        bool,
        Query(description="Include benchmark comparison."),
    ] = True,
    force_refresh: Annotated[
        bool,
        Query(description="Force refresh cache."),
    ] = False,
) -> HistoricalMetricsOnlyResponse:
    """
    Fetch summary historical metrics only.
    """
    summary = await service.analyze_security(
        ticker=ticker,
        horizon=horizon,
        custom_start=start_date,
        custom_end=end_date,
        benchmark_ticker=benchmark,
        include_benchmark=include_benchmark,
        force_refresh=force_refresh,
    )
    return HistoricalMetricsOnlyResponse(
        ticker=summary.ticker,
        horizon=summary.horizon.value,
        start_date=summary.start_date.isoformat(),
        end_date=summary.end_date.isoformat(),
        calendar_days=summary.calendar_days,
        trading_days=summary.trading_days,
        returns=ReturnMetricsResponse.from_domain(summary.returns),
        volatility=VolatilityMetricsResponse.from_domain(summary.volatility),
        drawdowns=DrawdownMetricsResponse.from_domain(summary.drawdowns),
        extremes=HistoricalExtremesResponse.from_domain(summary.extremes),
        benchmark_comparison=(
            BenchmarkComparisonResponse.from_domain(summary.benchmark_comparison)
            if summary.benchmark_comparison
            else None
        ),
    )
