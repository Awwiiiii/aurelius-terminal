"""
aurelius.api.v1.schemas.fundamental
===================================
Transport schemas for fundamental analysis API endpoints.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.api.v1.schemas.financials import FinancialPeriodSchema


class MetricDiagnosticSchema(BaseModel):
    """
    Diagnostic warning or unavailability reason for a fundamental metric.
    """

    model_config = ConfigDict(frozen=True)

    code: str = Field(..., description="Standardized diagnostic error/warning code.")
    message: str = Field(..., description="Human-readable explanation.")
    details: dict[str, str] = Field(
        default_factory=dict, description="Diagnostic parameters and context."
    )


class MetricProvenanceSchema(BaseModel):
    """
    Auditable calculation provenance for a fundamental metric.
    """

    model_config = ConfigDict(frozen=True)

    formula_id: str = Field(..., description="Canonical formula identifier.")
    methodology_version: str = Field(..., description="Methodology version.")
    source_fact_ids: list[str] = Field(
        default_factory=list, description="IDs of source FinancialFacts consumed."
    )
    source_concepts: list[str] = Field(
        default_factory=list, description="Canonical or source concept names utilized."
    )
    source_periods: list[str] = Field(
        default_factory=list, description="Period keys of contributing facts."
    )
    provider: str = Field(
        default="yahoo_finance", description="Upstream data provider."
    )
    methodology_notes: str | None = Field(
        default=None, description="Conventions, assumptions, or notes."
    )


class MetricResultSchema(BaseModel):
    """
    Representation of an individual fundamental analysis metric result.
    """

    model_config = ConfigDict(frozen=True)

    metric_id: str = Field(..., description="Canonical metric ID.")
    category: str = Field(..., description="Metric category (e.g. PROFITABILITY).")
    status: str = Field(..., description="Operational status: VALID, UNAVAILABLE, etc.")
    value: Decimal | None = Field(
        default=None, description="Exact calculated Decimal value."
    )
    formatted_value: str = Field(
        ..., description="Clean formatted representation (e.g. '24.50%', '1.85x', '—')."
    )
    unit: str = Field(..., description="PERCENT, RATIO, CURRENCY, etc.")
    currency: str | None = Field(
        default=None, description="Currency ISO code if monetary."
    )
    period_key: str = Field(..., description="Target period key.")
    is_derived: bool = Field(
        default=True, description="True if synthesized, False if reported."
    )
    diagnostics: list[MetricDiagnosticSchema] = Field(
        default_factory=list, description="Associated diagnostics."
    )
    provenance: MetricProvenanceSchema = Field(
        ..., description="Auditable calculation provenance."
    )


class FundamentalReportResponse(BaseModel):
    """
    Complete fundamental analysis dossier for a ticker across periods.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Ticker symbol.")
    frequency: str = Field(..., description="ANNUAL or QUARTERLY.")
    reporting_currency: str | None = Field(
        default=None, description="Primary reporting currency."
    )
    periods: list[FinancialPeriodSchema] = Field(
        default_factory=list, description="Chronological periods in report columns."
    )
    metrics: dict[str, list[MetricResultSchema]] = Field(
        default_factory=dict,
        description="Calculated metrics grouped by metric_id.",
    )
    diagnostics_summary: list[MetricDiagnosticSchema] = Field(
        default_factory=list, description="Distinct diagnostics reported."
    )
