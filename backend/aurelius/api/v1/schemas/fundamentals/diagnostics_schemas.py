"""
aurelius.api.v1.schemas.fundamentals.diagnostics_schemas
=========================================================
Pydantic transport schemas for Sloan Accruals and Operating Quality Ratio diagnostics.
"""

from pydantic import BaseModel, ConfigDict, Field

from aurelius.api.v1.schemas.fundamental import MetricDiagnosticSchema
from aurelius.api.v1.schemas.fundamentals.roic_schemas import MetricValueResponse


class QualityDiagnosticsResponse(BaseModel):
    """
    Quality and forensic accounting diagnostics dossier for a target period.
    """

    model_config = ConfigDict(frozen=True)

    sloan_accruals: MetricValueResponse = Field(
        ...,
        description="Sloan-style balance sheet accruals ratio relative to average assets.",
    )
    operating_quality_ratio: MetricValueResponse = Field(
        ...,
        description="Operating Quality Ratio (CFO / EBIT) with 2-period persistence analysis.",
    )
    diagnostics_summary: list[MetricDiagnosticSchema] = Field(
        default_factory=list, description="Aggregated diagnostic flags."
    )


# Canonical API schema aliases per architectural specification
SloanAccrualResult = MetricValueResponse
OperatingQualityRatioResult = MetricValueResponse
