"""
aurelius.domain.entities
========================
Core financial domain entities for AURELIUS.

Milestone 1 Entities:
  - Price, PriceChange: Point-in-time price observations using Decimal
  - Quote: Market price snapshot with integer volume
  - OHLCVBar, OHLCVSeries: Historical bar models with unadjusted raw OHLC and provider adj_close
  - Enums: AssetType, Currency, MarketInterval, MarketState

Milestone 2 Entities:
  - Security: Tradable asset representation with provider listing context
  - CompanyProfile: Corporate entity intelligence for operating companies
  - SecuritySearchResult: Matching item returned from security/company search
"""

from aurelius.domain.entities.company import CompanyProfile
from aurelius.domain.entities.enums import (
    AssetType,
    Currency,
    MarketInterval,
    MarketState,
)
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    Filing,
    FinancialConcept,
    FinancialFact,
    FinancialMatrixRow,
    FinancialPeriod,
    FinancialStatement,
    FinancialStatementMatrix,
    FiscalPeriodLabel,
    FiscalPeriodType,
    PeriodType,
    Scale,
    StatementType,
    Unit,
)
from aurelius.domain.entities.historical import (
    BenchmarkComparison,
    DrawdownMetrics,
    HistoricalAnalysisSummary,
    HistoricalBarPoint,
    HistoricalExtremes,
    HistoricalTimeHorizon,
    ReturnMetrics,
    VolatilityMetrics,
)
from aurelius.domain.entities.market_overview import (
    CANONICAL_BENCHMARKS,
    BenchmarkCategory,
    BenchmarkDefinition,
    BenchmarkSnapshot,
    DataFreshness,
    MarketMoverItem,
    MarketOverviewSnapshot,
    MarketSessionState,
    MarketStatus,
    MoverCategory,
)
from aurelius.domain.entities.ohlcv import OHLCVBar, OHLCVSeries
from aurelius.domain.entities.price import Price, PriceChange
from aurelius.domain.entities.quantitative import (
    DescriptiveStatistics,
    HistogramBin,
    MultiAssetCorrelationMatrix,
    PairwiseCorrelation,
    QuantileDistribution,
    ReturnDistributionSummary,
    RollingQuantitativeSeries,
    RollingStatisticPoint,
)
from aurelius.domain.entities.quote import Quote
from aurelius.domain.entities.search import SecuritySearchResult
from aurelius.domain.entities.security import Security

__all__ = [
    "AssetType",
    "BenchmarkCategory",
    "BenchmarkComparison",
    "BenchmarkDefinition",
    "BenchmarkSnapshot",
    "CANONICAL_BENCHMARKS",
    "CanonicalConcept",
    "CompanyProfile",
    "Currency",
    "DataFreshness",
    "DescriptiveStatistics",
    "DrawdownMetrics",
    "Filing",
    "FinancialConcept",
    "FinancialFact",
    "FinancialMatrixRow",
    "FinancialPeriod",
    "FinancialStatement",
    "FinancialStatementMatrix",
    "FiscalPeriodLabel",
    "FiscalPeriodType",
    "HistogramBin",
    "HistoricalAnalysisSummary",
    "HistoricalBarPoint",
    "HistoricalExtremes",
    "HistoricalTimeHorizon",
    "MarketInterval",
    "MarketMoverItem",
    "MarketOverviewSnapshot",
    "MarketSessionState",
    "MarketState",
    "MarketStatus",
    "MoverCategory",
    "MultiAssetCorrelationMatrix",
    "OHLCVBar",
    "OHLCVSeries",
    "PairwiseCorrelation",
    "PeriodType",
    "Price",
    "PriceChange",
    "QuantileDistribution",
    "Quote",
    "ReturnDistributionSummary",
    "ReturnMetrics",
    "RollingQuantitativeSeries",
    "RollingStatisticPoint",
    "Scale",
    "Security",
    "SecuritySearchResult",
    "StatementType",
    "Unit",
    "VolatilityMetrics",
]
