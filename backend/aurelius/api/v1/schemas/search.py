"""
aurelius.api.v1.schemas.search
==============================
Pydantic response models for security search endpoints.
"""

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.search import SecuritySearchResult


class SecuritySearchResultItem(BaseModel):
    """
    Individual security search result item.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Normalized ticker symbol.")
    name: str = Field(..., description="Display name of the security or company.")
    exchange: str | None = Field(
        default=None, description="Listing exchange code (e.g. 'NMS', 'NYQ')."
    )
    exchange_display: str | None = Field(
        default=None,
        description="Human-readable exchange venue name (e.g. 'NASDAQ', 'NYSE').",
    )
    asset_type: str = Field(
        ..., description="Asset classification (EQUITY, ETF, INDEX, etc.)."
    )
    currency: str | None = Field(
        default=None,
        description="Trading currency if reported; None/omitted if unknown.",
    )
    provider: str = Field(..., description="Data provider identifier.")

    @classmethod
    def from_domain(cls, result: SecuritySearchResult) -> "SecuritySearchResultItem":
        return cls(
            ticker=result.ticker,
            name=result.name,
            exchange=result.exchange,
            exchange_display=result.exchange_display,
            asset_type=result.asset_type.value,
            currency=result.currency.value if result.currency is not None else None,
            provider=result.provider,
        )


class SecuritySearchResponse(BaseModel):
    """
    Response model for security text search queries.
    """

    model_config = ConfigDict(frozen=True)

    query: str = Field(..., description="The validated search query string executed.")
    count: int = Field(..., description="Total count of matching results returned.")
    results: list[SecuritySearchResultItem] = Field(
        ..., description="List of matching security results."
    )
