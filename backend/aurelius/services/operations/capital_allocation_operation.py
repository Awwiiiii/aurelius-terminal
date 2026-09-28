"""
aurelius.services.operations.capital_allocation_operation
=========================================================
Application operation coordinating Capital Allocation and Shareholder Yield metrics.
"""

from typing import TYPE_CHECKING

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FiscalPeriodType,
    StatementType,
)
from aurelius.domain.errors import DataNotFoundError
from aurelius.domain.fundamental.engines.capital_allocation import (
    CapitalAllocationEngine,
)
from aurelius.domain.fundamental.models import (
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

if TYPE_CHECKING:
    pass


class CapitalAllocationOperation:
    """
    Orchestrates reported capital allocation cash flows and shareholder return yields.
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

        # Market Capitalization Resolution (Strict Temporal Compatibility)
        res_result = await MarketCapResolver.resolve(
            self.provider, normalized_ticker, target_period, sorted_periods
        )
        resolved_market_cap = res_result.value

        # Compute Metrics via Phase 1 CapitalAllocationEngine
        metrics: dict[str, MetricResult] = {}
        metrics["cfo"] = CapitalAllocationEngine.calculate_operating_cash_flow(
            target_period, fact_store
        )
        metrics["capex"] = CapitalAllocationEngine.calculate_capital_expenditures(
            target_period, fact_store
        )
        metrics["dividends_paid"] = CapitalAllocationEngine.calculate_dividends_paid(
            target_period, fact_store
        )
        metrics["stock_repurchases"] = (
            CapitalAllocationEngine.calculate_stock_repurchases(
                target_period, fact_store
            )
        )
        metrics["stock_issuance"] = CapitalAllocationEngine.calculate_stock_issuance(
            target_period, fact_store
        )
        metrics["debt_issued"] = CapitalAllocationEngine.calculate_debt_issued(
            target_period, fact_store
        )
        metrics["debt_repaid"] = CapitalAllocationEngine.calculate_debt_repaid(
            target_period, fact_store
        )
        metrics["net_debt_issued"] = CapitalAllocationEngine.calculate_net_debt_issued(
            target_period, fact_store
        )
        metrics["acquisitions_mna"] = CapitalAllocationEngine.calculate_ma_investment(
            target_period, fact_store
        )

        # Market-cap based yields
        metrics["dividend_yield"] = CapitalAllocationEngine.calculate_dividend_yield(
            target_period, fact_store, resolved_market_cap
        )
        metrics["buyback_yield"] = CapitalAllocationEngine.calculate_buyback_yield(
            target_period, fact_store, resolved_market_cap
        )
        metrics["gross_shareholder_yield"] = (
            CapitalAllocationEngine.calculate_gross_shareholder_yield(
                target_period, fact_store, resolved_market_cap
            )
        )
        metrics["net_shareholder_yield"] = (
            CapitalAllocationEngine.calculate_net_shareholder_yield(
                target_period, fact_store, resolved_market_cap
            )
        )

        return target_period, reporting_currency, metrics
