"""
aurelius.services.fundamental_service
=====================================
Application service orchestrating fundamental analysis computation.
Extracts reported facts from FinancialStatementService, aligns periods,
executes canonical calculation engines, and constructs auditable FundamentalReport dossiers.
"""

import logging

from fastapi import Depends

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FinancialStatement,
    FiscalPeriodType,
    StatementType,
    Unit,
)
from aurelius.domain.errors import DataNotFoundError
from aurelius.domain.fundamental.engines.cash_flow import CashFlowEngine
from aurelius.domain.fundamental.engines.common_size import (
    CommonSizeEngine,
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
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)
from aurelius.domain.fundamental.models import (
    FundamentalReport,
    MetricDiagnostic,
    MetricProvenance,
    MetricResult,
)
from aurelius.domain.fundamental.period_matching import (
    MultiPeriodFactStore,
    get_prior_period,
    sort_periods_chronologically,
)
from aurelius.domain.fundamental.ttm import TTMEngine
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
        stmt_freq = (
            FiscalPeriodType.QUARTERLY
            if frequency == FiscalPeriodType.TTM
            else frequency
        )
        income_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.INCOME_STATEMENT, stmt_freq
        )
        balance_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.BALANCE_SHEET, stmt_freq
        )
        cash_flow_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.CASH_FLOW, stmt_freq
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

        # 6. Branch for TTM frequency
        if frequency == FiscalPeriodType.TTM:
            ttm_windows = TTMEngine.find_all_ttm_windows(sorted_periods)
            if not ttm_windows:
                return FundamentalReport(
                    ticker=normalized_ticker,
                    frequency=frequency,
                    reporting_currency=reporting_currency or Currency.USD,
                    periods=[],
                    metrics={},
                    diagnostics_summary=[
                        MetricDiagnostic(
                            code=DiagnosticCode.INSUFFICIENT_PERIODS_FOR_TTM,
                            message=(
                                "Insufficient compatible quarterly periods available to compute TTM "
                                "(minimum 4 compatible quarters required)."
                            ),
                            details={"quarter_count": str(len(sorted_periods))},
                        )
                    ],
                )

            ttm_periods = [w.ttm_period for w in ttm_windows]
            for w in ttm_windows:
                # --- DURATION METRICS ---
                _record(TTMEngine.calculate_ttm_revenue(w, fact_store))
                _record(TTMEngine.calculate_ttm_gross_profit(w, fact_store))
                _record(TTMEngine.calculate_ttm_gross_margin(w, fact_store))
                _record(TTMEngine.calculate_ttm_operating_income(w, fact_store))
                _record(TTMEngine.calculate_ttm_operating_margin(w, fact_store))
                _record(TTMEngine.calculate_ttm_net_income(w, fact_store))
                _record(TTMEngine.calculate_ttm_net_profit_margin(w, fact_store))

                # --- CASH FLOW DURATION METRICS ---
                _record(TTMEngine.calculate_ttm_cfo(w, fact_store))
                _record(TTMEngine.calculate_ttm_capex(w, fact_store))
                _record(TTMEngine.calculate_ttm_fcf(w, fact_store))
                _record(TTMEngine.calculate_ttm_fcf_margin(w, fact_store))
                _record(TTMEngine.calculate_ttm_fcf_conversion(w, fact_store))
                _record(TTMEngine.calculate_ttm_cfo_to_net_income(w, fact_store))

                # --- INSTANT BALANCE SHEET METRICS (at anchor quarter cutoff) ---
                _record(
                    LiquidityEngine.calculate_working_capital(w.ttm_period, fact_store)
                )
                _record(
                    LiquidityEngine.calculate_current_ratio(w.ttm_period, fact_store)
                )
                _record(LiquidityEngine.calculate_quick_ratio(w.ttm_period, fact_store))
                _record(LiquidityEngine.calculate_cash_ratio(w.ttm_period, fact_store))

                _record(SolvencyEngine.calculate_gross_debt(w.ttm_period, fact_store))
                _record(SolvencyEngine.calculate_net_debt(w.ttm_period, fact_store))
                _record(
                    SolvencyEngine.calculate_debt_to_equity(w.ttm_period, fact_store)
                )
                _record(
                    SolvencyEngine.calculate_debt_to_assets(w.ttm_period, fact_store)
                )

            return FundamentalReport(
                ticker=normalized_ticker,
                frequency=frequency,
                reporting_currency=reporting_currency or Currency.USD,
                periods=ttm_periods,
                metrics=metrics_by_id,
                diagnostics_summary=all_diagnostics,
            )

        # 7. Process each period chronologically (ANNUAL / QUARTERLY)
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

    async def get_advanced_fundamentals(
        self,
        ticker: str,
        frequency: FiscalPeriodType = FiscalPeriodType.TTM,
        fiscal_year: int | None = None,
        fiscal_period: str | None = None,
        allow_point_in_time_fallback: bool = False,
    ) -> tuple[
        FinancialPeriod,
        Currency,
        MetricResult,
        MetricResult,
        MetricResult,
        MetricResult,
        MetricResult,
        DuPont3StepDecomposition,
        DuPont5StepDecomposition,
        MetricResult,
        MetricResult,
        list[MetricDiagnostic],
    ]:
        """
        Orchestrate Advanced Fundamentals (ROIC, NOPAT, Invested Capital, DuPont, Quality Diagnostics)
        for a specific target period.

        Returns:
          (target_period, reporting_currency, etr, nopat, ic, avg_ic, roic, dupont3, dupont5, sloan, oqr, diagnostics)
        """
        normalized_ticker = validate_ticker(ticker)
        stmt_freq = (
            FiscalPeriodType.QUARTERLY
            if frequency == FiscalPeriodType.TTM
            else frequency
        )

        income_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.INCOME_STATEMENT, stmt_freq
        )
        balance_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.BALANCE_SHEET, stmt_freq
        )
        cash_flow_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.CASH_FLOW, stmt_freq
        )

        all_stmts = [*income_stmts, *balance_stmts, *cash_flow_stmts]
        if not all_stmts:
            raise DataNotFoundError(
                ticker=normalized_ticker,
                message=f"No financial statements found for {normalized_ticker}.",
            )

        reporting_currency = Currency.USD
        for s in all_stmts:
            if s.currency is not None:
                reporting_currency = s.currency
                break

        period_map: dict[str, FinancialPeriod] = {}
        for stmt in income_stmts:
            period_map[stmt.period.period_key] = stmt.period
        for stmt in cash_flow_stmts:
            if stmt.period.period_key not in period_map:
                period_map[stmt.period.period_key] = stmt.period
        for stmt in balance_stmts:
            if stmt.period.period_key not in period_map:
                period_map[stmt.period.period_key] = stmt.period

        sorted_periods = sort_periods_chronologically(list(period_map.values()))
        fact_store = MultiPeriodFactStore(all_stmts)

        # ---------------------------------------------------------------------
        # TTM Resolution
        # ---------------------------------------------------------------------
        if frequency == FiscalPeriodType.TTM:
            ttm_windows = TTMEngine.find_all_ttm_windows(sorted_periods)
            if not ttm_windows:
                raise DataNotFoundError(
                    ticker=normalized_ticker,
                    message="Insufficient quarterly periods to establish a valid TTM window (minimum 4 compatible quarters required).",
                )

            # Target window selection
            target_window = ttm_windows[-1]
            if fiscal_year is not None:
                matching = [
                    w
                    for w in ttm_windows
                    if w.anchor_quarter.fiscal_year == fiscal_year
                    and (
                        fiscal_period is None
                        or (
                            w.anchor_quarter.fiscal_period
                            and w.anchor_quarter.fiscal_period.value == fiscal_period
                        )
                    )
                ]
                if matching:
                    target_window = matching[-1]

            target_period = target_window.ttm_period
            anchor_q = target_window.anchor_quarter
            q_oldest = target_window.quarters[0]
            prior_anchor = get_prior_period(
                q_oldest, sorted_periods, FiscalPeriodType.QUARTERLY
            )

            etr_res = ROICEngine.calculate_ttm_effective_tax_rate(
                target_window, fact_store
            )
            nopat_res = ROICEngine.calculate_ttm_nopat(target_window, fact_store)
            ic_res = ROICEngine.calculate_invested_capital(anchor_q, fact_store)
            (
                avg_ic_val,
                ic_fact_ids,
                ic_concepts,
                ic_periods,
                ic_diags,
                used_fb,
                ic_notes,
            ) = ROICEngine.calculate_average_invested_capital(
                current_period=anchor_q,
                prior_period=prior_anchor,
                fact_store=fact_store,
                allow_point_in_time_fallback=allow_point_in_time_fallback,
            )

            if avg_ic_val is None:
                avg_ic_res = MetricResult(
                    metric_id=FundamentalMetricId.INVESTED_CAPITAL,
                    category=MetricCategory.SOLVENCY,
                    status=MetricStatus.UNAVAILABLE,
                    value=None,
                    unit=Unit.CURRENCY,
                    currency=reporting_currency,
                    period=target_period,
                    diagnostics=ic_diags,
                    provenance=MetricProvenance(
                        formula_id="FORMULA_AVERAGE_INVESTED_CAPITAL_TTM",
                        source_fact_ids=ic_fact_ids,
                        source_concepts=ic_concepts,
                        source_periods=ic_periods,
                        methodology_notes="TTM average invested capital requires ending Q(t) and beginning Q(t-4) snapshots.",
                    ),
                )
            else:
                avg_ic_res = MetricResult(
                    metric_id=FundamentalMetricId.INVESTED_CAPITAL,
                    category=MetricCategory.SOLVENCY,
                    status=MetricStatus.VALID,
                    value=avg_ic_val,
                    unit=Unit.CURRENCY,
                    currency=reporting_currency,
                    period=target_period,
                    diagnostics=ic_diags,
                    provenance=MetricProvenance(
                        formula_id="FORMULA_AVERAGE_INVESTED_CAPITAL_TTM",
                        source_fact_ids=ic_fact_ids,
                        source_concepts=ic_concepts,
                        source_periods=ic_periods,
                        methodology_notes=ic_notes,
                    ),
                )

            roic_res = ROICEngine.calculate_ttm_roic(
                window=target_window,
                prior_anchor=prior_anchor,
                fact_store=fact_store,
                allow_point_in_time_fallback=allow_point_in_time_fallback,
            )

            dupont3 = DuPontEngine.calculate_3step_dupont_ttm(
                window=target_window,
                prior_anchor=prior_anchor,
                fact_store=fact_store,
                allow_point_in_time_fallback=allow_point_in_time_fallback,
            )
            dupont5 = DuPontEngine.calculate_5step_dupont_ttm(
                window=target_window,
                prior_anchor=prior_anchor,
                fact_store=fact_store,
                allow_point_in_time_fallback=allow_point_in_time_fallback,
            )

            sloan_res = DiagnosticsEngine.calculate_sloan_accruals_ttm(
                window=target_window,
                prior_anchor=prior_anchor,
                fact_store=fact_store,
                allow_point_in_time_fallback=allow_point_in_time_fallback,
            )
            oqr_res = DiagnosticsEngine.evaluate_oqr_with_persistence(
                current_period=anchor_q,
                all_periods=sorted_periods,
                frequency=FiscalPeriodType.QUARTERLY,
                fact_store=fact_store,
            )

            raw_diags = [
                *etr_res.diagnostics,
                *nopat_res.diagnostics,
                *ic_res.diagnostics,
                *avg_ic_res.diagnostics,
                *roic_res.diagnostics,
                *dupont3.reconstructed_roe.diagnostics,
                *dupont5.reconstructed_roe.diagnostics,
                *sloan_res.diagnostics,
                *oqr_res.diagnostics,
            ]
            seen_diag_keys = set()
            all_summary_diags = []
            for d in raw_diags:
                k = (
                    d.code,
                    d.message,
                    tuple(sorted(d.details.items())) if d.details else (),
                )
                if k not in seen_diag_keys:
                    seen_diag_keys.add(k)
                    all_summary_diags.append(d)

            return (
                target_period,
                reporting_currency,
                etr_res,
                nopat_res,
                ic_res,
                avg_ic_res,
                roic_res,
                dupont3,
                dupont5,
                sloan_res,
                oqr_res,
                all_summary_diags,
            )

        # ---------------------------------------------------------------------
        # ANNUAL / QUARTERLY Resolution
        # ---------------------------------------------------------------------
        target_period = sorted_periods[-1]
        if fiscal_year is not None:
            matching_periods = [
                p
                for p in sorted_periods
                if p.fiscal_year == fiscal_year
                and (
                    fiscal_period is None
                    or (p.fiscal_period and p.fiscal_period.value == fiscal_period)
                )
            ]
            if matching_periods:
                target_period = matching_periods[-1]

        prior_period = get_prior_period(target_period, sorted_periods, frequency)

        # 1. ROIC & NOPAT
        etr_res = ROICEngine.calculate_effective_tax_rate(target_period, fact_store)
        nopat_res = ROICEngine.calculate_nopat(target_period, fact_store)
        ic_res = ROICEngine.calculate_invested_capital(target_period, fact_store)
        (
            avg_ic_val,
            ic_fact_ids,
            ic_concepts,
            ic_periods,
            ic_diags,
            used_fb,
            ic_notes,
        ) = ROICEngine.calculate_average_invested_capital(
            current_period=target_period,
            prior_period=prior_period,
            fact_store=fact_store,
            allow_point_in_time_fallback=allow_point_in_time_fallback,
        )

        if avg_ic_val is None:
            avg_ic_res = MetricResult(
                metric_id=FundamentalMetricId.INVESTED_CAPITAL,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=reporting_currency,
                period=target_period,
                diagnostics=ic_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_AVERAGE_INVESTED_CAPITAL",
                    source_fact_ids=ic_fact_ids,
                    source_concepts=ic_concepts,
                    source_periods=ic_periods,
                ),
            )
        else:
            avg_ic_res = MetricResult(
                metric_id=FundamentalMetricId.INVESTED_CAPITAL,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.VALID,
                value=avg_ic_val,
                unit=Unit.CURRENCY,
                currency=reporting_currency,
                period=target_period,
                diagnostics=ic_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_AVERAGE_INVESTED_CAPITAL",
                    source_fact_ids=ic_fact_ids,
                    source_concepts=ic_concepts,
                    source_periods=ic_periods,
                    methodology_notes=ic_notes,
                ),
            )

        roic_res = ROICEngine.calculate_roic(
            current_period=target_period,
            prior_period=prior_period,
            fact_store=fact_store,
            allow_point_in_time_fallback=allow_point_in_time_fallback,
        )

        # 2. DuPont Decompositions
        dupont3 = DuPontEngine.calculate_3step_dupont(
            current_period=target_period,
            prior_period=prior_period,
            fact_store=fact_store,
            allow_point_in_time_fallback=allow_point_in_time_fallback,
        )
        dupont5 = DuPontEngine.calculate_5step_dupont(
            current_period=target_period,
            prior_period=prior_period,
            fact_store=fact_store,
            allow_point_in_time_fallback=allow_point_in_time_fallback,
        )

        # 3. Quality Diagnostics
        sloan_res = DiagnosticsEngine.calculate_sloan_accruals(
            current_period=target_period,
            prior_period=prior_period,
            fact_store=fact_store,
            allow_point_in_time_fallback=allow_point_in_time_fallback,
        )
        oqr_res = DiagnosticsEngine.evaluate_oqr_with_persistence(
            current_period=target_period,
            all_periods=sorted_periods,
            frequency=frequency,
            fact_store=fact_store,
        )

        raw_diags = [
            *etr_res.diagnostics,
            *nopat_res.diagnostics,
            *ic_res.diagnostics,
            *avg_ic_res.diagnostics,
            *roic_res.diagnostics,
            *dupont3.reconstructed_roe.diagnostics,
            *dupont5.reconstructed_roe.diagnostics,
            *sloan_res.diagnostics,
            *oqr_res.diagnostics,
        ]
        seen_diag_keys = set()
        all_summary_diags = []
        for d in raw_diags:
            k = (
                d.code,
                d.message,
                tuple(sorted(d.details.items())) if d.details else (),
            )
            if k not in seen_diag_keys:
                seen_diag_keys.add(k)
                all_summary_diags.append(d)

        return (
            target_period,
            reporting_currency,
            etr_res,
            nopat_res,
            ic_res,
            avg_ic_res,
            roic_res,
            dupont3,
            dupont5,
            sloan_res,
            oqr_res,
            all_summary_diags,
        )

    async def get_common_size_statements(
        self,
        ticker: str,
        frequency: FiscalPeriodType = FiscalPeriodType.ANNUAL,
        fiscal_year: int | None = None,
        fiscal_period: str | None = None,
    ) -> tuple[
        FinancialPeriod, CommonSizeStatement, CommonSizeStatement, CommonSizeStatement
    ]:
        """
        Orchestrate Common-Size Statements:
          - Income Statement
          - Balance Sheet (strictly point-in-time instant snapshot)
          - Cash Flow Statement
        """
        normalized_ticker = validate_ticker(ticker)
        stmt_freq = (
            FiscalPeriodType.QUARTERLY
            if frequency == FiscalPeriodType.TTM
            else frequency
        )

        income_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.INCOME_STATEMENT, stmt_freq
        )
        balance_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.BALANCE_SHEET, stmt_freq
        )
        cash_flow_stmts = await self.statement_service.get_statements(
            normalized_ticker, StatementType.CASH_FLOW, stmt_freq
        )

        all_stmts = [*income_stmts, *balance_stmts, *cash_flow_stmts]
        if not all_stmts:
            raise DataNotFoundError(
                ticker=normalized_ticker,
                message=f"No financial statements found for {normalized_ticker}.",
            )

        period_map: dict[str, FinancialPeriod] = {}
        for stmt in income_stmts:
            period_map[stmt.period.period_key] = stmt.period
        for stmt in cash_flow_stmts:
            if stmt.period.period_key not in period_map:
                period_map[stmt.period.period_key] = stmt.period
        for stmt in balance_stmts:
            if stmt.period.period_key not in period_map:
                period_map[stmt.period.period_key] = stmt.period

        sorted_periods = sort_periods_chronologically(list(period_map.values()))
        fact_store = MultiPeriodFactStore(all_stmts)

        if frequency == FiscalPeriodType.TTM:
            ttm_windows = TTMEngine.find_all_ttm_windows(sorted_periods)
            if not ttm_windows:
                raise DataNotFoundError(
                    ticker=normalized_ticker,
                    message="Insufficient quarterly periods to establish a valid TTM window.",
                )

            target_window = ttm_windows[-1]
            if fiscal_year is not None:
                matching = [
                    w
                    for w in ttm_windows
                    if w.anchor_quarter.fiscal_year == fiscal_year
                    and (
                        fiscal_period is None
                        or (
                            w.anchor_quarter.fiscal_period
                            and w.anchor_quarter.fiscal_period.value == fiscal_period
                        )
                    )
                ]
                if matching:
                    target_window = matching[-1]

            cs_is = CommonSizeEngine.calculate_common_size_ttm_income_statement(
                target_window, fact_store
            )
            # Balance sheet is strictly instant anchor quarter Q(t)
            cs_bs = CommonSizeEngine.calculate_common_size_balance_sheet(
                target_window.anchor_quarter, fact_store
            )
            cs_cf = CommonSizeEngine.calculate_common_size_ttm_cash_flow(
                target_window, fact_store
            )

            return target_window.ttm_period, cs_is, cs_bs, cs_cf

        # Annual / Quarterly
        target_period = sorted_periods[-1]
        if fiscal_year is not None:
            matching_periods = [
                p
                for p in sorted_periods
                if p.fiscal_year == fiscal_year
                and (
                    fiscal_period is None
                    or (p.fiscal_period and p.fiscal_period.value == fiscal_period)
                )
            ]
            if matching_periods:
                target_period = matching_periods[-1]

        cs_is = CommonSizeEngine.calculate_common_size_income_statement(
            target_period, fact_store
        )
        cs_bs = CommonSizeEngine.calculate_common_size_balance_sheet(
            target_period, fact_store
        )
        cs_cf = CommonSizeEngine.calculate_common_size_cash_flow(
            target_period, fact_store
        )

        return target_period, cs_is, cs_bs, cs_cf


def get_fundamental_analysis_service(
    statement_service: FinancialStatementService = Depends(
        get_financial_statement_service
    ),
) -> FundamentalAnalysisService:
    """
    FastAPI dependency provider for FundamentalAnalysisService.
    Accepts FinancialStatementService via Depends so that dependency_overrides
    propagate correctly in tests.
    """
    return FundamentalAnalysisService(statement_service=statement_service)
