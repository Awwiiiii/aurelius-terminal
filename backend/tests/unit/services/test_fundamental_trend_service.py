"""
tests.unit.services.test_fundamental_trend_service
==================================================
Unit tests for FundamentalTrendService orchestration, metric computation,
period-over-period variations (YoY, QoQ, TTM Sequential), and CAGR.
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
from aurelius.services.financial_statement_service import FinancialStatementService
from aurelius.services.fundamental_service import FundamentalAnalysisService
from aurelius.services.fundamental_trend_service import FundamentalTrendService
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)


@pytest.fixture
def mock_statement_service() -> AsyncMock:
    return AsyncMock(spec=FinancialStatementService)


@pytest.mark.asyncio
async def test_trend_service_annual(mock_statement_service):
    p2022 = make_period("2022-12-31", fiscal_year=2022, start_date=date(2022, 1, 1))
    p2023 = make_period("2023-12-31", fiscal_year=2023, start_date=date(2023, 1, 1))
    p2024 = make_period("2024-12-31", fiscal_year=2024, start_date=date(2024, 1, 1))

    # Income statements
    inc_2022 = make_statement(
        StatementType.INCOME_STATEMENT,
        p2022,
        [
            make_fact(
                StatementType.INCOME_STATEMENT, "1000", p2022, CanonicalConcept.REVENUE
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "600",
                p2022,
                CanonicalConcept.GROSS_PROFIT,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "300",
                p2022,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "200",
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
                "720",
                p2023,
                CanonicalConcept.GROSS_PROFIT,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "360",
                p2023,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "240",
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
                "900",
                p2024,
                CanonicalConcept.GROSS_PROFIT,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "450",
                p2024,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "300",
                p2024,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )

    # Balance sheet
    p2022_inst = make_period(
        "2022-12-31", period_type=PeriodType.INSTANT, fiscal_year=2022
    )
    p2023_inst = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )
    p2024_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )

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
                "1000",
                p2022_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
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
                "1200",
                p2023_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
        ],
    )
    bal_2024 = make_statement(
        StatementType.BALANCE_SHEET,
        p2024_inst,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "3000",
                p2024_inst,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1500",
                p2024_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
        ],
    )

    # Cash flow
    cf_2022 = make_statement(
        StatementType.CASH_FLOW,
        p2022,
        [
            make_fact(
                StatementType.CASH_FLOW,
                "250",
                p2022,
                CanonicalConcept.OPERATING_CASH_FLOW,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "50",
                p2022,
                CanonicalConcept.CAPITAL_EXPENDITURES,
            ),
        ],
    )
    cf_2023 = make_statement(
        StatementType.CASH_FLOW,
        p2023,
        [
            make_fact(
                StatementType.CASH_FLOW,
                "300",
                p2023,
                CanonicalConcept.OPERATING_CASH_FLOW,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "60",
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
                "380",
                p2024,
                CanonicalConcept.OPERATING_CASH_FLOW,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "80",
                p2024,
                CanonicalConcept.CAPITAL_EXPENDITURES,
            ),
        ],
    )

    async def _mock_get_statements(ticker, st_type, freq):
        if st_type == StatementType.INCOME_STATEMENT:
            return [inc_2022, inc_2023, inc_2024]
        if st_type == StatementType.BALANCE_SHEET:
            return [bal_2022, bal_2023, bal_2024]
        if st_type == StatementType.CASH_FLOW:
            return [cf_2022, cf_2023, cf_2024]
        return []

    mock_statement_service.get_statements.side_effect = _mock_get_statements
    fund_service = FundamentalAnalysisService(statement_service=mock_statement_service)
    trend_service = FundamentalTrendService(
        fundamental_service=fund_service,
    )

    ticker, freq, series_dict, cagr_dict = await trend_service.get_fundamental_trends(
        ticker="AAPL",
        frequency=FiscalPeriodType.ANNUAL,
        metrics=["revenue", "gross_margin", "fcf", "cagr"],
        limit=10,
    )

    assert ticker == "AAPL"
    assert freq == FiscalPeriodType.ANNUAL
    assert "revenue" in series_dict
    assert "gross_margin" in series_dict
    assert "fcf" in series_dict

    # Check revenue values: 1000, 1200, 1500
    rev_points = series_dict["revenue"]
    assert len(rev_points) == 3
    assert rev_points[0].value == Decimal("1000")
    assert rev_points[1].value == Decimal("1200")
    assert rev_points[2].value == Decimal("1500")

    # YoY variation for 2023: (1200 - 1000)/1000 = 0.20 (+20%)
    assert rev_points[0].yoy_change is None  # no prior year
    assert rev_points[1].yoy_change == Decimal("0.2")

    # In Annual, QoQ must be None
    assert rev_points[1].qoq_change is None

    # FCF values: 2022: 250 - 50 = 200; 2023: 300 - 60 = 240; 2024: 380 - 80 = 300
    fcf_points = series_dict["fcf"]
    assert fcf_points[0].value == Decimal("200")
    assert fcf_points[1].value == Decimal("240")
    assert fcf_points[2].value == Decimal("300")


@pytest.mark.asyncio
async def test_trend_service_ttm_sequential(mock_statement_service):
    # 5 quarters to test TTM sequential change
    quarters = [
        make_period("2023-03-31", fiscal_year=2023, fiscal_period=FiscalPeriodLabel.Q1),
        make_period("2023-06-30", fiscal_year=2023, fiscal_period=FiscalPeriodLabel.Q2),
        make_period("2023-09-30", fiscal_year=2023, fiscal_period=FiscalPeriodLabel.Q3),
        make_period("2023-12-31", fiscal_year=2023, fiscal_period=FiscalPeriodLabel.Q4),
        make_period("2024-03-31", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q1),
    ]

    inc_stmts = [
        make_statement(
            StatementType.INCOME_STATEMENT,
            q,
            [
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    str(100 + i * 10),
                    q,
                    CanonicalConcept.REVENUE,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    str(60 + i * 5),
                    q,
                    CanonicalConcept.GROSS_PROFIT,
                ),
            ],
        )
        for i, q in enumerate(quarters)
    ]

    async def _mock_get_statements(ticker, st_type, freq):
        if st_type == StatementType.INCOME_STATEMENT:
            return inc_stmts
        return []

    mock_statement_service.get_statements.side_effect = _mock_get_statements
    fund_service = FundamentalAnalysisService(statement_service=mock_statement_service)
    trend_service = FundamentalTrendService(
        fundamental_service=fund_service,
    )

    ticker, freq, series_dict, cagr_dict = await trend_service.get_fundamental_trends(
        ticker="AAPL",
        frequency=FiscalPeriodType.TTM,
        metrics=["revenue"],
        limit=10,
    )

    assert freq == FiscalPeriodType.TTM
    # 5 quarters allow 2 TTM windows: Q1-Q4 2023 and Q2 2023-Q1 2024
    rev_points = series_dict["revenue"]
    assert len(rev_points) == 2

    # TTM sequential change must be populated for the 2nd window
    assert rev_points[0].ttm_sequential_change is None
    assert rev_points[1].ttm_sequential_change is not None
    # In TTM, QoQ and YoY must be None
    assert rev_points[1].qoq_change is None
    assert rev_points[1].yoy_change is None


@pytest.mark.asyncio
async def test_trend_service_quarterly(mock_statement_service):
    # 5 quarters: Q1 2023, Q2 2023, Q3 2023, Q4 2023, Q1 2024
    quarters = [
        make_period("2023-03-31", fiscal_year=2023, fiscal_period=FiscalPeriodLabel.Q1),
        make_period("2023-06-30", fiscal_year=2023, fiscal_period=FiscalPeriodLabel.Q2),
        make_period("2023-09-30", fiscal_year=2023, fiscal_period=FiscalPeriodLabel.Q3),
        make_period("2023-12-31", fiscal_year=2023, fiscal_period=FiscalPeriodLabel.Q4),
        make_period("2024-03-31", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q1),
    ]

    inc_stmts = [
        make_statement(
            StatementType.INCOME_STATEMENT,
            q,
            [
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    str(100 + i * 20),
                    q,
                    CanonicalConcept.REVENUE,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    str(50 + i * 10),
                    q,
                    CanonicalConcept.GROSS_PROFIT,
                ),
            ],
        )
        for i, q in enumerate(quarters)
    ]

    async def _mock_get_statements(ticker, st_type, freq):
        if st_type == StatementType.INCOME_STATEMENT:
            return inc_stmts
        return []

    mock_statement_service.get_statements.side_effect = _mock_get_statements
    fund_service = FundamentalAnalysisService(statement_service=mock_statement_service)
    trend_service = FundamentalTrendService(
        fundamental_service=fund_service,
    )

    ticker, freq, series_dict, cagr_dict = await trend_service.get_fundamental_trends(
        ticker="AAPL",
        frequency=FiscalPeriodType.QUARTERLY,
        metrics=["revenue"],
        limit=10,
    )

    assert freq == FiscalPeriodType.QUARTERLY
    rev_points = series_dict["revenue"]
    assert len(rev_points) == 5

    # Check QoQ on Q2 2023: (120 - 100)/100 = 0.20
    assert rev_points[1].qoq_change == Decimal("0.2")

    # Check YoY on Q1 2024 (idx 4): (180 - 100)/100 = 0.80
    assert rev_points[4].yoy_change == Decimal("0.8")
    # In Quarterly, TTM sequential change must be None
    assert rev_points[4].ttm_sequential_change is None


@pytest.mark.asyncio
async def test_trend_service_cagr_calculation(mock_statement_service):
    # 4 annual periods: 2021, 2022, 2023, 2024 (enables 3Y horizon)
    p2021 = make_period("2021-12-31", fiscal_year=2021, start_date=date(2021, 1, 1))
    p2022 = make_period("2022-12-31", fiscal_year=2022, start_date=date(2022, 1, 1))
    p2023 = make_period("2023-12-31", fiscal_year=2023, start_date=date(2023, 1, 1))
    p2024 = make_period("2024-12-31", fiscal_year=2024, start_date=date(2024, 1, 1))

    # Revenue: 1000 in 2021, 1331 in 2024 (~10% CAGR over 3 years)
    inc_stmts = [
        make_statement(
            StatementType.INCOME_STATEMENT,
            p,
            [
                make_fact(
                    StatementType.INCOME_STATEMENT, val, p, CanonicalConcept.REVENUE
                )
            ],
        )
        for p, val in [
            (p2021, "1000"),
            (p2022, "1100"),
            (p2023, "1210"),
            (p2024, "1331"),
        ]
    ]

    async def _mock_get_statements(ticker, st_type, freq):
        if st_type == StatementType.INCOME_STATEMENT:
            return inc_stmts
        return []

    mock_statement_service.get_statements.side_effect = _mock_get_statements
    fund_service = FundamentalAnalysisService(statement_service=mock_statement_service)
    trend_service = FundamentalTrendService(
        fundamental_service=fund_service,
    )

    ticker, freq, series_dict, cagr_dict = await trend_service.get_fundamental_trends(
        ticker="AAPL",
        frequency=FiscalPeriodType.ANNUAL,
        metrics=["revenue", "cagr"],
        limit=10,
    )

    assert "revenue" in cagr_dict
    cagrs = cagr_dict["revenue"]
    assert len(cagrs) >= 1
    cagr_3y = next((c for c in cagrs if c.horizon == "3Y"), None)
    assert cagr_3y is not None
    assert cagr_3y.cagr is not None
    # 1331 / 1000 = 1.331; 1.331^(1/3) ~ 1.10 -> CAGR ~ 0.10
    assert abs(cagr_3y.cagr - Decimal("0.10")) < Decimal("0.01")
