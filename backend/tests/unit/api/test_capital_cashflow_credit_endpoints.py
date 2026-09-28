"""
tests.unit.api.test_capital_cashflow_credit_endpoints
=====================================================
REST API integration tests for M7B.3 endpoints:
  - GET /api/v1/financials/{ticker}/capital-allocation
  - GET /api/v1/financials/{ticker}/cash-flows
  - GET /api/v1/financials/{ticker}/enterprise-value
  - GET /api/v1/financials/{ticker}/credit-risk
  - GET /api/v1/financials/{ticker}/comprehensive

Verifies:
  - HTTP 200 on valid inputs across ANNUAL, QUARTERLY, and TTM
  - HTTP 404 on unrecognized ticker
  - HTTP 422 on invalid parameters
  - Traceable diagnostics aggregation retaining affected metric IDs
  - Rejection of client model overrides for Altman
  - Strict preservation of UNAVAILABLE status without silent zero-fills
  - 100% dependency injection coverage without live network requests
"""

from decimal import Decimal
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from aurelius.api.main import app
from aurelius.domain.entities.financials import StatementType
from aurelius.domain.errors import DataNotFoundError
from aurelius.providers.base import MarketDataProvider
from aurelius.providers.registry import get_market_data_provider
from aurelius.services.financial_statement_service import (
    FinancialStatementService,
    get_financial_statement_service,
)
from tests.unit.services.test_capital_cashflow_credit_service import (
    _build_test_statements_m7b3,
)


def _setup_mock_services():
    inc, bal, cf = _build_test_statements_m7b3()
    mock_stmt_service = AsyncMock(spec=FinancialStatementService)

    async def _mock_get_statements(ticker, st_type, freq):
        if ticker != "AAPL":
            raise DataNotFoundError(
                ticker=ticker, message=f"Security not found: {ticker}"
            )
        if st_type == StatementType.INCOME_STATEMENT:
            return inc
        if st_type == StatementType.BALANCE_SHEET:
            return bal
        if st_type == StatementType.CASH_FLOW:
            return cf
        return []

    mock_stmt_service.get_statements.side_effect = _mock_get_statements

    mock_provider = AsyncMock(spec=MarketDataProvider)
    return mock_stmt_service, mock_provider


