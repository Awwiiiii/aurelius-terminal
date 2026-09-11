"""
aurelius.domain.entities.company
================================
Company profile domain entity representing corporate entity intelligence.

Domain Principles:
  - Conceptual separation: A CompanyProfile represents an operating business entity,
    distinguished from a financial Security or an exchange Listing.
  - Ticker context: `lookup_ticker` is the provider symbol used to query the record,
    NOT a permanent canonical global company identifier.
  - Sector/Industry classification: Classified as 'Yahoo Finance provider-supplied
    sector/industry classification'. It is NOT an authoritative GICS classification,
    which is a licensed taxonomy administered by S&P and MSCI.
  - No plausible fabrication: Missing provider fields remain None; never defaulted.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyProfile(BaseModel):
    """
    Corporate intelligence profile for operating business companies.

    Applicable to corporate equities. Non-corporate instruments (ETFs, Indices)
    do not have an operating company profile.
    """

    model_config = ConfigDict(frozen=True)

    lookup_ticker: str = Field(
        ...,
        description="Provider lookup/listing ticker symbol used to fetch this record, not a global company ID.",
    )
    company_name: str = Field(..., description="Corporate name of the company.")
    legal_name: str | None = Field(
        default=None, description="Official legal registered name if distinct."
    )
    description: str | None = Field(
        default=None,
        description="Long business description / corporate overview.",
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
        default=None, description="State or province of headquarters."
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
        default=None,
        description="Reported full-time employee count. Must be non-negative if present.",
    )
    provider: str = Field(..., description="Data provider that supplied this profile.")
    fetched_at: datetime = Field(
        ..., description="Timestamp of profile retrieval (UTC)."
    )
