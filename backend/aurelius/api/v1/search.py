"""
aurelius.api.v1.search
======================
Security discovery search endpoints.

Endpoints:
  - GET /api/v1/market/search?q={query}&limit={limit}
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from aurelius.api.v1.schemas.search import (
    SecuritySearchResponse,
    SecuritySearchResultItem,
)
from aurelius.providers.base import MarketDataProvider
from aurelius.providers.registry import get_market_data_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["Security Search"])


@router.get(
    "/search",
    response_model=SecuritySearchResponse,
    summary="Search for securities and companies",
    description=(
        "Executes a multi-field search against securities, tickers, and companies. "
        "Accepts text queries up to 60 characters with spaces (e.g. 'Apple Inc.'). "
        "Returns normalized security matches with asset type and exchange venue."
    ),
)
async def search_securities(
    q: Annotated[
        str,
        Query(
            description="Search query string (1 to 60 characters).",
            min_length=1,
            max_length=60,
        ),
    ],
    limit: Annotated[
        int,
        Query(
            description="Maximum number of search results (1 to 50, default 10).",
            ge=1,
            le=50,
        ),
    ] = 10,
    provider: Annotated[
        MarketDataProvider,
        Depends(get_market_data_provider),
    ] = None,  # type: ignore[assignment]
) -> SecuritySearchResponse:
    """
    Search securities by name, ticker, or keyword.
    """
    logger.info(
        "Executing search: query=%r limit=%d provider=%s", q, limit, provider.name
    )
    results = await provider.search_securities(query=q, limit=limit)
    return SecuritySearchResponse(
        query=q,
        count=len(results),
        results=[SecuritySearchResultItem.from_domain(r) for r in results],
    )
