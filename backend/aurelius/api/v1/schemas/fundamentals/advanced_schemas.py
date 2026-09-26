"""
aurelius.api.v1.schemas.fundamentals.advanced_schemas
=====================================================
Top-level transport schemas for the Advanced Fundamentals API endpoint.
"""

from pydantic import BaseModel, ConfigDict, Field

from aurelius.api.v1.schemas.financials import FinancialPeriodSchema
from aurelius.api.v1.schemas.fundamental import (
    MetricDiagnosticSchema,
    MetricProvenanceSchema,
)
from aurelius.api.v1.schemas.fundamentals.diagnostics_schemas import (
    QualityDiagnosticsResponse,
)
from aurelius.api.v1.schemas.fundamentals.dupont_schemas import (
    DuPont3StepResponse,
    DuPont5StepResponse,
)
from aurelius.api.v1.schemas.fundamentals.roic_schemas import MetricValueResponse


class AdvancedFundamentalsResponse(BaseModel):
    """
    Combined analytical payload for Advanced Fundamental Analysis:
    ROIC, NOPAT, Invested Capital, 3-Step DuPont, 5-Step DuPont, and Quality Diagnostics.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Listing ticker symbol.")
    period_type: str = Field(..., description="ANNUAL, QUARTERLY, or TTM.")
    period: FinancialPeriodSchema = Field(
        ..., description="Target financial period represented."
    )
    reporting_currency: str | None = Field(
        default=None, description="Primary currency."
    )

    # 1. ROIC & Operational Profitability
    effective_tax_rate: MetricValueResponse
    nopat: MetricValueResponse
    invested_capital: MetricValueResponse
    average_invested_capital: MetricValueResponse
    roic: MetricValueResponse

    # 2. DuPont ROE Decompositions
    dupont_3step: DuPont3StepResponse
    dupont_5step: DuPont5StepResponse

    # 3. Quality Diagnostics
    quality_diagnostics: QualityDiagnosticsResponse
    diagnostics_summary: list[MetricDiagnosticSchema] = Field(default_factory=list)
    provenance: MetricProvenanceSchema | None = Field(default=None)
