"""
aurelius.api.v1.schemas.fundamentals.credit_schemas
===================================================
Transport schemas for Enterprise Value Bridge, Capital Structure,
Piotroski F-Score, and Altman Z-Score credit analytics.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from aurelius.api.v1.schemas.financials import FinancialPeriodSchema
from aurelius.api.v1.schemas.fundamentals.roic_schemas import MetricValueResponse


class TraceableMetricDiagnosticSchema(BaseModel):
    """
    Standardized diagnostic item preserving exact affected metric traceability.
    """

    model_config = ConfigDict(frozen=True)

    code: str = Field(..., description="Standard diagnostic code.")
    message: str = Field(..., description="Human-readable explanation.")
    severity: str = Field(
        default="WARNING", description="Severity: INFO, WARNING, ERROR."
    )
    affected_metric_ids: list[str] = Field(
        default_factory=list,
        description="Canonical metric identifiers impacted by this condition.",
    )
    details: dict[str, str] = Field(
        default_factory=dict, description="Contextual parameters."
    )


class EnterpriseValueResponse(BaseModel):
    """
    Enterprise Value bridge claims, deductions, and capital structure weights.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Listing ticker symbol.")
    period_type: str = Field(..., description="ANNUAL, QUARTERLY, or TTM.")
    period: FinancialPeriodSchema = Field(..., description="Target financial period.")
    reporting_currency: str | None = Field(
        default=None, description="Primary currency."
    )

    # Core Bridge Items
    market_capitalization: MetricValueResponse
    gross_debt: MetricValueResponse
    preferred_equity: MetricValueResponse
    minority_interest: MetricValueResponse
    cash_and_liquid_investments: MetricValueResponse
    enterprise_value: MetricValueResponse

    # 4-State Disclosure Taxonomies
    preferred_equity_disclosure_case: str = Field(
        ...,
        description="Taxonomy state: REPORTED_NON_ZERO, REPORTED_ZERO, CONFIDENTLY_ABSENT, INSUFFICIENTLY_DISCLOSED.",
    )
    minority_interest_disclosure_case: str = Field(
        ...,
        description="Taxonomy state: REPORTED_NON_ZERO, REPORTED_ZERO, CONFIDENTLY_ABSENT, INSUFFICIENTLY_DISCLOSED.",
    )

    # Capital Structure Claims and Weights
    total_capital: MetricValueResponse
    weight_equity: MetricValueResponse
    weight_debt: MetricValueResponse
    weight_preferred: MetricValueResponse

    diagnostics_summary: list[TraceableMetricDiagnosticSchema] = Field(
        default_factory=list,
        description="Deduplicated diagnostics with affected metrics.",
    )


class PiotroskiSignalSchema(BaseModel):
    """
    Evaluation of a single Piotroski signal (F1 through F9).
    """

    model_config = ConfigDict(frozen=True)

    signal_id: str = Field(
        ..., description="Signal identifier (e.g. F1_ROA, F5_DELTA_LEVER)."
    )
    status: str = Field(..., description="PASS, FAIL, or UNAVAILABLE.")
    raw_value: Decimal | None = Field(default=None, description="Current metric value.")
    comparison_value: Decimal | None = Field(
        default=None, description="Comparison threshold or prior-period metric value."
    )
    notes: str = Field(..., description="Detailed evaluation calculation notes.")


class PiotroskiScoreSchema(BaseModel):
    """
    Canonical 9-signal Piotroski score payload without fabricated 9-point scaling.
    """

    model_config = ConfigDict(frozen=True)

    raw_pass_count: int = Field(..., description="Sum of PASS signals (0 to 9).")
    evaluated_signal_count: int = Field(
        ..., description="Total evaluated signals (PASS + FAIL)."
    )
    total_signal_count: int = Field(
        default=9, description="Total possible signals in canonical model."
    )
    coverage_ratio: Decimal = Field(
        ..., description="Evaluated signal ratio (evaluated / total)."
    )
    status: str = Field(..., description="VALID, UNAVAILABLE, or PARTIAL.")
    metric_result: MetricValueResponse
    signals: list[PiotroskiSignalSchema] = Field(
        ..., description="Breakdown of all 9 signals."
    )


class AltmanZScoreSchema(BaseModel):
    """
    Altman Z-Score analysis with structural dispatch details and factor breakdown.
    """

    model_config = ConfigDict(frozen=True)

    dispatched_model: str = Field(
        ..., description="MODEL_1_MANUFACTURING, MODEL_2_SERVICE, or EXEMPT_FINANCIAL."
    )
    dispatch_rationale: str = Field(
        ..., description="Structural balance sheet dispatch reasoning."
    )
    coefficients: dict[str, Decimal] = Field(
        ..., description="Model coefficient weights."
    )
    factors: dict[str, Decimal] = Field(
        ..., description="Evaluated financial ratios X1-X5."
    )
    total_score: Decimal | None = Field(
        default=None, description="Weighted composite Z-score."
    )
    zone: str | None = Field(
        default=None, description="Credit zone: SAFE, GREY, DISTRESS."
    )
    metric_result: MetricValueResponse


class CreditRiskResponse(BaseModel):
    """
    Composite credit risk dossier containing Piotroski and Altman Z-score models.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Listing ticker symbol.")
    period_type: str = Field(..., description="ANNUAL, QUARTERLY, or TTM.")
    period: FinancialPeriodSchema = Field(..., description="Target financial period.")
    reporting_currency: str | None = Field(
        default=None, description="Primary currency."
    )

    piotroski_f_score: PiotroskiScoreSchema
    altman_z_score: AltmanZScoreSchema

    diagnostics_summary: list[TraceableMetricDiagnosticSchema] = Field(
        default_factory=list,
        description="Deduplicated diagnostics with affected metrics.",
    )


if TYPE_CHECKING:
    from aurelius.api.v1.schemas.fundamentals.capital_allocation_schemas import (
        CapitalAllocationResponse,
        CashFlowWorkingCapitalResponse,
    )


class M7B3ComprehensiveResponse(BaseModel):
    """
    Unified analytical payload combining Capital Allocation, Cash Flows,
    Enterprise Value, and Credit Risk for high-efficiency terminal loading.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Listing ticker symbol.")
    period_type: str = Field(..., description="ANNUAL, QUARTERLY, or TTM.")
    period: FinancialPeriodSchema = Field(..., description="Target financial period.")
    reporting_currency: str | None = Field(
        default=None, description="Primary currency."
    )

    capital_allocation: "CapitalAllocationResponse"
    cash_flows: "CashFlowWorkingCapitalResponse"
    enterprise_value: EnterpriseValueResponse
    credit_risk: CreditRiskResponse

    diagnostics_summary: list[TraceableMetricDiagnosticSchema] = Field(
        default_factory=list,
        description="Global deduplicated diagnostics across all operations.",
    )
