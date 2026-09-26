"""
aurelius.api.v1.schemas.fundamentals
====================================
Export namespace for M7B.2 advanced fundamental analysis transport schemas.
"""

from aurelius.api.v1.schemas.fundamentals.advanced_schemas import (
    AdvancedFundamentalsResponse,
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

__all__ = [
    "AdvancedFundamentalsResponse",
    "CAGRDataPoint",
    "CAGRDataPointSchema",
    "CommonSizeBalanceSheet",
    "CommonSizeCashFlow",
    "CommonSizeIncomeStatement",
    "CommonSizeItemSchema",
    "CommonSizeStatementItem",
    "CommonSizeStatementsResponse",
    "CommonSizeTableSchema",
    "DuPont3StepResponse",
    "DuPont3StepResult",
    "DuPont5StepResponse",
    "DuPont5StepResult",
    "DuPontFactor",
    "DuPontReconciliation",
    "FundamentalTrendsResponse",
    "InvestedCapitalResult",
    "MetricTrendSeries",
    "MetricTrendSeriesSchema",
    "MetricValueResponse",
    "NopatResult",
    "OperatingQualityRatioResult",
    "QualityDiagnosticsResponse",
    "RoicResult",
    "SloanAccrualResult",
    "TrendDataPoint",
    "TrendDataPointSchema",
]
