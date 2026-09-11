"""
aurelius.api.v1.schemas.company
===============================
Pydantic response models for company profile and security detail endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.company import CompanyProfile
from aurelius.domain.entities.security import Security


class CompanyProfileResponse(BaseModel):
    """
    Corporate intelligence profile response for operating companies.
    """

    model_config = ConfigDict(frozen=True)

    lookup_ticker: str = Field(
        ...,
        description="Provider lookup ticker used to fetch this record, not a global company ID.",
    )
    company_name: str = Field(..., description="Corporate name of the company.")
    legal_name: str | None = Field(
        default=None, description="Official legal registered name if distinct."
    )
    description: str | None = Field(
        default=None, description="Corporate overview / business summary."
    )
    sector: str | None = Field(
        default=None,
        description=(
            "Yahoo Finance provider-supplied sector classification. "
            "Note: This is a provider feed classification, NOT an authoritative GICS classification."
        ),
    )
    industry: str | None = Field(
        default=None,
        description=(
            "Yahoo Finance provider-supplied industry classification. "
            "Note: This is a provider feed classification, NOT an authoritative GICS classification."
        ),
    )
    country: str | None = Field(
        default=None, description="Country of corporate headquarters."
    )
    state: str | None = Field(
        default=None, description="State/province of corporate headquarters."
    )
    city: str | None = Field(
        default=None, description="City of corporate headquarters."
    )
    address: str | None = Field(
        default=None, description="Street address of corporate headquarters."
    )
    website: str | None = Field(
        default=None, description="Official corporate website URL."
    )
    employees: int | None = Field(
        default=None, description="Reported full-time employee count."
    )
    provider: str = Field(..., description="Data provider identifier.")
    fetched_at: datetime = Field(
        ..., description="Timestamp of profile retrieval (UTC)."
    )

    @classmethod
    def from_domain(cls, profile: CompanyProfile) -> "CompanyProfileResponse":
        return cls(
            lookup_ticker=profile.lookup_ticker,
            company_name=profile.company_name,
            legal_name=profile.legal_name,
            description=profile.description,
            sector=profile.sector,
            industry=profile.industry,
            country=profile.country,
            state=profile.state,
            city=profile.city,
            address=profile.address,
            website=profile.website,
            employees=profile.employees,
            provider=profile.provider,
            fetched_at=profile.fetched_at,
        )


class SecurityInfoResponse(BaseModel):
    """
    Tradable instrument metadata and listing context response.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Listing ticker symbol.")
    name: str = Field(..., description="Canonical security or company name.")
    asset_type: str = Field(
        ..., description="Instrument classification (EQUITY, ETF, INDEX, etc.)."
    )
    currency: str = Field(
        ...,
        description="Trading currency. UNKNOWN if omitted; never defaulted to USD.",
    )
    exchange: str | None = Field(
        default=None, description="Listing exchange venue code."
    )
    exchange_display: str | None = Field(
        default=None, description="Human-readable exchange venue name."
    )
    timezone: str | None = Field(
        default=None, description="IANA timezone of the listing venue."
    )
    country: str | None = Field(
        default=None, description="Country of listing or incorporation."
    )
    sector: str | None = Field(
        default=None,
        description="Provider-supplied sector classification. Not authoritative GICS.",
    )
    industry: str | None = Field(
        default=None,
        description="Provider-supplied industry classification. Not authoritative GICS.",
    )
    provider: str = Field(..., description="Data provider identifier.")
    fetched_at: datetime = Field(..., description="Timestamp of retrieval (UTC).")

    @classmethod
    def from_domain(cls, sec: Security) -> "SecurityInfoResponse":
        return cls(
            ticker=sec.ticker,
            name=sec.name,
            asset_type=sec.asset_type.value,
            currency=sec.currency.value,
            exchange=sec.exchange,
            exchange_display=sec.exchange_display,
            timezone=sec.timezone,
            country=sec.country,
            sector=sec.sector,
            industry=sec.industry,
            provider=sec.provider,
            fetched_at=sec.fetched_at,
        )


class SecurityDetailResponse(BaseModel):
    """
    Composite security response combining security instrument metadata
    and polymorphic company intelligence (null for non-corporate assets).
    """

    model_config = ConfigDict(frozen=True)

    security: SecurityInfoResponse = Field(
        ..., description="Tradable security instrument metadata."
    )
    company_profile: CompanyProfileResponse | None = Field(
        default=None,
        description="Corporate intelligence profile if an operating equity, null for ETFs/indices.",
    )
    is_operating_company: bool = Field(
        ...,
        description="True if the security is an operating company with a corporate profile.",
    )


class CompanyProfileEndpointResponse(BaseModel):
    """
    Response model for dedicated /market/company/{ticker} endpoint.
    Guarantees clean 200 OK responses for non-corporate assets without 404 errors.
    """

    model_config = ConfigDict(frozen=True)

    company_profile: CompanyProfileResponse | None = Field(
        default=None,
        description="Corporate intelligence profile, null for ETFs and indices.",
    )
    is_operating_company: bool = Field(
        ...,
        description="True if the security is an operating company with a corporate profile.",
    )
    message: str | None = Field(
        default=None,
        description="Informational message explaining non-corporate status when applicable.",
    )
