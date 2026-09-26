"""
aurelius.api.v1.schemas.fundamentals.roic_schemas
==================================================
Pydantic transport schemas for ROIC, NOPAT, ETR, and Invested Capital results.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.api.v1.schemas.fundamental import (
    MetricDiagnosticSchema,
    MetricProvenanceSchema,
)


class MetricValueResponse(BaseModel):
    """
    Standard atomic derived metric response preserving status, diagnostics, and provenance.
    """

    model_config = ConfigDict(frozen=True)

    metric_id: str = Field(..., description="Canonical metric identifier.")
    category: str = Field(..., description="Analytical category.")
    status: str = Field(
        ..., description="Operational status: VALID, UNAVAILABLE, DISTORTED, etc."
    )
    value: Decimal | None = Field(
        default=None, description="Calculated decimal value, or null."
    )
    formatted_value: str = Field(
        ...,
        description="Institutional display string (e.g. '18.45%', '$125.00M', '—').",
    )
    unit: str = Field(..., description="Measurement unit (PERCENT, RATIO, CURRENCY).")
    currency: str | None = Field(
        default=None, description="ISO currency code if monetary."
    )
    period_key: str = Field(..., description="Target financial period key.")
    is_derived: bool = Field(default=True, description="True for derived metrics.")
    diagnostics: list[MetricDiagnosticSchema] = Field(default_factory=list)
    provenance: MetricProvenanceSchema = Field(
        ..., description="Auditable calculation provenance."
    )


# Canonical API schema aliases per architectural specification
NopatResult = MetricValueResponse
InvestedCapitalResult = MetricValueResponse
RoicResult = MetricValueResponse
