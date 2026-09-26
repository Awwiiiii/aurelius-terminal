"""
aurelius.domain.fundamental.engines
===================================
Pure calculation engines for canonical fundamental analysis metrics.
"""

from aurelius.domain.fundamental.engines.cash_flow import CashFlowEngine
from aurelius.domain.fundamental.engines.common_size import (
    CommonSizeEngine,
    CommonSizeItem,
    CommonSizeStatement,
)
from aurelius.domain.fundamental.engines.diagnostics_engine import DiagnosticsEngine
from aurelius.domain.fundamental.engines.dupont import (
    DuPont3StepDecomposition,
    DuPont5StepDecomposition,
    DuPontEngine,
)
from aurelius.domain.fundamental.engines.efficiency import EfficiencyEngine
from aurelius.domain.fundamental.engines.growth import GrowthEngine
from aurelius.domain.fundamental.engines.liquidity import LiquidityEngine
from aurelius.domain.fundamental.engines.profitability import ProfitabilityEngine
from aurelius.domain.fundamental.engines.roic import ROICEngine
from aurelius.domain.fundamental.engines.solvency import SolvencyEngine
from aurelius.domain.fundamental.engines.trend_engine import (
    CAGRResult,
    TrendEngine,
    TrendPoint,
)

__all__ = [
    "CashFlowEngine",
    "CommonSizeEngine",
    "CommonSizeItem",
    "CommonSizeStatement",
    "DiagnosticsEngine",
    "DuPont3StepDecomposition",
    "DuPont5StepDecomposition",
    "DuPontEngine",
    "EfficiencyEngine",
    "GrowthEngine",
    "LiquidityEngine",
    "ProfitabilityEngine",
    "ROICEngine",
    "SolvencyEngine",
    "CAGRResult",
    "TrendEngine",
    "TrendPoint",
]
