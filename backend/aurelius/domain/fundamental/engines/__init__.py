"""
aurelius.domain.fundamental.engines
===================================
Pure calculation engines for canonical fundamental analysis metrics.
"""

from aurelius.domain.fundamental.engines.capital_allocation import (
    CapitalAllocationEngine,
)
from aurelius.domain.fundamental.engines.cash_flow import CashFlowEngine
from aurelius.domain.fundamental.engines.common_size import (
    CommonSizeEngine,
    CommonSizeItem,
    CommonSizeStatement,
)
from aurelius.domain.fundamental.engines.credit import (
    AltmanZScoreResult,
    FundamentalCreditEngine,
    PiotroskiResult,
    PiotroskiSignalResult,
)
from aurelius.domain.fundamental.engines.diagnostics_engine import DiagnosticsEngine
from aurelius.domain.fundamental.engines.dupont import (
    DuPont3StepDecomposition,
    DuPont5StepDecomposition,
    DuPontEngine,
)
from aurelius.domain.fundamental.engines.efficiency import EfficiencyEngine
from aurelius.domain.fundamental.engines.enterprise_value import (
    CapitalStructureResult,
    EnterpriseValueBridgeEngine,
)
from aurelius.domain.fundamental.engines.free_cash_flow import (
    FCFFReconciliationResult,
    FreeCashFlowEngine,
)
from aurelius.domain.fundamental.engines.growth import GrowthEngine
from aurelius.domain.fundamental.engines.liquidity import LiquidityEngine
from aurelius.domain.fundamental.engines.operating_nwc import OperatingNWCEngine
from aurelius.domain.fundamental.engines.profitability import ProfitabilityEngine
from aurelius.domain.fundamental.engines.reinvestment import ReinvestmentEngine
from aurelius.domain.fundamental.engines.roic import ROICEngine
from aurelius.domain.fundamental.engines.solvency import SolvencyEngine
from aurelius.domain.fundamental.engines.trend_engine import (
    CAGRResult,
    TrendEngine,
    TrendPoint,
)

__all__ = [
    "AltmanZScoreResult",
    "CAGRResult",
    "CapitalAllocationEngine",
    "CapitalStructureResult",
    "CashFlowEngine",
    "CommonSizeEngine",
    "CommonSizeItem",
    "CommonSizeStatement",
    "DiagnosticsEngine",
    "DuPont3StepDecomposition",
    "DuPont5StepDecomposition",
    "DuPontEngine",
    "EfficiencyEngine",
    "EnterpriseValueBridgeEngine",
    "FCFFReconciliationResult",
    "FreeCashFlowEngine",
    "FundamentalCreditEngine",
    "GrowthEngine",
    "LiquidityEngine",
    "OperatingNWCEngine",
    "PiotroskiResult",
    "PiotroskiSignalResult",
    "ProfitabilityEngine",
    "ReinvestmentEngine",
    "ROICEngine",
    "SolvencyEngine",
    "TrendEngine",
    "TrendPoint",
]