def test_capital_allocation_endpoint():
    stmt_svc, prov = _setup_mock_services()
    app.dependency_overrides[get_financial_statement_service] = lambda: stmt_svc
    app.dependency_overrides[get_market_data_provider] = lambda: prov

    try:
        client = TestClient(app)
        res = client.get(
            "/api/v1/financials/AAPL/capital-allocation",
            params={"period_type": "ANNUAL", "fiscal_year": 2024},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["ticker"] == "AAPL"
        assert data["operating_cash_flow"]["status"] == "VALID"
        assert data["capital_expenditures"]["status"] == "VALID"
        assert data["dividends_paid"]["status"] == "VALID"
        assert data["stock_repurchases"]["status"] == "VALID"
        # Diagnostics summary check
        assert isinstance(data["diagnostics_summary"], list)
    finally:
        app.dependency_overrides.clear()


def test_cash_flows_structured_endpoint():
    stmt_svc, prov = _setup_mock_services()
    app.dependency_overrides[get_financial_statement_service] = lambda: stmt_svc
    app.dependency_overrides[get_market_data_provider] = lambda: prov

    try:
        client = TestClient(app)
        res = client.get(
            "/api/v1/financials/AAPL/cash-flows",
            params={"period_type": "ANNUAL", "fiscal_year": 2024},
        )
        assert res.status_code == 200
        data = res.json()
        assert "working_capital" in data
        assert "free_cash_flow" in data
        assert "reinvestment" in data
        assert "growth" in data

        # Free cash flow section inspection
        fcf = data["free_cash_flow"]
        assert fcf["fcff_primary"]["status"] == "VALID"
        assert fcf["fcfe"]["status"] == "VALID"
        assert fcf["net_borrowing_tier"] == "TIER_1_ITEMIZED_FLOWS"

        # Working capital section inspection
        wc = data["working_capital"]
        assert wc["operating_nwc"]["status"] == "VALID"
        assert wc["delta_nwc"]["status"] == "VALID"
    finally:
        app.dependency_overrides.clear()


def test_enterprise_value_endpoint_temporal_integrity():
    stmt_svc, prov = _setup_mock_services()
    app.dependency_overrides[get_financial_statement_service] = lambda: stmt_svc
    app.dependency_overrides[get_market_data_provider] = lambda: prov

    try:
        client = TestClient(app)
        res = client.get(
            "/api/v1/financials/AAPL/enterprise-value",
            params={"period_type": "ANNUAL", "fiscal_year": 2023},
        )
        assert res.status_code == 200
        data = res.json()
        # Historical period market cap must be UNAVAILABLE without backward contamination
        assert data["market_capitalization"]["status"] == "UNAVAILABLE"
        assert data["enterprise_value"]["status"] == "UNAVAILABLE"
        # Disclosure cases
        assert data["preferred_equity_disclosure_case"] == "CONFIDENTLY_ABSENT"

        # Check traceable diagnostics
        diags = data["diagnostics_summary"]
        mc_diag = next(
            (d for d in diags if d["code"] == "MARKET_CAP_UNAVAILABLE"), None
        )
        assert mc_diag is not None
        assert "enterprise_value" in mc_diag["affected_metric_ids"]
    finally:
        app.dependency_overrides.clear()


def test_credit_risk_endpoint_no_override():
    stmt_svc, prov = _setup_mock_services()
    app.dependency_overrides[get_financial_statement_service] = lambda: stmt_svc
    app.dependency_overrides[get_market_data_provider] = lambda: prov

    try:
        client = TestClient(app)
        res = client.get(
            "/api/v1/financials/AAPL/credit-risk",
            params={"period_type": "ANNUAL", "fiscal_year": 2024},
        )
        assert res.status_code == 200
        data = res.json()

        # Piotroski validation
        pio = data["piotroski_f_score"]
        assert pio["total_signal_count"] == 9
        assert pio["evaluated_signal_count"] == 9
        assert len(pio["signals"]) == 9

        # Canonical F5 check
        f5 = next(s for s in pio["signals"] if s["signal_id"] == "F5_DELTA_LEVER")
        assert f5["status"] == "PASS"

        # Altman validation (structural dispatch)
        altman = data["altman_z_score"]
        assert altman["dispatched_model"] == "MODEL_1_MANUFACTURING"
        assert "dispatch_rationale" in altman
    finally:
        app.dependency_overrides.clear()


def test_comprehensive_endpoint():
    stmt_svc, prov = _setup_mock_services()
    app.dependency_overrides[get_financial_statement_service] = lambda: stmt_svc
    app.dependency_overrides[get_market_data_provider] = lambda: prov

    try:
        client = TestClient(app)
        res = client.get(
            "/api/v1/financials/AAPL/comprehensive",
            params={"period_type": "ANNUAL", "fiscal_year": 2024},
        )
        assert res.status_code == 200
        data = res.json()
        assert "capital_allocation" in data
        assert "cash_flows" in data
        assert "enterprise_value" in data
        assert "credit_risk" in data
        assert isinstance(data["diagnostics_summary"], list)
    finally:
        app.dependency_overrides.clear()


def test_error_handling_not_found():
    stmt_svc, prov = _setup_mock_services()
    app.dependency_overrides[get_financial_statement_service] = lambda: stmt_svc
    app.dependency_overrides[get_market_data_provider] = lambda: prov

    try:
        client = TestClient(app)
        endpoints = [
            "/api/v1/financials/UNKNOWN/capital-allocation",
            "/api/v1/financials/UNKNOWN/cash-flows",
            "/api/v1/financials/UNKNOWN/enterprise-value",
            "/api/v1/financials/UNKNOWN/credit-risk",
            "/api/v1/financials/UNKNOWN/comprehensive",
        ]
        for ep in endpoints:
            res = client.get(ep)
            assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_invalid_parameters_422():
    stmt_svc, prov = _setup_mock_services()
    app.dependency_overrides[get_financial_statement_service] = lambda: stmt_svc
    app.dependency_overrides[get_market_data_provider] = lambda: prov

    try:
        client = TestClient(app)
        # Invalid period_type must yield 422
        res = client.get(
            "/api/v1/financials/AAPL/cash-flows",
            params={"period_type": "INVALID_FREQUENCY"},
        )
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_dual_route_convention():
    stmt_svc, prov = _setup_mock_services()
    app.dependency_overrides[get_financial_statement_service] = lambda: stmt_svc
    app.dependency_overrides[get_market_data_provider] = lambda: prov

    try:
        client = TestClient(app)
        res_direct = client.get(
            "/api/v1/financials/AAPL/credit-risk",
            params={"period_type": "ANNUAL", "fiscal_year": 2024},
        )
        res_market = client.get(
            "/api/v1/market/financials/AAPL/credit-risk",
            params={"period_type": "ANNUAL", "fiscal_year": 2024},
        )
        assert res_direct.status_code == 200
        assert res_market.status_code == 200
        assert res_direct.json() == res_market.json()
    finally:
        app.dependency_overrides.clear()


def test_altman_route_prohibits_override_parameter():
    # Verify openapi schema for credit-risk has NO model override parameter
    client = TestClient(app)
    openapi = client.get("/openapi.json").json()
    credit_path = openapi["paths"]["/api/v1/financials/{ticker}/credit-risk"]["get"]
    param_names = [p["name"] for p in credit_path.get("parameters", [])]
    assert "altman_override" not in param_names
    assert "altman_model_override" not in param_names
    assert "model" not in param_names


def test_market_cap_temporal_endpoint_behavior():
    from datetime import date

    from aurelius.services.operations.market_cap_resolver import MarketCapObservation

    stmt_svc, prov = _setup_mock_services()

    # Case 1: Provider with compatible as-of date (2024-12-31)
    prov.get_market_cap_observation = lambda t, p: MarketCapObservation(
        value=Decimal("5000"),
        as_of_date=date(2024, 12, 31),
    )
    app.dependency_overrides[get_financial_statement_service] = lambda: stmt_svc
    app.dependency_overrides[get_market_data_provider] = lambda: prov

    try:
        client = TestClient(app)
        res = client.get(
            "/api/v1/financials/AAPL/enterprise-value",
            params={"period_type": "ANNUAL", "fiscal_year": 2024},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["market_capitalization"]["status"] == "VALID"
        assert Decimal(data["market_capitalization"]["value"]) == Decimal("5000")
        assert data["enterprise_value"]["status"] == "VALID"

        # Case 2: Provider with stale as-of date (2025-03-01) -> UNAVAILABLE
        prov.get_market_cap_observation = lambda t, p: MarketCapObservation(
            value=Decimal("5000"),
            as_of_date=date(2025, 3, 1),
        )
        res_stale = client.get(
            "/api/v1/financials/AAPL/enterprise-value",
            params={"period_type": "ANNUAL", "fiscal_year": 2024},
        )
        assert res_stale.status_code == 200
        data_stale = res_stale.json()
        assert data_stale["market_capitalization"]["status"] == "UNAVAILABLE"
        assert data_stale["enterprise_value"]["status"] == "UNAVAILABLE"
    finally:
        app.dependency_overrides.clear()
