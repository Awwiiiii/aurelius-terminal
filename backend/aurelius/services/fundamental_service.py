"""
aurelius.services.fundamental_service
=====================================
Application service orchestrating fundamental analysis computation.
Extracts reported facts from FinancialStatementService, aligns periods,
executes canonical calculation engines, and constructs auditable FundamentalReport dossiers.
"""

import logging

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FinancialStatement,
    FiscalPeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.cash_flow import CashFlowEngine
from aurelius.domain.fundamental.engines.efficiency import EfficiencyEngine
from aurelius.domain.fundamental.engines.growth import GrowthEngine
from aurelius.domain.fundamental.engines.liquidity import LiquidityEngine
from aurelius.domain.fundamental.engines.profitability import ProfitabilityEngine
from aurelius.domain.fundamental.engines.solvency import SolvencyEngine
from aurelius.domain.fundamental.models import (
    FundamentalReport,
    MetricDiagnostic,
    MetricResult,
)
from aurelius.domain.fundamental.period_matching import (
    MultiPeriodFactStore,
    get_prior_period,
    sort_periods_chronologically,
)
from aurelius.domain.validation import validate_ticker
from aurelius.services.financial_statement_service import (
    FinancialStatementService,
    get_financial_statement_service,
)

logger = logging.getLogger(__name__)


