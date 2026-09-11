"""
aurelius.api.v1.company
=======================
Company intelligence and security identity endpoints.

Endpoints:
  - GET /api/v1/market/security/{ticker}
  - GET /api/v1/market/company/{ticker}
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path

from aurelius.api.v1.schemas.company import (
    CompanyProfileEndpointResponse,
    CompanyProfileResponse,
    SecurityDetailResponse,
    SecurityInfoResponse,
)
from aurelius.domain.entities.enums import AssetType
from aurelius.providers.base import MarketDataProvider
from aurelius.providers.registry import get_market_data_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["Company & Security Intelligence"])


@router.get(
    "/security/{ticker}",
    response_model=SecurityDetailResponse,
    summary="Get security details and corporate profile",
    description=(
        "Retrieves tradable security instrument metadata (ticker, exchange, asset type, currency, timezone) "
        "and its corporate profile if an operating equity. Non-corporate instruments (ETFs, Indices) "
        "return 200 OK cleanly with company_profile: null and is_operating_company: false."
    ),
)
async def get_security_detail(
    ticker: Annotated[
        str,
        Path(description="Listing ticker symbol (e.g. 'AAPL', 'SPY', '^GSPC')."),
    ],
    provider: Annotated[
        MarketDataProvider,
        Depends(get_market_data_provider),
    ] = None,  # type: ignore[assignment]
) -> SecurityDetailResponse:
    """
    Fetch comprehensive security details and polymorphic company profile.
    """
    logger.info(
        "Fetching security detail: ticker=%s provider=%s", ticker, provider.name
    )
    security = await provider.get_security(ticker)
    company_profile = await provider.get_company_profile(ticker)

    is_operating = (
        company_profile is not None and security.asset_type == AssetType.EQUITY
    )

    return SecurityDetailResponse(
        security=SecurityInfoResponse.from_domain(security),
        company_profile=(
            CompanyProfileResponse.from_domain(company_profile)
            if company_profile is not None
            else None
        ),
        is_operating_company=is_operating,
    )


@router.get(
    "/company/{ticker}",
    response_model=CompanyProfileEndpointResponse,
    summary="Get company profile",
    description=(
        "Retrieves corporate intelligence profile for operating business companies. "
        "For non-corporate instruments (ETFs, Indices), returns 200 OK cleanly with "
        "company_profile: null and an informative message explaining its non-corporate status."
    ),
)
async def get_company_profile(
    ticker: Annotated[
        str,
        Path(description="Listing ticker symbol (e.g. 'AAPL', 'SPY')."),
    ],
    provider: Annotated[
        MarketDataProvider,
        Depends(get_market_data_provider),
    ] = None,  # type: ignore[assignment]
) -> CompanyProfileEndpointResponse:
    """
    Fetch corporate intelligence profile for a ticker symbol.
    """
    logger.info(
        "Fetching company profile: ticker=%s provider=%s", ticker, provider.name
    )
    # First verify security exists (raises DataNotFoundError if not)
    security = await provider.get_security(ticker)
    company_profile = await provider.get_company_profile(ticker)

    if company_profile is None:
        message = (
            f"Instrument '{security.ticker}' is not an operating company "
            f"(AssetType: {security.asset_type.value}). No corporate profile exists."
        )
        return CompanyProfileEndpointResponse(
            company_profile=None,
            is_operating_company=False,
            message=message,
        )

    return CompanyProfileEndpointResponse(
        company_profile=CompanyProfileResponse.from_domain(company_profile),
        is_operating_company=True,
        message=None,
    )
