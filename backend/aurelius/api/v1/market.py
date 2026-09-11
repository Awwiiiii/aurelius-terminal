"""
aurelius.api.v1.market
======================
Market data API endpoints for quotes and historical bars.

Endpoints:
  - GET /api/v1/market/quote/{ticker}
  - GET /api/v1/market/ohlcv/{ticker}
"""

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from aurelius.api.v1.schemas.market import OHLCVResponse, QuoteResponse
from aurelius.domain.entities.enums import MarketInterval
from aurelius.providers.base import MarketDataProvider
from aurelius.providers.registry import get_market_data_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get(
    "/quote/{ticker}",
    response_model=QuoteResponse,
    summary="Get security quote snapshot",
    description=(
        "Retrieves the latest available market quote for the given security ticker symbol. "
        "Returns current price, session high/low, trading volume, and provider delay metadata."
    ),
)
async def get_quote(
    ticker: Annotated[
        str,
        Path(description="Normalized ticker symbol (e.g. 'AAPL', 'MSFT')."),
    ],
    provider: Annotated[
        MarketDataProvider,
        Depends(get_market_data_provider),
    ],
) -> QuoteResponse:
    """
    Fetch market quote for a ticker symbol.
    """
    logger.info("Handling quote request: ticker=%s provider=%s", ticker, provider.name)
    quote = await provider.get_quote(ticker)
    return QuoteResponse.from_domain(quote)


@router.get(
    "/ohlcv/{ticker}",
    response_model=OHLCVResponse,
    summary="Get historical OHLCV bars",
    description=(
        "Retrieves historical Open/High/Low/Close/Volume bars for the given security ticker "
        "across the specified date range. Prices are unadjusted raw transaction prices, with "
        "provider adjusted close included where available."
    ),
)
async def get_ohlcv(
    ticker: Annotated[
        str,
        Path(description="Normalized ticker symbol (e.g. 'AAPL')."),
    ],
    start: Annotated[
        date,
        Query(description="Start date (inclusive, YYYY-MM-DD)."),
    ],
    end: Annotated[
        date,
        Query(description="End date (inclusive, YYYY-MM-DD)."),
    ],
    interval: Annotated[
        MarketInterval,
        Query(
            description="Bar aggregation interval (restricted to '1d' in Milestone 1)."
        ),
    ] = MarketInterval.DAILY,
    provider: Annotated[
        MarketDataProvider,
        Depends(get_market_data_provider),
    ] = None,  # type: ignore[assignment]
) -> OHLCVResponse:
    """
    Fetch historical daily OHLCV bars for a ticker symbol.
    """
    logger.info(
        "Handling OHLCV request: ticker=%s start=%s end=%s interval=%s provider=%s",
        ticker,
        start,
        end,
        interval,
        provider.name,
    )
    series = await provider.get_historical_bars(
        ticker=ticker,
        start=start,
        end=end,
        interval=interval,
    )
    return OHLCVResponse.from_domain(series)
