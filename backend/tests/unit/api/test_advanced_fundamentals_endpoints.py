"""
tests.unit.api.test_advanced_fundamentals_endpoints
===================================================
Integration tests for M7B.2 REST API endpoints:
  1. GET /api/v1/financials/{symbol}/advanced-fundamentals
  2. GET /api/v1/financials/{symbol}/common-size
  3. GET /api/v1/financials/{symbol}/fundamental-trends

Verifies:
  - ANNUAL, QUARTERLY, and TTM period handling
  - Exact JSON serialization (enums, Decimals, provenance)
  - Explicit unavailable values without fake numbers or NaNs
  - Point-in-time fallback flags
  - Common-size instant anchor semantics (never "TTM Balance Sheet")
  - Historical trends with YoY, QoQ, TTM sequential variation, and M4 CAGR
  - Proper HTTP error handling (404 for unknown/missing data, 422 for invalid parameters)
  - Dual routing (/api/v1/financials and /api/v1/market/financials)
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from aurelius.api.main import app
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FiscalPeriodLabel,
    PeriodType,
    StatementType,
)
from aurelius.domain.errors import DataNotFoundError
from aurelius.services.financial_statement_service import (
    FinancialStatementService,
    get_financial_statement_service,
)
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)


def _build_test_statements_annual():
    """Helper creating 2 annual periods for AAPL (2023, 2024)."""
    p2023 = make_period("2023-12-31", fiscal_year=2023, start_date=date(2023, 1, 1))
    p2024 = make_period("2024-12-31", fiscal_year=2024, start_date=date(2024, 1, 1))
    p2023_inst = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )
    p2024_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )

    inc_2023 = make_statement(
        StatementType.INCOME_STATEMENT,
        p2023,
        [
            make_fact(
                StatementType.INCOME_STATEMENT, "1000", p2023, CanonicalConcept.REVENUE
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "600",
                p2023,
                CanonicalConcept.GROSS_PROFIT,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "200",
                p2023,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "180",
                p2023,
                CanonicalConcept.PRETAX_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "36",
                p2023,
                CanonicalConcept.INCOME_TAX_EXPENSE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "144",
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
                "720",
                p2024,
                CanonicalConcept.GROSS_PROFIT,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "240",
                p2024,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "220",
                p2024,
                CanonicalConcept.PRETAX_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "44",
                p2024,
                CanonicalConcept.INCOME_TAX_EXPENSE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "176",
                p2024,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )

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
                "1200",
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
                "200",
                p2023_inst,
                CanonicalConcept.CASH_AND_EQUIVALENTS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "1500",
                p2023_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "400",
                p2023_inst,
                CanonicalConcept.LONG_TERM_DEBT,
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
                "1400",
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
                "1800",
                p2024_inst,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "400",
                p2024_inst,
                CanonicalConcept.LONG_TERM_DEBT,
            ),
        ],
    )

    cf_2023 = make_statement(
        StatementType.CASH_FLOW,
        p2023,
        [
            make_fact(
                StatementType.CASH_FLOW,
                "200",
                p2023,
                CanonicalConcept.OPERATING_CASH_FLOW,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "50",
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
                "250",
                p2024,
                CanonicalConcept.OPERATING_CASH_FLOW,
            ),
            make_fact(
                StatementType.CASH_FLOW,
                "60",
                p2024,
                CanonicalConcept.CAPITAL_EXPENDITURES,
            ),
        ],
    )

    return (
        [inc_2023, inc_2024],
        [bal_2023, bal_2024],
        [cf_2023, cf_2024],
    )


def _build_test_statements_quarterly(n_quarters: int = 5):
    """Helper creating n quarterly periods for AAPL."""
    quarter_defs = [
        ("2023-03-31", 2023, FiscalPeriodLabel.Q1),
        ("2023-06-30", 2023, FiscalPeriodLabel.Q2),
        ("2023-09-30", 2023, FiscalPeriodLabel.Q3),
        ("2023-12-31", 2023, FiscalPeriodLabel.Q4),
        ("2024-03-31", 2024, FiscalPeriodLabel.Q1),
    ][:n_quarters]

    inc_stmts = []
    bal_stmts = []
    cf_stmts = []

    for i, (end_dt, fy, fp) in enumerate(quarter_defs):
        dur_p = make_period(end_dt, fiscal_year=fy, fiscal_period=fp)
        inst_p = make_period(
            end_dt, period_type=PeriodType.INSTANT, fiscal_year=fy, fiscal_period=fp
        )

        inc_stmts.append(
            make_statement(
                StatementType.INCOME_STATEMENT,
                dur_p,
                [
                    make_fact(
                        StatementType.INCOME_STATEMENT,
                        str(250 + i * 20),
                        dur_p,
                        CanonicalConcept.REVENUE,
                    ),
                    make_fact(
                        StatementType.INCOME_STATEMENT,
                        str(150 + i * 10),
                        dur_p,
                        CanonicalConcept.GROSS_PROFIT,
                    ),
                    make_fact(
                        StatementType.INCOME_STATEMENT,
                        str(60 + i * 5),
                        dur_p,
                        CanonicalConcept.OPERATING_INCOME,
                    ),
                    make_fact(
                        StatementType.INCOME_STATEMENT,
                        str(50 + i * 5),
                        dur_p,
                        CanonicalConcept.PRETAX_INCOME,
                    ),
                    make_fact(
                        StatementType.INCOME_STATEMENT,
                        str(10 + i),
                        dur_p,
                        CanonicalConcept.INCOME_TAX_EXPENSE,
                    ),
                    make_fact(
                        StatementType.INCOME_STATEMENT,
                        str(40 + i * 4),
                        dur_p,
                        CanonicalConcept.NET_INCOME,
                    ),
                ],
            )
        )
        bal_stmts.append(
            make_statement(
                StatementType.BALANCE_SHEET,
                inst_p,
                [
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        str(4000 + i * 200),
                        inst_p,
                        CanonicalConcept.TOTAL_ASSETS,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        str(2000 + i * 100),
                        inst_p,
                        CanonicalConcept.CURRENT_ASSETS,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        str(800 + i * 50),
                        inst_p,
                        CanonicalConcept.CURRENT_LIABILITIES,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        str(400 + i * 20),
                        inst_p,
                        CanonicalConcept.CASH_AND_EQUIVALENTS,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        str(2500 + i * 150),
                        inst_p,
                        CanonicalConcept.STOCKHOLDERS_EQUITY,
                    ),
                    make_fact(
                        StatementType.BALANCE_SHEET,
                        "500",
                        inst_p,
                        CanonicalConcept.LONG_TERM_DEBT,
                    ),
                ],
            )
        )
        cf_stmts.append(
            make_statement(
                StatementType.CASH_FLOW,
                dur_p,
                [
                    make_fact(
                        StatementType.CASH_FLOW,
                        str(70 + i * 5),
                        dur_p,
                        CanonicalConcept.OPERATING_CASH_FLOW,
                    ),
                    make_fact(
                        StatementType.CASH_FLOW,
                        str(20 + i),
                        dur_p,
                        CanonicalConcept.CAPITAL_EXPENDITURES,
                    ),
                ],
            )
        )

    return inc_stmts, bal_stmts, cf_stmts


def _setup_mock_service(inc_stmts, bal_stmts, cf_stmts):
    mock_service = AsyncMock(spec=FinancialStatementService)

    async def _mock_get_statements(ticker, st_type, freq):
        if ticker != "AAPL":
            raise DataNotFoundError(ticker=ticker, message=f"Unknown security {ticker}")
        if st_type == StatementType.INCOME_STATEMENT:
            return inc_stmts
        if st_type == StatementType.BALANCE_SHEET:
            return bal_stmts
        if st_type == StatementType.CASH_FLOW:
            return cf_stmts
        return []

    mock_service.get_statements.side_effect = _mock_get_statements
    return mock_service


# =============================================================================
# 1. ADVANCED FUNDAMENTALS ENDPOINT TESTS
# =============================================================================


def test_advanced_fundamentals_annual():
    inc_stmts, bal_stmts, cf_stmts = _build_test_statements_annual()
    mock_service = _setup_mock_service(inc_stmts, bal_stmts, cf_stmts)
    app.dependency_overrides[get_financial_statement_service] = lambda: mock_service

    try:
        client = TestClient(app)
        # Test endpoint with prefix /api/v1/financials/{symbol}/advanced-fundamentals
        response = client.get(
            "/api/v1/financials/AAPL/advanced-fundamentals",
            params={"period_type": "ANNUAL", "fiscal_year": 2024},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["ticker"] == "AAPL"
        assert data["period_type"] == "ANNUAL"
        assert data["period"]["fiscal_year"] == 2024

        # Validate NOPAT
        assert data["nopat"]["status"] == "VALID"
        assert Decimal(str(data["nopat"]["value"])) > 0
        assert data["nopat"]["provenance"]["formula_id"] == "FORMULA_NOPAT"

        # Validate ETR
        assert data["effective_tax_rate"]["status"] == "VALID"
        # 44 / 220 = 0.20
        assert Decimal(str(data["effective_tax_rate"]["value"])) == Decimal("0.2")

        # Validate Invested Capital
        assert data["invested_capital"]["status"] == "VALID"
        assert data["average_invested_capital"]["status"] == "VALID"

        # Validate ROIC
        assert data["roic"]["status"] == "VALID"
        assert Decimal(str(data["roic"]["value"])) > 0

        # Validate DuPont 3-step & 5-step
        assert data["dupont_3step"]["reconstructed_roe"]["status"] == "VALID"
        assert data["dupont_3step"]["is_reconciled"] is True
        assert data["dupont_5step"]["reconstructed_roe"]["status"] == "VALID"
        assert data["dupont_5step"]["is_reconciled"] is True

        # Validate Diagnostics
        assert data["quality_diagnostics"]["sloan_accruals"]["status"] == "VALID"
        assert (
            data["quality_diagnostics"]["operating_quality_ratio"]["status"] == "VALID"
        )

        # Also verify the market route alias: /api/v1/market/financials/AAPL/advanced-fundamentals
        resp_market = client.get(
            "/api/v1/market/financials/AAPL/advanced-fundamentals",
            params={"period_type": "ANNUAL", "fiscal_year": 2024},
        )
        assert resp_market.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_advanced_fundamentals_ttm():
    inc_stmts, bal_stmts, cf_stmts = _build_test_statements_quarterly(5)
    mock_service = _setup_mock_service(inc_stmts, bal_stmts, cf_stmts)
    app.dependency_overrides[get_financial_statement_service] = lambda: mock_service

    try:
        client = TestClient(app)
        # Default period_type is TTM
        response = client.get("/api/v1/financials/AAPL/advanced-fundamentals")
        assert response.status_code == 200
        data = response.json()

        assert data["ticker"] == "AAPL"
        assert data["period_type"] == "TTM"
        assert data["period"]["fiscal_period"] == "TTM"

        # ROIC, NOPAT, and DuPont computed under TTM semantics
        assert data["nopat"]["status"] == "VALID"
        assert data["roic"]["status"] == "VALID"
        assert data["dupont_3step"]["reconstructed_roe"]["status"] == "VALID"
        assert data["dupont_5step"]["reconstructed_roe"]["status"] == "VALID"
        assert data["quality_diagnostics"]["sloan_accruals"]["status"] == "VALID"
    finally:
        app.dependency_overrides.clear()


def test_advanced_fundamentals_fallback_flag():
    # Only 1 annual period: 2024 (no beginning balance sheet)
    p2024 = make_period("2024-12-31", fiscal_year=2024)
    p2024_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )

    inc = [
        make_statement(
            StatementType.INCOME_STATEMENT,
            p2024,
            [
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    "1000",
                    p2024,
                    CanonicalConcept.REVENUE,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    "200",
                    p2024,
                    CanonicalConcept.OPERATING_INCOME,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    "180",
                    p2024,
                    CanonicalConcept.PRETAX_INCOME,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    "36",
                    p2024,
                    CanonicalConcept.INCOME_TAX_EXPENSE,
                ),
                make_fact(
                    StatementType.INCOME_STATEMENT,
                    "144",
                    p2024,
                    CanonicalConcept.NET_INCOME,
                ),
            ],
        )
    ]
    bal = [
        make_statement(
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
                    "1200",
                    p2024_inst,
                    CanonicalConcept.CURRENT_ASSETS,
                ),
                make_fact(
                    StatementType.BALANCE_SHEET,
                    "500",
                    p2024_inst,
                    CanonicalConcept.CURRENT_LIABILITIES,
                ),
                make_fact(
                    StatementType.BALANCE_SHEET,
                    "200",
                    p2024_inst,
                    CanonicalConcept.CASH_AND_EQUIVALENTS,
                ),
                make_fact(
                    StatementType.BALANCE_SHEET,
                    "1500",
                    p2024_inst,
                    CanonicalConcept.STOCKHOLDERS_EQUITY,
                ),
                make_fact(
                    StatementType.BALANCE_SHEET,
                    "400",
                    p2024_inst,
                    CanonicalConcept.LONG_TERM_DEBT,
                ),
            ],
        )
    ]

    mock_service = _setup_mock_service(inc, bal, [])
    app.dependency_overrides[get_financial_statement_service] = lambda: mock_service

    try:
        client = TestClient(app)
        # Without allow_point_in_time fallback -> ROIC must be UNAVAILABLE
        resp_no_fb = client.get(
            "/api/v1/financials/AAPL/advanced-fundamentals",
            params={
                "period_type": "ANNUAL",
                "fiscal_year": 2024,
                "allow_point_in_time": False,
            },
        )
        assert resp_no_fb.status_code == 200
        data_no_fb = resp_no_fb.json()
        assert data_no_fb["roic"]["status"] == "UNAVAILABLE"
        assert data_no_fb["roic"]["value"] is None

        # With allow_point_in_time=True -> ROIC is VALID using point-in-time fallback
        resp_fb = client.get(
            "/api/v1/financials/AAPL/advanced-fundamentals",
            params={
                "period_type": "ANNUAL",
                "fiscal_year": 2024,
                "allow_point_in_time": True,
            },
        )
        assert resp_fb.status_code == 200
        data_fb = resp_fb.json()
        assert data_fb["roic"]["status"] == "VALID"
        assert Decimal(str(data_fb["roic"]["value"])) > 0
        # Diagnostic should record fallback
        diag_codes = [d["code"] for d in data_fb["roic"]["diagnostics"]]
        assert "POINT_IN_TIME_DENOMINATOR_FALLBACK" in diag_codes
    finally:
        app.dependency_overrides.clear()


# =============================================================================
# 2. COMMON-SIZE STATEMENTS ENDPOINT TESTS
# =============================================================================


def test_common_size_ttm_instant_anchor():
    inc_stmts, bal_stmts, cf_stmts = _build_test_statements_quarterly(5)
    mock_service = _setup_mock_service(inc_stmts, bal_stmts, cf_stmts)
    app.dependency_overrides[get_financial_statement_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/financials/AAPL/common-size",
            params={"period_type": "TTM"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["ticker"] == "AAPL"
        assert data["period_type"] == "TTM"

        # Verify IS scaling: base concept is REVENUE
        is_tbl = data["income_statement"]
        assert is_tbl["base_concept_name"] == "REVENUE"
        rev_item = next(
            (it for it in is_tbl["items"] if it["concept_name"] == "REVENUE"), None
        )
        assert rev_item is not None
        assert Decimal(str(rev_item["common_size_percent"])) == Decimal("100.0")

        # Verify BS: instant anchor date exposed, NEVER "TTM Balance Sheet"
        bs_tbl = data["balance_sheet"]
        assert bs_tbl["base_concept_name"] == "TOTAL_ASSETS"
        assert "Quarter Ended" in bs_tbl["display_title"]
        assert "TTM Balance Sheet" not in bs_tbl["display_title"]
        # Anchor period matches latest quarter: 2024-03-31
        assert bs_tbl["period"]["end_date"] == "2024-03-31"

        # Verify CF scaling: base concept is REVENUE
        cf_tbl = data["cash_flow_statement"]
        assert cf_tbl["base_concept_name"] == "REVENUE"
    finally:
        app.dependency_overrides.clear()


# =============================================================================
# 3. FUNDAMENTAL TRENDS ENDPOINT TESTS
# =============================================================================


def test_fundamental_trends_annual():
    inc_stmts, bal_stmts, cf_stmts = _build_test_statements_annual()
    mock_service = _setup_mock_service(inc_stmts, bal_stmts, cf_stmts)
    app.dependency_overrides[get_financial_statement_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/financials/AAPL/fundamental-trends",
            params={
                "period_type": "ANNUAL",
                "metrics": "revenue,gross_margin,fcf",
                "limit": 10,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["ticker"] == "AAPL"
        assert data["period_type"] == "ANNUAL"

        # Check requested metrics present in series
        assert "revenue" in data["series"]
        assert "gross_margin" in data["series"]
        assert "fcf" in data["series"]

        # YoY present for 2nd period, QoQ and TTM sequential are None
        rev_pts = data["series"]["revenue"]["points"]
        assert len(rev_pts) == 2
        assert rev_pts[0]["yoy_change"] is None
        assert rev_pts[1]["yoy_change"] is not None
        assert rev_pts[1]["qoq_change"] is None
        assert rev_pts[1]["ttm_sequential_change"] is None
    finally:
        app.dependency_overrides.clear()


def test_fundamental_trends_quarterly():
    inc_stmts, bal_stmts, cf_stmts = _build_test_statements_quarterly(5)
    mock_service = _setup_mock_service(inc_stmts, bal_stmts, cf_stmts)
    app.dependency_overrides[get_financial_statement_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/financials/AAPL/fundamental-trends",
            params={"period_type": "QUARTERLY", "metrics": "revenue", "limit": 5},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["period_type"] == "QUARTERLY"
        assert "revenue" in data["series"]
        rev_pts = data["series"]["revenue"]["points"]
        assert len(rev_pts) == 5

        # QoQ present for point 1..4
        assert rev_pts[1]["qoq_change"] is not None
        # YoY present for Q1 2024 (idx 4 vs idx 0)
        assert rev_pts[4]["yoy_change"] is not None
        # In Quarterly, ttm_sequential_change is strictly None
        assert rev_pts[4]["ttm_sequential_change"] is None
    finally:
        app.dependency_overrides.clear()


def test_fundamental_trends_ttm():
    inc_stmts, bal_stmts, cf_stmts = _build_test_statements_quarterly(5)
    mock_service = _setup_mock_service(inc_stmts, bal_stmts, cf_stmts)
    app.dependency_overrides[get_financial_statement_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/financials/AAPL/fundamental-trends",
            params={"period_type": "TTM", "metrics": "revenue"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["period_type"] == "TTM"
        assert "revenue" in data["series"]
        rev_pts = data["series"]["revenue"]["points"]
        assert len(rev_pts) == 2

        # In TTM, sequential change is labeled ttm_sequential_change, NEVER qoq_change
        assert rev_pts[1]["ttm_sequential_change"] is not None
        assert rev_pts[1]["qoq_change"] is None
        assert rev_pts[1]["yoy_change"] is None
    finally:
        app.dependency_overrides.clear()


# =============================================================================
# 4. ERROR HANDLING & VALIDATION TESTS
# =============================================================================


def test_error_invalid_period_type():
    client = TestClient(app)
    response = client.get(
        "/api/v1/financials/AAPL/advanced-fundamentals",
        params={"period_type": "BIWEEKLY"},
    )
    assert response.status_code == 422


def test_error_unknown_security():
    mock_service = AsyncMock(spec=FinancialStatementService)
    mock_service.get_statements.side_effect = DataNotFoundError(
        ticker="UNKNOWN", message="Ticker UNKNOWN not found."
    )
    app.dependency_overrides[get_financial_statement_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.get("/api/v1/financials/UNKNOWN/advanced-fundamentals")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_error_invalid_ticker_format():
    client = TestClient(app)
    response = client.get("/api/v1/financials/INVALID$$$TICKER/advanced-fundamentals")
    assert response.status_code == 400


def test_error_missing_financial_data():
    mock_service = AsyncMock(spec=FinancialStatementService)
    mock_service.get_statements.side_effect = DataNotFoundError(
        ticker="AAPL", message="No statement data."
    )
    app.dependency_overrides[get_financial_statement_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.get("/api/v1/financials/AAPL/advanced-fundamentals")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
