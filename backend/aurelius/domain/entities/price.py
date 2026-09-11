"""
aurelius.domain.entities.price
==============================
Price domain models.

Financial principles:
  - Financial quantities (prices, changes) MUST be modeled using Python's `Decimal`
    to prevent binary floating-point representation and precision errors.
  - Floating-point numbers must be converted via `Decimal(str(val))`, never directly
    via `Decimal(val)` which preserves float inaccuracies.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.enums import Currency


class Price(BaseModel):
    """
    An immutable observation of a financial security's price at a point in time.
    """

    model_config = ConfigDict(frozen=True)

    amount: Decimal = Field(
        ..., description="Observed price amount represented as Decimal."
    )
    currency: Currency = Field(
        default=Currency.USD, description="Currency of the price."
    )
    timestamp: datetime = Field(
        ..., description="Timestamp of the price observation in UTC."
    )
    source: str = Field(
        ..., description="Provider or source identifier that reported the price."
    )


class PriceChange(BaseModel):
    """
    Representation of absolute and percentage price movement.
    """

    model_config = ConfigDict(frozen=True)

    absolute: Decimal = Field(
        ..., description="Absolute change (Price_current - Price_previous)."
    )
    percent: Decimal = Field(
        ...,
        description="Percentage change ((Price_current - Price_previous) / Price_previous * 100).",
    )
