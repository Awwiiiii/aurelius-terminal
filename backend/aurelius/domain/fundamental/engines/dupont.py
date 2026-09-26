"""
aurelius.domain.fundamental.engines.dupont
==========================================
Pure calculation engine for 3-Step and 5-Step DuPont ROE decomposition
and mathematical reconciliation.

Formulas:
  3-Step DuPont:
    ROE = Net Profit Margin * Asset Turnover * Equity Multiplier
    Where:
      Net Profit Margin = Net Income / Revenue
      Asset Turnover = Revenue / Average Total Assets
      Equity Multiplier = Average Total Assets / Average Stockholders' Equity

  5-Step DuPont:
    ROE = Tax Burden * Interest Burden * EBIT Margin * Asset Turnover * Equity Multiplier
    Where:
      Tax Burden = Net Income / EBT
      Interest Burden = EBT / EBIT
      EBIT Margin = EBIT / Revenue  (strictly standardized terminology)
      Asset Turnover = Revenue / Average Total Assets
      Equity Multiplier = Average Total Assets / Average Stockholders' Equity

Zero and Negative Rules:
  - EBT = 0: Tax Burden unavailable; 5-step DuPont unavailable (ZERO_PRETAX_INCOME).
  - EBIT = 0: Interest Burden unavailable; 5-step DuPont unavailable (ZERO_OPERATING_INCOME).
  - EBT < 0: 5-step marked DISTORTED (DISTORTED_PRETAX_EARNINGS).
  - EBIT < 0: EBIT Margin may remain valid; 5-step marked DISTORTED (DISTORTED_OPERATING_EARNINGS).
  - Average Total Assets <= 0: Asset Turnover unavailable; 3-step & 5-step unavailable (NON_POSITIVE_AVERAGE_ASSETS).
  - Average Equity <= 0: Equity Multiplier & direct ROE unavailable; 3-step & 5-step unavailable (NON_POSITIVE_AVERAGE_EQUITY).
  - Revenue <= 0: Revenue-dependent factors unavailable (NON_POSITIVE_REVENUE).
  - No denominator may EVER be transformed using abs().

Reconciliation:
  Direct ROE = Net Income / Average Stockholders' Equity.
  Tolerance: <= 0.0001
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialFact,
    FinancialPeriod,
    StatementType,
    Unit,
)
from aurelius.domain.fundamental.engines.profitability import ProfitabilityEngine
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)
from aurelius.domain.fundamental.models import (
    MetricDiagnostic,
    MetricProvenance,
    MetricResult,
)
from aurelius.domain.fundamental.period_matching import (
    MultiPeriodFactStore,
    calculate_two_point_average,
)
from aurelius.domain.fundamental.ttm import TTMEngine, TTMWindow


class DuPont3StepDecomposition(BaseModel):
    """
    3-Step DuPont decomposition factors and reconstructed ROE.
    """

    model_config = ConfigDict(frozen=True)

    net_profit_margin: MetricResult
    asset_turnover: MetricResult
    equity_multiplier: MetricResult
    reconstructed_roe: MetricResult
    direct_roe: MetricResult
    is_reconciled: bool
    reconciliation_discrepancy: Decimal | None = None


class DuPont5StepDecomposition(BaseModel):
    """
    5-Step DuPont decomposition factors and reconstructed ROE.
    """

    model_config = ConfigDict(frozen=True)

    tax_burden: MetricResult
    interest_burden: MetricResult
    ebit_margin: MetricResult
    asset_turnover: MetricResult
    equity_multiplier: MetricResult
    reconstructed_roe: MetricResult
    direct_roe: MetricResult
    is_reconciled: bool
    reconciliation_discrepancy: Decimal | None = None


class DuPontEngine:
    """
    Engine calculating 3-step and 5-step DuPont decomposition and reconciliation.
    """

    METHODOLOGY_VERSION = "1.0.0"
    RECONCILIATION_TOLERANCE = Decimal("0.0001")

    @classmethod
    def calculate_equity_multiplier(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Equity Multiplier = Average Total Assets / Average Stockholders' Equity.
        """
        avg_assets, a_diag, a_used_fb, asset_facts = calculate_two_point_average(
            CanonicalConcept.TOTAL_ASSETS,
            current_period,
            prior_period,
            fact_store,
            allow_point_in_time_fallback,
        )

        avg_equity, e_diag, e_used_fb, equity_facts = calculate_two_point_average(
            CanonicalConcept.STOCKHOLDERS_EQUITY,
            current_period,
            prior_period,
            fact_store,
            allow_point_in_time_fallback,
        )

        all_fact_ids = [
            *(f.fact_id for f in asset_facts),
            *(f.fact_id for f in equity_facts),
        ]
        all_concepts = ["TOTAL_ASSETS", "STOCKHOLDERS_EQUITY"]
        all_periods = list(
            dict.fromkeys(
                [
                    current_period.period_key,
                    *(f.period.period_key for f in asset_facts),
                    *(f.period.period_key for f in equity_facts),
                ]
            )
        )

        all_diags: list[MetricDiagnostic] = []
        if a_diag is not None:
            all_diags.append(a_diag)
        if e_diag is not None:
            all_diags.append(e_diag)

        # Missing input checks
        if avg_assets is None or (a_diag is not None and not a_used_fb):
            return MetricResult(
                metric_id=FundamentalMetricId.EQUITY_MULTIPLIER,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=all_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_EQUITY_MULTIPLIER",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="Average Total Assets is unavailable for Equity Multiplier.",
                ),
            )

        if avg_equity is None or (e_diag is not None and not e_used_fb):
            return MetricResult(
                metric_id=FundamentalMetricId.EQUITY_MULTIPLIER,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=all_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_EQUITY_MULTIPLIER",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="Average Stockholders' Equity is unavailable for Equity Multiplier.",
                ),
            )

        # Non-positive Average Assets
        if avg_assets <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.EQUITY_MULTIPLIER,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_AVERAGE_ASSETS,
                        message="Average Total Assets is zero or negative; Equity Multiplier is unavailable.",
                        details={
                            "average_assets": str(avg_assets),
                            "period": current_period.period_key,
                        },
                    ),
                    *all_diags,
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EQUITY_MULTIPLIER",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                ),
            )

        # Non-positive Average Equity
        if avg_equity <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.EQUITY_MULTIPLIER,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_AVERAGE_EQUITY,
                        message="Average Stockholders' Equity is zero or negative; Equity Multiplier is unavailable.",
                        details={
                            "average_equity": str(avg_equity),
                            "period": current_period.period_key,
                        },
                    ),
                    *all_diags,
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EQUITY_MULTIPLIER",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="No abs() transformation on negative average equity.",
                ),
            )

        em_val = avg_assets / avg_equity
        used_fb = a_used_fb or e_used_fb
        notes = (
            "Ending point-in-time values used under fallback mode."
            if used_fb
            else "Two-point average balance sheet assets and equity used."
        )

        return MetricResult(
            metric_id=FundamentalMetricId.EQUITY_MULTIPLIER,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=em_val,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=all_diags,
            provenance=MetricProvenance(
                formula_id="FORMULA_EQUITY_MULTIPLIER_POINT_IN_TIME"
                if used_fb
                else "FORMULA_EQUITY_MULTIPLIER_2PT_AVG",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_fact_ids,
                source_concepts=all_concepts,
                source_periods=all_periods,
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_3step_dupont(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> DuPont3StepDecomposition:
        """
        Compute 3-Step DuPont ROE:
          ROE = Net Profit Margin * Asset Turnover * Equity Multiplier.
        """
        npm = ProfitabilityEngine.calculate_net_profit_margin(
            current_period, fact_store
        )

        # Calculate Asset Turnover
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.REVENUE,
            current_period.period_key,
        )
        avg_assets, a_diag, a_used_fb, asset_facts = calculate_two_point_average(
            CanonicalConcept.TOTAL_ASSETS,
            current_period,
            prior_period,
            fact_store,
            allow_point_in_time_fallback,
        )

        all_at_facts = [
            *([rev_fact.fact_id] if rev_fact else []),
            *(f.fact_id for f in asset_facts),
        ]
        all_at_periods = list(
            dict.fromkeys(
                [current_period.period_key, *(f.period.period_key for f in asset_facts)]
            )
        )

        # Asset turnover evaluation
        if (
            rev_fact is None
            or avg_assets is None
            or (a_diag is not None and not a_used_fb)
        ):
            at_result = MetricResult(
                metric_id=FundamentalMetricId.ASSET_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[a_diag]
                if a_diag
                else [
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Missing inputs for Asset Turnover.",
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ASSET_TURNOVER",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_at_facts,
                    source_concepts=["REVENUE", "TOTAL_ASSETS"],
                    source_periods=all_at_periods,
                ),
            )
        elif rev_fact.value <= Decimal("0"):
            at_result = MetricResult(
                metric_id=FundamentalMetricId.ASSET_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_REVENUE,
                        message="Revenue is zero or negative; Asset Turnover is unavailable.",
                        details={"revenue": str(rev_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ASSET_TURNOVER",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_at_facts,
                    source_concepts=["REVENUE", "TOTAL_ASSETS"],
                    source_periods=all_at_periods,
                ),
            )
        elif avg_assets <= Decimal("0"):
            at_result = MetricResult(
                metric_id=FundamentalMetricId.ASSET_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_AVERAGE_ASSETS,
                        message="Average Total Assets is zero or negative; Asset Turnover is unavailable.",
                        details={"average_assets": str(avg_assets)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ASSET_TURNOVER",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_at_facts,
                    source_concepts=["REVENUE", "TOTAL_ASSETS"],
                    source_periods=all_at_periods,
                ),
            )
        else:
            at_val = rev_fact.value / avg_assets
            at_result = MetricResult(
                metric_id=FundamentalMetricId.ASSET_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.VALID,
                value=at_val,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[a_diag] if a_diag and a_used_fb else [],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ASSET_TURNOVER_POINT_IN_TIME"
                    if a_used_fb
                    else "FORMULA_ASSET_TURNOVER_2PT_AVG",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_at_facts,
                    source_concepts=["REVENUE", "TOTAL_ASSETS"],
                    source_periods=all_at_periods,
                ),
            )

        # Equity Multiplier
        em = cls.calculate_equity_multiplier(
            current_period, prior_period, fact_store, allow_point_in_time_fallback
        )

        # Direct ROE
        direct_roe = ProfitabilityEngine.calculate_roe(
            current_period, prior_period, fact_store, allow_point_in_time_fallback
        )

        all_provenance_facts = list(
            dict.fromkeys(
                [
                    *npm.provenance.source_fact_ids,
                    *at_result.provenance.source_fact_ids,
                    *em.provenance.source_fact_ids,
                ]
            )
        )
        all_provenance_concepts = list(
            dict.fromkeys(
                [
                    *npm.provenance.source_concepts,
                    *at_result.provenance.source_concepts,
                    *em.provenance.source_concepts,
                ]
            )
        )
        all_provenance_periods = list(
            dict.fromkeys(
                [
                    *npm.provenance.source_periods,
                    *at_result.provenance.source_periods,
                    *em.provenance.source_periods,
                ]
            )
        )

        # Check component statuses
        components_valid = (
            npm.status == MetricStatus.VALID
            and at_result.status == MetricStatus.VALID
            and em.status == MetricStatus.VALID
            and npm.value is not None
            and at_result.value is not None
            and em.value is not None
        )

        if not components_valid:
            # Aggregate diagnostics
            diags: list[MetricDiagnostic] = []
            for m in (npm, at_result, em):
                if m.status != MetricStatus.VALID:
                    diags.extend(m.diagnostics)

            recon_roe = MetricResult(
                metric_id=FundamentalMetricId.DUPONT_ROE_3STEP,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_DUPONT_ROE_3STEP",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_provenance_facts,
                    source_concepts=all_provenance_concepts,
                    source_periods=all_provenance_periods,
                    methodology_notes="3-Step DuPont ROE unavailable due to uncomputable factor(s).",
                ),
            )
            return DuPont3StepDecomposition(
                net_profit_margin=npm,
                asset_turnover=at_result,
                equity_multiplier=em,
                reconstructed_roe=recon_roe,
                direct_roe=direct_roe,
                is_reconciled=False,
                reconciliation_discrepancy=None,
            )

        reconstructed_val = npm.value * at_result.value * em.value
        recon_roe = MetricResult(
            metric_id=FundamentalMetricId.DUPONT_ROE_3STEP,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=reconstructed_val,
            unit=Unit.PERCENT,
            currency=None,
            period=current_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_DUPONT_ROE_3STEP",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_provenance_facts,
                source_concepts=all_provenance_concepts,
                source_periods=all_provenance_periods,
                methodology_notes="ROE = Net Profit Margin * Asset Turnover * Equity Multiplier.",
            ),
        )

        # Reconciliation against direct ROE
        is_reconciled = False
        discrepancy = None
        if direct_roe.status == MetricStatus.VALID and direct_roe.value is not None:
            discrepancy = abs(direct_roe.value - reconstructed_val)
            is_reconciled = discrepancy <= cls.RECONCILIATION_TOLERANCE

        return DuPont3StepDecomposition(
            net_profit_margin=npm,
            asset_turnover=at_result,
            equity_multiplier=em,
            reconstructed_roe=recon_roe,
            direct_roe=direct_roe,
            is_reconciled=is_reconciled,
            reconciliation_discrepancy=discrepancy,
        )

    @classmethod
    def calculate_5step_dupont(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> DuPont5StepDecomposition:
        """
        Compute 5-Step DuPont ROE:
          ROE = Tax Burden * Interest Burden * EBIT Margin * Asset Turnover * Equity Multiplier.

        Rules:
          - Tax Burden = Net Income / EBT.
              * EBT = 0 -> UNAVAILABLE (ZERO_PRETAX_INCOME).
              * EBT < 0 -> DISTORTED (DISTORTED_PRETAX_EARNINGS).
          - Interest Burden = EBT / EBIT.
              * EBIT = 0 -> UNAVAILABLE (ZERO_OPERATING_INCOME).
              * EBIT < 0 -> DISTORTED (DISTORTED_OPERATING_EARNINGS).
          - EBIT Margin = EBIT / Revenue. (standardized name)
              * Revenue <= 0 -> UNAVAILABLE (NON_POSITIVE_REVENUE).
          - Asset Turnover & Equity Multiplier: reused from standard logic.
          - If EBT < 0 or EBIT < 0: 5-step decomposition is marked DISTORTED/UNAVAILABLE.
        """
        ni_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.NET_INCOME,
            current_period.period_key,
        )
        ebt_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.PRETAX_INCOME,
            current_period.period_key,
        )
        ebit_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.OPERATING_INCOME,
            current_period.period_key,
        )
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.REVENUE,
            current_period.period_key,
        )

        # 1. Tax Burden = NI / EBT
        tb_facts = [
            *([ni_fact.fact_id] if ni_fact else []),
            *([ebt_fact.fact_id] if ebt_fact else []),
        ]
        if ni_fact is None or ebt_fact is None:
            tax_burden = MetricResult(
                metric_id=FundamentalMetricId.TAX_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Missing Net Income or Pretax Income for Tax Burden.",
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TAX_BURDEN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=tb_facts,
                    source_concepts=["NET_INCOME", "PRETAX_INCOME"],
                    source_periods=[current_period.period_key],
                ),
            )
        elif ebt_fact.value == Decimal("0"):
            tax_burden = MetricResult(
                metric_id=FundamentalMetricId.TAX_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_PRETAX_INCOME,
                        message="Pretax Income (EBT) is zero; Tax Burden is undefined.",
                        details={"ebt": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TAX_BURDEN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=tb_facts,
                    source_concepts=["NET_INCOME", "PRETAX_INCOME"],
                    source_periods=[current_period.period_key],
                ),
            )
        elif ebt_fact.value < Decimal("0"):
            # Distorted
            tb_val = ni_fact.value / ebt_fact.value
            tax_burden = MetricResult(
                metric_id=FundamentalMetricId.TAX_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.DISTORTED,
                value=tb_val,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.DISTORTED_PRETAX_EARNINGS,
                        message="Pretax Income (EBT) is negative; Tax Burden ratio is economically distorted.",
                        details={"ebt": str(ebt_fact.value), "ni": str(ni_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TAX_BURDEN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=tb_facts,
                    source_concepts=["NET_INCOME", "PRETAX_INCOME"],
                    source_periods=[current_period.period_key],
                    methodology_notes="Negative EBT produces an economically distorted Tax Burden ratio.",
                ),
            )
        else:
            tax_burden = MetricResult(
                metric_id=FundamentalMetricId.TAX_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.VALID,
                value=ni_fact.value / ebt_fact.value,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TAX_BURDEN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=tb_facts,
                    source_concepts=["NET_INCOME", "PRETAX_INCOME"],
                    source_periods=[current_period.period_key],
                    methodology_notes="Tax Burden = Net Income / EBT.",
                ),
            )

        # 2. Interest Burden = EBT / EBIT
        ib_facts = [
            *([ebt_fact.fact_id] if ebt_fact else []),
            *([ebit_fact.fact_id] if ebit_fact else []),
        ]
        if ebt_fact is None or ebit_fact is None:
            interest_burden = MetricResult(
                metric_id=FundamentalMetricId.INTEREST_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Missing Pretax Income or Operating Income for Interest Burden.",
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_INTEREST_BURDEN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=ib_facts,
                    source_concepts=["PRETAX_INCOME", "OPERATING_INCOME"],
                    source_periods=[current_period.period_key],
                ),
            )
        elif ebit_fact.value == Decimal("0"):
            interest_burden = MetricResult(
                metric_id=FundamentalMetricId.INTEREST_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_OPERATING_INCOME,
                        message="Operating Income (EBIT) is zero; Interest Burden is undefined.",
                        details={"ebit": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_INTEREST_BURDEN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=ib_facts,
                    source_concepts=["PRETAX_INCOME", "OPERATING_INCOME"],
                    source_periods=[current_period.period_key],
                ),
            )
        elif ebit_fact.value < Decimal("0"):
            ib_val = ebt_fact.value / ebit_fact.value
            interest_burden = MetricResult(
                metric_id=FundamentalMetricId.INTEREST_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.DISTORTED,
                value=ib_val,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.DISTORTED_OPERATING_EARNINGS,
                        message="Operating Income (EBIT) is negative; Interest Burden ratio is economically distorted.",
                        details={
                            "ebit": str(ebit_fact.value),
                            "ebt": str(ebt_fact.value),
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_INTEREST_BURDEN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=ib_facts,
                    source_concepts=["PRETAX_INCOME", "OPERATING_INCOME"],
                    source_periods=[current_period.period_key],
                    methodology_notes="Negative EBIT produces an economically distorted Interest Burden ratio.",
                ),
            )
        else:
            interest_burden = MetricResult(
                metric_id=FundamentalMetricId.INTEREST_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.VALID,
                value=ebt_fact.value / ebit_fact.value,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[],
                provenance=MetricProvenance(
                    formula_id="FORMULA_INTEREST_BURDEN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=ib_facts,
                    source_concepts=["PRETAX_INCOME", "OPERATING_INCOME"],
                    source_periods=[current_period.period_key],
                    methodology_notes="Interest Burden = EBT / EBIT.",
                ),
            )

        # 3. EBIT Margin = EBIT / Revenue (standardized naming)
        em_facts = [
            *([ebit_fact.fact_id] if ebit_fact else []),
            *([rev_fact.fact_id] if rev_fact else []),
        ]
        if ebit_fact is None or rev_fact is None:
            ebit_margin = MetricResult(
                metric_id=FundamentalMetricId.EBIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Missing Operating Income or Revenue for EBIT Margin.",
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EBIT_MARGIN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=em_facts,
                    source_concepts=["OPERATING_INCOME", "REVENUE"],
                    source_periods=[current_period.period_key],
                ),
            )
        elif rev_fact.value <= Decimal("0"):
            ebit_margin = MetricResult(
                metric_id=FundamentalMetricId.EBIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_REVENUE,
                        message="Revenue is zero or negative; EBIT Margin is unavailable.",
                        details={"revenue": str(rev_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EBIT_MARGIN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=em_facts,
                    source_concepts=["OPERATING_INCOME", "REVENUE"],
                    source_periods=[current_period.period_key],
                ),
            )
        else:
            em_val = ebit_fact.value / rev_fact.value
            em_diags = []
            if ebit_fact.value < Decimal("0"):
                em_diags.append(
                    MetricDiagnostic(
                        code=DiagnosticCode.NEGATIVE_EBIT_WARNING,
                        message="Operating Income (EBIT) is negative; EBIT Margin is negative.",
                        details={"ebit": str(ebit_fact.value)},
                    )
                )
            ebit_margin = MetricResult(
                metric_id=FundamentalMetricId.EBIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.VALID,
                value=em_val,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=em_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_EBIT_MARGIN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=em_facts,
                    source_concepts=["OPERATING_INCOME", "REVENUE"],
                    source_periods=[current_period.period_key],
                    methodology_notes="EBIT Margin = EBIT / Revenue.",
                ),
            )

        # 4 & 5: Asset Turnover and Equity Multiplier from 3-step
        decomp3 = cls.calculate_3step_dupont(
            current_period, prior_period, fact_store, allow_point_in_time_fallback
        )
        asset_turnover = decomp3.asset_turnover
        equity_multiplier = decomp3.equity_multiplier
        direct_roe = decomp3.direct_roe

        all_provenance_facts = list(
            dict.fromkeys(
                [
                    *tax_burden.provenance.source_fact_ids,
                    *interest_burden.provenance.source_fact_ids,
                    *ebit_margin.provenance.source_fact_ids,
                    *asset_turnover.provenance.source_fact_ids,
                    *equity_multiplier.provenance.source_fact_ids,
                ]
            )
        )
        all_provenance_concepts = list(
            dict.fromkeys(
                [
                    *tax_burden.provenance.source_concepts,
                    *interest_burden.provenance.source_concepts,
                    *ebit_margin.provenance.source_concepts,
                    *asset_turnover.provenance.source_concepts,
                    *equity_multiplier.provenance.source_concepts,
                ]
            )
        )
        all_provenance_periods = list(
            dict.fromkeys(
                [
                    *tax_burden.provenance.source_periods,
                    *interest_burden.provenance.source_periods,
                    *ebit_margin.provenance.source_periods,
                    *asset_turnover.provenance.source_periods,
                    *equity_multiplier.provenance.source_periods,
                ]
            )
        )

        # Collect diagnostics across factors
        all_diags: list[MetricDiagnostic] = []
        for m in (
            tax_burden,
            interest_burden,
            ebit_margin,
            asset_turnover,
            equity_multiplier,
        ):
            if m.status != MetricStatus.VALID:
                all_diags.extend(m.diagnostics)

        # Distortion rule: If EBT < 0 or EBIT < 0 -> mark 5-step decomposition as DISTORTED
        is_distorted = (
            tax_burden.status == MetricStatus.DISTORTED
            or interest_burden.status == MetricStatus.DISTORTED
        )
        is_unavailable = any(
            m.status == MetricStatus.UNAVAILABLE
            for m in (
                tax_burden,
                interest_burden,
                ebit_margin,
                asset_turnover,
                equity_multiplier,
            )
        )

        if is_unavailable:
            recon_roe = MetricResult(
                metric_id=FundamentalMetricId.DUPONT_ROE_5STEP,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=all_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_DUPONT_ROE_5STEP",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_provenance_facts,
                    source_concepts=all_provenance_concepts,
                    source_periods=all_provenance_periods,
                    methodology_notes="5-Step DuPont ROE unavailable due to uncomputable factor(s).",
                ),
            )
            return DuPont5StepDecomposition(
                tax_burden=tax_burden,
                interest_burden=interest_burden,
                ebit_margin=ebit_margin,
                asset_turnover=asset_turnover,
                equity_multiplier=equity_multiplier,
                reconstructed_roe=recon_roe,
                direct_roe=direct_roe,
                is_reconciled=False,
                reconciliation_discrepancy=None,
            )

        if is_distorted:
            recon_roe = MetricResult(
                metric_id=FundamentalMetricId.DUPONT_ROE_5STEP,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=all_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_DUPONT_ROE_5STEP",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_provenance_facts,
                    source_concepts=all_provenance_concepts,
                    source_periods=all_provenance_periods,
                    methodology_notes="5-Step DuPont decomposition is economically distorted due to negative pre-tax or operating income.",
                ),
            )
            return DuPont5StepDecomposition(
                tax_burden=tax_burden,
                interest_burden=interest_burden,
                ebit_margin=ebit_margin,
                asset_turnover=asset_turnover,
                equity_multiplier=equity_multiplier,
                reconstructed_roe=recon_roe,
                direct_roe=direct_roe,
                is_reconciled=False,
                reconciliation_discrepancy=None,
            )

        # All 5 factors valid
        recon_val = (
            tax_burden.value
            * interest_burden.value
            * ebit_margin.value
            * asset_turnover.value
            * equity_multiplier.value
        )
        recon_roe = MetricResult(
            metric_id=FundamentalMetricId.DUPONT_ROE_5STEP,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=recon_val,
            unit=Unit.PERCENT,
            currency=None,
            period=current_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_DUPONT_ROE_5STEP",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_provenance_facts,
                source_concepts=all_provenance_concepts,
                source_periods=all_provenance_periods,
                methodology_notes="ROE = Tax Burden * Interest Burden * EBIT Margin * Asset Turnover * Equity Multiplier.",
            ),
        )

        is_reconciled = False
        discrepancy = None
        if direct_roe.status == MetricStatus.VALID and direct_roe.value is not None:
            discrepancy = abs(direct_roe.value - recon_val)
            is_reconciled = discrepancy <= cls.RECONCILIATION_TOLERANCE

        return DuPont5StepDecomposition(
            tax_burden=tax_burden,
            interest_burden=interest_burden,
            ebit_margin=ebit_margin,
            asset_turnover=asset_turnover,
            equity_multiplier=equity_multiplier,
            reconstructed_roe=recon_roe,
            direct_roe=direct_roe,
            is_reconciled=is_reconciled,
            reconciliation_discrepancy=discrepancy,
        )

    @classmethod
    def calculate_3step_dupont_ttm(
        cls,
        window: TTMWindow,
        prior_anchor: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> DuPont3StepDecomposition:
        """
        Calculate 3-Step DuPont decomposition for a 4-quarter TTM window.
        Uses 4-quarter duration flows and 2-point balance sheet averages (Q(t-4) to Q(t)).
        """
        npm = TTMEngine.calculate_ttm_net_profit_margin(window, fact_store)
        ttm_rev = TTMEngine.calculate_ttm_revenue(window, fact_store)
        avg_assets, a_diag, a_used_fb, asset_facts = calculate_two_point_average(
            CanonicalConcept.TOTAL_ASSETS,
            window.anchor_quarter,
            prior_anchor,
            fact_store,
            allow_point_in_time_fallback,
        )

        all_at_facts = [
            *ttm_rev.provenance.source_fact_ids,
            *(f.fact_id for f in asset_facts),
        ]
        all_at_periods = list(
            dict.fromkeys(
                [
                    *ttm_rev.provenance.source_periods,
                    *(f.period.period_key for f in asset_facts),
                ]
            )
        )

        if (
            ttm_rev.status != MetricStatus.VALID
            or ttm_rev.value is None
            or avg_assets is None
            or (a_diag is not None and not a_used_fb)
        ):
            at_result = MetricResult(
                metric_id=FundamentalMetricId.ASSET_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=[a_diag] if a_diag else list(ttm_rev.diagnostics),
                provenance=MetricProvenance(
                    formula_id="FORMULA_ASSET_TURNOVER_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_at_facts,
                    source_concepts=["REVENUE", "TOTAL_ASSETS"],
                    source_periods=all_at_periods,
                ),
            )
        elif ttm_rev.value <= Decimal("0"):
            at_result = MetricResult(
                metric_id=FundamentalMetricId.ASSET_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_REVENUE,
                        message="TTM Revenue is zero or negative; Asset Turnover is unavailable.",
                        details={"ttm_revenue": str(ttm_rev.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ASSET_TURNOVER_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_at_facts,
                    source_concepts=["REVENUE", "TOTAL_ASSETS"],
                    source_periods=all_at_periods,
                ),
            )
        elif avg_assets <= Decimal("0"):
            at_result = MetricResult(
                metric_id=FundamentalMetricId.ASSET_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_AVERAGE_ASSETS,
                        message="Average Total Assets is zero or negative; Asset Turnover is unavailable.",
                        details={"average_assets": str(avg_assets)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ASSET_TURNOVER_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_at_facts,
                    source_concepts=["REVENUE", "TOTAL_ASSETS"],
                    source_periods=all_at_periods,
                ),
            )
        else:
            at_val = ttm_rev.value / avg_assets
            at_result = MetricResult(
                metric_id=FundamentalMetricId.ASSET_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.VALID,
                value=at_val,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=[a_diag] if a_diag and a_used_fb else [],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ASSET_TURNOVER_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_at_facts,
                    source_concepts=["REVENUE", "TOTAL_ASSETS"],
                    source_periods=all_at_periods,
                ),
            )

        em = cls.calculate_equity_multiplier(
            window.anchor_quarter,
            prior_anchor,
            fact_store,
            allow_point_in_time_fallback,
        )

        # Direct ROE
        ttm_ni = TTMEngine.calculate_ttm_net_income(window, fact_store)
        avg_equity, e_diag, e_used_fb, equity_facts = calculate_two_point_average(
            CanonicalConcept.STOCKHOLDERS_EQUITY,
            window.anchor_quarter,
            prior_anchor,
            fact_store,
            allow_point_in_time_fallback,
        )

        all_roe_facts = list(
            dict.fromkeys(
                [*ttm_ni.provenance.source_fact_ids, *(f.fact_id for f in equity_facts)]
            )
        )
        all_roe_periods = list(
            dict.fromkeys(
                [
                    *ttm_ni.provenance.source_periods,
                    *(f.period.period_key for f in equity_facts),
                ]
            )
        )

        if (
            ttm_ni.status != MetricStatus.VALID
            or ttm_ni.value is None
            or avg_equity is None
            or (e_diag is not None and not e_used_fb)
        ):
            direct_roe = MetricResult(
                metric_id=FundamentalMetricId.RETURN_ON_EQUITY,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=[e_diag] if e_diag else list(ttm_ni.diagnostics),
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROE_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_roe_facts,
                    source_concepts=["NET_INCOME", "STOCKHOLDERS_EQUITY"],
                    source_periods=all_roe_periods,
                ),
            )
        elif avg_equity <= Decimal("0"):
            direct_roe = MetricResult(
                metric_id=FundamentalMetricId.RETURN_ON_EQUITY,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_AVERAGE_EQUITY,
                        message="Average Stockholders' Equity is zero or negative; direct ROE is unavailable.",
                        details={"average_equity": str(avg_equity)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROE_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_roe_facts,
                    source_concepts=["NET_INCOME", "STOCKHOLDERS_EQUITY"],
                    source_periods=all_roe_periods,
                ),
            )
        else:
            direct_roe_val = ttm_ni.value / avg_equity
            direct_roe = MetricResult(
                metric_id=FundamentalMetricId.RETURN_ON_EQUITY,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.VALID,
                value=direct_roe_val,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=[e_diag] if e_diag and e_used_fb else [],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROE_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_roe_facts,
                    source_concepts=["NET_INCOME", "STOCKHOLDERS_EQUITY"],
                    source_periods=all_roe_periods,
                ),
            )

        all_provenance_facts = list(
            dict.fromkeys(
                [
                    *npm.provenance.source_fact_ids,
                    *at_result.provenance.source_fact_ids,
                    *em.provenance.source_fact_ids,
                ]
            )
        )
        all_provenance_concepts = list(
            dict.fromkeys(
                [
                    *npm.provenance.source_concepts,
                    *at_result.provenance.source_concepts,
                    *em.provenance.source_concepts,
                ]
            )
        )
        all_provenance_periods = list(
            dict.fromkeys(
                [
                    *npm.provenance.source_periods,
                    *at_result.provenance.source_periods,
                    *em.provenance.source_periods,
                ]
            )
        )

        if (
            npm.status != MetricStatus.VALID
            or at_result.status != MetricStatus.VALID
            or em.status != MetricStatus.VALID
            or npm.value is None
            or at_result.value is None
            or em.value is None
        ):
            recon_roe = MetricResult(
                metric_id=FundamentalMetricId.DUPONT_ROE_3STEP,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=list(npm.diagnostics)
                + list(at_result.diagnostics)
                + list(em.diagnostics),
                provenance=MetricProvenance(
                    formula_id="FORMULA_DUPONT_ROE_3STEP_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_provenance_facts,
                    source_concepts=all_provenance_concepts,
                    source_periods=all_provenance_periods,
                ),
            )
            return DuPont3StepDecomposition(
                net_profit_margin=npm,
                asset_turnover=at_result,
                equity_multiplier=em,
                reconstructed_roe=recon_roe,
                direct_roe=direct_roe,
                is_reconciled=False,
                reconciliation_discrepancy=None,
            )

        recon_val = npm.value * at_result.value * em.value
        recon_roe = MetricResult(
            metric_id=FundamentalMetricId.DUPONT_ROE_3STEP,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=recon_val,
            unit=Unit.PERCENT,
            currency=None,
            period=window.ttm_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_DUPONT_ROE_3STEP_TTM",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_provenance_facts,
                source_concepts=all_provenance_concepts,
                source_periods=all_provenance_periods,
                methodology_notes="TTM 3-Step DuPont = TTM Net Profit Margin * TTM Asset Turnover * Equity Multiplier.",
            ),
        )

        is_reconciled = False
        discrepancy = None
        if direct_roe.status == MetricStatus.VALID and direct_roe.value is not None:
            discrepancy = abs(direct_roe.value - recon_val)
            is_reconciled = discrepancy <= cls.RECONCILIATION_TOLERANCE

        return DuPont3StepDecomposition(
            net_profit_margin=npm,
            asset_turnover=at_result,
            equity_multiplier=em,
            reconstructed_roe=recon_roe,
            direct_roe=direct_roe,
            is_reconciled=is_reconciled,
            reconciliation_discrepancy=discrepancy,
        )

    @classmethod
    def calculate_5step_dupont_ttm(
        cls,
        window: TTMWindow,
        prior_anchor: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> DuPont5StepDecomposition:
        """
        Calculate 5-Step DuPont decomposition for a 4-quarter TTM window.
        Uses 4-quarter duration flows and 2-point balance sheet averages (Q(t-4) to Q(t)).
        """
        ttm_ni = TTMEngine.calculate_ttm_net_income(window, fact_store)
        ttm_ebit = TTMEngine.calculate_ttm_operating_income(window, fact_store)
        ttm_rev = TTMEngine.calculate_ttm_revenue(window, fact_store)

        ebt_facts: list[FinancialFact] = []
        for q in window.quarters:
            ef = fact_store.get_canonical_fact(
                StatementType.INCOME_STATEMENT,
                CanonicalConcept.PRETAX_INCOME,
                q.period_key,
            )
            if ef is not None:
                ebt_facts.append(ef)

        ttm_ebt = (
            sum((f.value for f in ebt_facts), start=Decimal("0"))
            if len(ebt_facts) == 4
            else None
        )

        # Tax Burden: TTM Net Income / TTM Pretax Income
        all_tb_facts = [
            *ttm_ni.provenance.source_fact_ids,
            *(f.fact_id for f in ebt_facts),
        ]
        all_tb_periods = list(
            dict.fromkeys(
                [
                    *ttm_ni.provenance.source_periods,
                    *(f.period.period_key for f in ebt_facts),
                ]
            )
        )
        if (
            ttm_ni.status != MetricStatus.VALID
            or ttm_ni.value is None
            or ttm_ebt is None
        ):
            tax_burden = MetricResult(
                metric_id=FundamentalMetricId.TAX_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=list(ttm_ni.diagnostics),
                provenance=MetricProvenance(
                    formula_id="FORMULA_TAX_BURDEN_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_tb_facts,
                    source_concepts=["NET_INCOME", "PRETAX_INCOME"],
                    source_periods=all_tb_periods,
                ),
            )
        elif ttm_ebt == Decimal("0"):
            tax_burden = MetricResult(
                metric_id=FundamentalMetricId.TAX_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_PRETAX_INCOME,
                        message="TTM Pretax Income (EBT) is zero; Tax Burden is unavailable.",
                        details={"ttm_ebt": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TAX_BURDEN_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_tb_facts,
                    source_concepts=["NET_INCOME", "PRETAX_INCOME"],
                    source_periods=all_tb_periods,
                ),
            )
        else:
            tb_val = ttm_ni.value / ttm_ebt
            tb_diags = []
            tb_status = MetricStatus.VALID
            if ttm_ebt < Decimal("0"):
                tb_status = MetricStatus.DISTORTED
                tb_diags.append(
                    MetricDiagnostic(
                        code=DiagnosticCode.DISTORTED_PRETAX_EARNINGS,
                        message="TTM Pretax Income (EBT) is negative; Tax Burden ratio is economically distorted.",
                        details={"ttm_ebt": str(ttm_ebt)},
                    )
                )
            tax_burden = MetricResult(
                metric_id=FundamentalMetricId.TAX_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=tb_status,
                value=tb_val,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=tb_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_TAX_BURDEN_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_tb_facts,
                    source_concepts=["NET_INCOME", "PRETAX_INCOME"],
                    source_periods=all_tb_periods,
                ),
            )

        # Interest Burden: TTM Pretax Income / TTM EBIT
        all_ib_facts = [
            *ttm_ebit.provenance.source_fact_ids,
            *(f.fact_id for f in ebt_facts),
        ]
        all_ib_periods = list(
            dict.fromkeys(
                [
                    *ttm_ebit.provenance.source_periods,
                    *(f.period.period_key for f in ebt_facts),
                ]
            )
        )
        if (
            ttm_ebit.status != MetricStatus.VALID
            or ttm_ebit.value is None
            or ttm_ebt is None
        ):
            interest_burden = MetricResult(
                metric_id=FundamentalMetricId.INTEREST_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=list(ttm_ebit.diagnostics),
                provenance=MetricProvenance(
                    formula_id="FORMULA_INTEREST_BURDEN_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_ib_facts,
                    source_concepts=["PRETAX_INCOME", "OPERATING_INCOME"],
                    source_periods=all_ib_periods,
                ),
            )
        elif ttm_ebit.value == Decimal("0"):
            interest_burden = MetricResult(
                metric_id=FundamentalMetricId.INTEREST_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_OPERATING_INCOME,
                        message="TTM Operating Income (EBIT) is zero; Interest Burden is unavailable.",
                        details={"ttm_ebit": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_INTEREST_BURDEN_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_ib_facts,
                    source_concepts=["PRETAX_INCOME", "OPERATING_INCOME"],
                    source_periods=all_ib_periods,
                ),
            )
        else:
            ib_val = ttm_ebt / ttm_ebit.value
            ib_diags = []
            ib_status = MetricStatus.VALID
            if ttm_ebit.value < Decimal("0"):
                ib_status = MetricStatus.DISTORTED
                ib_diags.append(
                    MetricDiagnostic(
                        code=DiagnosticCode.DISTORTED_OPERATING_EARNINGS,
                        message="TTM Operating Income (EBIT) is negative; Interest Burden ratio is distorted.",
                        details={"ttm_ebit": str(ttm_ebit.value)},
                    )
                )
            interest_burden = MetricResult(
                metric_id=FundamentalMetricId.INTEREST_BURDEN,
                category=MetricCategory.PROFITABILITY,
                status=ib_status,
                value=ib_val,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=ib_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_INTEREST_BURDEN_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_ib_facts,
                    source_concepts=["PRETAX_INCOME", "OPERATING_INCOME"],
                    source_periods=all_ib_periods,
                ),
            )

        # EBIT Margin: TTM Operating Income / TTM Revenue
        all_em_facts = [
            *ttm_ebit.provenance.source_fact_ids,
            *ttm_rev.provenance.source_fact_ids,
        ]
        all_em_periods = list(
            dict.fromkeys(
                [
                    *ttm_ebit.provenance.source_periods,
                    *ttm_rev.provenance.source_periods,
                ]
            )
        )
        if (
            ttm_ebit.status != MetricStatus.VALID
            or ttm_rev.status != MetricStatus.VALID
            or ttm_ebit.value is None
            or ttm_rev.value is None
        ):
            ebit_margin = MetricResult(
                metric_id=FundamentalMetricId.EBIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=list(ttm_ebit.diagnostics) + list(ttm_rev.diagnostics),
                provenance=MetricProvenance(
                    formula_id="FORMULA_EBIT_MARGIN_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_em_facts,
                    source_concepts=["OPERATING_INCOME", "REVENUE"],
                    source_periods=all_em_periods,
                ),
            )
        elif ttm_rev.value <= Decimal("0"):
            ebit_margin = MetricResult(
                metric_id=FundamentalMetricId.EBIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_REVENUE,
                        message="TTM Revenue is zero or negative; EBIT Margin is unavailable.",
                        details={"ttm_revenue": str(ttm_rev.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EBIT_MARGIN_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_em_facts,
                    source_concepts=["OPERATING_INCOME", "REVENUE"],
                    source_periods=all_em_periods,
                ),
            )
        else:
            ebm_val = ttm_ebit.value / ttm_rev.value
            ebit_margin = MetricResult(
                metric_id=FundamentalMetricId.EBIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.VALID,
                value=ebm_val,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=[],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EBIT_MARGIN_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_em_facts,
                    source_concepts=["OPERATING_INCOME", "REVENUE"],
                    source_periods=all_em_periods,
                ),
            )

        # Asset Turnover & Equity Multiplier (reused from 3-step)
        step3 = cls.calculate_3step_dupont_ttm(
            window, prior_anchor, fact_store, allow_point_in_time_fallback
        )
        asset_turnover = step3.asset_turnover
        equity_multiplier = step3.equity_multiplier
        direct_roe = step3.direct_roe

        all_provenance_facts = list(
            dict.fromkeys(
                [
                    *tax_burden.provenance.source_fact_ids,
                    *interest_burden.provenance.source_fact_ids,
                    *ebit_margin.provenance.source_fact_ids,
                    *asset_turnover.provenance.source_fact_ids,
                    *equity_multiplier.provenance.source_fact_ids,
                ]
            )
        )
        all_provenance_concepts = list(
            dict.fromkeys(
                [
                    *tax_burden.provenance.source_concepts,
                    *interest_burden.provenance.source_concepts,
                    *ebit_margin.provenance.source_concepts,
                    *asset_turnover.provenance.source_concepts,
                    *equity_multiplier.provenance.source_concepts,
                ]
            )
        )
        all_provenance_periods = list(
            dict.fromkeys(
                [
                    *tax_burden.provenance.source_periods,
                    *interest_burden.provenance.source_periods,
                    *ebit_margin.provenance.source_periods,
                    *asset_turnover.provenance.source_periods,
                    *equity_multiplier.provenance.source_periods,
                ]
            )
        )

        all_valid = all(
            f.status in (MetricStatus.VALID, MetricStatus.DISTORTED)
            and f.value is not None
            for f in (
                tax_burden,
                interest_burden,
                ebit_margin,
                asset_turnover,
                equity_multiplier,
            )
        )

        if not all_valid:
            recon_roe = MetricResult(
                metric_id=FundamentalMetricId.DUPONT_ROE_5STEP,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=list(tax_burden.diagnostics)
                + list(interest_burden.diagnostics)
                + list(ebit_margin.diagnostics)
                + list(asset_turnover.diagnostics)
                + list(equity_multiplier.diagnostics),
                provenance=MetricProvenance(
                    formula_id="FORMULA_DUPONT_ROE_5STEP_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_provenance_facts,
                    source_concepts=all_provenance_concepts,
                    source_periods=all_provenance_periods,
                ),
            )
            return DuPont5StepDecomposition(
                tax_burden=tax_burden,
                interest_burden=interest_burden,
                ebit_margin=ebit_margin,
                asset_turnover=asset_turnover,
                equity_multiplier=equity_multiplier,
                reconstructed_roe=recon_roe,
                direct_roe=direct_roe,
                is_reconciled=False,
                reconciliation_discrepancy=None,
            )

        recon_val = (
            tax_burden.value  # type: ignore[operator]
            * interest_burden.value  # type: ignore[operator]
            * ebit_margin.value  # type: ignore[operator]
            * asset_turnover.value  # type: ignore[operator]
            * equity_multiplier.value  # type: ignore[operator]
        )
        recon_status = (
            MetricStatus.DISTORTED
            if any(
                f.status == MetricStatus.DISTORTED
                for f in (tax_burden, interest_burden)
            )
            else MetricStatus.VALID
        )
        recon_roe = MetricResult(
            metric_id=FundamentalMetricId.DUPONT_ROE_5STEP,
            category=MetricCategory.PROFITABILITY,
            status=recon_status,
            value=recon_val,
            unit=Unit.PERCENT,
            currency=None,
            period=window.ttm_period,
            diagnostics=list(tax_burden.diagnostics)
            + list(interest_burden.diagnostics),
            provenance=MetricProvenance(
                formula_id="FORMULA_DUPONT_ROE_5STEP_TTM",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_provenance_facts,
                source_concepts=all_provenance_concepts,
                source_periods=all_provenance_periods,
                methodology_notes="TTM 5-Step DuPont = Tax Burden * Interest Burden * EBIT Margin * Asset Turnover * Equity Multiplier.",
            ),
        )

        is_reconciled = False
        discrepancy = None
        if direct_roe.status == MetricStatus.VALID and direct_roe.value is not None:
            discrepancy = abs(direct_roe.value - recon_val)
            is_reconciled = discrepancy <= cls.RECONCILIATION_TOLERANCE

        return DuPont5StepDecomposition(
            tax_burden=tax_burden,
            interest_burden=interest_burden,
            ebit_margin=ebit_margin,
            asset_turnover=asset_turnover,
            equity_multiplier=equity_multiplier,
            reconstructed_roe=recon_roe,
            direct_roe=direct_roe,
            is_reconciled=is_reconciled,
            reconciliation_discrepancy=discrepancy,
        )
