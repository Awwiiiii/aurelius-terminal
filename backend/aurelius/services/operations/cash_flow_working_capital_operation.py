"""
aurelius.services.operations.cash_flow_working_capital_operation
================================================================
Application operation coordinating Operating NWC, Free Cash Flows,
Reinvestment, and Fundamental Growth.
"""

from decimal import Decimal

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialPeriod,
    FiscalPeriodType,
    StatementType,
    Unit,
)
from aurelius.domain.errors import DataNotFoundError
from aurelius.domain.fundamental.engines.free_cash_flow import (
    FCFFReconciliationResult,
    FreeCashFlowEngine,
)
from aurelius.domain.fundamental.engines.operating_nwc import OperatingNWCEngine
from aurelius.domain.fundamental.engines.reinvestment import ReinvestmentEngine
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)
from aurelius.domain.fundamental.models import (
    MetricDiagnostic,
    MetricProvenance,
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
)


class CashFlowWorkingCapitalOperation:
    """
    Orchestrates Operating NWC, multi-period Delta NWC, FCFF, FCFE,
    Reinvestment, and Fundamental Growth without formula duplication.
    """

    def __init__(self, statement_service: FinancialStatementService) -> None:
        self.statement_service = statement_service

    async def execute(
        self,
        ticker: str,
        frequency: FiscalPeriodType,
        fiscal_year: int | None = None,
        fiscal_period: str | None = None,
    ) -> tuple[
        FinancialPeriod,
        Currency | None,
        dict[str, MetricResult],
        FCFFReconciliationResult,
        str | None,
    ]:
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

        reporting_currency: Currency | None = None
        for s in all_stmts:
            if s.currency is not None:
                reporting_currency = s.currency
                break

        period_map: dict[str, FinancialPeriod] = {}
        for s in income_stmts:
            period_map[s.period.period_key] = s.period
        for s in cash_flow_stmts:
            if s.period.period_key not in period_map:
                period_map[s.period.period_key] = s.period
        for s in balance_stmts:
            if s.period.period_key not in period_map:
                period_map[s.period.period_key] = s.period

        sorted_periods = sort_periods_chronologically(list(period_map.values()))
        if not sorted_periods:
            raise DataNotFoundError(
                ticker=normalized_ticker,
                message=f"No valid financial periods discovered for {normalized_ticker}.",
            )

        fact_store = MultiPeriodFactStore(all_stmts)

        # Period and Prior Period Resolution
        target_period: FinancialPeriod
        prior_period: FinancialPeriod | None = None

        if frequency == FiscalPeriodType.TTM:
            from aurelius.services.operations.ttm_helpers import (
                find_ttm_window_and_prior,
                synthesize_ttm_statements,
            )

            target_window, q_t_minus_4 = find_ttm_window_and_prior(
                sorted_periods, fiscal_year, fiscal_period
            )
            if target_window is None:
                raise DataNotFoundError(
                    ticker=normalized_ticker,
                    message="Insufficient consecutive quarterly periods to form a valid TTM window.",
                )
            target_period = target_window.ttm_period
            prior_period = q_t_minus_4
            synthetic_stmts = synthesize_ttm_statements(target_window, fact_store)
            all_stmts = [*all_stmts, *synthetic_stmts]
            fact_store = MultiPeriodFactStore(all_stmts)
        else:
            target_period = sorted_periods[-1]
            if fiscal_year is not None:
                matching = [
                    p
                    for p in sorted_periods
                    if p.fiscal_year == fiscal_year
                    and (
                        fiscal_period is None
                        or (p.fiscal_period and p.fiscal_period.value == fiscal_period)
                    )
                ]
                if matching:
                    target_period = matching[-1]

            prior_period = get_prior_period(target_period, sorted_periods, frequency)

        # 1. Operating Working Capital & Delta NWC
        metrics: dict[str, MetricResult] = {}
        metrics["operating_nwc"] = OperatingNWCEngine.calculate_operating_nwc(
            target_period, fact_store
        )
        # Operating CA & Operating CL
        metrics["operating_ca"] = self._calculate_operating_ca(
            target_period, fact_store
        )
        metrics["operating_cl"] = self._calculate_operating_cl(
            target_period, fact_store
        )
        metrics["delta_nwc"] = OperatingNWCEngine.calculate_delta_nwc(
            target_period, prior_period, fact_store
        )

        # 2. Free Cash Flows (Primary, Reconciled, and FCFE)
        recon_result = FreeCashFlowEngine.calculate_fcff_reconciliation(
            target_period, prior_period, fact_store
        )
        metrics["fcff_primary"] = recon_result.fcff_primary
        metrics["fcff_reconciled"] = recon_result.fcff_reconciled
        metrics["fcfe"] = FreeCashFlowEngine.calculate_fcfe(target_period, fact_store)

        # Determine net borrowing tier used
        net_borrowing_tier = self._identify_net_borrowing_tier(metrics["fcfe"])

        # 3. Reinvestment & Growth
        metrics["reinvestment"] = ReinvestmentEngine.calculate_reinvestment(
            target_period, prior_period, fact_store
        )
        metrics["reinvestment_rate"] = ReinvestmentEngine.calculate_reinvestment_rate(
            target_period, prior_period, fact_store
        )
        metrics["fundamental_growth"] = ReinvestmentEngine.calculate_fundamental_growth(
            target_period, prior_period, fact_store
        )

        return (
            target_period,
            reporting_currency,
            metrics,
            recon_result,
            net_borrowing_tier,
        )

    def _calculate_operating_ca(
        self,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        ca_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_ASSETS,
            period.period_key,
        )
        if ca_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_NWC,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Current assets is missing from balance sheet.",
                        details={"period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_OPERATING_CA_V1",
                    methodology_version="1.0.0",
                    source_concepts=["CURRENT_ASSETS"],
                    source_periods=[period.period_key],
                ),
            )

        cash_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
            period.period_key,
        )
        sti_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.SHORT_TERM_INVESTMENTS,
            period.period_key,
        )
        cash_val = cash_fact.value if cash_fact else Decimal(0)
        sti_val = sti_fact.value if sti_fact else Decimal(0)
        op_ca = ca_fact.value - (cash_val + sti_val)

        source_fact_ids = [ca_fact.fact_id]
        source_concepts = ["CURRENT_ASSETS"]
        if cash_fact:
            source_fact_ids.append(cash_fact.fact_id)
            source_concepts.append("CASH_AND_EQUIVALENTS")
        if sti_fact:
            source_fact_ids.append(sti_fact.fact_id)
            source_concepts.append("SHORT_TERM_INVESTMENTS")

        return MetricResult(
            metric_id=FundamentalMetricId.OPERATING_NWC,
            category=MetricCategory.LIQUIDITY,
            status=MetricStatus.VALID,
            value=op_ca,
            unit=Unit.CURRENCY,
            currency=ca_fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_OPERATING_CA_V1",
                methodology_version="1.0.0",
                source_fact_ids=source_fact_ids,
                source_concepts=source_concepts,
                source_periods=[period.period_key],
                methodology_notes=f"Operating Current Assets = Current Assets ({ca_fact.value}) - Cash ({cash_val}) - STI ({sti_val}) = {op_ca}.",
            ),
        )

    def _calculate_operating_cl(
        self,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        cl_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_LIABILITIES,
            period.period_key,
        )
        if cl_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_NWC,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Current liabilities is missing from balance sheet.",
                        details={"period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_OPERATING_CL_V1",
                    methodology_version="1.0.0",
                    source_concepts=["CURRENT_LIABILITIES"],
                    source_periods=[period.period_key],
                ),
            )

        st_debt_fact = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            [
                "Current Debt",
                "Short Term Debt",
                "Current Debt And Capital Lease Obligation",
                "Current Portion Of Long Term Debt",
                "Short Term Borrowings",
                "Commercial Paper",
            ],
            period.period_key,
        )
        st_debt_val = st_debt_fact.value if st_debt_fact else Decimal(0)
        op_cl = cl_fact.value - st_debt_val

        source_fact_ids = [cl_fact.fact_id]
        source_concepts = ["CURRENT_LIABILITIES"]
        if st_debt_fact:
            source_fact_ids.append(st_debt_fact.fact_id)
            source_concepts.append(st_debt_fact.concept.source_concept)

        return MetricResult(
            metric_id=FundamentalMetricId.OPERATING_NWC,
            category=MetricCategory.LIQUIDITY,
            status=MetricStatus.VALID,
            value=op_cl,
            unit=Unit.CURRENCY,
            currency=cl_fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_OPERATING_CL_V1",
                methodology_version="1.0.0",
                source_fact_ids=source_fact_ids,
                source_concepts=source_concepts,
                source_periods=[period.period_key],
                methodology_notes=f"Operating Current Liabilities = Current Liabilities ({cl_fact.value}) - ST Debt ({st_debt_val}) = {op_cl}.",
            ),
        )

    def _identify_net_borrowing_tier(self, fcfe_res: MetricResult) -> str | None:
        """Extract net borrowing tier utilized from provenance and diagnostics."""
        for d in fcfe_res.diagnostics:
            if d.code.value == "ZERO_NET_BORROWING_VERIFIED":
                return "TIER_3_ZERO_DEBT_VERIFIED"
            if d.code.value == "NET_BORROWING_UNAVAILABLE":
                return "TIER_4_UNAVAILABLE"
        if "Net Issuance Payments Of Debt" in fcfe_res.provenance.source_concepts:
            return "TIER_2_REPORTED_AGGREGATE"
        if "Issuance Of Debt" in fcfe_res.provenance.source_concepts:
            return "TIER_1_ITEMIZED_FLOWS"
        return None
