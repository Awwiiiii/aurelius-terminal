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
from aurelius.api.v1.schemas.fundamentals import (
    AdvancedFundamentalsResponse,
    CAGRDataPointSchema,
    CommonSizeItemSchema,
    CommonSizeStatementsResponse,
    CommonSizeTableSchema,
    DuPont3StepResponse,
    DuPont5StepResponse,
    DuPontReconciliation,
    FundamentalTrendsResponse,
    MetricTrendSeriesSchema,
    MetricValueResponse,
    QualityDiagnosticsResponse,
    TrendDataPointSchema,
)
from aurelius.api.v1.schemas.fundamentals.capital_allocation_schemas import (
    CapitalAllocationResponse,
    CashFlowWorkingCapitalResponse,
    FreeCashFlowSectionSchema,
    FundamentalGrowthSectionSchema,
    ReinvestmentSectionSchema,
    WorkingCapitalSectionSchema,
)
from aurelius.api.v1.schemas.fundamentals.credit_schemas import (
    AltmanZScoreSchema,
    CreditRiskResponse,
    EnterpriseValueResponse,
    M7B3ComprehensiveResponse,
    PiotroskiScoreSchema,
    PiotroskiSignalSchema,
    TraceableMetricDiagnosticSchema,
)
from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FiscalPeriodLabel,
    FiscalPeriodType,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.common_size import CommonSizeStatement
