"""
tests.unit.services.test_fundamental_service
============================================
Unit tests for FundamentalAnalysisService orchestration, statement retrieval,
and report assembly.
"""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FiscalPeriodType,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.enums import FundamentalMetricId, MetricStatus
from aurelius.services.financial_statement_service import FinancialStatementService
from aurelius.services.fundamental_service import FundamentalAnalysisService
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)


@pytest.fixture
def mock_statement_service() -> AsyncMock:
    return AsyncMock(spec=FinancialStatementService)


@pytest.mark.asyncio
async def test_fundamental_report_orchestration(mock_statement_service):
    p2023 = make_period("2023-12-31", fiscal_year=2023)
    p2024 = make_period("2024-12-31", fiscal_year=2024)
    p2023_inst = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )
    p2024_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )

    # Income Statements
    inc_2023 = make_statement(
        StatementType.INCOME_STATEMENT,
        p2023,
        [
            make_fact(
                StatementType.INCOME_STATEMENT, "1000", p2023, CanonicalConcept.REVENUE
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "400",
                p2023,
                CanonicalConcept.COST_OF_REVENUE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "600",
                p2023,
                CanonicalConcept.GROSS_PROFIT,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "300",
                p2023,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "200",
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
                StatementType.INCOME_STATEMENT, "1200", p2024, CanonicalConcept.REVENUE
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "450",
                p2024,
                CanonicalConcept.COST_OF_REVENUE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "750",
                p2024,
                CanonicalConcept.GROSS_PROFIT,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "360",
                p2024,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "250",
                p2024,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )

    # Balance Sheets
    bal_2023 = make_statement(
        StatementType.BALANCE_SHEET,
        p2023_inst,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "2000",
                p2023_inst,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1000",
                p2023_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "500",
                p2023_inst,
                CanonicalConcept.CURRENT_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "250",
                p2023_inst,
                CanonicalConcept.CURRENT_LIABILITIES,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "400",
                p2023_inst,
                CanonicalConcept.LONG_TERM_DEBT,
                "Long Term Debt",
            ),
        ],
    )
    bal_2024 = make_statement(
        StatementType.BALANCE_SHEET,
        p2024_inst,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "2400",
                p2024_inst,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1200",
                p2024_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "600",
                p2024_inst,
                CanonicalConcept.CURRENT_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "300",
                p2024_inst,
                CanonicalConcept.CURRENT_LIABILITIES,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "400",
                p2024_inst,
                CanonicalConcept.LONG_TERM_DEBT,
                "Long Term Debt",
            ),
        ],
    )

    # Cash Flow Statements
    cf_2023 = make_statement(
        StatementType.CASH_FLOW,
        p2023,
        [
            make_fact(
                StatementType.CASH_FLOW,
                "350",
                p2023,
                CanonicalConcept.OPERATING_CASH_FLOW,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "-100",
                p2023,
                CanonicalConcept.CAPITAL_EXPENDITURES,
            ),
        ],
    )
    cf_2024 = make_statement(
        StatementType.CASH_FLOW,
        p2024,
        [
            make_fact(
                StatementType.CASH_FLOW,
                "420",
                p2024,
                CanonicalConcept.OPERATING_CASH_FLOW,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "-120",
                p2024,
                CanonicalConcept.CAPITAL_EXPENDITURES,
            ),
        ],
    )

    async def _mock_get_statements(ticker, st_type, freq):
        if st_type == StatementType.INCOME_STATEMENT:
            return [inc_2023, inc_2024]
        if st_type == StatementType.BALANCE_SHEET:
            return [bal_2023, bal_2024]
        if st_type == StatementType.CASH_FLOW:
            return [cf_2023, cf_2024]
        return []

    mock_statement_service.get_statements.side_effect = _mock_get_statements

    service = FundamentalAnalysisService(statement_service=mock_statement_service)
    report = await service.get_fundamental_report("AAPL", FiscalPeriodType.ANNUAL)

    assert report.ticker == "AAPL"
    assert len(report.periods) == 2
    assert FundamentalMetricId.REVENUE_GROWTH_YOY.value in report.metrics
    assert FundamentalMetricId.GROSS_PROFIT_MARGIN.value in report.metrics
    assert FundamentalMetricId.FREE_CASH_FLOW.value in report.metrics

    # Check 2024 Revenue YoY: (1200 - 1000) / 1000 = 20%
    yoy_metrics = report.metrics[FundamentalMetricId.REVENUE_GROWTH_YOY.value]
    assert len(yoy_metrics) == 2
    res_2024_yoy = yoy_metrics[1]
    assert res_2024_yoy.status == MetricStatus.VALID
    assert res_2024_yoy.value == Decimal("0.2")

    # Check 2024 ROA: NI = 250, Avg Assets = (2000 + 2400) / 2 = 2200 => 250 / 2200
    roa_metrics = report.metrics[FundamentalMetricId.RETURN_ON_ASSETS.value]
    res_2024_roa = roa_metrics[1]
    assert res_2024_roa.status == MetricStatus.VALID
    assert res_2024_roa.value == Decimal("250") / Decimal("2200")


