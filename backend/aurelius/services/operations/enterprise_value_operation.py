"""
aurelius.services.operations.enterprise_value_operation
======================================================
Application operation coordinating Enterprise Value Bridge
and Capital Structure Weights with strict temporal compatibility.
"""

from decimal import Decimal

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FiscalPeriodType,
    StatementType,
    Unit,
)
from aurelius.domain.errors import DataNotFoundError
from aurelius.domain.fundamental.engines.enterprise_value import (
    CapitalStructureResult,
    EnterpriseValueBridgeEngine,
)
from aurelius.domain.fundamental.engines.solvency import SolvencyEngine
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
    sort_periods_chronologically,
)
from aurelius.domain.validation import validate_ticker
from aurelius.providers.base import MarketDataProvider
from aurelius.services.financial_statement_service import (
    FinancialStatementService,
)
from aurelius.services.operations.market_cap_resolver import MarketCapResolver


class EnterpriseValueCapitalStructureOperation:
    """
    Orchestrates Enterprise Value and Capital Structure Weights.
    Enforces strict temporal matching between balance-sheet dates and market capitalization.
    """

    def __init__(
        self,
        statement_service: FinancialStatementService,
        provider: MarketDataProvider,
    ) -> None:
        self.statement_service = statement_service
        self.provider = provider

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
        str,
        str,
        CapitalStructureResult,
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

        # Period Resolution
        target_period: FinancialPeriod
        if frequency == FiscalPeriodType.TTM:
            from aurelius.services.operations.ttm_helpers import (
                find_ttm_window_and_prior,
                synthesize_ttm_statements,
            )

            target_window, _ = find_ttm_window_and_prior(
                sorted_periods, fiscal_year, fiscal_period
            )
            if target_window is None:
                raise DataNotFoundError(
                    ticker=normalized_ticker,
                    message="Insufficient consecutive quarterly periods to form a valid TTM window.",
                )
            target_period = target_window.ttm_period
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

        # ---------------------------------------------------------------------
        # Temporal Market Capitalization Verification
        # ---------------------------------------------------------------------
        res_result = await MarketCapResolver.resolve(
            self.provider, normalized_ticker, target_period, sorted_periods
        )
        market_cap_val = res_result.value

        metrics: dict[str, MetricResult] = {}

        # 1. Market Capitalization MetricResult
        if market_cap_val is not None:
            metrics["market_capitalization"] = MetricResult(
                metric_id=FundamentalMetricId.MARKET_CAPITALIZATION,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.VALID,
                value=market_cap_val,
                unit=Unit.CURRENCY,
                currency=reporting_currency or Currency.USD,
                period=target_period,
                diagnostics=[],
                provenance=MetricProvenance(
                    formula_id="FORMULA_MARKET_CAP_CONTEMPORARY_V1",
                    methodology_version="1.0.0",
                    source_concepts=["MARKET_CAPITALIZATION"],
                    source_periods=[target_period.period_key],
                    methodology_notes=res_result.methodology_notes,
                ),
            )
        else:
            metrics["market_capitalization"] = MetricResult(
                metric_id=FundamentalMetricId.MARKET_CAPITALIZATION,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=reporting_currency or Currency.USD,
                period=target_period,
                diagnostics=res_result.diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_MARKET_CAP_UNAVAILABLE",
                    methodology_version="1.0.0",
                    source_concepts=["MARKET_CAPITALIZATION"],
                    source_periods=[target_period.period_key],
                    methodology_notes=res_result.methodology_notes,
                ),
            )

        # 2. Gross Debt
        metrics["gross_debt"] = SolvencyEngine.calculate_gross_debt(
            target_period, fact_store
        )

        # 3. Cash and Liquid Investments
        metrics["cash_and_liquid_investments"] = self._resolve_cash_liquid(
            target_period, fact_store
        )

        # 4. Preferred Equity & Minority Interest (4-case disclosure taxonomies)
        pref_val, pref_facts, pref_concepts, pref_diags, pref_notes = (
            EnterpriseValueBridgeEngine.resolve_preferred_equity(
                target_period, fact_store
            )
        )
        pref_case = self._classify_disclosure_case(pref_val, pref_diags)
        metrics["preferred_equity"] = MetricResult(
            metric_id=FundamentalMetricId.PREFERRED_EQUITY,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID
            if pref_val is not None
            else MetricStatus.UNAVAILABLE,
            value=pref_val,
            unit=Unit.CURRENCY,
            currency=reporting_currency,
            period=target_period,
            diagnostics=pref_diags,
            provenance=MetricProvenance(
                formula_id="FORMULA_PREFERRED_EQUITY_TAXONOMY_V1",
                methodology_version="1.0.0",
                source_fact_ids=[f.fact_id for f in pref_facts],
                source_concepts=pref_concepts,
                source_periods=[target_period.period_key],
                methodology_notes=pref_notes,
            ),
        )

        min_val, min_facts, min_concepts, min_diags, min_notes = (
            EnterpriseValueBridgeEngine.resolve_minority_interest(
                target_period, fact_store
            )
        )
        min_case = self._classify_disclosure_case(min_val, min_diags)
        metrics["minority_interest"] = MetricResult(
            metric_id=FundamentalMetricId.MINORITY_INTEREST,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID
            if min_val is not None
            else MetricStatus.UNAVAILABLE,
            value=min_val,
            unit=Unit.CURRENCY,
            currency=reporting_currency,
            period=target_period,
            diagnostics=min_diags,
            provenance=MetricProvenance(
                formula_id="FORMULA_MINORITY_INTEREST_TAXONOMY_V1",
                methodology_version="1.0.0",
                source_fact_ids=[f.fact_id for f in min_facts],
                source_concepts=min_concepts,
                source_periods=[target_period.period_key],
                methodology_notes=min_notes,
            ),
        )

        # 5. Enterprise Value Bridge
        metrics["enterprise_value"] = (
            EnterpriseValueBridgeEngine.calculate_enterprise_value(
                target_period, fact_store, market_cap_val
            )
        )

        # 6. Capital Structure Weights
        cap_struct_res = (
            EnterpriseValueBridgeEngine.calculate_capital_structure_weights(
                target_period, fact_store, market_cap_val
            )
        )
        metrics["total_capital"] = cap_struct_res.total_capital
        metrics["weight_equity"] = cap_struct_res.weight_equity
        metrics["weight_debt"] = cap_struct_res.weight_debt
        metrics["weight_preferred"] = cap_struct_res.weight_preferred

        return (
            target_period,
            reporting_currency,
            metrics,
            pref_case,
            min_case,
            cap_struct_res,
        )

    def _resolve_cash_liquid(
        self,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        from aurelius.domain.entities.financials import CanonicalConcept

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
        if cash_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.CASH_AND_SHORT_TERM_INVESTMENTS,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Cash and equivalents line item is missing from balance sheet.",
                        details={"period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CASH_LIQUID_V1",
                    methodology_version="1.0.0",
                    source_concepts=["CASH_AND_EQUIVALENTS"],
                    source_periods=[period.period_key],
                ),
            )

        cash_val = cash_fact.value
        sti_val = sti_fact.value if sti_fact else Decimal(0)
        tot_liquid = cash_val + sti_val

        source_fact_ids = [cash_fact.fact_id]
        source_concepts = ["CASH_AND_EQUIVALENTS"]
        if sti_fact:
            source_fact_ids.append(sti_fact.fact_id)
            source_concepts.append("SHORT_TERM_INVESTMENTS")

        return MetricResult(
            metric_id=FundamentalMetricId.CASH_AND_SHORT_TERM_INVESTMENTS,
            category=MetricCategory.LIQUIDITY,
            status=MetricStatus.VALID,
            value=tot_liquid,
            unit=Unit.CURRENCY,
            currency=cash_fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_CASH_LIQUID_V1",
                methodology_version="1.0.0",
                source_fact_ids=source_fact_ids,
                source_concepts=source_concepts,
                source_periods=[period.period_key],
                methodology_notes=f"Cash & Liquid Investments = Cash ({cash_val}) + Short-Term Investments ({sti_val}) = {tot_liquid}.",
            ),
        )

    def _classify_disclosure_case(
        self,
        val: Decimal | None,
        diags: list[MetricDiagnostic],
    ) -> str:
        for d in diags:
            if (
                d.code == DiagnosticCode.PREFERRED_EQUITY_CONFIDENTLY_ABSENT
                or d.code == DiagnosticCode.MINORITY_INTEREST_CONFIDENTLY_ABSENT
            ):
                return "CONFIDENTLY_ABSENT"
            if (
                d.code == DiagnosticCode.PREFERRED_EQUITY_INSUFFICIENTLY_DISCLOSED
                or d.code == DiagnosticCode.MINORITY_INTEREST_INSUFFICIENTLY_DISCLOSED
            ):
                return "INSUFFICIENTLY_DISCLOSED"
        if val is not None:
            return "REPORTED_NON_ZERO" if val != Decimal(0) else "REPORTED_ZERO"
        return "INSUFFICIENTLY_DISCLOSED"