class FundamentalAnalysisService:
    """
    Application service coordinating fundamental financial analysis calculations.
    """

    def __init__(self, statement_service: FinancialStatementService) -> None:
        self.statement_service = statement_service

    async def get_fundamental_report(
        self,
        ticker: str,
        frequency: FiscalPeriodType = FiscalPeriodType.ANNUAL,
        allow_point_in_time_fallback: bool = False,
    ) -> FundamentalReport:
        """
        Produce a comprehensive fundamental analysis report across all available periods.
        """
        normalized_ticker = validate_ticker(ticker)

        # 1. Retrieve all three statement types from M6 service concurrently or sequentially
        income_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.INCOME_STATEMENT, frequency
        )
        balance_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.BALANCE_SHEET, frequency
        )
        cash_flow_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.CASH_FLOW, frequency
        )

        all_stmts: list[FinancialStatement] = [
            *income_stmts,
            *balance_stmts,
            *cash_flow_stmts,
        ]

        # 2. Extract reporting currency
        reporting_currency: Currency | None = None
        for s in all_stmts:
            if s.currency is not None:
                reporting_currency = s.currency
                break

        # 3. Collect unique periods aligned by period key
        period_map: dict[str, FinancialPeriod] = {}
        # Prioritize duration periods (income statement/cash flow) for labels, then balance sheet
        for stmt in income_stmts:
            period_map[stmt.period.period_key] = stmt.period
        for stmt in cash_flow_stmts:
            if stmt.period.period_key not in period_map:
                period_map[stmt.period.period_key] = stmt.period
        for stmt in balance_stmts:
            if stmt.period.period_key not in period_map:
                period_map[stmt.period.period_key] = stmt.period

        sorted_periods = sort_periods_chronologically(list(period_map.values()))

        if not sorted_periods:
            return FundamentalReport(
                ticker=normalized_ticker,
                frequency=frequency,
                reporting_currency=reporting_currency or Currency.USD,
                periods=[],
                metrics={},
                diagnostics_summary=[],
            )

        # 4. Construct MultiPeriodFactStore
        fact_store = MultiPeriodFactStore(all_stmts)

        # 5. Initialize metric collection
        metrics_by_id: dict[str, list[MetricResult]] = {}
        all_diagnostics: list[MetricDiagnostic] = []

        def _record(res: MetricResult) -> None:
            m_key = res.metric_id.value
            if m_key not in metrics_by_id:
                metrics_by_id[m_key] = []
            metrics_by_id[m_key].append(res)
            for d in res.diagnostics:
                if d not in all_diagnostics:
                    all_diagnostics.append(d)

        # 6. Process each period chronologically
        for i, current_period in enumerate(sorted_periods):
            # Prior sequential period (prior year for annual, prior quarter for quarterly)
            prior_period = get_prior_period(current_period, sorted_periods, frequency)

            # Prior year period specifically (for YoY quarterly calculations)
            prior_year_period: FinancialPeriod | None = None
            if frequency == FiscalPeriodType.ANNUAL:
                prior_year_period = prior_period
            else:
                # Look for matching quarter in prior year
                for candidate in sorted_periods[:i]:
                    if (
                        candidate.fiscal_year
                        and current_period.fiscal_year
                        and candidate.fiscal_year == current_period.fiscal_year - 1
                        and candidate.fiscal_period == current_period.fiscal_period
                    ):
                        prior_year_period = candidate
                        break

            # Prior sequential quarter (for QoQ quarterly calculations)
            prior_quarter_period = (
                prior_period if frequency == FiscalPeriodType.QUARTERLY else None
            )

            # --- GROWTH ---
            _record(
                GrowthEngine.calculate_revenue_growth_yoy(
                    current_period, prior_year_period, fact_store
                )
            )
            _record(
                GrowthEngine.calculate_revenue_growth_qoq(
                    current_period, prior_quarter_period, frequency, fact_store
                )
            )

            # --- PROFITABILITY ---
            _record(
                ProfitabilityEngine.calculate_gross_profit(current_period, fact_store)
            )
            _record(
                ProfitabilityEngine.calculate_gross_margin(current_period, fact_store)
            )
            _record(
                ProfitabilityEngine.calculate_operating_income(
                    current_period, fact_store
                )
            )
            _record(
                ProfitabilityEngine.calculate_operating_margin(
                    current_period, fact_store
                )
            )
            _record(
                ProfitabilityEngine.calculate_net_income(current_period, fact_store)
            )
            _record(
                ProfitabilityEngine.calculate_net_profit_margin(
                    current_period, fact_store
                )
            )
            _record(
                ProfitabilityEngine.calculate_roa(
                    current_period,
                    prior_period,
                    fact_store,
                    allow_point_in_time_fallback,
                )
            )
            _record(
                ProfitabilityEngine.calculate_roe(
                    current_period,
                    prior_period,
                    fact_store,
                    allow_point_in_time_fallback,
                )
            )
            _record(
                ProfitabilityEngine.calculate_ebitda_margin(current_period, fact_store)
            )

            # --- LIQUIDITY ---
            _record(
                LiquidityEngine.calculate_working_capital(current_period, fact_store)
            )
            _record(LiquidityEngine.calculate_current_ratio(current_period, fact_store))
            _record(LiquidityEngine.calculate_quick_ratio(current_period, fact_store))
            _record(LiquidityEngine.calculate_cash_ratio(current_period, fact_store))

            # --- SOLVENCY ---
            _record(SolvencyEngine.calculate_gross_debt(current_period, fact_store))
            _record(SolvencyEngine.calculate_net_debt(current_period, fact_store))
            _record(SolvencyEngine.calculate_debt_to_equity(current_period, fact_store))
            _record(SolvencyEngine.calculate_debt_to_assets(current_period, fact_store))
            _record(
                SolvencyEngine.calculate_interest_coverage(current_period, fact_store)
            )
            _record(SolvencyEngine.calculate_debt_to_ebitda(current_period, fact_store))
            _record(
                SolvencyEngine.calculate_net_debt_to_ebitda(current_period, fact_store)
            )

            # --- EFFICIENCY ---
            _record(
                EfficiencyEngine.calculate_asset_turnover(
                    current_period,
                    prior_period,
                    fact_store,
                    allow_point_in_time_fallback,
                )
            )
            _record(
                EfficiencyEngine.calculate_receivables_turnover(
                    current_period,
                    prior_period,
                    fact_store,
                    allow_point_in_time_fallback,
                )
            )
            _record(
                EfficiencyEngine.calculate_inventory_turnover(
                    current_period,
                    prior_period,
                    fact_store,
                    allow_point_in_time_fallback,
                )
            )
            _record(
                EfficiencyEngine.calculate_payables_turnover(
                    current_period,
                    prior_period,
                    fact_store,
                    allow_point_in_time_fallback,
                )
            )
            _record(
                EfficiencyEngine.calculate_dso(
                    current_period,
                    prior_period,
                    fact_store,
                    allow_point_in_time_fallback,
                )
            )
            _record(
                EfficiencyEngine.calculate_dio(
                    current_period,
                    prior_period,
                    fact_store,
                    allow_point_in_time_fallback,
                )
            )
            _record(
                EfficiencyEngine.calculate_dpo(
                    current_period,
                    prior_period,
                    fact_store,
                    allow_point_in_time_fallback,
                )
            )
            _record(
                EfficiencyEngine.calculate_ccc(
                    current_period,
                    prior_period,
                    fact_store,
                    allow_point_in_time_fallback,
                )
            )

            # --- CASH FLOW ---
            _record(
                CashFlowEngine.calculate_operating_cash_flow(current_period, fact_store)
            )
            _record(
                CashFlowEngine.calculate_capital_expenditures(
                    current_period, fact_store
                )
            )
            _record(CashFlowEngine.calculate_free_cash_flow(current_period, fact_store))
            _record(CashFlowEngine.calculate_fcf_margin(current_period, fact_store))
            _record(CashFlowEngine.calculate_fcf_conversion(current_period, fact_store))
            _record(
                CashFlowEngine.calculate_cfo_to_net_income(current_period, fact_store)
            )

        return FundamentalReport(
            ticker=normalized_ticker,
            frequency=frequency,
            reporting_currency=reporting_currency or Currency.USD,
            periods=sorted_periods,
            metrics=metrics_by_id,
            diagnostics_summary=all_diagnostics,
        )


_fundamental_service_instance: FundamentalAnalysisService | None = None


def get_fundamental_analysis_service() -> FundamentalAnalysisService:
    """
    FastAPI dependency provider for FundamentalAnalysisService.
    """
    global _fundamental_service_instance
    if _fundamental_service_instance is None:
        _fundamental_service_instance = FundamentalAnalysisService(
            statement_service=get_financial_statement_service()
        )
    return _fundamental_service_instance
