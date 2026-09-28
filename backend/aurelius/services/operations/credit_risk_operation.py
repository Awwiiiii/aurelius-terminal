"""
aurelius.services.operations.credit_risk_operation
==================================================
Application operation coordinating Piotroski F-Score and Altman Z-Score
credit analytics with strictly deterministic dispatch (zero model override).
"""

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FiscalPeriodType,
    StatementType,
)
from aurelius.domain.errors import DataNotFoundError
from aurelius.domain.fundamental.engines.credit import (
    AltmanZScoreResult,
    FundamentalCreditEngine,
    PiotroskiResult,
)
from aurelius.domain.fundamental.period_matching import (
    MultiPeriodFactStore,
    get_prior_period,
    sort_periods_chronologically,
)
from aurelius.domain.validation import validate_ticker
from aurelius.providers.base import MarketDataProvider
from aurelius.services.financial_statement_service import (
    FinancialStatementService,
)
from aurelius.services.operations.market_cap_resolver import MarketCapResolver


class CreditRiskOperation:
    """
    Orchestrates credit risk and insolvency distress evaluation:
    Piotroski F-Score (9 canonical signals, 2-point Average Assets F5)
    and Altman Z-Score (deterministic balance sheet structural dispatch).
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
        PiotroskiResult,
        AltmanZScoreResult,
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

        # Period and Multi-Lag Periods Resolution
        target_period: FinancialPeriod
        prior_period: FinancialPeriod | None = None
        prior_prior_period: FinancialPeriod | None = None

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
            if prior_period is not None:
                prior_prior_period = get_prior_period(
                    prior_period, sorted_periods, frequency
                )

        # Market Capitalization (for Altman X4 factor)
        res_result = await MarketCapResolver.resolve(
            self.provider, normalized_ticker, target_period, sorted_periods
        )
        market_cap_val = res_result.value

        # 1. Piotroski F-Score (9 canonical signals, 2-point Average Assets F5)
        piotroski_res = FundamentalCreditEngine.calculate_piotroski_f_score(
            current_period=target_period,
            prior_period=prior_period,
            prior_prior_period=prior_prior_period,
            fact_store=fact_store,
        )

        # 2. Altman Z-Score (Deterministic structural dispatch - NO client override)
        altman_res = FundamentalCreditEngine.calculate_altman_z_score(
            period=target_period,
            fact_store=fact_store,
            market_cap=market_cap_val,
            altman_model_override=None,  # STRICT PROHIBITION: client override forbidden
        )

        return target_period, reporting_currency, piotroski_res, altman_res
