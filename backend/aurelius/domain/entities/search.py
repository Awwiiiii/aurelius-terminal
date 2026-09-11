"""
aurelius.domain.entities.search
===============================
Domain entities for security and company search results.
"""

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.enums import AssetType, Currency


class SecuritySearchResult(BaseModel):
    """
    An individual security result returned from a search query.

    Represents a matching tradable instrument with provider listing context.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(
        ..., description="Normalized ticker symbol (e.g. 'AAPL', 'BRK-B')."
    )
    name: str = Field(
        ..., description="Display name of the security or issuing entity."
    )
    exchange: str | None = Field(
        default=None, description="Exchange code (e.g. 'NMS', 'NYQ')."
    )
    exchange_display: str | None = Field(
        default=None,
        description="Human-readable exchange venue name (e.g. 'NASDAQ', 'NYSE').",
    )
    asset_type: AssetType = Field(
        default=AssetType.UNKNOWN,
        description="Classification of the instrument (EQUITY, ETF, INDEX, etc.).",
    )
    currency: Currency | None = Field(
        default=None,
        description=(
            "Trading currency if reported by provider. Preserved as None or UNKNOWN "
            "if omitted; never fabricated with a default."
        ),
    )
    provider: str = Field(
        ..., description="Identifier of the data provider that supplied this result."
    )
