"""
tests.unit.services.test_capital_cashflow_credit_service
========================================================
Unit tests for M7B.3 application operations and CapitalCashflowCreditService facade.
Verifies:
  - Capital allocation flows and shareholder yields
  - Operating NWC, Delta NWC, FCFF dual methodologies, FCFE, Reinvestment, and Growth
  - Enterprise Value temporal market cap matching and 4-case disclosure taxonomy
  - Canonical 9-signal Piotroski and structural Altman scoring (zero client override)
  - Full audit provenance and traceable diagnostic aggregation
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FiscalPeriodLabel,
    FiscalPeriodType,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    MetricStatus,
)
from aurelius.providers.base import MarketDataProvider
from aurelius.services.capital_cashflow_credit_service import (
    CapitalCashflowCreditService,
)
from aurelius.services.financial_statement_service import (
    FinancialStatementService,
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
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)


def _build_test_statements_m7b3():
    """Build multi-period statements for testing M7B.3 operations."""
    p2022 = make_period("2022-12-31", fiscal_year=2022, start_date=date(2022, 1, 1))
    p2023 = make_period("2023-12-31", fiscal_year=2023, start_date=date(2023, 1, 1))
    p2024 = make_period("2024-12-31", fiscal_year=2024, start_date=date(2024, 1, 1))

    p2022_inst = make_period(
        "2022-12-31", period_type=PeriodType.INSTANT, fiscal_year=2022
    )
    p2023_inst = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )
    p2024_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )

    # Income Statements
    inc_2022 = make_statement(
        StatementType.INCOME_STATEMENT,
        p2022,
        [
            make_fact(
                StatementType.INCOME_STATEMENT, "1000", p2022, CanonicalConcept.REVENUE
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "500",
                p2022,
                CanonicalConcept.GROSS_PROFIT,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "200",
                p2022,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "20",
                p2022,
                source_concept="Interest Expense",
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "180",
                p2022,
                CanonicalConcept.PRETAX_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "36",
                p2022,
                CanonicalConcept.INCOME_TAX_EXPENSE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "144",
                p2022,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )
    inc_2023 = make_statement(
        StatementType.INCOME_STATEMENT,
        p2023,
        [
            make_fact(
                StatementType.INCOME_STATEMENT, "1200", p2023, CanonicalConcept.REVENUE
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "600",
                p2023,
                CanonicalConcept.GROSS_PROFIT,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "250",
                p2023,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "25",
                p2023,
                source_concept="Interest Expense",
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "225",
                p2023,
                CanonicalConcept.PRETAX_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "45",
                p2023,
                CanonicalConcept.INCOME_TAX_EXPENSE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "180",
                p2023,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )
    inc_2024 = make_statement(
        StatementType.INCOME_STATEMENT,
        p2024,
        [
            make_fact(
                StatementType.INCOME_STATEMENT, "1500", p2024, CanonicalConcept.REVENUE
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "800",
                p2024,
                CanonicalConcept.GROSS_PROFIT,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "300",
                p2024,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "30",
                p2024,
                source_concept="Interest Expense",
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "270",
                p2024,
                CanonicalConcept.PRETAX_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "54",
                p2024,
                CanonicalConcept.INCOME_TAX_EXPENSE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "216",
                p2024,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )

    # Balance Sheets
    bal_2022 = make_statement(
        StatementType.BALANCE_SHEET,
        p2022_inst,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "2000",
                p2022_inst,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "800",
                p2022_inst,
                CanonicalConcept.CURRENT_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "400",
                p2022_inst,
                CanonicalConcept.CURRENT_LIABILITIES,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "200",
                p2022_inst,
                CanonicalConcept.CASH_AND_EQUIVALENTS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "100",
                p2022_inst,
                CanonicalConcept.SHORT_TERM_INVESTMENTS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "150",
                p2022_inst,
                CanonicalConcept.INVENTORY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET, "400", p2022_inst, source_concept="Net PPE"
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "300",
                p2022_inst,
                CanonicalConcept.LONG_TERM_DEBT,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "500",
                p2022_inst,
                CanonicalConcept.TOTAL_LIABILITIES,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1500",
                p2022_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1500",
                p2022_inst,
                source_concept="Common Stock Equity",
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "600",
                p2022_inst,
                source_concept="Retained Earnings",
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1000",
                p2022_inst,
                source_concept="Ordinary Shares Number",
            ),
        ],
    )
    bal_2023 = make_statement(
        StatementType.BALANCE_SHEET,
        p2023_inst,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "2400",
                p2023_inst,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1000",
                p2023_inst,
                CanonicalConcept.CURRENT_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "500",
                p2023_inst,
                CanonicalConcept.CURRENT_LIABILITIES,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "250",
                p2023_inst,
                CanonicalConcept.CASH_AND_EQUIVALENTS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "100",
                p2023_inst,
                CanonicalConcept.SHORT_TERM_INVESTMENTS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "180",
                p2023_inst,
                CanonicalConcept.INVENTORY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET, "500", p2023_inst, source_concept="Net PPE"
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "350",
                p2023_inst,
                CanonicalConcept.LONG_TERM_DEBT,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "650",
                p2023_inst,
                CanonicalConcept.TOTAL_LIABILITIES,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1750",
                p2023_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1750",
                p2023_inst,
                source_concept="Common Stock Equity",
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "750",
                p2023_inst,
                source_concept="Retained Earnings",
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1000",
                p2023_inst,
                source_concept="Ordinary Shares Number",
            ),
        ],
    )
    bal_2024 = make_statement(
        StatementType.BALANCE_SHEET,
        p2024_inst,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "2800",
                p2024_inst,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1200",
                p2024_inst,
                CanonicalConcept.CURRENT_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "600",
                p2024_inst,
                CanonicalConcept.CURRENT_LIABILITIES,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "300",
                p2024_inst,
                CanonicalConcept.CASH_AND_EQUIVALENTS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "100",
                p2024_inst,
                CanonicalConcept.SHORT_TERM_INVESTMENTS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "200",
                p2024_inst,
                CanonicalConcept.INVENTORY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET, "600", p2024_inst, source_concept="Net PPE"
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "300",
                p2024_inst,
                CanonicalConcept.LONG_TERM_DEBT,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "700",
                p2024_inst,
                CanonicalConcept.TOTAL_LIABILITIES,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "2100",
                p2024_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "2100",
                p2024_inst,
                source_concept="Common Stock Equity",
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "950",
                p2024_inst,
                source_concept="Retained Earnings",
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1000",
                p2024_inst,
                source_concept="Ordinary Shares Number",
            ),
        ],
    )

    # Cash Flow Statements
    cf_2022 = make_statement(
        StatementType.CASH_FLOW,
        p2022,
        [
            make_fact(
                StatementType.CASH_FLOW,
                "220",
                p2022,
                CanonicalConcept.OPERATING_CASH_FLOW,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "60",
                p2022,
                CanonicalConcept.CAPITAL_EXPENDITURES,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "50",
                p2022,
                source_concept="Depreciation And Amortization",
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "30",
                p2022,
                source_concept="Cash Dividends Paid",
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "20",
                p2022,
                source_concept="Repurchase Of Capital Stock",
            ),
            make_fact(
                StatementType.CASH_FLOW, "50", p2022, source_concept="Issuance Of Debt"
            ),
            make_fact(
                StatementType.CASH_FLOW, "30", p2022, source_concept="Repayment Of Debt"
            ),
        ],
    )
    cf_2023 = make_statement(
        StatementType.CASH_FLOW,
        p2023,
        [
            make_fact(
                StatementType.CASH_FLOW,
                "260",
                p2023,
                CanonicalConcept.OPERATING_CASH_FLOW,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "70",
                p2023,
                CanonicalConcept.CAPITAL_EXPENDITURES,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "55",
                p2023,
                source_concept="Depreciation And Amortization",
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "35",
                p2023,
                source_concept="Cash Dividends Paid",
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "25",
                p2023,
                source_concept="Repurchase Of Capital Stock",
            ),
            make_fact(
                StatementType.CASH_FLOW, "60", p2023, source_concept="Issuance Of Debt"
            ),
            make_fact(
                StatementType.CASH_FLOW, "40", p2023, source_concept="Repayment Of Debt"
            ),
        ],
    )
    cf_2024 = make_statement(
        StatementType.CASH_FLOW,
        p2024,
        [
            make_fact(
                StatementType.CASH_FLOW,
                "310",
                p2024,
                CanonicalConcept.OPERATING_CASH_FLOW,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "80",
                p2024,
                CanonicalConcept.CAPITAL_EXPENDITURES,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "60",
                p2024,
                source_concept="Depreciation And Amortization",
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "40",
                p2024,
                source_concept="Cash Dividends Paid",
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "30",
                p2024,
                source_concept="Repurchase Of Capital Stock",
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "0",
                p2024,
                source_concept="Common Stock Issuance",
            ),
            make_fact(
                StatementType.CASH_FLOW, "40", p2024, source_concept="Issuance Of Debt"
            ),
            make_fact(
                StatementType.CASH_FLOW, "50", p2024, source_concept="Repayment Of Debt"
            ),
        ],
    )

    return (
        [inc_2022, inc_2023, inc_2024],
        [bal_2022, bal_2023, bal_2024],
        [cf_2022, cf_2023, cf_2024],
    )


@pytest.fixture
def mock_statement_service():
    inc, bal, cf = _build_test_statements_m7b3()
    mock_service = AsyncMock(spec=FinancialStatementService)

    async def _mock_get_statements(ticker, st_type, freq):
        if st_type == StatementType.INCOME_STATEMENT:
            return inc
        if st_type == StatementType.BALANCE_SHEET:
            return bal
        if st_type == StatementType.CASH_FLOW:
            return cf
        return []

    mock_service.get_statements.side_effect = _mock_get_statements
    return mock_service


@pytest.fixture
def mock_market_data_provider():
    mock_provider = AsyncMock(spec=MarketDataProvider)
    return mock_provider


@pytest.fixture
def service_facade(mock_statement_service, mock_market_data_provider):
    ca_op = CapitalAllocationOperation(
        mock_statement_service, mock_market_data_provider
    )
    cf_op = CashFlowWorkingCapitalOperation(mock_statement_service)
    ev_op = EnterpriseValueCapitalStructureOperation(
        mock_statement_service, mock_market_data_provider
    )
    cr_op = CreditRiskOperation(mock_statement_service, mock_market_data_provider)
    return CapitalCashflowCreditService(
        capital_allocation_op=ca_op,
        cash_flow_working_capital_op=cf_op,
        enterprise_value_op=ev_op,
        credit_risk_op=cr_op,
    )


# =============================================================================
# TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_capital_allocation_operation(service_facade):
    period, rep_curr, metrics = await service_facade.get_capital_allocation(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2024
    )
    assert period.fiscal_year == 2024
    assert metrics["cfo"].status == MetricStatus.VALID
    assert metrics["cfo"].value == Decimal("310")
    assert metrics["capex"].value == Decimal("80")
    assert metrics["dividends_paid"].value == Decimal("40")
    assert metrics["stock_repurchases"].value == Decimal("30")
    # Historical market cap is unavailable from mock provider -> yield metrics UNAVAILABLE
    assert metrics["dividend_yield"].status == MetricStatus.UNAVAILABLE
    assert (
        metrics["dividend_yield"].diagnostics[0].code
        == DiagnosticCode.MARKET_CAP_UNAVAILABLE
    )


@pytest.mark.asyncio
async def test_cash_flow_working_capital_operation(service_facade):
    period, rep_curr, metrics, recon_res, nb_tier = await service_facade.get_cash_flows(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2024
    )
    assert period.fiscal_year == 2024
    # Operating NWC = (1200 - 300 - 100) - (600 - 0) = 800 - 600 = 200
    assert metrics["operating_nwc"].value == Decimal("200")
    # Delta NWC = NWC(2024) [200] - NWC(2023) [(1000 - 250 - 100) - 500 = 150] = 50
    assert metrics["delta_nwc"].value == Decimal("50")

    # FCFF primary: NOPAT + D&A - CapEx - Delta NWC
    # NOPAT = 300 * (1 - 54/270 = 0.2) = 240
    # FCFF = 240 + 60 - 80 - 50 = 170
    assert metrics["fcff_primary"].status == MetricStatus.VALID
    assert metrics["fcff_primary"].value == Decimal("170")

    # FCFE = CFO (310) - CapEx (80) + Net Borrowing (-10) - Preferred Divs (0) = 220
    assert metrics["fcfe"].status == MetricStatus.VALID
    assert metrics["fcfe"].value == Decimal("220")
    assert nb_tier == "TIER_1_ITEMIZED_FLOWS"

    # Reinvestment = CapEx (80) - D&A (60) + Delta NWC (50) = 70
    assert metrics["reinvestment"].value == Decimal("70")
    # Reinvestment Rate = 70 / 240 = 0.291666...
    assert metrics["reinvestment_rate"].status == MetricStatus.VALID


@pytest.mark.asyncio
async def test_enterprise_value_temporal_rule(service_facade):
    # Historical fiscal year 2023 -> historical market cap unavailable -> EV UNAVAILABLE
    (
        period,
        rep_curr,
        metrics,
        pref_case,
        min_case,
        cap_struct_res,
    ) = await service_facade.get_enterprise_value(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2023
    )
    assert metrics["market_capitalization"].status == MetricStatus.UNAVAILABLE
    assert metrics["enterprise_value"].status == MetricStatus.UNAVAILABLE
    assert (
        metrics["enterprise_value"].diagnostics[0].code
        == DiagnosticCode.MARKET_CAP_UNAVAILABLE
    )
    # Disclosure case should be CONFIDENTLY_ABSENT since common stock equity == stockholders equity
    assert pref_case == "CONFIDENTLY_ABSENT"


@pytest.mark.asyncio
async def test_credit_risk_piotroski_and_altman(service_facade):
    period, rep_curr, piotroski_res, altman_res = await service_facade.get_credit_risk(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2024
    )
    # Piotroski F-score verification
    assert piotroski_res.total_signal_count == 9
    assert piotroski_res.evaluated_signal_count == 9
    assert piotroski_res.status == MetricStatus.VALID

    # F5 Canonical Leverage Check:
    # 2024 LTD = 300, Avg Assets 2024 = (2400 + 2800) / 2 = 2600. Lever 2024 = 300 / 2600 = 0.11538
    # 2023 LTD = 350, Avg Assets 2023 = (2000 + 2400) / 2 = 2200. Lever 2023 = 350 / 2200 = 0.15909
    # Leverage decreased from 0.159 to 0.115 -> F5 must PASS!
    f5_sig = next(s for s in piotroski_res.signals if s.signal_id == "F5_DELTA_LEVER")
    assert f5_sig.status == "PASS"

    # Altman Z-Score: Inventory / TA = 200/2800 = 7.1% (>= 5%), Net PPE / TA = 600/2800 = 21.4% (>= 15%)
    # Structural dispatch must select MODEL_1_MANUFACTURING
    assert altman_res.dispatched_model == "MODEL_1_MANUFACTURING"


@pytest.mark.asyncio
async def test_comprehensive_dossier(service_facade):
    dossier = await service_facade.get_m7b3_comprehensive_dossier(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2024
    )
    assert dossier["period"].fiscal_year == 2024
    assert "capital_allocation" in dossier
    assert "cash_flows" in dossier
    assert "enterprise_value" in dossier
    assert "credit_risk" in dossier


@pytest.mark.asyncio
async def test_capital_allocation_compatible_market_cap_yields(mock_statement_service):
    # Mock provider supplying contemporary market cap for latest period with verified as_of_date
    mock_prov = AsyncMock(spec=MarketDataProvider)

    # Simulate yfinance _get_ticker fast_info with verified contemporary as_of_date
    class MockTicker:
        fast_info = {"market_cap": 2500.0, "as_of_date": date(2024, 12, 31)}

    mock_prov._get_ticker = lambda t: MockTicker()

    ca_op = CapitalAllocationOperation(mock_statement_service, mock_prov)
    period, rep_curr, metrics = await ca_op.execute(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2024
    )
    # Market cap 2500 is resolved
    # Divs = 40 -> 40 / 2500 = 0.016
    assert metrics["dividend_yield"].status == MetricStatus.VALID
    assert metrics["dividend_yield"].value == Decimal("40") / Decimal("2500")

    # Repurchases = 30 -> 30 / 2500 = 0.012
    assert metrics["buyback_yield"].status == MetricStatus.VALID
    assert metrics["buyback_yield"].value == Decimal("30") / Decimal("2500")

    # Gross Shareholder Yield = (40 + 30) / 2500 = 70 / 2500 = 0.028
    assert metrics["gross_shareholder_yield"].status == MetricStatus.VALID
    assert metrics["gross_shareholder_yield"].value == Decimal("70") / Decimal("2500")

    # Net Shareholder Yield = (40 + 30 - 0) / 2500 = 0.028
    assert metrics["net_shareholder_yield"].status == MetricStatus.VALID
    assert metrics["net_shareholder_yield"].value == Decimal("70") / Decimal("2500")


@pytest.mark.asyncio
async def test_market_cap_temporal_compatibility_rules(mock_statement_service):
    mock_prov = AsyncMock(spec=MarketDataProvider)

    # 1. Compatible as-of date accepted as VALID
    class CompatibleTicker:
        fast_info = {"market_cap": 3000.0, "as_of_date": date(2024, 12, 31)}

    mock_prov._get_ticker = lambda t: CompatibleTicker()
    ca_op = CapitalAllocationOperation(mock_statement_service, mock_prov)
    period, rep_curr, metrics = await ca_op.execute(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2024
    )
    assert metrics["dividend_yield"].status == MetricStatus.VALID

    # 2. Incompatible/stale as-of date is NOT accepted as VALID
    class StaleTicker:
        fast_info = {"market_cap": 3000.0, "as_of_date": date(2025, 2, 15)}

    mock_prov._get_ticker = lambda t: StaleTicker()
    period, rep_curr, metrics_stale = await ca_op.execute(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2024
    )
    assert metrics_stale["dividend_yield"].status == MetricStatus.UNAVAILABLE
    assert (
        metrics_stale["dividend_yield"].diagnostics[0].code
        == DiagnosticCode.MARKET_CAP_UNAVAILABLE
    )

    # 3. Missing quote/as-of metadata does not become VALID merely because it is the latest period
    class UnannotatedTicker:
        fast_info = {"market_cap": 3000.0}  # No as_of_date

    mock_prov._get_ticker = lambda t: UnannotatedTicker()
    period, rep_curr, metrics_no_date = await ca_op.execute(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2024
    )
    assert metrics_no_date["dividend_yield"].status == MetricStatus.UNAVAILABLE
    assert (
        metrics_no_date["dividend_yield"].diagnostics[0].code
        == DiagnosticCode.MARKET_CAP_UNAVAILABLE
    )

    # 4. Historical financial period cannot consume today's/current market cap (no leakage)
    class ContemporaryQuoteTicker:
        fast_info = {"market_cap": 3000.0, "as_of_date": date(2024, 12, 31)}

    mock_prov._get_ticker = lambda t: ContemporaryQuoteTicker()
    # Query FY2023 (historical)
    period_hist, rep_curr, metrics_hist = await ca_op.execute(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2023
    )
    assert metrics_hist["dividend_yield"].status == MetricStatus.UNAVAILABLE
    assert (
        metrics_hist["dividend_yield"].diagnostics[0].code
        == DiagnosticCode.MARKET_CAP_UNAVAILABLE
    )
    assert metrics_hist["buyback_yield"].status == MetricStatus.UNAVAILABLE
    assert metrics_hist["gross_shareholder_yield"].status == MetricStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_enterprise_value_temporal_compatibility_propagation(
    mock_statement_service,
):
    mock_prov = AsyncMock(spec=MarketDataProvider)

    # Stale quote date for latest period 2024 -> EV and Capital Weights UNAVAILABLE
    class StaleTicker:
        fast_info = {"market_cap": 3000.0, "as_of_date": date(2025, 3, 1)}

    mock_prov._get_ticker = lambda t: StaleTicker()
    ev_op = EnterpriseValueCapitalStructureOperation(mock_statement_service, mock_prov)
    (
        period,
        rep_curr,
        metrics,
        pref_case,
        min_case,
        cap_struct_res,
    ) = await ev_op.execute(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2024
    )

    # EV reports MARKET_CAP_UNAVAILABLE
    assert metrics["market_capitalization"].status == MetricStatus.UNAVAILABLE
    assert (
        metrics["market_capitalization"].diagnostics[0].code
        == DiagnosticCode.MARKET_CAP_UNAVAILABLE
    )
    assert metrics["enterprise_value"].status == MetricStatus.UNAVAILABLE
    assert (
        metrics["enterprise_value"].diagnostics[0].code
        == DiagnosticCode.MARKET_CAP_UNAVAILABLE
    )

    # Capital weights report MARKET_CAP_UNAVAILABLE
    assert metrics["weight_equity"].status == MetricStatus.UNAVAILABLE
    assert (
        metrics["weight_equity"].diagnostics[0].code
        == DiagnosticCode.MARKET_CAP_UNAVAILABLE
    )
    assert metrics["weight_debt"].status == MetricStatus.UNAVAILABLE
    assert (
        metrics["weight_debt"].diagnostics[0].code
        == DiagnosticCode.MARKET_CAP_UNAVAILABLE
    )

    # Missing date metadata on latest period -> also UNAVAILABLE
    class MissingDateTicker:
        fast_info = {"market_cap": 3000.0}

    mock_prov._get_ticker = lambda t: MissingDateTicker()
    (
        period,
        rep_curr,
        metrics_no_date,
        pref_case,
        min_case,
        cap_struct_res,
    ) = await ev_op.execute(
        ticker="AAPL", frequency=FiscalPeriodType.ANNUAL, fiscal_year=2024
    )
    assert metrics_no_date["market_capitalization"].status == MetricStatus.UNAVAILABLE
    assert metrics_no_date["enterprise_value"].status == MetricStatus.UNAVAILABLE
    assert metrics_no_date["weight_equity"].status == MetricStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_altman_service_model_and_financial_exemption(mock_market_data_provider):
    # 1. Service Model: low inventory and net PPE
    p2024 = make_period("2024-12-31", fiscal_year=2024, start_date=date(2024, 1, 1))
    p2024_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )

    inc = make_statement(
        StatementType.INCOME_STATEMENT,
        p2024,
        [
            make_fact(
                StatementType.INCOME_STATEMENT, "1000", p2024, CanonicalConcept.REVENUE
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "200",
                p2024,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "150",
                p2024,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )
    bal_service = make_statement(
        StatementType.BALANCE_SHEET,
        p2024_inst,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "2000",
                p2024_inst,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "800",
                p2024_inst,
                CanonicalConcept.CURRENT_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "400",
                p2024_inst,
                CanonicalConcept.CURRENT_LIABILITIES,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "20",
                p2024_inst,
                CanonicalConcept.INVENTORY,
            ),  # 20/2000 = 1% < 5%
            make_fact(
                StatementType.BALANCE_SHEET, "50", p2024_inst, source_concept="Net PPE"
            ),  # 50/2000 = 2.5% < 15%
            make_fact(
                StatementType.BALANCE_SHEET,
                "100",
                p2024_inst,
                CanonicalConcept.LONG_TERM_DEBT,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "500",
                p2024_inst,
                CanonicalConcept.TOTAL_LIABILITIES,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1500",
                p2024_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1500",
                p2024_inst,
                source_concept="Common Stock Equity",
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "600",
                p2024_inst,
                source_concept="Retained Earnings",
            ),
        ],
    )

    mock_svc = AsyncMock(spec=FinancialStatementService)
    mock_svc.get_statements.side_effect = lambda t, st, f: (
        [inc]
        if st == StatementType.INCOME_STATEMENT
        else ([bal_service] if st == StatementType.BALANCE_SHEET else [])
    )

    cr_op = CreditRiskOperation(mock_svc, mock_market_data_provider)
    _, _, _, altman_res = await cr_op.execute(
        "SERV", FiscalPeriodType.ANNUAL, fiscal_year=2024
    )
    assert altman_res.dispatched_model == "MODEL_2_SERVICE"

    # 2. Financial Exemption: unclassified balance sheet (no Current Assets)
    bal_fin = make_statement(
        StatementType.BALANCE_SHEET,
        p2024_inst,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "2000",
                p2024_inst,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1500",
                p2024_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "500",
                p2024_inst,
                CanonicalConcept.TOTAL_LIABILITIES,
            ),
        ],
    )
    mock_svc.get_statements.side_effect = lambda t, st, f: (
        [inc]
        if st == StatementType.INCOME_STATEMENT
        else ([bal_fin] if st == StatementType.BALANCE_SHEET else [])
    )
    _, _, _, altman_fin = await cr_op.execute(
        "BANK", FiscalPeriodType.ANNUAL, fiscal_year=2024
    )
    assert altman_fin.dispatched_model == "EXEMPT_FINANCIAL"
    assert altman_fin.metric_result.status == MetricStatus.NOT_APPLICABLE


@pytest.mark.asyncio
async def test_ttm_four_quarters_and_delta_nwc(mock_market_data_provider):
    # Construct 5 consecutive quarters: Q1 2023, Q2 2023, Q3 2023, Q4 2023, Q1 2024
    periods_q = [
        make_period(
            "2023-03-31",
            fiscal_year=2023,
            fiscal_period=FiscalPeriodLabel.Q1,
            start_date=date(2023, 1, 1),
        ),
        make_period(
            "2023-06-30",
            fiscal_year=2023,
            fiscal_period=FiscalPeriodLabel.Q2,
            start_date=date(2023, 4, 1),
        ),
        make_period(
            "2023-09-30",
            fiscal_year=2023,
            fiscal_period=FiscalPeriodLabel.Q3,
            start_date=date(2023, 7, 1),
        ),
        make_period(
            "2023-12-31",
            fiscal_year=2023,
            fiscal_period=FiscalPeriodLabel.Q4,
            start_date=date(2023, 10, 1),
        ),
        make_period(
            "2024-03-31",
            fiscal_year=2024,
            fiscal_period=FiscalPeriodLabel.Q1,
            start_date=date(2024, 1, 1),
        ),
    ]
    periods_inst = [
        make_period(
            "2023-03-31",
            period_type=PeriodType.INSTANT,
            fiscal_year=2023,
            fiscal_period=FiscalPeriodLabel.Q1,
        ),
        make_period(
            "2023-06-30",
            period_type=PeriodType.INSTANT,
            fiscal_year=2023,
            fiscal_period=FiscalPeriodLabel.Q2,
        ),
        make_period(
            "2023-09-30",
            period_type=PeriodType.INSTANT,
            fiscal_year=2023,
            fiscal_period=FiscalPeriodLabel.Q3,
        ),
        make_period(
            "2023-12-31",
            period_type=PeriodType.INSTANT,
            fiscal_year=2023,
            fiscal_period=FiscalPeriodLabel.Q4,
        ),
        make_period(
            "2024-03-31",
            period_type=PeriodType.INSTANT,
            fiscal_year=2024,
            fiscal_period=FiscalPeriodLabel.Q1,
        ),
    ]

    inc_stmts = [
        make_statement(
            StatementType.INCOME_STATEMENT,
            p,
            [
                make_fact(
                    StatementType.INCOME_STATEMENT, "250", p, CanonicalConcept.REVENUE
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    "50",
                    p,
                    CanonicalConcept.OPERATING_INCOME,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    "50",
                    p,
                    CanonicalConcept.PRETAX_INCOME,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    "10",
                    p,
                    CanonicalConcept.INCOME_TAX_EXPENSE,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT, "40", p, CanonicalConcept.NET_INCOME
                ),
            ],
        )
        for p in periods_q
    ]

    # Balance sheets: NWC at Q1 2023 = (400 - 100) - 200 = 100.
    # NWC at Q1 2024 = (500 - 100) - 250 = 150.
    # TTM Delta NWC between Q1 2024 (anchor) and Q1 2023 (Q(t-4)) must equal 150 - 100 = 50!
    bal_stmts = []
    for idx, p in enumerate(periods_inst):
        ca_val = "400" if idx == 0 else "500"
        cl_val = "200" if idx == 0 else "250"
        bal_stmts.append(
            make_statement(
                StatementType.BALANCE_SHEET,
                p,
                [
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        "1000",
                        p,
                        CanonicalConcept.TOTAL_ASSETS,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        ca_val,
                        p,
                        CanonicalConcept.CURRENT_ASSETS,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        cl_val,
                        p,
                        CanonicalConcept.CURRENT_LIABILITIES,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        "100",
                        p,
                        CanonicalConcept.CASH_AND_EQUIVALENTS,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        "0",
                        p,
                        CanonicalConcept.SHORT_TERM_INVESTMENTS,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        "100",
                        p,
                        CanonicalConcept.LONG_TERM_DEBT,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        "300",
                        p,
                        CanonicalConcept.TOTAL_LIABILITIES,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        "700",
                        p,
                        CanonicalConcept.STOCKHOLDERS_EQUITY,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        "700",
                        p,
                        source_concept="Common Stock Equity",
                    ),
                ],
            )
        )

    cf_stmts = [
        make_statement(
            StatementType.CASH_FLOW,
            p,
            [
                make_fact(
                    StatementType.CASH_FLOW,
                    "60",
                    p,
                    CanonicalConcept.OPERATING_CASH_FLOW,
                ),
                make_fact(
                    StatementType.CASH_FLOW,
                    "20",
                    p,
                    CanonicalConcept.CAPITAL_EXPENDITURES,
                ),
                make_fact(
                    StatementType.CASH_FLOW,
                    "10",
                    p,
                    source_concept="Depreciation And Amortization",
                ),
            ],
        )
        for p in periods_q
    ]

    mock_svc = AsyncMock(spec=FinancialStatementService)

    def _get_q_stmts(ticker, st, freq):
        if st == StatementType.INCOME_STATEMENT:
            return inc_stmts
        if st == StatementType.BALANCE_SHEET:
            return bal_stmts
        if st == StatementType.CASH_FLOW:
            return cf_stmts
        return []

    mock_svc.get_statements.side_effect = _get_q_stmts

    cf_op = CashFlowWorkingCapitalOperation(mock_svc)
    target_p, _, metrics, _, _ = await cf_op.execute("TTMCO", FiscalPeriodType.TTM)

    # Verify TTM period
    assert target_p.fiscal_period == FiscalPeriodLabel.TTM

    # Instant balance sheet at Q(t): Operating NWC = (500 - 100) - 250 = 150
    assert metrics["operating_nwc"].value == Decimal("150")

    # TTM Delta NWC = NWC(Q1 2024) - NWC(Q1 2023) = 150 - 100 = 50
    assert metrics["delta_nwc"].value == Decimal("50")

    # 4-quarter duration summation:
    # 4 quarters of CFO: 60 * 4 = 240
    # 4 quarters of CapEx: 20 * 4 = 80
    # NOPAT = (50 * 4) * (1 - 40/200) = 200 * 0.8 = 160
    # FCFF primary = NOPAT (160) + D&A (40) - CapEx (80) - Delta NWC (50) = 70
    assert metrics["fcff_primary"].value == Decimal("70")