from aurelius.domain.fundamental.engines.dupont import (
    DuPont3StepDecomposition,
    DuPont5StepDecomposition,
)
from aurelius.domain.fundamental.engines.trend_engine import (
    CAGRResult,
    TrendPoint,
)
from aurelius.domain.fundamental.models import (
    MetricDiagnostic,
    MetricResult,
)
from aurelius.services.capital_cashflow_credit_service import (
    CapitalCashflowCreditService,
    get_capital_cashflow_credit_service,
)
from aurelius.services.financial_statement_service import (
    FinancialStatementService,
    get_financial_statement_service,
)
from aurelius.services.fundamental_service import (
    FundamentalAnalysisService,
    get_fundamental_analysis_service,
)
from aurelius.services.fundamental_trend_service import (
    FundamentalTrendService,
    get_fundamental_trend_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market/financials", tags=["Financial Statements"])
direct_router = APIRouter(prefix="/financials", tags=["Advanced Fundamentals"])


def _to_period_schema(period: FinancialPeriod) -> FinancialPeriodSchema:
    """
    Format domain FinancialPeriod into transport schema with clear display label.
    """
    if period.fiscal_period == FiscalPeriodLabel.TTM:
        display = (
            f"TTM ({period.end_date.isoformat()})"
            if period.end_date
            else f"TTM {period.fiscal_year or ''}".strip()
        )
    elif period.fiscal_period and period.fiscal_year:
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
        Query(description="Reporting frequency: ANNUAL, QUARTERLY, or TTM."),
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


CANONICAL_METRIC_UNITS: dict[str, str] = {
    "revenue": "CURRENCY",
    "revenue_growth": "PERCENT",
    "gross_margin": "PERCENT",
    "operating_margin": "PERCENT",
    "net_margin": "PERCENT",
    "roa": "PERCENT",
    "roe": "PERCENT",
    "roic": "PERCENT",
    "cfo": "CURRENCY",
    "fcf": "CURRENCY",
    "fcf_margin": "PERCENT",
    "cfo_to_net_income": "RATIO",
    "fcf_to_net_income": "RATIO",
    "debt_to_ebitda": "RATIO",
    "net_debt_to_ebitda": "RATIO",
    "cash_conversion_cycle": "DAYS",
}


def _to_metric_value_response(r: MetricResult) -> MetricValueResponse:
    return MetricValueResponse(
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


def _to_dupont_3step_response(r: DuPont3StepDecomposition) -> DuPont3StepResponse:
    recon = DuPontReconciliation(
        is_reconciled=r.is_reconciled,
        reconciliation_discrepancy=r.reconciliation_discrepancy,
    )
    return DuPont3StepResponse(
        net_profit_margin=_to_metric_value_response(r.net_profit_margin),
        asset_turnover=_to_metric_value_response(r.asset_turnover),
        equity_multiplier=_to_metric_value_response(r.equity_multiplier),
        reconstructed_roe=_to_metric_value_response(r.reconstructed_roe),
        direct_roe=_to_metric_value_response(r.direct_roe),
        is_reconciled=r.is_reconciled,
        reconciliation_discrepancy=r.reconciliation_discrepancy,
        reconciliation=recon,
    )


def _to_dupont_5step_response(r: DuPont5StepDecomposition) -> DuPont5StepResponse:
    recon = DuPontReconciliation(
        is_reconciled=r.is_reconciled,
        reconciliation_discrepancy=r.reconciliation_discrepancy,
    )
    return DuPont5StepResponse(
        tax_burden=_to_metric_value_response(r.tax_burden),
        interest_burden=_to_metric_value_response(r.interest_burden),
        ebit_margin=_to_metric_value_response(r.ebit_margin),
        asset_turnover=_to_metric_value_response(r.asset_turnover),
        equity_multiplier=_to_metric_value_response(r.equity_multiplier),
        reconstructed_roe=_to_metric_value_response(r.reconstructed_roe),
        direct_roe=_to_metric_value_response(r.direct_roe),
        is_reconciled=r.is_reconciled,
        reconciliation_discrepancy=r.reconciliation_discrepancy,
        reconciliation=recon,
    )


def _to_quality_diagnostics_response(
    sloan: MetricResult,
    oqr: MetricResult,
    summary_diags: list[MetricDiagnostic],
) -> QualityDiagnosticsResponse:
    return QualityDiagnosticsResponse(
        sloan_accruals=_to_metric_value_response(sloan),
        operating_quality_ratio=_to_metric_value_response(oqr),
        diagnostics_summary=[
            MetricDiagnosticSchema(
                code=d.code.value,
                message=d.message,
                details=d.details,
            )
            for d in summary_diags
        ],
    )


def _format_common_size_title(stmt: CommonSizeStatement) -> str:
    p = stmt.period
    date_str = (
        p.end_date.isoformat()
        if p.end_date
        else (p.instant_date.isoformat() if p.instant_date else p.period_key)
    )
    if stmt.statement_type == StatementType.BALANCE_SHEET:
        return f"Balance Sheet — Quarter Ended {date_str}"
    elif stmt.statement_type == StatementType.INCOME_STATEMENT:
        period_lbl = p.fiscal_period.value if p.fiscal_period else ""
        year_lbl = str(p.fiscal_year) if p.fiscal_year else date_str
        return f"Income Statement — {period_lbl} {year_lbl}".strip()
    else:
        period_lbl = p.fiscal_period.value if p.fiscal_period else ""
        year_lbl = str(p.fiscal_year) if p.fiscal_year else date_str
        return f"Cash Flow Statement — {period_lbl} {year_lbl}".strip()


def _to_common_size_table_schema(stmt: CommonSizeStatement) -> CommonSizeTableSchema:
    return CommonSizeTableSchema(
        statement_type=stmt.statement_type.value,
        period=_to_period_schema(stmt.period),
        display_title=_format_common_size_title(stmt),
        base_concept_name=stmt.base_concept_name,
        base_value=stmt.base_value,
        status=stmt.status.value,
        items=[
            CommonSizeItemSchema(
                concept_name=it.concept_name,
                reported_value=it.reported_value,
                common_size_percent=it.common_size_percent,
                status=it.status.value,
                diagnostics=[
                    MetricDiagnosticSchema(
                        code=d.code.value,
                        message=d.message,
                        details=d.details,
                    )
                    for d in it.diagnostics
                ],
                provenance=MetricProvenanceSchema(
                    formula_id=it.provenance.formula_id,
                    methodology_version=it.provenance.methodology_version,
                    source_fact_ids=it.provenance.source_fact_ids,
                    source_concepts=it.provenance.source_concepts,
                    source_periods=it.provenance.source_periods,
                    provider=it.provenance.provider,
                    methodology_notes=it.provenance.methodology_notes,
                ),
            )
            for it in stmt.items
        ],
        diagnostics=[
            MetricDiagnosticSchema(
                code=d.code.value,
                message=d.message,
                details=d.details,
            )
            for d in stmt.diagnostics
        ],
        provenance=MetricProvenanceSchema(
            formula_id=stmt.provenance.formula_id,
            methodology_version=stmt.provenance.methodology_version,
            source_fact_ids=stmt.provenance.source_fact_ids,
            source_concepts=stmt.provenance.source_concepts,
            source_periods=stmt.provenance.source_periods,
            provider=stmt.provenance.provider,
            methodology_notes=stmt.provenance.methodology_notes,
        ),
    )


def _to_trend_point_schema(tp: TrendPoint) -> TrendDataPointSchema:
    fmt_val = str(tp.value) if tp.value is not None else "UNAVAILABLE"
    return TrendDataPointSchema(
        period=_to_period_schema(tp.period),
        value=tp.value,
        formatted_value=fmt_val,
        status=tp.status.value,
        qoq_change=tp.qoq_change,
        yoy_change=tp.yoy_change,
        ttm_sequential_change=tp.ttm_sequential_change,
        diagnostics=[
            MetricDiagnosticSchema(
                code=d.code.value,
                message=d.message,
                details=d.details,
            )
            for d in tp.diagnostics
        ],
        provenance=MetricProvenanceSchema(
            formula_id=tp.provenance.formula_id,
            methodology_version=tp.provenance.methodology_version,
            source_fact_ids=tp.provenance.source_fact_ids,
            source_concepts=tp.provenance.source_concepts,
            source_periods=tp.provenance.source_periods,
            provider=tp.provenance.provider,
            methodology_notes=tp.provenance.methodology_notes,
        ),
    )


def _to_cagr_point_schema(cagr: CAGRResult) -> CAGRDataPointSchema:
    formatted_cagr = (
        f"{float(cagr.cagr) * 100:.2f}%" if cagr.cagr is not None else "UNAVAILABLE"
    )
    return CAGRDataPointSchema(
        metric_name=cagr.metric_name,
        horizon=cagr.horizon,
        cagr=cagr.cagr,
        formatted_cagr=formatted_cagr,
        status=cagr.status.value,
        start_period=_to_period_schema(cagr.start_period),
        end_period=_to_period_schema(cagr.end_period),
        calendar_days=cagr.calendar_days,
        diagnostics=[
            MetricDiagnosticSchema(
                code=d.code.value,
                message=d.message,
                details=d.details,
            )
            for d in cagr.diagnostics
        ],
        provenance=MetricProvenanceSchema(
            formula_id=cagr.provenance.formula_id,
            methodology_version=cagr.provenance.methodology_version,
            source_fact_ids=cagr.provenance.source_fact_ids,
            source_concepts=cagr.provenance.source_concepts,
            source_periods=cagr.provenance.source_periods,
            provider=cagr.provenance.provider,
            methodology_notes=cagr.provenance.methodology_notes,
        ),
    )


@router.get(
    "/{ticker}/advanced-fundamentals",
    response_model=AdvancedFundamentalsResponse,
    summary="Get Advanced Fundamentals",
    description=(
        "Retrieve ROIC, NOPAT, Invested Capital, 3-Step DuPont, 5-Step DuPont, "
        "and Quality Diagnostics across Annual, Quarterly, or TTM periods."
    ),
)
@direct_router.get(
    "/{ticker}/advanced-fundamentals",
    response_model=AdvancedFundamentalsResponse,
    summary="Get Advanced Fundamentals",
    description=(
        "Retrieve ROIC, NOPAT, Invested Capital, 3-Step DuPont, 5-Step DuPont, "
        "and Quality Diagnostics across Annual, Quarterly, or TTM periods."
    ),
)
async def get_advanced_fundamentals(
    ticker: Annotated[
        str,
        Path(description="Listing ticker symbol (e.g. 'AAPL')."),
    ],
    period_type: Annotated[
        FiscalPeriodType,
        Query(description="Period type: ANNUAL, QUARTERLY, or TTM."),
    ] = FiscalPeriodType.TTM,
    fiscal_year: Annotated[
        int | None,
        Query(description="Target fiscal year (optional)."),
    ] = None,
    fiscal_period: Annotated[
        str | None,
        Query(description="Target fiscal period (e.g. Q1, Q2, Q3, Q4) (optional)."),
    ] = None,
    allow_point_in_time: Annotated[
        bool,
        Query(
            description=(
                "If True, allows point-in-time ending balance sheet fallback when beginning period is missing. "
                "Default is False (strict two-point averaging)."
            )
        ),
    ] = False,
    service: Annotated[
        FundamentalAnalysisService,
        Depends(get_fundamental_analysis_service),
    ] = None,  # type: ignore[assignment]
) -> AdvancedFundamentalsResponse:
    adv = await service.get_advanced_fundamentals(
        ticker=ticker,
        frequency=period_type,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        allow_point_in_time_fallback=allow_point_in_time,
    )
    (
        target_period,
        reporting_currency,
        etr_res,
        nopat_res,
        ic_res,
        avg_ic_res,
        roic_res,
        dupont3,
        dupont5,
        sloan_res,
        oqr_res,
        summary_diags,
    ) = adv

    return AdvancedFundamentalsResponse(
        ticker=ticker.upper(),
        period_type=period_type.value,
        period=_to_period_schema(target_period),
        reporting_currency=reporting_currency.value if reporting_currency else None,
        effective_tax_rate=_to_metric_value_response(etr_res),
        nopat=_to_metric_value_response(nopat_res),
        invested_capital=_to_metric_value_response(ic_res),
        average_invested_capital=_to_metric_value_response(avg_ic_res),
        roic=_to_metric_value_response(roic_res),
        dupont_3step=_to_dupont_3step_response(dupont3),
        dupont_5step=_to_dupont_5step_response(dupont5),
        quality_diagnostics=_to_quality_diagnostics_response(
            sloan_res, oqr_res, summary_diags
        ),
        diagnostics_summary=[
            MetricDiagnosticSchema(
                code=d.code.value,
                message=d.message,
                details=d.details,
            )
            for d in summary_diags
        ],
        provenance=MetricProvenanceSchema(
            formula_id="FORMULA_ADVANCED_FUNDAMENTALS",
            methodology_version="1.0.0",
            source_fact_ids=roic_res.provenance.source_fact_ids,
            source_concepts=roic_res.provenance.source_concepts,
            source_periods=roic_res.provenance.source_periods,
            provider=roic_res.provenance.provider,
            methodology_notes="Advanced Fundamental dossier unifying ROIC, DuPont ROE decompositions, and earnings quality.",
        ),
    )


@router.get(
    "/{ticker}/common-size",
    response_model=CommonSizeStatementsResponse,
    summary="Get Common-Size Financial Statements",
    description=(
        "Retrieve Common-Size Income Statement, Balance Sheet (instant snapshot), "
        "and Cash Flow Statement across Annual, Quarterly, or TTM periods."
    ),
)
@direct_router.get(
    "/{ticker}/common-size",
    response_model=CommonSizeStatementsResponse,
    summary="Get Common-Size Financial Statements",
    description=(
        "Retrieve Common-Size Income Statement, Balance Sheet (instant snapshot), "
        "and Cash Flow Statement across Annual, Quarterly, or TTM periods."
    ),
)
async def get_common_size(
    ticker: Annotated[
        str,
        Path(description="Listing ticker symbol (e.g. 'AAPL')."),
    ],
    period_type: Annotated[
        FiscalPeriodType,
        Query(description="Period type: ANNUAL, QUARTERLY, or TTM."),
    ] = FiscalPeriodType.ANNUAL,
    fiscal_year: Annotated[
        int | None,
        Query(description="Target fiscal year (optional)."),
    ] = None,
    fiscal_period: Annotated[
        str | None,
        Query(description="Target fiscal period (e.g. Q1, Q2, Q3, Q4) (optional)."),
    ] = None,
    service: Annotated[
        FundamentalAnalysisService,
        Depends(get_fundamental_analysis_service),
    ] = None,  # type: ignore[assignment]
) -> CommonSizeStatementsResponse:
    target_period, cs_is, cs_bs, cs_cf = await service.get_common_size_statements(
        ticker=ticker,
        frequency=period_type,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
    )

    all_facts = (
        cs_is.provenance.source_fact_ids
        + cs_bs.provenance.source_fact_ids
        + cs_cf.provenance.source_fact_ids
    )
    all_concepts = (
        cs_is.provenance.source_concepts
        + cs_bs.provenance.source_concepts
        + cs_cf.provenance.source_concepts
    )
    all_periods = (
        cs_is.provenance.source_periods
        + cs_bs.provenance.source_periods
        + cs_cf.provenance.source_periods
    )

    return CommonSizeStatementsResponse(
        ticker=ticker.upper(),
        period_type=period_type.value,
        income_statement=_to_common_size_table_schema(cs_is),
        balance_sheet=_to_common_size_table_schema(cs_bs),
        cash_flow_statement=_to_common_size_table_schema(cs_cf),
        period=_to_period_schema(target_period),
        provenance=MetricProvenanceSchema(
            formula_id="FORMULA_COMMON_SIZE_STATEMENTS",
            methodology_version="1.0.0",
            source_fact_ids=list(dict.fromkeys(all_facts)),
            source_concepts=list(dict.fromkeys(all_concepts)),
            source_periods=list(dict.fromkeys(all_periods)),
            provider="yahoo_finance",
            methodology_notes="Common-Size Statements dossier. Balance Sheet is strictly point-in-time instant snapshot.",
        ),
    )


@router.get(
    "/{ticker}/fundamental-trends",
    response_model=FundamentalTrendsResponse,
    summary="Get Fundamental Trends and CAGR",
    description=(
        "Retrieve historical fundamental trajectories, sequential QoQ/YoY changes, "
        "and M4 calendar-time CAGR across Annual, Quarterly, or TTM periods."
    ),
)
@direct_router.get(
    "/{ticker}/fundamental-trends",
    response_model=FundamentalTrendsResponse,
    summary="Get Fundamental Trends and CAGR",
    description=(
        "Retrieve historical fundamental trajectories, sequential QoQ/YoY changes, "
        "and M4 calendar-time CAGR across Annual, Quarterly, or TTM periods."
    ),
)
async def get_fundamental_trends(
    ticker: Annotated[
        str,
        Path(description="Listing ticker symbol (e.g. 'AAPL')."),
    ],
    period_type: Annotated[
        FiscalPeriodType,
        Query(description="Period type: ANNUAL, QUARTERLY, or TTM."),
    ] = FiscalPeriodType.ANNUAL,
    metrics: Annotated[
        list[str] | None,
        Query(description="List of canonical metrics to include."),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=20,
            description="Maximum number of historical periods (default 10, max 20).",
        ),
    ] = 10,
    service: Annotated[
        FundamentalTrendService,
        Depends(get_fundamental_trend_service),
    ] = None,  # type: ignore[assignment]
) -> FundamentalTrendsResponse:
    flattened_metrics: list[str] | None = None
    if metrics:
        flattened_metrics = [
            part.strip() for m in metrics for part in m.split(",") if part.strip()
        ]

    norm_ticker, freq, series_dict, cagr_dict = await service.get_fundamental_trends(
        ticker=ticker,
        frequency=period_type,
        metrics=flattened_metrics,
        limit=limit,
    )

    series_schema: dict[str, MetricTrendSeriesSchema] = {}
    for m_name, points in series_dict.items():
        unit_str = CANONICAL_METRIC_UNITS.get(m_name, "RATIO")
        series_schema[m_name] = MetricTrendSeriesSchema(
            metric_name=m_name,
            unit=unit_str,
            points=[_to_trend_point_schema(p) for p in points],
        )

    cagr_schema: dict[str, list[CAGRDataPointSchema]] = {}
    for m_name, cagr_list in cagr_dict.items():
        cagr_schema[m_name] = [_to_cagr_point_schema(c) for c in cagr_list]

    return FundamentalTrendsResponse(
        ticker=norm_ticker,
        period_type=freq.value,
        series=series_schema,
        cagr_results=cagr_schema,
        provenance=MetricProvenanceSchema(
            formula_id="FORMULA_FUNDAMENTAL_TRENDS",
            methodology_version="1.0.0",
            source_fact_ids=[],
            source_concepts=list(series_dict.keys()),
            source_periods=[],
            provider="yahoo_finance",
            methodology_notes="Multi-period fundamental trends with YoY, QoQ, TTM sequential variation and M4 calendar-time CAGR.",
        ),
    )


# =============================================================================
# M7B.3 HELPER: TRACEABLE DIAGNOSTICS AGGREGATION
# =============================================================================


def _aggregate_traceable_diagnostics(
    metric_results: list[MetricResult],
) -> list[TraceableMetricDiagnosticSchema]:
    """
    Deduplicate diagnostics across multiple metric results while preserving
    affected metric traceability.
    """
    summary_map: dict[str, dict] = {}

    for res in metric_results:
        metric_name = res.metric_id.value.lower()
        for diag in res.diagnostics:
            code_str = diag.code.value
            if code_str not in summary_map:
                summary_map[code_str] = {
                    "code": code_str,
                    "message": diag.message,
                    "severity": "WARNING",
                    "affected_metric_ids": set(),
                    "details": dict(diag.details),
                }
            summary_map[code_str]["affected_metric_ids"].add(metric_name)
            summary_map[code_str]["details"].update(diag.details)

    return [
        TraceableMetricDiagnosticSchema(
            code=v["code"],
            message=v["message"],
            severity=v["severity"],
            affected_metric_ids=sorted(list(v["affected_metric_ids"])),
            details=v["details"],
        )
        for v in summary_map.values()
    ]


# =============================================================================
# M7B.3 REST ENDPOINTS
# =============================================================================


@router.get(
    "/{ticker}/capital-allocation",
    response_model=CapitalAllocationResponse,
    summary="Get Capital Allocation & Shareholder Yields",
    description="Retrieve capital deployment flows, shareholder distributions, and market-cap-based yields.",
)
@direct_router.get(
    "/{ticker}/capital-allocation",
    response_model=CapitalAllocationResponse,
    summary="Get Capital Allocation & Shareholder Yields",
    description="Retrieve capital deployment flows, shareholder distributions, and market-cap-based yields.",
)
async def get_capital_allocation(
    ticker: Annotated[str, Path(description="Listing ticker symbol.")],
    period_type: Annotated[
        FiscalPeriodType,
        Query(description="Period type: ANNUAL, QUARTERLY, or TTM."),
    ] = FiscalPeriodType.TTM,
    fiscal_year: Annotated[int | None, Query(description="Target fiscal year.")] = None,
    fiscal_period: Annotated[
        str | None, Query(description="Target fiscal period (Q1-Q4).")
    ] = None,
    service: Annotated[
        CapitalCashflowCreditService,
        Depends(get_capital_cashflow_credit_service),
    ] = None,  # type: ignore[assignment]
) -> CapitalAllocationResponse:
    period, rep_curr, metrics = await service.get_capital_allocation(
        ticker=ticker,
        frequency=period_type,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
    )

    all_metric_results = list(metrics.values())
    summary_diags = _aggregate_traceable_diagnostics(all_metric_results)

    return CapitalAllocationResponse(
        ticker=ticker.upper(),
        period_type=period_type.value,
        period=_to_period_schema(period),
        reporting_currency=rep_curr.value if rep_curr else None,
        operating_cash_flow=_to_metric_value_response(metrics["cfo"]),
        capital_expenditures=_to_metric_value_response(metrics["capex"]),
        dividends_paid=_to_metric_value_response(metrics["dividends_paid"]),
        stock_repurchases=_to_metric_value_response(metrics["stock_repurchases"]),
        stock_issuance=_to_metric_value_response(metrics["stock_issuance"]),
        debt_issued=_to_metric_value_response(metrics["debt_issued"]),
        debt_repaid=_to_metric_value_response(metrics["debt_repaid"]),
        net_debt_issued=_to_metric_value_response(metrics["net_debt_issued"]),
        acquisitions_mna=_to_metric_value_response(metrics["acquisitions_mna"]),
        dividend_yield=_to_metric_value_response(metrics["dividend_yield"]),
        buyback_yield=_to_metric_value_response(metrics["buyback_yield"]),
        gross_shareholder_yield=_to_metric_value_response(
            metrics["gross_shareholder_yield"]
        ),
        net_shareholder_yield=_to_metric_value_response(
            metrics["net_shareholder_yield"]
        ),
        diagnostics_summary=summary_diags,
    )


@router.get(
    "/{ticker}/cash-flows",
    response_model=CashFlowWorkingCapitalResponse,
    summary="Get Structured Cash Flows & Working Capital",
    description="Retrieve Operating NWC, multi-period Delta NWC, FCFF primary/reconciliation, FCFE, Reinvestment, and Growth.",
)
@direct_router.get(
    "/{ticker}/cash-flows",
    response_model=CashFlowWorkingCapitalResponse,
    summary="Get Structured Cash Flows & Working Capital",
    description="Retrieve Operating NWC, multi-period Delta NWC, FCFF primary/reconciliation, FCFE, Reinvestment, and Growth.",
)
async def get_cash_flows(
    ticker: Annotated[str, Path(description="Listing ticker symbol.")],
    period_type: Annotated[
        FiscalPeriodType,
        Query(description="Period type: ANNUAL, QUARTERLY, or TTM."),
    ] = FiscalPeriodType.TTM,
    fiscal_year: Annotated[int | None, Query(description="Target fiscal year.")] = None,
    fiscal_period: Annotated[
        str | None, Query(description="Target fiscal period (Q1-Q4).")
    ] = None,
    service: Annotated[
        CapitalCashflowCreditService,
        Depends(get_capital_cashflow_credit_service),
    ] = None,  # type: ignore[assignment]
) -> CashFlowWorkingCapitalResponse:
    period, rep_curr, metrics, recon_res, nb_tier = await service.get_cash_flows(
        ticker=ticker,
        frequency=period_type,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
    )

    all_metric_results = list(metrics.values())
    summary_diags = _aggregate_traceable_diagnostics(all_metric_results)

    working_cap_sec = WorkingCapitalSectionSchema(
        operating_current_assets=_to_metric_value_response(metrics["operating_ca"]),
        operating_current_liabilities=_to_metric_value_response(
            metrics["operating_cl"]
        ),
        operating_nwc=_to_metric_value_response(metrics["operating_nwc"]),
        delta_nwc=_to_metric_value_response(metrics["delta_nwc"]),
    )

    fcf_sec = FreeCashFlowSectionSchema(
        fcff_primary=_to_metric_value_response(metrics["fcff_primary"]),
        fcff_reconciled=_to_metric_value_response(metrics["fcff_reconciled"]),
        reconciliation_delta=recon_res.reconciliation_delta,
        divergence_ratio=recon_res.divergence_ratio,
        is_divergent=recon_res.is_divergent,
        fcfe=_to_metric_value_response(metrics["fcfe"]),
        net_borrowing_tier=nb_tier,
    )

    reinv_sec = ReinvestmentSectionSchema(
        reinvestment=_to_metric_value_response(metrics["reinvestment"]),
        reinvestment_rate=_to_metric_value_response(metrics["reinvestment_rate"]),
    )

    growth_sec = FundamentalGrowthSectionSchema(
        fundamental_growth=_to_metric_value_response(metrics["fundamental_growth"]),
    )

    return CashFlowWorkingCapitalResponse(
        ticker=ticker.upper(),
        period_type=period_type.value,
        period=_to_period_schema(period),
        reporting_currency=rep_curr.value if rep_curr else None,
        working_capital=working_cap_sec,
        free_cash_flow=fcf_sec,
        reinvestment=reinv_sec,
        growth=growth_sec,
        diagnostics_summary=summary_diags,
    )


@router.get(
    "/{ticker}/enterprise-value",
    response_model=EnterpriseValueResponse,
    summary="Get Enterprise Value Bridge & Capital Structure",
    description="Retrieve EV bridge claims and capital structure weights with strict historical market-cap temporal matching.",
)
@direct_router.get(
    "/{ticker}/enterprise-value",
    response_model=EnterpriseValueResponse,
    summary="Get Enterprise Value Bridge & Capital Structure",
    description="Retrieve EV bridge claims and capital structure weights with strict historical market-cap temporal matching.",
)
async def get_enterprise_value(
    ticker: Annotated[str, Path(description="Listing ticker symbol.")],
    period_type: Annotated[
        FiscalPeriodType,
        Query(description="Period type: ANNUAL, QUARTERLY, or TTM."),
    ] = FiscalPeriodType.TTM,
    fiscal_year: Annotated[int | None, Query(description="Target fiscal year.")] = None,
    fiscal_period: Annotated[
        str | None, Query(description="Target fiscal period (Q1-Q4).")
    ] = None,
    service: Annotated[
        CapitalCashflowCreditService,
        Depends(get_capital_cashflow_credit_service),
    ] = None,  # type: ignore[assignment]
) -> EnterpriseValueResponse:
    (
        period,
        rep_curr,
        metrics,
        pref_case,
        min_case,
        cap_struct_res,
    ) = await service.get_enterprise_value(
        ticker=ticker,
        frequency=period_type,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
    )

    all_metric_results = list(metrics.values())
    summary_diags = _aggregate_traceable_diagnostics(all_metric_results)

    return EnterpriseValueResponse(
        ticker=ticker.upper(),
        period_type=period_type.value,
        period=_to_period_schema(period),
        reporting_currency=rep_curr.value if rep_curr else None,
        market_capitalization=_to_metric_value_response(
            metrics["market_capitalization"]
        ),
        gross_debt=_to_metric_value_response(metrics["gross_debt"]),
        preferred_equity=_to_metric_value_response(metrics["preferred_equity"]),
        minority_interest=_to_metric_value_response(metrics["minority_interest"]),
        cash_and_liquid_investments=_to_metric_value_response(
            metrics["cash_and_liquid_investments"]
        ),
        enterprise_value=_to_metric_value_response(metrics["enterprise_value"]),
        preferred_equity_disclosure_case=pref_case,
        minority_interest_disclosure_case=min_case,
        total_capital=_to_metric_value_response(metrics["total_capital"]),
        weight_equity=_to_metric_value_response(metrics["weight_equity"]),
        weight_debt=_to_metric_value_response(metrics["weight_debt"]),
        weight_preferred=_to_metric_value_response(metrics["weight_preferred"]),
        diagnostics_summary=summary_diags,
    )


@router.get(
    "/{ticker}/credit-risk",
    response_model=CreditRiskResponse,
    summary="Get Credit Risk & Solvency Scoring",
    description="Retrieve canonical 9-signal Piotroski F-score and structural Altman Z-score (strictly deterministic dispatch, zero override).",
)
@direct_router.get(
    "/{ticker}/credit-risk",
    response_model=CreditRiskResponse,
    summary="Get Credit Risk & Solvency Scoring",
    description="Retrieve canonical 9-signal Piotroski F-score and structural Altman Z-score (strictly deterministic dispatch, zero override).",
)
async def get_credit_risk(
    ticker: Annotated[str, Path(description="Listing ticker symbol.")],
    period_type: Annotated[
        FiscalPeriodType,
        Query(description="Period type: ANNUAL, QUARTERLY, or TTM."),
    ] = FiscalPeriodType.TTM,
    fiscal_year: Annotated[int | None, Query(description="Target fiscal year.")] = None,
    fiscal_period: Annotated[
        str | None, Query(description="Target fiscal period (Q1-Q4).")
    ] = None,
    service: Annotated[
        CapitalCashflowCreditService,
        Depends(get_capital_cashflow_credit_service),
    ] = None,  # type: ignore[assignment]
) -> CreditRiskResponse:
    period, rep_curr, piotroski_res, altman_res = await service.get_credit_risk(
        ticker=ticker,
        frequency=period_type,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
    )

    all_metric_results = [piotroski_res.metric_result, altman_res.metric_result]
    summary_diags = _aggregate_traceable_diagnostics(all_metric_results)

    piotroski_signals = [
        PiotroskiSignalSchema(
            signal_id=s.signal_id,
            status=s.status,
            raw_value=s.raw_value,
            comparison_value=s.comparison_value,
            notes=s.notes,
        )
        for s in piotroski_res.signals
    ]

    piotroski_schema = PiotroskiScoreSchema(
        raw_pass_count=piotroski_res.raw_pass_count,
        evaluated_signal_count=piotroski_res.evaluated_signal_count,
        total_signal_count=piotroski_res.total_signal_count,
        coverage_ratio=piotroski_res.coverage_ratio,
        status=piotroski_res.status.value,
        metric_result=_to_metric_value_response(piotroski_res.metric_result),
        signals=piotroski_signals,
    )

    altman_schema = AltmanZScoreSchema(
        dispatched_model=altman_res.dispatched_model,
        dispatch_rationale=altman_res.dispatch_rationale,
        coefficients=altman_res.coefficients,
        factors=altman_res.factors,
        total_score=altman_res.total_score,
        zone=altman_res.zone,
        metric_result=_to_metric_value_response(altman_res.metric_result),
    )

    return CreditRiskResponse(
        ticker=ticker.upper(),
        period_type=period_type.value,
        period=_to_period_schema(period),
        reporting_currency=rep_curr.value if rep_curr else None,
        piotroski_f_score=piotroski_schema,
        altman_z_score=altman_schema,
        diagnostics_summary=summary_diags,
    )


@router.get(
    "/{ticker}/comprehensive",
    response_model=M7B3ComprehensiveResponse,
    summary="Get Comprehensive Fundamental Analysis Dossier",
    description="Retrieve unified multi-dimensional fundamental dossier combining Capital Allocation, Cash Flows, EV, and Credit Risk.",
)
@direct_router.get(
    "/{ticker}/comprehensive",
    response_model=M7B3ComprehensiveResponse,
    summary="Get Comprehensive Fundamental Analysis Dossier",
    description="Retrieve unified multi-dimensional fundamental dossier combining Capital Allocation, Cash Flows, EV, and Credit Risk.",
)
async def get_comprehensive_dossier(
    ticker: Annotated[str, Path(description="Listing ticker symbol.")],
    period_type: Annotated[
        FiscalPeriodType,
        Query(description="Period type: ANNUAL, QUARTERLY, or TTM."),
    ] = FiscalPeriodType.TTM,
    fiscal_year: Annotated[int | None, Query(description="Target fiscal year.")] = None,
    fiscal_period: Annotated[
        str | None, Query(description="Target fiscal period (Q1-Q4).")
    ] = None,
    service: Annotated[
        CapitalCashflowCreditService,
        Depends(get_capital_cashflow_credit_service),
    ] = None,  # type: ignore[assignment]
) -> M7B3ComprehensiveResponse:
    dossier = await service.get_m7b3_comprehensive_dossier(
        ticker=ticker,
        frequency=period_type,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
    )

    # Convert Capital Allocation
    ca_period, ca_curr, ca_metrics = dossier["capital_allocation"]
    ca_resp = CapitalAllocationResponse(
        ticker=ticker.upper(),
        period_type=period_type.value,
        period=_to_period_schema(ca_period),
        reporting_currency=ca_curr.value if ca_curr else None,
        operating_cash_flow=_to_metric_value_response(ca_metrics["cfo"]),
        capital_expenditures=_to_metric_value_response(ca_metrics["capex"]),
        dividends_paid=_to_metric_value_response(ca_metrics["dividends_paid"]),
        stock_repurchases=_to_metric_value_response(ca_metrics["stock_repurchases"]),
        stock_issuance=_to_metric_value_response(ca_metrics["stock_issuance"]),
        debt_issued=_to_metric_value_response(ca_metrics["debt_issued"]),
        debt_repaid=_to_metric_value_response(ca_metrics["debt_repaid"]),
        net_debt_issued=_to_metric_value_response(ca_metrics["net_debt_issued"]),
        acquisitions_mna=_to_metric_value_response(ca_metrics["acquisitions_mna"]),
        dividend_yield=_to_metric_value_response(ca_metrics["dividend_yield"]),
        buyback_yield=_to_metric_value_response(ca_metrics["buyback_yield"]),
        gross_shareholder_yield=_to_metric_value_response(
            ca_metrics["gross_shareholder_yield"]
        ),
        net_shareholder_yield=_to_metric_value_response(
            ca_metrics["net_shareholder_yield"]
        ),
        diagnostics_summary=_aggregate_traceable_diagnostics(list(ca_metrics.values())),
    )

    # Convert Cash Flows
    cf_period, cf_curr, cf_metrics, recon_res, nb_tier = dossier["cash_flows"]
    cf_resp = CashFlowWorkingCapitalResponse(
        ticker=ticker.upper(),
        period_type=period_type.value,
        period=_to_period_schema(cf_period),
        reporting_currency=cf_curr.value if cf_curr else None,
        working_capital=WorkingCapitalSectionSchema(
            operating_current_assets=_to_metric_value_response(
                cf_metrics["operating_ca"]
            ),
            operating_current_liabilities=_to_metric_value_response(
                cf_metrics["operating_cl"]
            ),
            operating_nwc=_to_metric_value_response(cf_metrics["operating_nwc"]),
            delta_nwc=_to_metric_value_response(cf_metrics["delta_nwc"]),
        ),
        free_cash_flow=FreeCashFlowSectionSchema(
            fcff_primary=_to_metric_value_response(cf_metrics["fcff_primary"]),
            fcff_reconciled=_to_metric_value_response(cf_metrics["fcff_reconciled"]),
            reconciliation_delta=recon_res.reconciliation_delta,
            divergence_ratio=recon_res.divergence_ratio,
            is_divergent=recon_res.is_divergent,
            fcfe=_to_metric_value_response(cf_metrics["fcfe"]),
            net_borrowing_tier=nb_tier,
        ),
        reinvestment=ReinvestmentSectionSchema(
            reinvestment=_to_metric_value_response(cf_metrics["reinvestment"]),
            reinvestment_rate=_to_metric_value_response(
                cf_metrics["reinvestment_rate"]
            ),
        ),
        growth=FundamentalGrowthSectionSchema(
            fundamental_growth=_to_metric_value_response(
                cf_metrics["fundamental_growth"]
            ),
        ),
        diagnostics_summary=_aggregate_traceable_diagnostics(list(cf_metrics.values())),
    )

    # Convert Enterprise Value
    ev_period, ev_curr, ev_metrics, pref_case, min_case, _ = dossier["enterprise_value"]
    ev_resp = EnterpriseValueResponse(
        ticker=ticker.upper(),
        period_type=period_type.value,
        period=_to_period_schema(ev_period),
        reporting_currency=ev_curr.value if ev_curr else None,
        market_capitalization=_to_metric_value_response(
            ev_metrics["market_capitalization"]
        ),
        gross_debt=_to_metric_value_response(ev_metrics["gross_debt"]),
        preferred_equity=_to_metric_value_response(ev_metrics["preferred_equity"]),
        minority_interest=_to_metric_value_response(ev_metrics["minority_interest"]),
        cash_and_liquid_investments=_to_metric_value_response(
            ev_metrics["cash_and_liquid_investments"]
        ),
        enterprise_value=_to_metric_value_response(ev_metrics["enterprise_value"]),
        preferred_equity_disclosure_case=pref_case,
        minority_interest_disclosure_case=min_case,
        total_capital=_to_metric_value_response(ev_metrics["total_capital"]),
        weight_equity=_to_metric_value_response(ev_metrics["weight_equity"]),
        weight_debt=_to_metric_value_response(ev_metrics["weight_debt"]),
        weight_preferred=_to_metric_value_response(ev_metrics["weight_preferred"]),
        diagnostics_summary=_aggregate_traceable_diagnostics(list(ev_metrics.values())),
    )

    # Convert Credit Risk
    cr_period, cr_curr, piotroski_res, altman_res = dossier["credit_risk"]
    cr_resp = CreditRiskResponse(
        ticker=ticker.upper(),
        period_type=period_type.value,
        period=_to_period_schema(cr_period),
        reporting_currency=cr_curr.value if cr_curr else None,
        piotroski_f_score=PiotroskiScoreSchema(
            raw_pass_count=piotroski_res.raw_pass_count,
            evaluated_signal_count=piotroski_res.evaluated_signal_count,
            total_signal_count=piotroski_res.total_signal_count,
            coverage_ratio=piotroski_res.coverage_ratio,
            status=piotroski_res.status.value,
            metric_result=_to_metric_value_response(piotroski_res.metric_result),
            signals=[
                PiotroskiSignalSchema(
                    signal_id=s.signal_id,
                    status=s.status,
                    raw_value=s.raw_value,
                    comparison_value=s.comparison_value,
                    notes=s.notes,
                )
                for s in piotroski_res.signals
            ],
        ),
        altman_z_score=AltmanZScoreSchema(
            dispatched_model=altman_res.dispatched_model,
            dispatch_rationale=altman_res.dispatch_rationale,
            coefficients=altman_res.coefficients,
            factors=altman_res.factors,
            total_score=altman_res.total_score,
            zone=altman_res.zone,
            metric_result=_to_metric_value_response(altman_res.metric_result),
        ),
        diagnostics_summary=_aggregate_traceable_diagnostics(
            [piotroski_res.metric_result, altman_res.metric_result]
        ),
    )

    # Combine global diagnostics
    all_res = [
        *ca_metrics.values(),
        *cf_metrics.values(),
        *ev_metrics.values(),
        piotroski_res.metric_result,
        altman_res.metric_result,
    ]
    global_diags = _aggregate_traceable_diagnostics(all_res)

    return M7B3ComprehensiveResponse(
        ticker=ticker.upper(),
        period_type=period_type.value,
        period=_to_period_schema(ca_period),
        reporting_currency=ca_curr.value if ca_curr else None,
        capital_allocation=ca_resp,
        cash_flows=cf_resp,
        enterprise_value=ev_resp,
        credit_risk=cr_resp,
        diagnostics_summary=global_diags,
    )
