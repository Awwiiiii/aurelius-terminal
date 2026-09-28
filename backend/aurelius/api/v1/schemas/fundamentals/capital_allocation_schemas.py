"""
aurelius.api.v1.schemas.fundamentals.capital_allocation_schemas
==============================================================
Transport schemas for M7B.3 Capital Allocation and Structured Cash Flows.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.api.v1.schemas.financials import FinancialPeriodSchema
from aurelius.api.v1.schemas.fundamentals.credit_schemas import (
    TraceableMetricDiagnosticSchema,
)
from aurelius.api.v1.schemas.fundamentals.roic_schemas import MetricValueResponse


class CapitalAllocationResponse(BaseModel):
    """
    Capital allocation flows, investments, financing activities, and shareholder yields.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Listing ticker symbol.")
    period_type: str = Field(..., description="ANNUAL, QUARTERLY, or TTM.")
    period: FinancialPeriodSchema = Field(..., description="Target financial period.")
    reporting_currency: str | None = Field(
        default=None, description="Primary currency."
    )

    # Core Reported Cash Flows (Normalized Outflow Magnitudes)
    operating_cash_flow: MetricValueResponse
    capital_expenditures: MetricValueResponse
    dividends_paid: MetricValueResponse
    stock_repurchases: MetricValueResponse
    stock_issuance: MetricValueResponse
    debt_issued: MetricValueResponse
    debt_repaid: MetricValueResponse
    net_debt_issued: MetricValueResponse
    acquisitions_mna: MetricValueResponse

    # Relative Allocations & Shareholder Yields
    dividend_yield: MetricValueResponse
    buyback_yield: MetricValueResponse
    gross_shareholder_yield: MetricValueResponse
    net_shareholder_yield: MetricValueResponse

    diagnostics_summary: list[TraceableMetricDiagnosticSchema] = Field(
        default_factory=list,
        description="Deduplicated diagnostics with affected metrics.",
    )


class WorkingCapitalSectionSchema(BaseModel):
    """
    Non-cash operating working capital balances and multi-period changes.
    """

    model_config = ConfigDict(frozen=True)

    operating_current_assets: MetricValueResponse
    operating_current_liabilities: MetricValueResponse
    operating_nwc: MetricValueResponse
    delta_nwc: MetricValueResponse


class FreeCashFlowSectionSchema(BaseModel):
    """
    Dual FCFF metrics (NOPAT vs CFO accrual reconciliation) and FCFE.
    """

    model_config = ConfigDict(frozen=True)

    fcff_primary: MetricValueResponse
    fcff_reconciled: MetricValueResponse
    reconciliation_delta: Decimal | None = Field(
        default=None, description="Absolute difference: FCFF_primary - FCFF_reconciled."
    )
    divergence_ratio: Decimal | None = Field(
        default=None, description="Relative discrepancy: |delta| / |FCFF_primary|."
    )
    is_divergent: bool = Field(
        default=False, description="True if divergence ratio exceeds 15% threshold."
    )
    fcfe: MetricValueResponse
    net_borrowing_tier: str | None = Field(
        default=None, description="Net borrowing resolution tier utilized."
    )


class ReinvestmentSectionSchema(BaseModel):
    """
    Operational reinvestment and reinvestment rate relative to operating profit.
    """

    model_config = ConfigDict(frozen=True)

    reinvestment: MetricValueResponse
    reinvestment_rate: MetricValueResponse


class FundamentalGrowthSectionSchema(BaseModel):
    """
    Retrospective fundamental growth rate (Reinvestment Rate * ROIC).
    """

    model_config = ConfigDict(frozen=True)

    fundamental_growth: MetricValueResponse


class CashFlowWorkingCapitalResponse(BaseModel):
    """
    Structured analytical payload for Working Capital, FCF, Reinvestment, and Growth.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Listing ticker symbol.")
    period_type: str = Field(..., description="ANNUAL, QUARTERLY, or TTM.")
    period: FinancialPeriodSchema = Field(..., description="Target financial period.")
    reporting_currency: str | None = Field(
        default=None, description="Primary currency."
    )

    working_capital: WorkingCapitalSectionSchema
    free_cash_flow: FreeCashFlowSectionSchema
    reinvestment: ReinvestmentSectionSchema
    growth: FundamentalGrowthSectionSchema

    diagnostics_summary: list[TraceableMetricDiagnosticSchema] = Field(
        default_factory=list,
        description="Deduplicated diagnostics with affected metrics.",
    )
