"""
aurelius.api.v1.schemas.fundamentals
====================================
Export namespace for M7B.2 advanced fundamental analysis transport schemas.
"""

from aurelius.api.v1.schemas.fundamentals.advanced_schemas import (
    AdvancedFundamentalsResponse,
)
from aurelius.api.v1.schemas.fundamentals.capital_allocation_schemas import (
    CapitalAllocationResponse,
    CashFlowWorkingCapitalResponse,
    FreeCashFlowSectionSchema,
    FundamentalGrowthSectionSchema,
    ReinvestmentSectionSchema,
    WorkingCapitalSectionSchema,
)
from aurelius.api.v1.schemas.fundamentals.common_size_schemas import (
    CommonSizeBalanceSheet,
    CommonSizeCashFlow,
    CommonSizeIncomeStatement,
    CommonSizeItemSchema,
    CommonSizeStatementItem,
    CommonSizeStatementsResponse,
    CommonSizeTableSchema,
)
from aurelius.api.v1.schemas.fundamentals.credit_schemas import (
    AltmanZScoreSchema,
    CreditRiskResponse,
    EnterpriseValueResponse,
    M7B3ComprehensiveResponse,
    PiotroskiScoreSchema,
    PiotroskiSignalSchema,
    TraceableMetricDiagnosticSchema,
)
from aurelius.api.v1.schemas.fundamentals.diagnostics_schemas import (
    OperatingQualityRatioResult,
    QualityDiagnosticsResponse,
    SloanAccrualResult,
)
from aurelius.api.v1.schemas.fundamentals.dupont_schemas import (
    DuPont3StepResponse,
    DuPont3StepResult,
    DuPont5StepResponse,
    DuPont5StepResult,
    DuPontFactor,
    DuPontReconciliation,
)
from aurelius.api.v1.schemas.fundamentals.roic_schemas import (
    InvestedCapitalResult,
    MetricValueResponse,
    NopatResult,
    RoicResult,
)
from aurelius.api.v1.schemas.fundamentals.trend_schemas import (
    CAGRDataPoint,
    CAGRDataPointSchema,
    FundamentalTrendsResponse,
    MetricTrendSeries,
    MetricTrendSeriesSchema,
    TrendDataPoint,
    TrendDataPointSchema,
)

M7B3ComprehensiveResponse.model_rebuild(
    _types_namespace={
        "CapitalAllocationResponse": CapitalAllocationResponse,
        "CashFlowWorkingCapitalResponse": CashFlowWorkingCapitalResponse,
    }
)

__all__ = [
    "AdvancedFundamentalsResponse",
    "AltmanZScoreSchema",
    "CAGRDataPoint",
    "CAGRDataPointSchema",
    "CapitalAllocationResponse",
    "CashFlowWorkingCapitalResponse",
    "CommonSizeBalanceSheet",
    "CommonSizeCashFlow",
    "CommonSizeIncomeStatement",
    "CommonSizeItemSchema",
    "CommonSizeStatementItem",
    "CommonSizeStatementsResponse",
    "CommonSizeTableSchema",
    "CreditRiskResponse",
    "DuPont3StepResponse",
    "DuPont3StepResult",
    "DuPont5StepResponse",
    "DuPont5StepResult",
    "DuPontFactor",
    "DuPontReconciliation",
    "EnterpriseValueResponse",
    "FreeCashFlowSectionSchema",
    "FundamentalGrowthSectionSchema",
    "FundamentalTrendsResponse",
    "InvestedCapitalResult",
    "M7B3ComprehensiveResponse",
    "MetricTrendSeries",
    "MetricTrendSeriesSchema",
    "MetricValueResponse",
    "NopatResult",
    "OperatingQualityRatioResult",
    "PiotroskiScoreSchema",
    "PiotroskiSignalSchema",
    "QualityDiagnosticsResponse",
    "ReinvestmentSectionSchema",
    "RoicResult",
    "SloanAccrualResult",
    "TraceableMetricDiagnosticSchema",
    "TrendDataPoint",
    "TrendDataPointSchema",
    "WorkingCapitalSectionSchema",
]
