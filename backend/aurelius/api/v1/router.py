"""
aurelius.api.v1.router
=======================
Top-level router for API version 1.

Milestone 0: Only the health check endpoint is implemented.
             All other endpoints will be added in subsequent milestones.

Endpoint inventory (Milestone 0):
  GET /api/v1/health   — Health check; confirms the API is running.

Planned endpoints (Milestone 1):
  GET /api/v1/market/quote/{ticker}
  GET /api/v1/market/ohlcv/{ticker}
  GET /api/v1/market/search
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter

from aurelius import __version__
from aurelius.api.v1.company import router as company_router
from aurelius.api.v1.financials import router as financials_router
from aurelius.api.v1.historical import router as historical_router
from aurelius.api.v1.market import router as market_router
from aurelius.api.v1.overview import router as overview_router
from aurelius.api.v1.quantitative import router as quantitative_router
from aurelius.api.v1.search import router as search_router
from aurelius.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()
router.include_router(market_router)
router.include_router(overview_router)
router.include_router(historical_router)
router.include_router(quantitative_router)
router.include_router(search_router)
router.include_router(company_router)
router.include_router(financials_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    summary="Health check",
    description=(
        "Returns the current status of the AURELIUS API. "
        "Use this endpoint to confirm the server is running and reachable. "
        "Does not check database connectivity or provider availability."
    ),
    tags=["System"],
)
async def health_check() -> dict:
    """
    Minimal health check endpoint.

    Returns HTTP 200 if the API process is running.

    Note:
        This endpoint does NOT verify:
        - Database connectivity
        - Provider API availability
        - Cache state
        Those checks will be added in a dedicated /api/v1/status endpoint
        when the database and providers are introduced in Milestone 1.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "environment": settings.aurelius_env,
        "timestamp": datetime.now(UTC).isoformat(),
    }
