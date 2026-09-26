"""
aurelius.domain.fundamental.engines.common_size
================================================
Pure calculation engine for Common-Size Financial Statements:
  - Common-Size Income Statement (Line Item / Revenue * 100)
  - Common-Size Balance Sheet (Line Item / Total Assets * 100)
  - Common-Size Cash Flow Statement (CFO, CapEx, FCF / Revenue * 100)

Key Invariants:
  - Income Statement & Cash Flow Statement: scaled by Revenue * 100.
      * If Revenue <= 0 -> UNAVAILABLE with NON_POSITIVE_BASE_REVENUE.
  - Balance Sheet: scaled by Total Assets * 100.
      * If Total Assets <= 0 -> UNAVAILABLE with NON_POSITIVE_BASE_ASSETS.
  - Cash Flow Statement CapEx:
      * CapEx preserves AURELIUS canonical positive economic magnitude for outflows.
  - TTM Semantics:
      * Income Statement TTM: four-quarter duration fact aggregation.
      * Cash Flow Statement TTM: four-quarter duration fact aggregation.
      * Balance Sheet: strictly instant snapshot of the anchor quarter.
      * NEVER aggregate four balance sheets across time.
      * NEVER describe or label a balance sheet as "TTM Balance Sheet".
  - Missing facts are never treated as zero.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialPeriod,
    StatementType,
)
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)
from aurelius.domain.fundamental.models import (
    MetricDiagnostic,
    MetricProvenance,
)
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore
from aurelius.domain.fundamental.ttm import TTMEngine, TTMWindow


class CommonSizeItem(BaseModel):
    """
    Individual common-size statement line item.
    """

    model_config = ConfigDict(frozen=True)

    concept_name: str = Field(
        ..., description="Canonical or source line item concept name."
    )
    reported_value: Decimal | None = Field(
        default=None, description="Absolute reported currency value."
    )
    common_size_percent: Decimal | None = Field(
        default=None,
        description="Common-size value expressed as a percentage (e.g. 24.5 for 24.5%).",
    )
    status: MetricStatus = Field(
        default=MetricStatus.VALID, description="Operational status."
    )
    diagnostics: list[MetricDiagnostic] = Field(
        default_factory=list, description="Line item diagnostics."
    )
    provenance: MetricProvenance = Field(
        ..., description="Auditable provenance for this line item."
    )


class CommonSizeStatement(BaseModel):
    """
    A complete common-size financial statement table for a specific period.
    """

    model_config = ConfigDict(frozen=True)

    statement_type: StatementType = Field(
        ..., description="INCOME_STATEMENT, BALANCE_SHEET, or CASH_FLOW."
    )
    period: FinancialPeriod = Field(..., description="Financial period represented.")
    base_concept_name: str = Field(
        ...,
        description="Base concept used for scaling (e.g. 'REVENUE' or 'TOTAL_ASSETS').",
    )
    base_value: Decimal | None = Field(..., description="Reported base value.")
    status: MetricStatus = Field(
        ..., description="Overall statement common-size status."
    )
    items: list[CommonSizeItem] = Field(
        default_factory=list, description="Line items scaled by base."
    )
    diagnostics: list[MetricDiagnostic] = Field(
        default_factory=list, description="Statement-level diagnostics."
    )
    provenance: MetricProvenance = Field(
        ..., description="Statement-level calculation provenance."
    )


class CommonSizeEngine:
    """
    Engine calculating common-size income statement, balance sheet, and cash flow statement.
    """

    METHODOLOGY_VERSION = "1.0.0"

    CANONICAL_IS_CONCEPTS = [
        CanonicalConcept.REVENUE,
        CanonicalConcept.COST_OF_REVENUE,
        CanonicalConcept.GROSS_PROFIT,
        CanonicalConcept.OPERATING_EXPENSES,
        CanonicalConcept.RESEARCH_AND_DEVELOPMENT,
        CanonicalConcept.SELLING_GENERAL_AND_ADMINISTRATIVE,
        CanonicalConcept.OPERATING_INCOME,
        CanonicalConcept.OTHER_INCOME_EXPENSE,
        CanonicalConcept.PRETAX_INCOME,
        CanonicalConcept.INCOME_TAX_EXPENSE,
        CanonicalConcept.NET_INCOME,
    ]

    CANONICAL_BS_CONCEPTS = [
        CanonicalConcept.CASH_AND_EQUIVALENTS,
        CanonicalConcept.SHORT_TERM_INVESTMENTS,
        CanonicalConcept.ACCOUNTS_RECEIVABLE,
        CanonicalConcept.INVENTORY,
        CanonicalConcept.CURRENT_ASSETS,
        CanonicalConcept.PROPERTY_PLANT_EQUIPMENT,
        CanonicalConcept.GOODWILL,
        CanonicalConcept.INTANGIBLE_ASSETS,
        CanonicalConcept.TOTAL_ASSETS,
        CanonicalConcept.ACCOUNTS_PAYABLE,
        CanonicalConcept.CURRENT_LIABILITIES,
        CanonicalConcept.LONG_TERM_DEBT,
        CanonicalConcept.TOTAL_LIABILITIES,
        CanonicalConcept.STOCKHOLDERS_EQUITY,
    ]

    @classmethod
    def calculate_common_size_income_statement(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> CommonSizeStatement:
        """
        Calculate Common-Size Income Statement: Line Item / Revenue * 100.
        """
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.REVENUE, period.period_key
        )

        all_facts: list[str] = [rev_fact.fact_id] if rev_fact else []
        if rev_fact is None:
            return CommonSizeStatement(
                statement_type=StatementType.INCOME_STATEMENT,
                period=period,
                base_concept_name="REVENUE",
                base_value=None,
                status=MetricStatus.UNAVAILABLE,
                items=[],
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Revenue fact is missing for common-size income statement.",
                        details={"concept": "REVENUE", "period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_COMMON_SIZE_IS",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        if rev_fact.value <= Decimal("0"):
            return CommonSizeStatement(
                statement_type=StatementType.INCOME_STATEMENT,
                period=period,
                base_concept_name="REVENUE",
                base_value=rev_fact.value,
                status=MetricStatus.UNAVAILABLE,
                items=[],
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_BASE_REVENUE,
                        message="Revenue is zero or negative; common-size income statement cannot be calculated.",
                        details={
                            "revenue": str(rev_fact.value),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_COMMON_SIZE_IS",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[rev_fact.fact_id],
                    source_concepts=["REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        base_val = rev_fact.value
        items: list[CommonSizeItem] = []

        for concept in cls.CANONICAL_IS_CONCEPTS:
            fact = fact_store.get_canonical_fact(
                StatementType.INCOME_STATEMENT, concept, period.period_key
            )
            if fact is not None:
                all_facts.append(fact.fact_id)
                pct = (fact.value / base_val) * Decimal("100")
                items.append(
                    CommonSizeItem(
                        concept_name=concept.value,
                        reported_value=fact.value,
                        common_size_percent=pct,
                        status=MetricStatus.VALID,
                        diagnostics=[],
                        provenance=MetricProvenance(
                            formula_id="FORMULA_COMMON_SIZE_IS_ITEM",
                            methodology_version=cls.METHODOLOGY_VERSION,
                            source_fact_ids=[fact.fact_id, rev_fact.fact_id],
                            source_concepts=[concept.value, "REVENUE"],
                            source_periods=[period.period_key],
                            methodology_notes=f"Scaled by Revenue ({base_val}) * 100.",
                        ),
                    )
                )

        return CommonSizeStatement(
            statement_type=StatementType.INCOME_STATEMENT,
            period=period,
            base_concept_name="REVENUE",
            base_value=base_val,
            status=MetricStatus.VALID,
            items=items,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_COMMON_SIZE_IS",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=list(dict.fromkeys(all_facts)),
                source_concepts=["REVENUE", *(i.concept_name for i in items)],
                source_periods=[period.period_key],
                methodology_notes="Common-size Income Statement: Line Item / Revenue * 100.",
            ),
        )

    @classmethod
    def calculate_common_size_balance_sheet(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> CommonSizeStatement:
        """
        Calculate Common-Size Balance Sheet: Line Item / Total Assets * 100.
        """
        asset_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.TOTAL_ASSETS,
            period.period_key,
        )

        all_facts: list[str] = [asset_fact.fact_id] if asset_fact else []
        if asset_fact is None:
            return CommonSizeStatement(
                statement_type=StatementType.BALANCE_SHEET,
                period=period,
                base_concept_name="TOTAL_ASSETS",
                base_value=None,
                status=MetricStatus.UNAVAILABLE,
                items=[],
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Total Assets fact is missing for common-size balance sheet.",
                        details={
                            "concept": "TOTAL_ASSETS",
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_COMMON_SIZE_BS",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["TOTAL_ASSETS"],
                    source_periods=[period.period_key],
                ),
            )

        if asset_fact.value <= Decimal("0"):
            return CommonSizeStatement(
                statement_type=StatementType.BALANCE_SHEET,
                period=period,
                base_concept_name="TOTAL_ASSETS",
                base_value=asset_fact.value,
                status=MetricStatus.UNAVAILABLE,
                items=[],
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_BASE_ASSETS,
                        message="Total Assets is zero or negative; common-size balance sheet cannot be calculated.",
                        details={
                            "total_assets": str(asset_fact.value),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_COMMON_SIZE_BS",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[asset_fact.fact_id],
                    source_concepts=["TOTAL_ASSETS"],
                    source_periods=[period.period_key],
                ),
            )

        base_val = asset_fact.value
        items: list[CommonSizeItem] = []

        for concept in cls.CANONICAL_BS_CONCEPTS:
            fact = fact_store.get_canonical_fact(
                StatementType.BALANCE_SHEET, concept, period.period_key
            )
            if fact is not None:
                all_facts.append(fact.fact_id)
                pct = (fact.value / base_val) * Decimal("100")
                items.append(
                    CommonSizeItem(
                        concept_name=concept.value,
                        reported_value=fact.value,
                        common_size_percent=pct,
                        status=MetricStatus.VALID,
                        diagnostics=[],
                        provenance=MetricProvenance(
                            formula_id="FORMULA_COMMON_SIZE_BS_ITEM",
                            methodology_version=cls.METHODOLOGY_VERSION,
                            source_fact_ids=[fact.fact_id, asset_fact.fact_id],
                            source_concepts=[concept.value, "TOTAL_ASSETS"],
                            source_periods=[period.period_key],
                            methodology_notes=f"Scaled by Total Assets ({base_val}) * 100.",
                        ),
                    )
                )

        return CommonSizeStatement(
            statement_type=StatementType.BALANCE_SHEET,
            period=period,
            base_concept_name="TOTAL_ASSETS",
            base_value=base_val,
            status=MetricStatus.VALID,
            items=items,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_COMMON_SIZE_BS",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=list(dict.fromkeys(all_facts)),
                source_concepts=["TOTAL_ASSETS", *(i.concept_name for i in items)],
                source_periods=[period.period_key],
                methodology_notes="Common-size Balance Sheet: Line Item / Total Assets * 100. Strictly point-in-time instant snapshot.",
            ),
        )

    @classmethod
    def calculate_common_size_cash_flow(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> CommonSizeStatement:
        """
        Calculate Common-Size Cash Flow Ratios scaled by Revenue:
          - CFO / Revenue * 100
          - CapEx / Revenue * 100 (preserving positive economic magnitude)
          - FCF / Revenue * 100 (where FCF = CFO - abs(CapEx))
        """
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.REVENUE, period.period_key
        )
        cfo_fact = fact_store.get_canonical_fact(
            StatementType.CASH_FLOW,
            CanonicalConcept.OPERATING_CASH_FLOW,
            period.period_key,
        )
        capex_fact = fact_store.get_canonical_fact(
            StatementType.CASH_FLOW,
            CanonicalConcept.CAPITAL_EXPENDITURES,
            period.period_key,
        )

        all_facts: list[str] = [rev_fact.fact_id] if rev_fact else []
        if rev_fact is None:
            return CommonSizeStatement(
                statement_type=StatementType.CASH_FLOW,
                period=period,
                base_concept_name="REVENUE",
                base_value=None,
                status=MetricStatus.UNAVAILABLE,
                items=[],
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Revenue fact is missing for common-size cash flow statement.",
                        details={"concept": "REVENUE", "period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_COMMON_SIZE_CF",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        if rev_fact.value <= Decimal("0"):
            return CommonSizeStatement(
                statement_type=StatementType.CASH_FLOW,
                period=period,
                base_concept_name="REVENUE",
                base_value=rev_fact.value,
                status=MetricStatus.UNAVAILABLE,
                items=[],
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_BASE_REVENUE,
                        message="Revenue is zero or negative; common-size cash flow statement cannot be calculated.",
                        details={
                            "revenue": str(rev_fact.value),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_COMMON_SIZE_CF",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[rev_fact.fact_id],
                    source_concepts=["REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        base_val = rev_fact.value
        items: list[CommonSizeItem] = []

        # 1. CFO
        if cfo_fact is not None:
            all_facts.append(cfo_fact.fact_id)
            cfo_pct = (cfo_fact.value / base_val) * Decimal("100")
            items.append(
                CommonSizeItem(
                    concept_name="OPERATING_CASH_FLOW",
                    reported_value=cfo_fact.value,
                    common_size_percent=cfo_pct,
                    status=MetricStatus.VALID,
                    diagnostics=[],
                    provenance=MetricProvenance(
                        formula_id="FORMULA_COMMON_SIZE_CFO",
                        methodology_version=cls.METHODOLOGY_VERSION,
                        source_fact_ids=[cfo_fact.fact_id, rev_fact.fact_id],
                        source_concepts=["OPERATING_CASH_FLOW", "REVENUE"],
                        source_periods=[period.period_key],
                        methodology_notes=f"CFO / Revenue ({base_val}) * 100.",
                    ),
                )
            )

        # 2. CapEx (Positive Economic Magnitude)
        capex_mag: Decimal | None = None
        if capex_fact is not None:
            all_facts.append(capex_fact.fact_id)
            capex_mag = abs(capex_fact.value)
            capex_pct = (capex_mag / base_val) * Decimal("100")
            items.append(
                CommonSizeItem(
                    concept_name="CAPITAL_EXPENDITURES",
                    reported_value=capex_mag,
                    common_size_percent=capex_pct,
                    status=MetricStatus.VALID,
                    diagnostics=[],
                    provenance=MetricProvenance(
                        formula_id="FORMULA_COMMON_SIZE_CAPEX",
                        methodology_version=cls.METHODOLOGY_VERSION,
                        source_fact_ids=[capex_fact.fact_id, rev_fact.fact_id],
                        source_concepts=["CAPITAL_EXPENDITURES", "REVENUE"],
                        source_periods=[period.period_key],
                        methodology_notes=f"CapEx positive magnitude ({capex_mag}) / Revenue ({base_val}) * 100.",
                    ),
                )
            )

        # 3. FCF (CFO - CapEx Magnitude)
        if cfo_fact is not None and capex_mag is not None:
            fcf_val = cfo_fact.value - capex_mag
            fcf_pct = (fcf_val / base_val) * Decimal("100")
            items.append(
                CommonSizeItem(
                    concept_name="FREE_CASH_FLOW",
                    reported_value=fcf_val,
                    common_size_percent=fcf_pct,
                    status=MetricStatus.VALID,
                    diagnostics=[],
                    provenance=MetricProvenance(
                        formula_id="FORMULA_COMMON_SIZE_FCF",
                        methodology_version=cls.METHODOLOGY_VERSION,
                        source_fact_ids=[
                            cfo_fact.fact_id,
                            capex_fact.fact_id,
                            rev_fact.fact_id,
                        ],
                        source_concepts=[
                            "OPERATING_CASH_FLOW",
                            "CAPITAL_EXPENDITURES",
                            "REVENUE",
                        ],
                        source_periods=[period.period_key],
                        methodology_notes=f"FCF ({fcf_val}) / Revenue ({base_val}) * 100.",
                    ),
                )
            )

        return CommonSizeStatement(
            statement_type=StatementType.CASH_FLOW,
            period=period,
            base_concept_name="REVENUE",
            base_value=base_val,
            status=MetricStatus.VALID,
            items=items,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_COMMON_SIZE_CF",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=list(dict.fromkeys(all_facts)),
                source_concepts=["REVENUE", *(i.concept_name for i in items)],
                source_periods=[period.period_key],
                methodology_notes="Common-size Cash Flow: CFO, CapEx (positive magnitude), and FCF scaled by Revenue.",
            ),
        )

    @classmethod
    def calculate_common_size_ttm_income_statement(
        cls,
        window: TTMWindow,
        fact_store: MultiPeriodFactStore,
    ) -> CommonSizeStatement:
        """
        Calculate Common-Size TTM Income Statement:
        Durations are aggregated across the 4 quarters of the TTM window.
        """
        ttm_rev_result = TTMEngine.calculate_ttm_revenue(window, fact_store)
        if ttm_rev_result.status != MetricStatus.VALID or ttm_rev_result.value is None:
            return CommonSizeStatement(
                statement_type=StatementType.INCOME_STATEMENT,
                period=window.ttm_period,
                base_concept_name="REVENUE",
                base_value=None,
                status=MetricStatus.UNAVAILABLE,
                items=[],
                diagnostics=list(ttm_rev_result.diagnostics),
                provenance=MetricProvenance(
                    formula_id="FORMULA_COMMON_SIZE_IS_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                    methodology_notes="TTM Revenue unavailable for common-size income statement scaling.",
                ),
            )

        if ttm_rev_result.value <= Decimal("0"):
            return CommonSizeStatement(
                statement_type=StatementType.INCOME_STATEMENT,
                period=window.ttm_period,
                base_concept_name="REVENUE",
                base_value=ttm_rev_result.value,
                status=MetricStatus.UNAVAILABLE,
                items=[],
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_BASE_REVENUE,
                        message="TTM Revenue is zero or negative; common-size income statement cannot be calculated.",
                        details={"revenue": str(ttm_rev_result.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_COMMON_SIZE_IS_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=list(ttm_rev_result.provenance.source_fact_ids),
                    source_concepts=["REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
            )

        base_val = ttm_rev_result.value
        items: list[CommonSizeItem] = []
        all_fact_ids: list[str] = list(ttm_rev_result.provenance.source_fact_ids)

        for concept in cls.CANONICAL_IS_CONCEPTS:
            agg_result = TTMEngine.aggregate_duration_fact(
                window=window,
                statement_type=StatementType.INCOME_STATEMENT,
                concept=concept,
                metric_id=FundamentalMetricId.REVENUE,
                category=MetricCategory.GROWTH,
                fact_store=fact_store,
                formula_id=f"FORMULA_TTM_{concept.value}",
            )
            if agg_result.status == MetricStatus.VALID and agg_result.value is not None:
                all_fact_ids.extend(agg_result.provenance.source_fact_ids)
                pct = (agg_result.value / base_val) * Decimal("100")
                items.append(
                    CommonSizeItem(
                        concept_name=concept.value,
                        reported_value=agg_result.value,
                        common_size_percent=pct,
                        status=MetricStatus.VALID,
                        diagnostics=[],
                        provenance=MetricProvenance(
                            formula_id="FORMULA_COMMON_SIZE_IS_TTM_ITEM",
                            methodology_version=cls.METHODOLOGY_VERSION,
                            source_fact_ids=list(
                                dict.fromkeys(
                                    [
                                        *agg_result.provenance.source_fact_ids,
                                        *ttm_rev_result.provenance.source_fact_ids,
                                    ]
                                )
                            ),
                            source_concepts=[concept.value, "REVENUE"],
                            source_periods=[q.period_key for q in window.quarters],
                            methodology_notes=f"4-quarter TTM sum scaled by TTM Revenue ({base_val}) * 100.",
                        ),
                    )
                )

        return CommonSizeStatement(
            statement_type=StatementType.INCOME_STATEMENT,
            period=window.ttm_period,
            base_concept_name="REVENUE",
            base_value=base_val,
            status=MetricStatus.VALID,
            items=items,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_COMMON_SIZE_IS_TTM",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=list(dict.fromkeys(all_fact_ids)),
                source_concepts=["REVENUE", *(i.concept_name for i in items)],
                source_periods=[q.period_key for q in window.quarters],
                methodology_notes="Common-size TTM Income Statement: 4-quarter duration facts scaled by TTM Revenue.",
            ),
        )

    @classmethod
    def calculate_common_size_ttm_cash_flow(
        cls,
        window: TTMWindow,
        fact_store: MultiPeriodFactStore,
    ) -> CommonSizeStatement:
        """
        Calculate Common-Size TTM Cash Flow Statement:
        Durations are aggregated across the 4 quarters of the TTM window.
        """
        ttm_rev_result = TTMEngine.calculate_ttm_revenue(window, fact_store)
        ttm_cfo_result = TTMEngine.calculate_ttm_cfo(window, fact_store)
        ttm_capex_result = TTMEngine.calculate_ttm_capex(window, fact_store)
        ttm_fcf_result = TTMEngine.calculate_ttm_fcf(window, fact_store)

        if ttm_rev_result.status != MetricStatus.VALID or ttm_rev_result.value is None:
            return CommonSizeStatement(
                statement_type=StatementType.CASH_FLOW,
                period=window.ttm_period,
                base_concept_name="REVENUE",
                base_value=None,
                status=MetricStatus.UNAVAILABLE,
                items=[],
                diagnostics=list(ttm_rev_result.diagnostics),
                provenance=MetricProvenance(
                    formula_id="FORMULA_COMMON_SIZE_CF_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
            )

        if ttm_rev_result.value <= Decimal("0"):
            return CommonSizeStatement(
                statement_type=StatementType.CASH_FLOW,
                period=window.ttm_period,
                base_concept_name="REVENUE",
                base_value=ttm_rev_result.value,
                status=MetricStatus.UNAVAILABLE,
                items=[],
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_BASE_REVENUE,
                        message="TTM Revenue is zero or negative; common-size cash flow cannot be calculated.",
                        details={"revenue": str(ttm_rev_result.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_COMMON_SIZE_CF_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=list(ttm_rev_result.provenance.source_fact_ids),
                    source_concepts=["REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
            )

        base_val = ttm_rev_result.value
        items: list[CommonSizeItem] = []
        all_fact_ids: list[str] = list(ttm_rev_result.provenance.source_fact_ids)

        if (
            ttm_cfo_result.status == MetricStatus.VALID
            and ttm_cfo_result.value is not None
        ):
            all_fact_ids.extend(ttm_cfo_result.provenance.source_fact_ids)
            cfo_pct = (ttm_cfo_result.value / base_val) * Decimal("100")
            items.append(
                CommonSizeItem(
                    concept_name="OPERATING_CASH_FLOW",
                    reported_value=ttm_cfo_result.value,
                    common_size_percent=cfo_pct,
                    status=MetricStatus.VALID,
                    diagnostics=[],
                    provenance=MetricProvenance(
                        formula_id="FORMULA_COMMON_SIZE_CFO_TTM",
                        methodology_version=cls.METHODOLOGY_VERSION,
                        source_fact_ids=list(
                            dict.fromkeys(
                                [
                                    *ttm_cfo_result.provenance.source_fact_ids,
                                    *ttm_rev_result.provenance.source_fact_ids,
                                ]
                            )
                        ),
                        source_concepts=["OPERATING_CASH_FLOW", "REVENUE"],
                        source_periods=[q.period_key for q in window.quarters],
                    ),
                )
            )

        if (
            ttm_capex_result.status == MetricStatus.VALID
            and ttm_capex_result.value is not None
        ):
            all_fact_ids.extend(ttm_capex_result.provenance.source_fact_ids)
            capex_pct = (ttm_capex_result.value / base_val) * Decimal("100")
            items.append(
                CommonSizeItem(
                    concept_name="CAPITAL_EXPENDITURES",
                    reported_value=ttm_capex_result.value,
                    common_size_percent=capex_pct,
                    status=MetricStatus.VALID,
                    diagnostics=[],
                    provenance=MetricProvenance(
                        formula_id="FORMULA_COMMON_SIZE_CAPEX_TTM",
                        methodology_version=cls.METHODOLOGY_VERSION,
                        source_fact_ids=list(
                            dict.fromkeys(
                                [
                                    *ttm_capex_result.provenance.source_fact_ids,
                                    *ttm_rev_result.provenance.source_fact_ids,
                                ]
                            )
                        ),
                        source_concepts=["CAPITAL_EXPENDITURES", "REVENUE"],
                        source_periods=[q.period_key for q in window.quarters],
                        methodology_notes="TTM CapEx preserves positive economic magnitude.",
                    ),
                )
            )

        if (
            ttm_fcf_result.status == MetricStatus.VALID
            and ttm_fcf_result.value is not None
        ):
            all_fact_ids.extend(ttm_fcf_result.provenance.source_fact_ids)
            fcf_pct = (ttm_fcf_result.value / base_val) * Decimal("100")
            items.append(
                CommonSizeItem(
                    concept_name="FREE_CASH_FLOW",
                    reported_value=ttm_fcf_result.value,
                    common_size_percent=fcf_pct,
                    status=MetricStatus.VALID,
                    diagnostics=[],
                    provenance=MetricProvenance(
                        formula_id="FORMULA_COMMON_SIZE_FCF_TTM",
                        methodology_version=cls.METHODOLOGY_VERSION,
                        source_fact_ids=list(
                            dict.fromkeys(
                                [
                                    *ttm_fcf_result.provenance.source_fact_ids,
                                    *ttm_rev_result.provenance.source_fact_ids,
                                ]
                            )
                        ),
                        source_concepts=["FREE_CASH_FLOW", "REVENUE"],
                        source_periods=[q.period_key for q in window.quarters],
                    ),
                )
            )

        return CommonSizeStatement(
            statement_type=StatementType.CASH_FLOW,
            period=window.ttm_period,
            base_concept_name="REVENUE",
            base_value=base_val,
            status=MetricStatus.VALID,
            items=items,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_COMMON_SIZE_CF_TTM",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=list(dict.fromkeys(all_fact_ids)),
                source_concepts=["REVENUE", *(i.concept_name for i in items)],
                source_periods=[q.period_key for q in window.quarters],
                methodology_notes="Common-size TTM Cash Flow Statement: 4-quarter duration facts scaled by TTM Revenue.",
            ),
        )
