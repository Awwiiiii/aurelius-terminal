"""
aurelius.domain.entities.market_cap
===================================
Domain entity representing a market capitalization observation with explicit temporal provenance.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.enums import Currency


class MarketCapObservation(BaseModel):
    """
    Explicit market capitalization observation with temporal provenance.
    """

    model_config = ConfigDict(frozen=True)

    value: Decimal = Field(..., description="Observed market capitalization value.")
    as_of_date: date | None = Field(
        default=None,
        description="Exact calendar date of the market-cap observation or quote. None if unannotated.",
    )
    currency: Currency | None = Field(
        default=None, description="Currency of observation."
    )
    source: str = Field(
        default="provider", description="Source provider or telemetry channel."
    )
