"""
aurelius.api.v1.schemas.fundamentals.trend_schemas
===================================================
Pydantic transport schemas for Fundamental Trends and M4 Calendar-Time CAGR.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.api.v1.schemas.financials import FinancialPeriodSchema
from aurelius.api.v1.schemas.fundamental import (
    MetricDiagnosticSchema,
    MetricProvenanceSchema,
)


class TrendDataPointSchema(BaseModel):
    """
    Chronological data point for a trend trajectory.
    """

    model_config = ConfigDict(frozen=True)

    period: FinancialPeriodSchema = Field(
        ..., description="Financial period represented."
    )
    value: Decimal | None = Field(default=None, description="Calculated metric value.")
    formatted_value: str = Field(..., description="Display formatted string.")
    status: str = Field(..., description="Operational status.")
    qoq_change: Decimal | None = Field(
        default=None,
        description="Sequential quarter-over-quarter percentage change (Quarterly only).",
    )
    yoy_change: Decimal | None = Field(
        default=None,
        description="Year-over-year percentage change (Annual and Quarterly).",
    )
    ttm_sequential_change: Decimal | None = Field(
        default=None,
        description="TTM vs Previous TTM sequential percentage change (TTM only).",
    )
    diagnostics: list[MetricDiagnosticSchema] = Field(default_factory=list)
    provenance: MetricProvenanceSchema = Field(
        ..., description="Calculation provenance."
    )


class MetricTrendSeriesSchema(BaseModel):
    """
    Chronological series of trend observations for a specific canonical metric.
    """

    model_config = ConfigDict(frozen=True)

    metric_name: str = Field(..., description="Canonical metric identifier.")
    unit: str = Field(..., description="PERCENT, RATIO, CURRENCY, etc.")
    points: list[TrendDataPointSchema] = Field(default_factory=list)


class CAGRDataPointSchema(BaseModel):
    """
    Calendar-time CAGR growth rate over a 3Y or 5Y horizon.
    """

    model_config = ConfigDict(frozen=True)

    metric_name: str = Field(..., description="Target canonical metric name.")
    horizon: str = Field(..., description="'3Y' or '5Y'.")
    cagr: Decimal | None = Field(default=None, description="Annualized compound rate.")
    formatted_cagr: str = Field(
        ..., description="Formatted string (e.g. '12.45%', '—')."
    )
    status: str = Field(..., description="VALID, UNAVAILABLE, etc.")
    start_period: FinancialPeriodSchema = Field(..., description="Start anchor period.")
    end_period: FinancialPeriodSchema = Field(..., description="End anchor period.")
    calendar_days: int = Field(..., description="Exact elapsed calendar days.")
    diagnostics: list[MetricDiagnosticSchema] = Field(default_factory=list)
    provenance: MetricProvenanceSchema = Field(..., description="Audit provenance.")


class FundamentalTrendsResponse(BaseModel):
    """
    Combined fundamental trend trajectories and CAGR response.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Listing ticker symbol.")
    period_type: str = Field(..., description="ANNUAL, QUARTERLY, or TTM.")
    series: dict[str, MetricTrendSeriesSchema] = Field(
        default_factory=dict, description="Trend series keyed by canonical metric name."
    )
    cagr_results: dict[str, list[CAGRDataPointSchema]] = Field(
        default_factory=dict,
        description="CAGR evaluations keyed by canonical metric name.",
    )
    provenance: MetricProvenanceSchema | None = Field(
        default=None, description="Response-level provenance."
    )


# Canonical API schema aliases per architectural specification
TrendDataPoint = TrendDataPointSchema
MetricTrendSeries = MetricTrendSeriesSchema
CAGRDataPoint = CAGRDataPointSchema
