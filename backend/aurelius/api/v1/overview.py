"""
aurelius.api.v1.overview
========================
API endpoints for Market Overview workspace: session telemetry, canonical benchmarks,
and market mover rankings.

Endpoints:
  - GET /api/v1/market/overview
  - GET /api/v1/market/benchmarks
  - GET /api/v1/market/movers
  - GET /api/v1/market/status
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from aurelius.api.v1.schemas.overview import (
    BenchmarkResponse,
    MarketMoverResponse,
    MarketOverviewResponse,
    MarketStatusResponse,
)
from aurelius.domain.entities.market_overview import MoverCategory
from aurelius.services.market_overview_service import (
    MarketOverviewService,
    get_market_overview_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["Market Overview"])


@router.get(
    "/overview",
    response_model=MarketOverviewResponse,
    summary="Get composite market overview snapshot",
    description=(
        "Retrieves a unified market overview snapshot including operational session telemetry, "
        "canonical benchmark index performance, and top market movers (gainers, losers, active). "
        "Protected by an in-memory 60-second TTL cache to prevent provider rate-limiting."
    ),
)
async def get_market_overview(
    service: Annotated[
        MarketOverviewService,
        Depends(get_market_overview_service),
    ],
    force_refresh: Annotated[
        bool,
        Query(
            description="Force provider bypass and refresh cache immediately.",
        ),
    ] = False,
) -> MarketOverviewResponse:
    """
    Fetch complete market overview snapshot.
    """
    logger.info("Handling market overview request: force_refresh=%s", force_refresh)
    snapshot = await service.get_overview_snapshot(force_refresh=force_refresh)
    return MarketOverviewResponse.from_domain(snapshot)


@router.get(
    "/benchmarks",
    response_model=list[BenchmarkResponse],
    summary="Get canonical market benchmark snapshots",
    description=(
        "Retrieves performance snapshots for major canonical market benchmarks "
        "(S&P 500, Dow Jones, Nasdaq, Russell 2000, and CBOE VIX). "
        "VIX is represented with index-point semantics and is not a currency-priced equity asset."
    ),
)
async def get_benchmarks(
    service: Annotated[
        MarketOverviewService,
        Depends(get_market_overview_service),
    ],
) -> list[BenchmarkResponse]:
    """
    Fetch canonical benchmark index snapshots.
    """
    benchmarks = await service.get_benchmarks()
    return [BenchmarkResponse.from_domain(b) for b in benchmarks]


@router.get(
    "/movers",
    response_model=list[MarketMoverResponse],
    summary="Get market movers by category",
    description=(
        "Retrieves ranked market movers for a specified category: GAINERS, LOSERS, or ACTIVE. "
        "Volume missing from provider is null (never defaulted to zero). "
        "Market capitalization is sourced strictly from provider-reported marketCap."
    ),
)
async def get_market_movers(
    service: Annotated[
        MarketOverviewService,
        Depends(get_market_overview_service),
    ],
    category: Annotated[
        MoverCategory,
        Query(
            description="Mover category (GAINERS, LOSERS, ACTIVE).",
        ),
    ] = MoverCategory.GAINERS,
) -> list[MarketMoverResponse]:
    """
    Fetch ranked market movers by category.
    """
    movers = await service.get_market_movers(category)
    return [MarketMoverResponse.from_domain(m) for m in movers]


@router.get(
    "/status",
    response_model=MarketStatusResponse,
    summary="Get market operational session telemetry",
    description=(
        "Retrieves current trading session operational telemetry. In the absence of "
        "an authoritative exchange holiday calendar, unverified weekday sessions default to UNKNOWN."
    ),
)
async def get_market_status(
    service: Annotated[
        MarketOverviewService,
        Depends(get_market_overview_service),
    ],
) -> MarketStatusResponse:
    """
    Fetch market operational session telemetry.
    """
    status = await service.get_market_status()
    return MarketStatusResponse.from_domain(status)
