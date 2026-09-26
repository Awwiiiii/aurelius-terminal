"""
aurelius.api.v1.financials
===========================
REST endpoints for financial statement infrastructure.

Endpoints:
  - GET /api/v1/market/financials/{ticker}/statements: Returns full domain statement responses.
  - GET /api/v1/market/financials/{ticker}/matrix: Returns multi-period presentation matrix
    for high-density terminal grid rendering.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from aurelius.api.v1.schemas.financials import (
    FinancialFactSchema,
    FinancialMatrixRowSchema,
    FinancialPeriodSchema,
    FinancialStatementMatrixResponse,
    FinancialStatementResponse,
)
from aurelius.api.v1.schemas.fundamental import (
    FundamentalReportResponse,
    MetricDiagnosticSchema,
    MetricProvenanceSchema,
    MetricResultSchema,
)
from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FiscalPeriodType,
    PeriodType,
    StatementType,
)
from aurelius.services.financial_statement_service import (
    FinancialStatementService,
    get_financial_statement_service,
)
from aurelius.services.fundamental_service import (
    FundamentalAnalysisService,
    get_fundamental_analysis_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market/financials", tags=["Financial Statements"])


def _to_period_schema(period: FinancialPeriod) -> FinancialPeriodSchema:
    """
    Format domain FinancialPeriod into transport schema with clear display label.
    """
    if period.fiscal_period and period.fiscal_year:
        display = f"{period.fiscal_period.value} {period.fiscal_year}"
    elif period.calendar_year:
        display = f"CY {period.calendar_year}"
    elif period.period_type == PeriodType.INSTANT and period.instant_date:
        display = period.instant_date.isoformat()
    elif period.end_date:
        display = period.end_date.isoformat()
    else:
        display = period.period_key

    return FinancialPeriodSchema(
        period_key=period.period_key,
        period_type=period.period_type,
        instant_date=period.instant_date,
        start_date=period.start_date,
        end_date=period.end_date,
        fiscal_year=period.fiscal_year,
        fiscal_period=period.fiscal_period,
        is_period_label_source_reported=period.is_period_label_source_reported,
        calendar_year=period.calendar_year,
        display_label=display,
    )


@router.get(
    "/{ticker}/statements",
    response_model=list[FinancialStatementResponse],
    summary="Get Financial Statements",
    description=(
        "Retrieve historical financial statements (Income Statement, Balance Sheet, Cash Flow) "
        "for an operating corporate equity across annual or quarterly reporting periods."
    ),
)
async def get_financial_statements(
    ticker: Annotated[
        str,
        Path(description="Listing ticker symbol (e.g. 'AAPL')."),
    ],
    statement_type: Annotated[
        StatementType,
        Query(
            description="Statement type: INCOME_STATEMENT, BALANCE_SHEET, or CASH_FLOW."
        ),
    ] = StatementType.INCOME_STATEMENT,
    frequency: Annotated[
        FiscalPeriodType,
        Query(description="Reporting frequency: ANNUAL or QUARTERLY."),
    ] = FiscalPeriodType.ANNUAL,
    service: Annotated[
        FinancialStatementService,
        Depends(get_financial_statement_service),
    ] = None,  # type: ignore[assignment]
) -> list[FinancialStatementResponse]:
    statements = await service.get_statements(ticker, statement_type, frequency)

    responses: list[FinancialStatementResponse] = []
    for stmt in statements:
        period_schema = _to_period_schema(stmt.period)
        facts_schema = [
            FinancialFactSchema(
                fact_id=fact.fact_id,
                concept_name=fact.concept.source_concept,
                canonical_concept=fact.concept.canonical_concept,
                value=fact.value,
                unit=fact.unit,
                currency=fact.currency,
                scale=fact.scale,
                dimensions=fact.dimensions,
                provenance=fact.provenance,
            )
            for fact in stmt.facts
        ]
        responses.append(
            FinancialStatementResponse(
                statement_id=stmt.statement_id,
                company_id=stmt.company_id,
                statement_type=stmt.statement_type,
                period=period_schema,
                currency=stmt.currency,
                facts=facts_schema,
            )
        )
    return responses


@router.get(
    "/{ticker}/matrix",
    response_model=FinancialStatementMatrixResponse,
    summary="Get Financial Statement Matrix",
    description=(
        "Retrieve a multi-period financial statement presentation matrix with ordered line items "
        "and period columns for high-density tabular terminal display."
    ),
)
async def get_financial_statement_matrix(
    ticker: Annotated[
        str,
        Path(description="Listing ticker symbol (e.g. 'AAPL')."),
    ],
    statement_type: Annotated[
        StatementType,
        Query(
            description="Statement type: INCOME_STATEMENT, BALANCE_SHEET, or CASH_FLOW."
        ),
    ] = StatementType.INCOME_STATEMENT,
    frequency: Annotated[
        FiscalPeriodType,
        Query(description="Reporting frequency: ANNUAL or QUARTERLY."),
    ] = FiscalPeriodType.ANNUAL,
    service: Annotated[
        FinancialStatementService,
        Depends(get_financial_statement_service),
    ] = None,  # type: ignore[assignment]
) -> FinancialStatementMatrixResponse:
    matrix = await service.get_statement_matrix(ticker, statement_type, frequency)

    periods_schema = [_to_period_schema(p) for p in matrix.periods]
    rows_schema = [
        FinancialMatrixRowSchema(
            concept_key=r.concept_key,
            display_name=r.display_name,
            canonical_concept=r.canonical_concept,
            is_canonical=r.is_canonical,
            values_by_period=r.values_by_period,
        )
        for r in matrix.rows
    ]

    return FinancialStatementMatrixResponse(
        company_id=matrix.company_id,
        statement_type=matrix.statement_type,
        frequency=matrix.frequency,
        currency=matrix.currency,
        periods=periods_schema,
        rows=rows_schema,
    )


@router.get(
    "/{ticker}/fundamentals",
    response_model=FundamentalReportResponse,
    summary="Get Fundamental Analysis",
    description=(
        "Retrieve canonical fundamental analysis metrics and financial ratios across "
        "growth, profitability, liquidity, solvency, efficiency, and cash flow."
    ),
)
async def get_fundamentals(
    ticker: Annotated[
        str,
        Path(description="Listing ticker symbol (e.g. 'AAPL')."),
    ],
    frequency: Annotated[
        FiscalPeriodType,
        Query(description="Reporting frequency: ANNUAL or QUARTERLY."),
    ] = FiscalPeriodType.ANNUAL,
    allow_point_in_time_fallback: Annotated[
        bool,
        Query(
            description=(
                "If True, allows point-in-time ending balance sheet fallback when prior period is missing. "
                "Default is False (strict two-point averaging)."
            )
        ),
    ] = False,
    service: Annotated[
        FundamentalAnalysisService,
        Depends(get_fundamental_analysis_service),
    ] = None,  # type: ignore[assignment]
) -> FundamentalReportResponse:
    report = await service.get_fundamental_report(
        ticker=ticker,
        frequency=frequency,
        allow_point_in_time_fallback=allow_point_in_time_fallback,
    )

    periods_schema = [_to_period_schema(p) for p in report.periods]
    metrics_schema: dict[str, list[MetricResultSchema]] = {}

    for metric_id, results in report.metrics.items():
        metrics_schema[metric_id] = [
            MetricResultSchema(
                metric_id=r.metric_id.value,
                category=r.category.value,
                status=r.status.value,
                value=r.value,
                formatted_value=r.formatted_value,
                unit=r.unit.value,
                currency=r.currency.value if r.currency else None,
                period_key=r.period.period_key,
                is_derived=r.is_derived,
                diagnostics=[
                    MetricDiagnosticSchema(
                        code=d.code.value,
                        message=d.message,
                        details=d.details,
                    )
                    for d in r.diagnostics
                ],
                provenance=MetricProvenanceSchema(
                    formula_id=r.provenance.formula_id,
                    methodology_version=r.provenance.methodology_version,
                    source_fact_ids=r.provenance.source_fact_ids,
                    source_concepts=r.provenance.source_concepts,
                    source_periods=r.provenance.source_periods,
                    provider=r.provenance.provider,
                    methodology_notes=r.provenance.methodology_notes,
                ),
            )
            for r in results
        ]

    diagnostics_schema = [
        MetricDiagnosticSchema(
            code=d.code.value,
            message=d.message,
            details=d.details,
        )
        for d in report.diagnostics_summary
    ]

    return FundamentalReportResponse(
        ticker=report.ticker,
        frequency=report.frequency.value,
        reporting_currency=report.reporting_currency.value
        if report.reporting_currency
        else None,
        periods=periods_schema,
        metrics=metrics_schema,
        diagnostics_summary=diagnostics_schema,
    )
