"""
aurelius.api.v1.schemas.fundamentals.common_size_schemas
=========================================================
Pydantic transport schemas for Common-Size Statements.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.api.v1.schemas.financials import FinancialPeriodSchema
from aurelius.api.v1.schemas.fundamental import (
    MetricDiagnosticSchema,
    MetricProvenanceSchema,
)


class CommonSizeItemSchema(BaseModel):
    """
    Line item scaled to common-size percentage.
    """

    model_config = ConfigDict(frozen=True)

    concept_name: str = Field(..., description="Canonical concept name.")
    reported_value: Decimal | None = Field(
        default=None, description="Absolute reported currency value."
    )
    common_size_percent: Decimal | None = Field(
        default=None,
        description="Scaled common-size percentage value (e.g. 25.50 for 25.50%).",
    )
    status: str = Field(..., description="VALID, UNAVAILABLE, etc.")
    diagnostics: list[MetricDiagnosticSchema] = Field(default_factory=list)
    provenance: MetricProvenanceSchema = Field(..., description="Item provenance.")


class CommonSizeTableSchema(BaseModel):
    """
    Complete common-size financial statement table.
    """

    model_config = ConfigDict(frozen=True)

    statement_type: str = Field(
        ..., description="INCOME_STATEMENT, BALANCE_SHEET, or CASH_FLOW."
    )
    period: FinancialPeriodSchema = Field(
        ..., description="Financial period represented."
    )
    display_title: str = Field(
        ...,
        description="Display title (e.g. 'Balance Sheet — Quarter Ended 2024-09-30').",
    )
    base_concept_name: str = Field(
        ...,
        description="Base concept utilized for scaling ('REVENUE' or 'TOTAL_ASSETS').",
    )
    base_value: Decimal | None = Field(default=None, description="Reported base value.")
    status: str = Field(..., description="Operational status.")
    items: list[CommonSizeItemSchema] = Field(
        default_factory=list, description="Common-size items."
    )
    diagnostics: list[MetricDiagnosticSchema] = Field(default_factory=list)
    provenance: MetricProvenanceSchema = Field(
        ..., description="Statement-level provenance."
    )


class CommonSizeStatementsResponse(BaseModel):
    """
    Combined common-size statements response for a security and period.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Listing ticker symbol.")
    period_type: str = Field(..., description="ANNUAL, QUARTERLY, or TTM.")
    income_statement: CommonSizeTableSchema
    balance_sheet: CommonSizeTableSchema = Field(
        ...,
        description="Point-in-time balance sheet anchored to the latest compatible quarter.",
    )
    cash_flow_statement: CommonSizeTableSchema
    period: FinancialPeriodSchema | None = Field(
        default=None, description="Statement period metadata."
    )
    provenance: MetricProvenanceSchema | None = Field(
        default=None, description="Response-level provenance."
    )


# Canonical API schema aliases per architectural specification
CommonSizeStatementItem = CommonSizeItemSchema
CommonSizeIncomeStatement = CommonSizeTableSchema
CommonSizeBalanceSheet = CommonSizeTableSchema
CommonSizeCashFlow = CommonSizeTableSchema
