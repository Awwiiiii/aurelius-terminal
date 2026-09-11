"""
aurelius.api.v1.quantitative
============================
FastAPI routes for quantitative analytics:
  - GET /api/v1/analytics/distribution/{ticker}
  - GET /api/v1/analytics/compare
  - GET /api/v1/analytics/rolling
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from aurelius.api.v1.schemas.quantitative import (
    MultiAssetCorrelationMatrixResponse,
    ReturnDistributionSummaryResponse,
    RollingQuantitativeSeriesResponse,
)
from aurelius.domain.entities.historical import HistoricalTimeHorizon
from aurelius.domain.errors import AureliusError
from aurelius.services.quantitative_analytics_service import (
    QuantitativeAnalyticsService,
    get_quantitative_analytics_service,
)

router = APIRouter(prefix="/analytics", tags=["quantitative-analytics"])


@router.get(
    "/distribution/{ticker}",
    response_model=ReturnDistributionSummaryResponse,
    summary="Get empirical return distribution profile",
    description="Calculates moments, quantiles, and deterministic frequency histogram for an asset's returns.",
)
async def get_return_distribution(
    ticker: str,
    service: Annotated[
        QuantitativeAnalyticsService, Depends(get_quantitative_analytics_service)
    ],
    horizon: Annotated[
        HistoricalTimeHorizon,
        Query(description="Historical analysis time horizon (default: 1Y)."),
    ] = HistoricalTimeHorizon.ONE_YEAR,
    return_type: Annotated[
        Literal["SIMPLE", "LOG"],
        Query(description="Return methodology: 'SIMPLE' or 'LOG' (default: SIMPLE)."),
    ] = "SIMPLE",
    custom_start: Annotated[
        date | None,
        Query(description="Start date for custom horizon (YYYY-MM-DD)."),
    ] = None,
    custom_end: Annotated[
        date | None,
        Query(description="End date for custom horizon (YYYY-MM-DD)."),
    ] = None,
    force_refresh: Annotated[
        bool,
        Query(description="Bypass cache and force fresh computation."),
    ] = False,
) -> ReturnDistributionSummaryResponse:
    try:
        summary = await service.get_return_distribution(
            ticker=ticker,
            horizon=horizon,
            return_type=return_type,
            custom_start=custom_start,
            custom_end=custom_end,
            force_refresh=force_refresh,
        )
        return ReturnDistributionSummaryResponse.from_domain(summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except AureliusError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get(
    "/compare",
    response_model=MultiAssetCorrelationMatrixResponse,
    summary="Compare multi-asset universe",
    description="Performs inner date alignment across multiple securities and computes pairwise Pearson correlation and covariance matrices.",
)
async def compare_assets(
    tickers: Annotated[
        str,
        Query(
            description="Comma-separated ticker list, e.g. 'AAPL,MSFT,NVDA'. Minimum 2 required.",
            examples=["AAPL,MSFT,NVDA"],
        ),
    ],
    service: Annotated[
        QuantitativeAnalyticsService, Depends(get_quantitative_analytics_service)
    ],
    horizon: Annotated[
        HistoricalTimeHorizon,
        Query(description="Historical analysis time horizon (default: 1Y)."),
    ] = HistoricalTimeHorizon.ONE_YEAR,
    custom_start: Annotated[
        date | None,
        Query(description="Start date for custom horizon (YYYY-MM-DD)."),
    ] = None,
    custom_end: Annotated[
        date | None,
        Query(description="End date for custom horizon (YYYY-MM-DD)."),
    ] = None,
    force_refresh: Annotated[
        bool,
        Query(description="Bypass cache and force fresh computation."),
    ] = False,
) -> MultiAssetCorrelationMatrixResponse:
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    if len(ticker_list) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 comma-separated tickers are required for asset comparison.",
        )

    try:
        matrix = await service.compare_assets(
            tickers=ticker_list,
            horizon=horizon,
            custom_start=custom_start,
            custom_end=custom_end,
            force_refresh=force_refresh,
        )
        return MultiAssetCorrelationMatrixResponse.from_domain(matrix)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except AureliusError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get(
    "/rolling",
    response_model=RollingQuantitativeSeriesResponse,
    summary="Get rolling quantitative time series",
    description="Computes sliding window rolling metrics (volatility, correlation, mean) over W return observations.",
)
async def get_rolling_series(
    ticker_a: Annotated[
        str,
        Query(description="Primary security ticker symbol, e.g. 'AAPL'."),
    ],
    service: Annotated[
        QuantitativeAnalyticsService, Depends(get_quantitative_analytics_service)
    ],
    ticker_b: Annotated[
        str | None,
        Query(
            description="Secondary security ticker symbol (required if metric is 'CORRELATION')."
        ),
    ] = None,
    metric: Annotated[
        Literal["VOLATILITY", "CORRELATION", "MEAN"],
        Query(description="Rolling metric to compute (default: VOLATILITY)."),
    ] = "VOLATILITY",
    window: Annotated[
        int,
        Query(
            ge=2,
            le=252,
            description="Rolling window size in return observations (default: 20).",
        ),
    ] = 20,
    horizon: Annotated[
        HistoricalTimeHorizon,
        Query(description="Historical analysis time horizon (default: 1Y)."),
    ] = HistoricalTimeHorizon.ONE_YEAR,
    custom_start: Annotated[
        date | None,
        Query(description="Start date for custom horizon (YYYY-MM-DD)."),
    ] = None,
    custom_end: Annotated[
        date | None,
        Query(description="End date for custom horizon (YYYY-MM-DD)."),
    ] = None,
    force_refresh: Annotated[
        bool,
        Query(description="Bypass cache and force fresh computation."),
    ] = False,
) -> RollingQuantitativeSeriesResponse:
    if metric == "CORRELATION" and not ticker_b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Secondary ticker (ticker_b) is required when metric is 'CORRELATION'.",
        )

    try:
        series_res = await service.get_rolling_series(
            ticker_a=ticker_a,
            ticker_b=ticker_b,
            metric=metric,
            window=window,
            horizon=horizon,
            custom_start=custom_start,
            custom_end=custom_end,
            force_refresh=force_refresh,
        )
        return RollingQuantitativeSeriesResponse.from_domain(series_res)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except AureliusError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
