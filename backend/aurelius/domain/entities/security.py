"""
aurelius.domain.entities.security
=================================
Security domain entity representing an instrument/asset definition.
"""

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.enums import AssetType, Currency


class Security(BaseModel):
    """
    Metadata representation of a tradable financial asset.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Canonical ticker symbol (e.g. 'AAPL').")
    name: str | None = Field(default=None, description="Company or asset name.")
    asset_type: AssetType = Field(
        default=AssetType.EQUITY, description="Classification of the asset."
    )
    currency: Currency = Field(
        default=Currency.USD, description="Primary currency the security trades in."
    )
    exchange: str | None = Field(
        default=None, description="Listing exchange code or name (e.g. 'NASDAQ')."
    )
    country: str | None = Field(
        default=None, description="Country of incorporation or listing."
    )
    sector: str | None = Field(
        default=None, description="Economic sector (e.g. 'Technology')."
    )
    industry: str | None = Field(default=None, description="Industry grouping.")
