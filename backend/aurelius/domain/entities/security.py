"""
aurelius.domain.entities.security
=================================
Security domain entity representing a tradable financial asset / instrument.

Architecture and Domain Notes:
  - Conceptual boundary: This entity models a tradable security instrument.
  - Listing context: The fields `ticker`, `exchange`, `exchange_display`, `currency`,
    and `timezone` currently represent the provider-facing listing context for this
    instrument on a specific venue.
  - Evolution path: A future dedicated multi-venue `Listing` entity can be introduced
    without architectural rework of `Security` or `CompanyProfile`.
  - Non-goal: This entity explicitly does NOT claim to be a complete institutional
    security master (which requires permanent identifier reconciliation across CUSIP,
    ISIN, FIGI, and SEDOL).
  - No plausible fabrication: `currency` defaults to `Currency.UNKNOWN`, NEVER to USD.
    Missing fields remain None.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.enums import AssetType, Currency


class Security(BaseModel):
    """
    Metadata representation of a tradable financial security/asset.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(
        ..., description="Provider-facing listing ticker symbol (e.g. 'AAPL', 'BRK-B')."
    )
    name: str = Field(..., description="Canonical security or company name.")
    asset_type: AssetType = Field(
        default=AssetType.EQUITY,
        description="Classification of the instrument (EQUITY, ETF, INDEX, etc.).",
    )
    currency: Currency = Field(
        default=Currency.UNKNOWN,
        description=(
            "Primary currency the security trades in for this listing context. "
            "Defaults to UNKNOWN if not supplied by provider; never defaulted to USD."
        ),
    )
    exchange: str | None = Field(
        default=None, description="Listing exchange code (e.g. 'NMS', 'NYQ')."
    )
    exchange_display: str | None = Field(
        default=None,
        description="Human-readable exchange venue name (e.g. 'NASDAQ', 'NYSE').",
    )
    timezone: str | None = Field(
        default=None,
        description="IANA timezone of the exchange (e.g. 'America/New_York').",
    )
    country: str | None = Field(
        default=None, description="Country of listing or incorporation."
    )
    sector: str | None = Field(
        default=None,
        description="Provider-supplied sector classification. Not an authoritative GICS classification.",
    )
    industry: str | None = Field(
        default=None,
        description="Provider-supplied industry classification. Not an authoritative GICS classification.",
    )
    provider: str = Field(
        default="unknown",
        description="Identifier of data provider supplying this metadata.",
    )
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of retrieval (UTC).",
    )
