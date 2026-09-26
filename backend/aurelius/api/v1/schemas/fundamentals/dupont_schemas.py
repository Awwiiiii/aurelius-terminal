"""
aurelius.api.v1.schemas.fundamentals.dupont_schemas
====================================================
Pydantic transport schemas for 3-Step and 5-Step DuPont decompositions and reconciliation.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.api.v1.schemas.fundamentals.roic_schemas import MetricValueResponse


class DuPontReconciliation(BaseModel):
    """
    Mathematical reconciliation between direct ROE and reconstructed ROE.
    """

    model_config = ConfigDict(frozen=True)

    is_reconciled: bool = Field(..., description="True if discrepancy <= 0.0001.")
    reconciliation_discrepancy: Decimal | None = Field(
        default=None,
        description="Absolute difference between direct ROE and reconstructed ROE.",
    )


class DuPont3StepResponse(BaseModel):
    """
    3-Step DuPont decomposition: Net Profit Margin * Asset Turnover * Equity Multiplier.
    """

    model_config = ConfigDict(frozen=True)

    net_profit_margin: MetricValueResponse
    asset_turnover: MetricValueResponse
    equity_multiplier: MetricValueResponse
    reconstructed_roe: MetricValueResponse
    direct_roe: MetricValueResponse
    is_reconciled: bool = Field(..., description="True if discrepancy <= 0.0001.")
    reconciliation_discrepancy: Decimal | None = Field(
        default=None,
        description="Absolute difference between direct ROE and reconstructed ROE.",
    )
    reconciliation: DuPontReconciliation | None = Field(
        default=None, description="Reconciliation summary object."
    )


class DuPont5StepResponse(BaseModel):
    """
    5-Step DuPont decomposition: Tax Burden * Interest Burden * EBIT Margin * Asset Turnover * Equity Multiplier.
    """

    model_config = ConfigDict(frozen=True)

    tax_burden: MetricValueResponse
    interest_burden: MetricValueResponse
    ebit_margin: MetricValueResponse
    asset_turnover: MetricValueResponse
    equity_multiplier: MetricValueResponse
    reconstructed_roe: MetricValueResponse
    direct_roe: MetricValueResponse
    is_reconciled: bool = Field(..., description="True if discrepancy <= 0.0001.")
    reconciliation_discrepancy: Decimal | None = Field(
        default=None,
        description="Absolute difference between direct ROE and reconstructed ROE.",
    )
    reconciliation: DuPontReconciliation | None = Field(
        default=None, description="Reconciliation summary object."
    )


# Canonical API schema aliases per architectural specification
DuPontFactor = MetricValueResponse
DuPont3StepResult = DuPont3StepResponse
DuPont5StepResult = DuPont5StepResponse
