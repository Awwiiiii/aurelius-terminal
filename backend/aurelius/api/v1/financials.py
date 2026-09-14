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
