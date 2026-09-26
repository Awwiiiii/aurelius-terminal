"""
tests.unit.api.test_fundamentals_endpoints
==========================================
Unit tests for Fundamental Analysis REST API endpoints.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from aurelius.api.main import app
from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FiscalPeriodLabel,
    FiscalPeriodType,
    PeriodType,
    Unit,
)
from aurelius.domain.fundamental.enums import (
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)
from aurelius.domain.fundamental.models import (
    FundamentalReport,
    MetricProvenance,
    MetricResult,
)
from aurelius.services.fundamental_service import (
    FundamentalAnalysisService,
    get_fundamental_analysis_service,
)


def test_get_fundamentals_endpoint():
    client = TestClient(app)

    p = FinancialPeriod(
        period_type=PeriodType.DURATION,
        end_date=date(2024, 9, 30),
        fiscal_year=2024,
        fiscal_period=FiscalPeriodLabel.FY,
    )

    mock_report = FundamentalReport(
        ticker="AAPL",
        frequency=FiscalPeriodType.ANNUAL,
        reporting_currency=Currency.USD,
        periods=[p],
        metrics={
            FundamentalMetricId.GROSS_PROFIT_MARGIN.value: [
                MetricResult(
                    metric_id=FundamentalMetricId.GROSS_PROFIT_MARGIN,
                    category=MetricCategory.PROFITABILITY,
                    status=MetricStatus.VALID,
                    value=Decimal("0.4621"),
                    unit=Unit.PERCENT,
                    currency=None,
                    period=p,
                    diagnostics=[],
                    provenance=MetricProvenance(
                        formula_id="FORMULA_GROSS_MARGIN_FROM_REPORTED_GP",
                        source_concepts=["GROSS_PROFIT", "REVENUE"],
                        source_periods=[p.period_key],
                    ),
                )
            ]
        },
        diagnostics_summary=[],
    )

    mock_service = AsyncMock(spec=FundamentalAnalysisService)
    mock_service.get_fundamental_report.return_value = mock_report

    app.dependency_overrides[get_fundamental_analysis_service] = lambda: mock_service
    try:
        response = client.get(
            "/api/v1/market/financials/AAPL/fundamentals",
            params={"frequency": "ANNUAL", "allow_point_in_time_fallback": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["frequency"] == "ANNUAL"
        assert len(data["periods"]) == 1
        assert "GROSS_PROFIT_MARGIN" in data["metrics"]
        m_item = data["metrics"]["GROSS_PROFIT_MARGIN"][0]
        assert m_item["status"] == "VALID"
        assert m_item["formatted_value"] == "46.21%"
        assert m_item["value"] == 0.4621 or Decimal(str(m_item["value"])) == Decimal(
            "0.4621"
        )
        assert (
            m_item["provenance"]["formula_id"]
            == "FORMULA_GROSS_MARGIN_FROM_REPORTED_GP"
        )
    finally:
        app.dependency_overrides.pop(get_fundamental_analysis_service, None)
