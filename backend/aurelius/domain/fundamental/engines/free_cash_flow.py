"""
aurelius.domain.fundamental.engines.free_cash_flow
==================================================
Pure calculation engine for Free Cash Flow to Firm (FCFF) and
Free Cash Flow to Equity (FCFE).

Formulas:
  Primary FCFF (NOPAT-based):
    FCFF_NOPAT = NOPAT + D&A - CapEx - Delta NWC = NOPAT - Reinvestment
  Reconciled FCFF (CFO-based, accrual interest convention):
    FCFF_CFO = CFO + [Gross Interest Expense * (1 - ETR)] - CapEx
  FCFE (Common Equity Cash Flow):
    FCFE = CFO - CapEx + Net Borrowing - Preferred Dividends Paid

Key Invariants:
  - PROHIBITION: CFO - CapEx - Delta NWC is strictly forbidden (double-counts Delta NWC).
  - Accrual Interest Convention: FORMULA_FCFF_CFO_ACCRUAL_INTEREST_V1 uses gross interest
    expense as proxy for cash interest paid due to vendor disclosure limits.
  - Net Borrowing Resolution: itemized gross flows -> reported aggregate -> verified debt-free zero -> unavailable.
  - Preferred Dividends are deducted from FCFE (FCFE is cash flow to common equity).
  - Missing inputs emit explicit UNAVAILABLE status with diagnostics; never fabricate zeros.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialPeriod,
    StatementType,
    Unit,
)
from aurelius.domain.fundamental.engines.cash_flow import CashFlowEngine
from aurelius.domain.fundamental.engines.operating_nwc import OperatingNWCEngine
from aurelius.domain.fundamental.engines.roic import ROICEngine
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
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore


class FCFFReconciliationResult(BaseModel):
    """
    Dual-methodology FCFF output with reconciliation delta and diagnostic metadata.
    """

    model_config = ConfigDict(frozen=True)

    fcff_primary: MetricResult
    fcff_reconciled: MetricResult
    reconciliation_delta: Decimal | None
    divergence_ratio: Decimal | None
    is_divergent: bool


class FreeCashFlowEngine:
    """
    Engine calculating unlevered (FCFF) and levered (FCFE) cash generation metrics.
    """

    METHODOLOGY_VERSION = "1.0.0"

    # -------------------------------------------------------------------------
    # FCFF (Primary NOPAT-driven)
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_fcff_nopat(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Primary Unlevered Free Cash Flow to Firm:
          FCFF_NOPAT = NOPAT + D&A - CapEx - Delta NWC.

        Methodology ID: FORMULA_FCFF_NOPAT_V1.
        """
        nopat_res = ROICEngine.calculate_nopat(current_period, fact_store)
        capex_res = CashFlowEngine.calculate_capital_expenditures(
            current_period, fact_store
        )
        delta_nwc_res = OperatingNWCEngine.calculate_delta_nwc(
            current_period, prior_period, fact_store
        )

        # Extract D&A
        da_fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            [
                "Depreciation And Amortization",
                "Depreciation Amortization Depletion",
                "Depreciation & Amortization",
            ],
            current_period.period_key,
        )
        if da_fact is None:
            da_fact = fact_store.get_source_fact(
                StatementType.INCOME_STATEMENT,
                [
                    "Depreciation And Amortization",
                    "Depreciation & Amortization",
                ],
                current_period.period_key,
            )

        missing_components: list[str] = []
        diagnostics: list[MetricDiagnostic] = []

        if nopat_res.status != MetricStatus.VALID or nopat_res.value is None:
            missing_components.append("NOPAT")
            diagnostics.extend(nopat_res.diagnostics)

        if capex_res.status != MetricStatus.VALID or capex_res.value is None:
            missing_components.append("Capital Expenditures")
            diagnostics.extend(capex_res.diagnostics)

        if da_fact is None:
            missing_components.append("Depreciation & Amortization")
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.MISSING_DEPRECIATION_AMORTIZATION,
                    message="Depreciation & Amortization is absent from both Cash Flow and Income Statement.",
                    details={"period": current_period.period_key},
                )
            )

        if delta_nwc_res.status != MetricStatus.VALID or delta_nwc_res.value is None:
            missing_components.append("Delta NWC")
            diagnostics.extend(delta_nwc_res.diagnostics)

        if missing_components:
            return MetricResult(
                metric_id=FundamentalMetricId.FCFF,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=nopat_res.currency or capex_res.currency,
                period=current_period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_FCFF_NOPAT_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=missing_components,
                    source_periods=[current_period.period_key],
                    methodology_notes=f"Missing inputs for Primary FCFF: {', '.join(missing_components)}.",
                ),
            )

        assert da_fact is not None
        assert nopat_res.value is not None
        assert capex_res.value is not None
        assert delta_nwc_res.value is not None
        da_val = abs(da_fact.value)
        fcff_val = nopat_res.value + da_val - capex_res.value - delta_nwc_res.value

        source_fact_ids = list(
            dict.fromkeys(
                nopat_res.provenance.source_fact_ids
                + capex_res.provenance.source_fact_ids
                + [da_fact.fact_id]
                + delta_nwc_res.provenance.source_fact_ids
            )
        )
        source_concepts = list(
            dict.fromkeys(
                nopat_res.provenance.source_concepts
                + capex_res.provenance.source_concepts
                + [da_fact.concept.source_concept]
                + delta_nwc_res.provenance.source_concepts
            )
        )

        return MetricResult(
            metric_id=FundamentalMetricId.FCFF,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=fcff_val,
            unit=Unit.CURRENCY,
            currency=nopat_res.currency or capex_res.currency,
            period=current_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_FCFF_NOPAT_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=source_fact_ids,
                source_concepts=source_concepts,
                source_periods=[current_period.period_key],
                methodology_notes=(
                    f"FCFF (NOPAT) = NOPAT ({nopat_res.value}) + D&A ({da_val}) "
                    f"- CapEx ({capex_res.value}) - Delta NWC ({delta_nwc_res.value}) = {fcff_val}."
                ),
            ),
        )

    # -------------------------------------------------------------------------
    # FCFF (Reconciled CFO-driven)
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_fcff_cfo(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Reconciled Unlevered Free Cash Flow to Firm (CFO-based):
          FCFF_CFO = CFO + [Gross Interest Expense * (1 - ETR)] - CapEx.

        Methodology ID: FORMULA_FCFF_CFO_ACCRUAL_INTEREST_V1.
        Accrual Interest Convention: Uses gross accounting interest expense as proxy for
        cash interest paid due to vendor disclosure limits.
        """
        cfo_res = CashFlowEngine.calculate_operating_cash_flow(period, fact_store)
        capex_res = CashFlowEngine.calculate_capital_expenditures(period, fact_store)
        etr_res = ROICEngine.calculate_effective_tax_rate(period, fact_store)

        diagnostics: list[MetricDiagnostic] = []
        missing_components: list[str] = []

        if cfo_res.status != MetricStatus.VALID or cfo_res.value is None:
            missing_components.append("Operating Cash Flow")
            diagnostics.extend(cfo_res.diagnostics)

        if capex_res.status != MetricStatus.VALID or capex_res.value is None:
            missing_components.append("Capital Expenditures")
            diagnostics.extend(capex_res.diagnostics)

        if etr_res.status != MetricStatus.VALID or etr_res.value is None:
            missing_components.append("Effective Tax Rate")
            diagnostics.extend(etr_res.diagnostics)

        # Interest Expense lookup
        interest_fact = fact_store.get_source_fact(
            StatementType.INCOME_STATEMENT,
            ["Interest Expense", "Interest Expense Non Operating"],
            period.period_key,
        )
        is_net_interest = False
        if interest_fact is None:
            interest_fact = fact_store.get_source_fact(
                StatementType.INCOME_STATEMENT,
                ["Net Interest Expense"],
                period.period_key,
            )
            if interest_fact is not None:
                is_net_interest = True

        if interest_fact is None:
            missing_components.append("Interest Expense")
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.MISSING_REQUIRED_FACT,
                    message="Interest expense line item absent from income statement.",
                    details={
                        "period": period.period_key,
                        "concept": "INTEREST_EXPENSE",
                    },
                )
            )

        if missing_components:
            return MetricResult(
                metric_id=FundamentalMetricId.FCFF_CFO,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=cfo_res.currency or capex_res.currency,
                period=period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_FCFF_CFO_ACCRUAL_INTEREST_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=missing_components,
                    source_periods=[period.period_key],
                    methodology_notes=f"Missing inputs for Reconciled FCFF: {', '.join(missing_components)}.",
                ),
            )

        if is_net_interest:
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.NET_INTEREST_EXPENSE_FALLBACK,
                    message="Gross interest expense unavailable; net interest expense utilized as fallback.",
                    details={"period": period.period_key},
                )
            )

        diagnostics.append(
            MetricDiagnostic(
                code=DiagnosticCode.ACCRUAL_INTEREST_CFO_RECONCILIATION_NOTE,
                message="Unlevered FCFF (CFO-based) utilizes accounting accrual interest expense as proxy for cash interest paid.",
                details={"period": period.period_key},
            )
        )

        assert interest_fact is not None
        assert etr_res.value is not None
        assert cfo_res.value is not None
        assert capex_res.value is not None
        interest_mag = abs(interest_fact.value)
        after_tax_interest = interest_mag * (Decimal(1) - etr_res.value)
        fcff_cfo_val = cfo_res.value + after_tax_interest - capex_res.value

        source_fact_ids = list(
            dict.fromkeys(
                cfo_res.provenance.source_fact_ids
                + capex_res.provenance.source_fact_ids
                + etr_res.provenance.source_fact_ids
                + [interest_fact.fact_id]
            )
        )
        source_concepts = list(
            dict.fromkeys(
                cfo_res.provenance.source_concepts
                + capex_res.provenance.source_concepts
                + etr_res.provenance.source_concepts
                + [interest_fact.concept.source_concept]
            )
        )

        return MetricResult(
            metric_id=FundamentalMetricId.FCFF_CFO,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=fcff_cfo_val,
            unit=Unit.CURRENCY,
            currency=cfo_res.currency,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_FCFF_CFO_ACCRUAL_INTEREST_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=source_fact_ids,
                source_concepts=source_concepts,
                source_periods=[period.period_key],
                methodology_notes=(
                    f"FCFF (CFO) = CFO ({cfo_res.value}) + [Interest ({interest_mag}) * (1 - ETR ({etr_res.value}))] "
                    f"- CapEx ({capex_res.value}) = {fcff_cfo_val}."
                ),
            ),
        )

    # -------------------------------------------------------------------------
    # FCFF Reconciliation Orchestration
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_fcff_reconciliation(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
    ) -> FCFFReconciliationResult:
        """
        Orchestrate dual FCFF calculations and reconciliation variance analysis.
        If Primary FCFF is unavailable due to missing D&A or Delta NWC, promotes FCFF_CFO.
        """
        fcff_primary = cls.calculate_fcff_nopat(
            current_period, prior_period, fact_store
        )
        fcff_reconciled = cls.calculate_fcff_cfo(current_period, fact_store)

        # Check fallback promotion
        if (
            fcff_primary.status != MetricStatus.VALID
            and fcff_reconciled.status == MetricStatus.VALID
        ):
            # Promote CFO version as primary available
            promoted_diags = [
                MetricDiagnostic(
                    code=DiagnosticCode.FCFF_PROMOTED_CFO_FALLBACK,
                    message="Primary NOPAT FCFF unavailable; promoted CFO-based FCFF as available unlevered metric.",
                    details={"period": current_period.period_key},
                ),
                *fcff_reconciled.diagnostics,
            ]
            fcff_primary = MetricResult(
                metric_id=FundamentalMetricId.FCFF,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.VALID,
                value=fcff_reconciled.value,
                unit=Unit.CURRENCY,
                currency=fcff_reconciled.currency,
                period=current_period,
                diagnostics=promoted_diags,
                provenance=fcff_reconciled.provenance,
            )

        delta: Decimal | None = None
        divergence_ratio: Decimal | None = None
        is_divergent = False

        if (
            fcff_primary.status == MetricStatus.VALID
            and fcff_reconciled.status == MetricStatus.VALID
            and fcff_primary.value is not None
            and fcff_reconciled.value is not None
        ):
            delta = fcff_primary.value - fcff_reconciled.value
            if fcff_primary.value != Decimal(0):
                divergence_ratio = abs(delta) / abs(fcff_primary.value)
                if divergence_ratio > Decimal("0.15"):
                    is_divergent = True

        return FCFFReconciliationResult(
            fcff_primary=fcff_primary,
            fcff_reconciled=fcff_reconciled,
            reconciliation_delta=delta,
            divergence_ratio=divergence_ratio,
            is_divergent=is_divergent,
        )

    # -------------------------------------------------------------------------
    # FCFE (Free Cash Flow to Equity)
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_fcfe(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Free Cash Flow to Equity (FCFE):
          FCFE = CFO - CapEx + Net Borrowing - Preferred Dividends Paid.

        Methodology ID: FORMULA_FCFE_COMMON_V1.
        Debt-flow universe: Long-term debt issuance/repayment, short-term debt,
        and finance lease principal payments. Excludes operating leases.
        """
        cfo_res = CashFlowEngine.calculate_operating_cash_flow(period, fact_store)
        capex_res = CashFlowEngine.calculate_capital_expenditures(period, fact_store)

        diagnostics: list[MetricDiagnostic] = []
        missing_components: list[str] = []

        if cfo_res.status != MetricStatus.VALID or cfo_res.value is None:
            missing_components.append("Operating Cash Flow")
            diagnostics.extend(cfo_res.diagnostics)

        if capex_res.status != MetricStatus.VALID or capex_res.value is None:
            missing_components.append("Capital Expenditures")
            diagnostics.extend(capex_res.diagnostics)

        # Net Borrowing resolution hierarchy
        net_borrowing_val, nb_fact_ids, nb_concepts, nb_diag = (
            cls._resolve_net_borrowing(period, fact_store)
        )
        if nb_diag is not None:
            diagnostics.append(nb_diag)

        if net_borrowing_val is None:
            missing_components.append("Net Borrowing")

        # Preferred Dividends deduction
        pref_div_val, pd_fact_ids, pd_concepts, pd_diag = (
            cls._resolve_preferred_dividends(period, fact_store)
        )
        if pd_diag is not None:
            diagnostics.append(pd_diag)

        if missing_components:
            return MetricResult(
                metric_id=FundamentalMetricId.FCFE,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=cfo_res.currency or capex_res.currency,
                period=period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_FCFE_COMMON_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=missing_components,
                    source_periods=[period.period_key],
                    methodology_notes=f"Missing inputs for FCFE: {', '.join(missing_components)}.",
                ),
            )

        assert cfo_res.value is not None
        assert capex_res.value is not None
        assert net_borrowing_val is not None
        fcfe_val = cfo_res.value - capex_res.value + net_borrowing_val - pref_div_val

        source_fact_ids = list(
            dict.fromkeys(
                cfo_res.provenance.source_fact_ids
                + capex_res.provenance.source_fact_ids
                + nb_fact_ids
                + pd_fact_ids
            )
        )
        source_concepts = list(
            dict.fromkeys(
                cfo_res.provenance.source_concepts
                + capex_res.provenance.source_concepts
                + nb_concepts
                + pd_concepts
            )
        )

        return MetricResult(
            metric_id=FundamentalMetricId.FCFE,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=fcfe_val,
            unit=Unit.CURRENCY,
            currency=cfo_res.currency,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_FCFE_COMMON_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=source_fact_ids,
                source_concepts=source_concepts,
                source_periods=[period.period_key],
                methodology_notes=(
                    f"FCFE = CFO ({cfo_res.value}) - CapEx ({capex_res.value}) "
                    f"+ Net Borrowing ({net_borrowing_val}) - Preferred Dividends ({pref_div_val}) = {fcfe_val}."
                ),
            ),
        )

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    @classmethod
    def _resolve_net_borrowing(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> tuple[Decimal | None, list[str], list[str], MetricDiagnostic | None]:
        """
        Resolve Net Borrowing under the 4-tier hierarchy:
          Tier 1: Itemized gross debt flows (issued - repaid - finance leases).
          Tier 2: Reported aggregate 'Net Issuance Payments Of Debt'.
          Tier 3: Verified debt-free firm (zero borrowing).
          Tier 4: Missing data (UNAVAILABLE).
        """
        issued_fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            ["Issuance Of Debt", "Long Term Debt Issuance"],
            period.period_key,
        )
        repaid_fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            ["Repayment Of Debt", "Long Term Debt Payments"],
            period.period_key,
        )
        fl_fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            [
                "Finance Lease Principal Payments",
                "Payment Of Capital Lease Obligations",
            ],
            period.period_key,
        )

        # Tier 1: Itemized gross flows
        if issued_fact is not None and repaid_fact is not None:
            issued_val = issued_fact.value
            repaid_val = abs(repaid_fact.value)
            fl_val = abs(fl_fact.value) if fl_fact is not None else Decimal(0)
            net_borrowing = issued_val - repaid_val - fl_val
            fact_ids = [issued_fact.fact_id, repaid_fact.fact_id]
            concepts = [
                issued_fact.concept.source_concept,
                repaid_fact.concept.source_concept,
            ]
            if fl_fact is not None:
                fact_ids.append(fl_fact.fact_id)
                concepts.append(fl_fact.concept.source_concept)
            return net_borrowing, fact_ids, concepts, None

        # Tier 2: Reported aggregate
        net_debt_fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            ["Net Issuance Payments Of Debt"],
            period.period_key,
        )
        if net_debt_fact is not None:
            return (
                net_debt_fact.value,
                [net_debt_fact.fact_id],
                [net_debt_fact.concept.source_concept],
                None,
            )

        # Tier 3: Verified debt-free firm
        lt_debt = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.LONG_TERM_DEBT,
            period.period_key,
        )
        if lt_debt is None:
            lt_debt = fact_store.get_source_fact(
                StatementType.BALANCE_SHEET,
                ["Long Term Debt", "Total Debt"],
                period.period_key,
            )
        if lt_debt is not None and lt_debt.value == Decimal(0):
            diag = MetricDiagnostic(
                code=DiagnosticCode.ZERO_NET_BORROWING_VERIFIED,
                message="Company maintains zero debt on balance sheet; Net Borrowing evaluated as zero.",
                details={"period": period.period_key},
            )
            return Decimal(0), [lt_debt.fact_id], ["Long Term Debt"], diag

        # Tier 4: Missing data
        diag = MetricDiagnostic(
            code=DiagnosticCode.NET_BORROWING_UNAVAILABLE,
            message="Debt issuance and repayment cash flows are unavailable.",
            details={"period": period.period_key},
        )
        return None, [], [], diag

    @classmethod
    def _resolve_preferred_dividends(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> tuple[Decimal, list[str], list[str], MetricDiagnostic | None]:
        """
        Resolve Preferred Dividends:
          - Explicitly reported line item -> abs(val).
          - No preferred stock on balance sheet -> Decimal(0).
          - Preferred stock present but dividend line absent -> Decimal(0) with warning.
        """
        pref_div_fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            ["Preferred Stock Dividends Paid", "Payment Of Preferred Dividends"],
            period.period_key,
        )
        if pref_div_fact is not None:
            return (
                abs(pref_div_fact.value),
                [pref_div_fact.fact_id],
                [pref_div_fact.concept.source_concept],
                None,
            )

        # Check if preferred stock exists on balance sheet
        pref_stock_fact = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            ["Preferred Stock", "Preferred Stock Equity"],
            period.period_key,
        )
        if pref_stock_fact is not None and pref_stock_fact.value > Decimal(0):
            diag = MetricDiagnostic(
                code=DiagnosticCode.PREFERRED_DIVIDEND_ABSENCE_UNVERIFIED,
                message="Preferred stock is reported on balance sheet, but preferred dividends are not disclosed in cash flows; evaluated as zero with audit warning.",
                details={
                    "period": period.period_key,
                    "preferred_stock": str(pref_stock_fact.value),
                },
            )
            return Decimal(0), [pref_stock_fact.fact_id], ["Preferred Stock"], diag

        return Decimal(0), [], [], None