@pytest.mark.asyncio
async def test_empty_statements_handling(mock_statement_service):
    mock_statement_service.get_statements.return_value = []
    service = FundamentalAnalysisService(statement_service=mock_statement_service)
    report = await service.get_fundamental_report("AAPL")
    assert report.ticker == "AAPL"
    assert report.periods == []
    assert report.metrics == {}


@pytest.mark.asyncio
async def test_fundamental_report_orchestration_ttm(mock_statement_service):
    """Verify that get_fundamental_report with frequency=TTM aggregates quarterly statements into TTM."""
    from aurelius.domain.entities.financials import FiscalPeriodLabel

    q1 = make_period("2024-03-31", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q1)
    q2 = make_period("2024-06-30", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q2)
    q3 = make_period("2024-09-30", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q3)
    q4 = make_period("2024-12-31", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q4)
    quarters = [q1, q2, q3, q4]

    # Revenue across quarters: 100, 110, 120, 130 -> TTM = 460
    inc_stmts = [
        make_statement(
            StatementType.INCOME_STATEMENT,
            q,
            [
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    str(rev),
                    q,
                    CanonicalConcept.REVENUE,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    str(rev // 2),
                    q,
                    CanonicalConcept.GROSS_PROFIT,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    str(rev // 4),
                    q,
                    CanonicalConcept.OPERATING_INCOME,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    str(rev // 5),
                    q,
                    CanonicalConcept.NET_INCOME,
                ),
            ],
        )
        for q, rev in zip(quarters, [100, 110, 120, 130], strict=True)
    ]

    # Cash Flow: CFO 50, 60, 70, 80 (=260); CapEx -10, -15, -20, -25 (magnitude=70) -> FCF = 190
    cf_stmts = [
        make_statement(
            StatementType.CASH_FLOW,
            q,
            [
                make_fact(
                    StatementType.CASH_FLOW,
                    str(cfo),
                    q,
                    CanonicalConcept.OPERATING_CASH_FLOW,
                ),
                make_fact(
                    StatementType.CASH_FLOW,
                    str(capex),
                    q,
                    CanonicalConcept.CAPITAL_EXPENDITURES,
                ),
            ],
        )
        for q, cfo, capex in zip(
            quarters, [50, 60, 70, 80], [-10, -15, -20, -25], strict=True
        )
    ]

    bal_stmts = [
        make_statement(
            StatementType.BALANCE_SHEET,
            q,
            [
                make_fact(
                    StatementType.BALANCE_SHEET,
                    "500",
                    q,
                    CanonicalConcept.CURRENT_ASSETS,
                ),
                make_fact(
                    StatementType.BALANCE_SHEET,
                    "250",
                    q,
                    CanonicalConcept.CURRENT_LIABILITIES,
                ),
            ],
        )
        for q in quarters
    ]

    async def _mock_get_statements(ticker, st_type, freq):
        # Must be called with QUARTERLY frequency
        assert freq == FiscalPeriodType.QUARTERLY
        if st_type == StatementType.INCOME_STATEMENT:
            return inc_stmts
        if st_type == StatementType.BALANCE_SHEET:
            return bal_stmts
        if st_type == StatementType.CASH_FLOW:
            return cf_stmts
        return []

    mock_statement_service.get_statements.side_effect = _mock_get_statements

    service = FundamentalAnalysisService(statement_service=mock_statement_service)
    report = await service.get_fundamental_report("AAPL", FiscalPeriodType.TTM)

    assert report.ticker == "AAPL"
    assert report.frequency == FiscalPeriodType.TTM
    assert len(report.periods) == 1
    ttm_p = report.periods[0]
    assert ttm_p.fiscal_period == FiscalPeriodLabel.TTM

    # Verify TTM Revenue: 100 + 110 + 120 + 130 = 460
    rev_res = report.metrics[FundamentalMetricId.REVENUE.value][0]
    assert rev_res.status == MetricStatus.VALID
    assert rev_res.value == Decimal("460")
    assert len(rev_res.provenance.source_fact_ids) == 4

    # Verify TTM CFO: 50 + 60 + 70 + 80 = 260
    cfo_res = report.metrics[FundamentalMetricId.OPERATING_CASH_FLOW.value][0]
    assert cfo_res.status == MetricStatus.VALID
    assert cfo_res.value == Decimal("260")

    # Verify TTM CapEx: 10 + 15 + 20 + 25 = 70
    capex_res = report.metrics[FundamentalMetricId.CAPITAL_EXPENDITURES.value][0]
    assert capex_res.status == MetricStatus.VALID
    assert capex_res.value == Decimal("70")

    # Verify TTM FCF: 260 - 70 = 190
    fcf_res = report.metrics[FundamentalMetricId.FREE_CASH_FLOW.value][0]
    assert fcf_res.status == MetricStatus.VALID
    assert fcf_res.value == Decimal("190")

    # Verify Balance sheet instant metric at Q4 cutoff: Current Ratio = 500 / 250 = 2.0
    cr_res = report.metrics[FundamentalMetricId.CURRENT_RATIO.value][0]
    assert cr_res.status == MetricStatus.VALID
    assert cr_res.value == Decimal("2")
