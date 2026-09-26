"""
aurelius.domain.fundamental.models
==================================
Domain entities and audit models for fundamental analysis metrics,
diagnostics, calculation provenance, and comprehensive company reports.
"""

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FiscalPeriodType,
    Unit,
)
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)


class MetricDiagnostic(BaseModel):
    """
    Auditable structured diagnostic explaining an edge-case, warning,
    or calculation failure.
    """

    model_config = ConfigDict(frozen=True)

    code: DiagnosticCode = Field(
        ..., description="Machine-readable diagnostic classification."
    )
    message: str = Field(
        ..., description="Human-readable description of calculation condition."
    )
    details: dict[str, str] = Field(
        default_factory=dict,
        description="Structured context metadata (e.g. {'denominator': '0'}).",
    )


class MetricProvenance(BaseModel):
    """
    Auditable calculation provenance tracing a metric to source facts and exact formulas.
    Calculation timestamp is explicitly excluded to preserve deterministic equality.
    """

    model_config = ConfigDict(frozen=True)

    formula_id: str = Field(
        ..., description="Standardized formula identifier (e.g. 'FORMULA_ROE_2PT_AVG')."
    )
    methodology_version: str = Field(
        default="1.0.0",
        description="Semantic version of the calculation methodology.",
    )
    source_fact_ids: list[str] = Field(
        default_factory=list,
        description="Immutable list of M6 FinancialFact.fact_id instances utilized.",
    )
    source_concepts: list[str] = Field(
        default_factory=list,
        description="Canonical or source concept names consumed during calculation.",
    )
    source_periods: list[str] = Field(
        default_factory=list,
        description="Period keys of contributing facts.",
    )
    provider: str = Field(
        default="yahoo_finance", description="Source financial data provider."
    )
    methodology_notes: str | None = Field(
        default=None,
        description="Conventions, assumptions, or fallback policies applied.",
    )


class MetricResult(BaseModel):
    """
    The atomic result of a fundamental analysis metric computation.
    """

    model_config = ConfigDict(frozen=True)

    metric_id: FundamentalMetricId = Field(
        ..., description="Canonical metric identifier."
    )
    category: MetricCategory = Field(
        ..., description="Analytical category classification."
    )
    status: MetricStatus = Field(
        ..., description="Operational status: VALID, UNAVAILABLE, etc."
    )
    value: Decimal | None = Field(
        default=None,
        description="Exact calculated Decimal value, or None if unavailable/distorted.",
    )
    unit: Unit = Field(
        ..., description="Measurement unit: PERCENT, RATIO, CURRENCY, etc."
    )
    currency: Currency | None = Field(
        default=None,
        description="ISO currency code if unit is CURRENCY, else None.",
    )
    period: FinancialPeriod = Field(
        ..., description="Primary financial period represented by this metric."
    )
    diagnostics: list[MetricDiagnostic] = Field(
        default_factory=list,
        description="Audit diagnostics, warnings, or unavailability reasons.",
    )
    provenance: MetricProvenance = Field(
        ..., description="Complete auditable calculation provenance."
    )
    is_derived: bool = Field(
        default=True,
        description="True for all synthesized metrics; False if directly reported.",
    )

    @model_validator(mode="after")
    def validate_currency_and_status(self) -> Self:
        if self.unit == Unit.CURRENCY and self.status == MetricStatus.VALID:
            if self.currency is None or self.currency == Currency.UNKNOWN:
                raise ValueError(
                    f"MetricResult with unit=CURRENCY must have a known currency, got {self.currency}."
                )
        elif (
            self.unit in (Unit.PERCENT, Unit.RATIO, Unit.SHARES)
            and self.currency is not None
        ):
            raise ValueError(
                f"MetricResult with unit={self.unit.value} must have currency=None."
            )
        return self

    @property
    def formatted_value(self) -> str:
        """
        Produce a clean, institutional-grade string representation of the metric value.
        """
        if self.value is None or self.status != MetricStatus.VALID:
            return "—"

        if self.unit == Unit.PERCENT:
            # Expressed as e.g. 0.2450 -> 24.50%
            pct = self.value * Decimal("100")
            return f"{pct:.2f}%"
        if self.unit == Unit.RATIO:
            return f"{self.value:.2f}x"
        if self.unit == Unit.CURRENCY:
            curr_sym = (
                "$"
                if self.currency == Currency.USD
                else (self.currency.value if self.currency else "")
            )
            # Large numbers: format with commas
            return f"{curr_sym}{self.value:,.2f}"
        return f"{self.value}"


class FundamentalReport(BaseModel):
    """
    Comprehensive fundamental analysis report containing calculated metrics
    across all available periods.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Ticker symbol.")
    frequency: FiscalPeriodType = Field(
        ..., description="Reporting frequency: ANNUAL or QUARTERLY."
    )
    reporting_currency: Currency | None = Field(
        default=None, description="Primary reporting currency."
    )
    periods: list[FinancialPeriod] = Field(
        default_factory=list,
        description="Chronologically sorted periods represented in the report.",
    )
    metrics: dict[str, list[MetricResult]] = Field(
        default_factory=dict,
        description="Metrics keyed by FundamentalMetricId.value, each containing a list of period results.",
    )
    diagnostics_summary: list[MetricDiagnostic] = Field(
        default_factory=list,
        description="Aggregated diagnostics across the report.",
    )
