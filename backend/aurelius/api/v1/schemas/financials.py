"""
aurelius.api.v1.schemas.financials
===================================
Pydantic v2 transport schemas for financial statement endpoints.

Principles:
  - Exact Decimal serialization: Numerical values are transported as exact Decimals.
  - Transparent Provenance: Exposes period semantics (INSTANT vs DURATION),
    orthogonal unit/currency/scale, and whether fiscal period labels were source-reported.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FiscalPeriodLabel,
    FiscalPeriodType,
    PeriodType,
    Scale,
    StatementType,
    Unit,
)


class FinancialPeriodSchema(BaseModel):
    """
    Schema representing temporal boundaries and fiscal reporting context.
    """

    model_config = ConfigDict(frozen=True)

    period_key: str = Field(
        ..., description="Unique deterministic string key (YYYY-MM-DD)."
    )
    period_type: PeriodType = Field(..., description="INSTANT or DURATION.")
    instant_date: date | None = Field(
        default=None, description="Balance sheet cutoff date."
    )
    start_date: date | None = Field(default=None, description="Interval start date.")
    end_date: date | None = Field(default=None, description="Interval end date.")
    fiscal_year: int | None = Field(
        default=None, description="Fiscal year (e.g. 2024)."
    )
    fiscal_period: FiscalPeriodLabel | None = Field(
        default=None, description="FY, Q1, Q2, Q3, Q4."
    )
    is_period_label_source_reported: bool = Field(
        default=False,
        description="True if period label was reported by provider; False if safely derived.",
    )
    calendar_year: int | None = Field(default=None, description="Calendar year.")
    display_label: str = Field(
        ...,
        description="User-friendly formatted period label (e.g. 'FY 2024' or '2024-09-30').",
    )


class FinancialFactSchema(BaseModel):
    """
    Schema for an individual financial fact observation.
    """

    model_config = ConfigDict(frozen=True)

    fact_id: str
    concept_name: str
    canonical_concept: CanonicalConcept | None = None
    value: Decimal
    unit: Unit
    currency: Currency | None = None
    scale: Scale
    dimensions: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)


class FinancialStatementResponse(BaseModel):
    """
    Schema representing a single financial statement for a specific reporting period.
    """

    model_config = ConfigDict(frozen=True)

    statement_id: str
    company_id: str
    statement_type: StatementType
    period: FinancialPeriodSchema
    currency: Currency | None = None
    facts: list[FinancialFactSchema]


class FinancialMatrixRowSchema(BaseModel):
    """
    A single line-item row across multiple historical reporting periods.
    """

    model_config = ConfigDict(frozen=True)

    concept_key: str
    display_name: str
    canonical_concept: CanonicalConcept | None = None
    is_canonical: bool = False
    values_by_period: dict[str, Decimal | None] = Field(
        default_factory=dict,
        description="Map of period_key -> exact Decimal value (or null if missing).",
    )


class FinancialStatementMatrixResponse(BaseModel):
    """
    Multi-period query-optimized view for terminal grid and table presentation.
    """

    model_config = ConfigDict(frozen=True)

    company_id: str
    statement_type: StatementType
    frequency: FiscalPeriodType
    currency: Currency | None = None
    periods: list[FinancialPeriodSchema]
    rows: list[FinancialMatrixRowSchema]
