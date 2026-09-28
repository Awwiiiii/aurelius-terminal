"""
aurelius.services.capital_cashflow_credit_service
=================================================
Orchestration facade coordinating M7B.3 Capital Allocation, Cash Flows,
Enterprise Value Bridge, and Credit Risk operations.
"""

from typing import Annotated

from fastapi import Depends

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FiscalPeriodType,
)
from aurelius.domain.fundamental.engines.credit import (
    AltmanZScoreResult,
    PiotroskiResult,
)
from aurelius.domain.fundamental.engines.enterprise_value import (
    CapitalStructureResult,
)
from aurelius.domain.fundamental.engines.free_cash_flow import (
    FCFFReconciliationResult,
)
from aurelius.domain.fundamental.models import (
    MetricResult,
)
from aurelius.providers.base import MarketDataProvider
from aurelius.providers.registry import get_market_data_provider
from aurelius.services.financial_statement_service import (
    FinancialStatementService,
    get_financial_statement_service,
)
from aurelius.services.operations.capital_allocation_operation import (
    CapitalAllocationOperation,
)
from aurelius.services.operations.cash_flow_working_capital_operation import (
    CashFlowWorkingCapitalOperation,
)
from aurelius.services.operations.credit_risk_operation import (
    CreditRiskOperation,
)
from aurelius.services.operations.enterprise_value_operation import (
    EnterpriseValueCapitalStructureOperation,
)


class CapitalCashflowCreditService:
    """
    Application service facade coordinating specialized M7B.3 operations.
    Delegates all domain math to pure Phase 1 engines via focused collaborators.
    """

    def __init__(
        self,
        capital_allocation_op: CapitalAllocationOperation,
        cash_flow_working_capital_op: CashFlowWorkingCapitalOperation,
        enterprise_value_op: EnterpriseValueCapitalStructureOperation,
        credit_risk_op: CreditRiskOperation,
    ) -> None:
        self.capital_allocation_op = capital_allocation_op
        self.cash_flow_working_capital_op = cash_flow_working_capital_op
        self.enterprise_value_op = enterprise_value_op
        self.credit_risk_op = credit_risk_op

    async def get_capital_allocation(
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
        return await self.capital_allocation_op.execute(
            ticker=ticker,
            frequency=frequency,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
        )

    async def get_cash_flows(
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
        return await self.cash_flow_working_capital_op.execute(
            ticker=ticker,
            frequency=frequency,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
        )

    async def get_enterprise_value(
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
        return await self.enterprise_value_op.execute(
            ticker=ticker,
            frequency=frequency,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
        )

    async def get_credit_risk(
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
        return await self.credit_risk_op.execute(
            ticker=ticker,
            frequency=frequency,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
        )

    async def get_m7b3_comprehensive_dossier(
        self,
        ticker: str,
        frequency: FiscalPeriodType,
        fiscal_year: int | None = None,
        fiscal_period: str | None = None,
    ) -> dict:
        """
        Unified multi-dimensional dossier orchestrating all four operations.
        """
        ca = await self.get_capital_allocation(
            ticker, frequency, fiscal_year, fiscal_period
        )
        cf = await self.get_cash_flows(ticker, frequency, fiscal_year, fiscal_period)
        ev = await self.get_enterprise_value(
            ticker, frequency, fiscal_year, fiscal_period
        )
        cr = await self.get_credit_risk(ticker, frequency, fiscal_year, fiscal_period)

        return {
            "period": ca[0],
            "reporting_currency": ca[1],
            "capital_allocation": ca,
            "cash_flows": cf,
            "enterprise_value": ev,
            "credit_risk": cr,
        }


# ---------------------------------------------------------------------------
# Dependency Providers for FastAPI DI
# ---------------------------------------------------------------------------


def get_capital_allocation_operation(
    statement_service: Annotated[
        FinancialStatementService, Depends(get_financial_statement_service)
    ],
    provider: Annotated[MarketDataProvider, Depends(get_market_data_provider)],
) -> CapitalAllocationOperation:
    return CapitalAllocationOperation(
        statement_service=statement_service, provider=provider
    )


def get_cash_flow_working_capital_operation(
    statement_service: Annotated[
        FinancialStatementService, Depends(get_financial_statement_service)
    ],
) -> CashFlowWorkingCapitalOperation:
    return CashFlowWorkingCapitalOperation(statement_service=statement_service)


def get_enterprise_value_operation(
    statement_service: Annotated[
        FinancialStatementService, Depends(get_financial_statement_service)
    ],
    provider: Annotated[MarketDataProvider, Depends(get_market_data_provider)],
) -> EnterpriseValueCapitalStructureOperation:
    return EnterpriseValueCapitalStructureOperation(
        statement_service=statement_service, provider=provider
    )


def get_credit_risk_operation(
    statement_service: Annotated[
        FinancialStatementService, Depends(get_financial_statement_service)
    ],
    provider: Annotated[MarketDataProvider, Depends(get_market_data_provider)],
) -> CreditRiskOperation:
    return CreditRiskOperation(statement_service=statement_service, provider=provider)


def get_capital_cashflow_credit_service(
    ca_op: Annotated[
        CapitalAllocationOperation, Depends(get_capital_allocation_operation)
    ],
    cf_op: Annotated[
        CashFlowWorkingCapitalOperation,
        Depends(get_cash_flow_working_capital_operation),
    ],
    ev_op: Annotated[
        EnterpriseValueCapitalStructureOperation,
        Depends(get_enterprise_value_operation),
    ],
    cr_op: Annotated[CreditRiskOperation, Depends(get_credit_risk_operation)],
) -> CapitalCashflowCreditService:
    return CapitalCashflowCreditService(
        capital_allocation_op=ca_op,
        cash_flow_working_capital_op=cf_op,
        enterprise_value_op=ev_op,
        credit_risk_op=cr_op,
    )
