"""
aurelius.domain.fundamental.engines.enterprise_value
====================================================
Pure calculation engine for Enterprise Value (EV) Bridge and
Capital Structure Weights.

Formulas:
  Enterprise Value:
    EV = Market Capitalization + Gross Debt + Preferred Equity + Minority Interest
         - (Cash & Cash Equivalents + Short-Term Investments)
    Equivalently:
    EV = Market Capitalization + Net Debt + Preferred Equity + Minority Interest
    where Net Debt = Gross Debt - (Cash & Equivalents + Short-Term Investments)

  Capital Structure:
    Total Capital = Market Capitalization + Gross Debt + Preferred Equity
    Weight of Equity (We) = Market Capitalization / Total Capital
    Weight of Debt (Wd) = Gross Debt / Total Capital
    Weight of Preferred (Wp) = Preferred Equity / Total Capital
    Invariant: We + Wd + Wp = 1.0 (100%)

Key Invariants:
  - MISSING != ZERO Doctrine: Non-common claims (Preferred Equity and Minority Interest)
    strictly follow the 4-case disclosure taxonomy:
      Case 1: Explicitly Reported Non-Zero -> exact reported value (VALID)
      Case 2: Explicitly Reported Zero -> 0 (VALID with confirmation note)
      Case 3: Confidently Absent -> 0 (VALID under strict structural completeness criteria)
      Case 4: Insufficiently Disclosed -> None (UNAVAILABLE; EV cannot compute)
  - Market Capitalization must be positive. None -> UNAVAILABLE; <= 0 -> DISTORTED.
  - Gross Debt is resolved via the canonical SolvencyEngine hierarchy.
  - Negative Enterprise Value is valid (accompanies NEGATIVE_ENTERPRISE_VALUE_WARNING).
  - Total Capital <= 0 renders weights DISTORTED with ZERO_OR_NEGATIVE_CAPITAL.
  - Provider-independent and side-effect free Decimal arithmetic.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialFact,
    FinancialPeriod,
    StatementType,
    Unit,
)
from aurelius.domain.fundamental.engines.solvency import SolvencyEngine
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


class CapitalStructureResult(BaseModel):
    """
    Capital structure weights and total capital claims.
    """

    model_config = ConfigDict(frozen=True)

    total_capital: MetricResult
    weight_equity: MetricResult
    weight_debt: MetricResult
    weight_preferred: MetricResult


class EnterpriseValueBridgeEngine:
    """
    Engine calculating Enterprise Value and Capital Structure Weights.
    """

    METHODOLOGY_VERSION = "1.0.0"

    # -------------------------------------------------------------------------
    # 4-State Disclosure Taxonomy: Preferred Equity & Minority Interest
    # -------------------------------------------------------------------------

    @classmethod
    def resolve_preferred_equity(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> tuple[
        Decimal | None, list[FinancialFact], list[str], list[MetricDiagnostic], str
    ]:
        """
        Resolve Preferred Equity under the 4-Case Disclosure Taxonomy:
          Case 1: Reported Non-Zero -> use reported value.
          Case 2: Reported Zero -> 0.
          Case 3: Confidently Absent -> 0 under strict structural completeness criteria.
          Case 4: Insufficiently Disclosed -> None (UNAVAILABLE).

        Returns:
          (value, facts, concepts, diagnostics, note)
        """
        pref_fact = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            ["Preferred Stock", "Preferred Stock Equity", "Preferred Equity"],
            period.period_key,
        )

        if pref_fact is not None:
            if pref_fact.value != Decimal(0):
                # Case 1: Explicitly Reported Non-Zero
                return (
                    abs(pref_fact.value),
                    [pref_fact],
                    [pref_fact.concept.source_concept],
                    [],
                    f"Reported preferred equity of {abs(pref_fact.value)}.",
                )
            else:
                # Case 2: Explicitly Reported Zero
                return (
                    Decimal(0),
                    [pref_fact],
                    [pref_fact.concept.source_concept],
                    [],
                    "Explicitly reported zero preferred equity.",
                )

        # Line item is absent: test for Case 3 ("Confidently Absent") vs Case 4 ("Insufficiently Disclosed")
        stockholders_eq = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.STOCKHOLDERS_EQUITY,
            period.period_key,
        )
        common_stock_eq = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            ["Common Stock Equity", "Common Equity"],
            period.period_key,
        )
        retained_earnings = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            ["Retained Earnings", "Retained Earnings Total Equity"],
            period.period_key,
        )
        common_stock = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            ["Common Stock", "Common Stocks"],
            period.period_key,
        )
        apic = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            ["Additional Paid In Capital", "Capital Surplus"],
            period.period_key,
        )

        # Criterion 1: Common Stock Equity == Stockholders Equity
        if (
            common_stock_eq is not None
            and stockholders_eq is not None
            and common_stock_eq.value == stockholders_eq.value
        ):
            diag = MetricDiagnostic(
                code=DiagnosticCode.PREFERRED_EQUITY_CONFIDENTLY_ABSENT,
                message="Preferred equity confidently absent: Common Stock Equity exactly equals Stockholders Equity.",
                details={"period": period.period_key},
            )
            return (
                Decimal(0),
                [common_stock_eq, stockholders_eq],
                ["Common Stock Equity", "STOCKHOLDERS_EQUITY"],
                [diag],
                "Preferred equity confidently absent: Common Stock Equity equals Stockholders Equity.",
            )

        # Criterion 2: Detailed itemized equity components exist
        if retained_earnings is not None or (
            common_stock is not None and apic is not None
        ):
            contributing = [
                f
                for f in [stockholders_eq, retained_earnings, common_stock, apic]
                if f is not None
            ]
            diag = MetricDiagnostic(
                code=DiagnosticCode.PREFERRED_EQUITY_CONFIDENTLY_ABSENT,
                message="Preferred equity confidently absent: balance sheet contains itemized common equity breakdown with no preferred claims.",
                details={"period": period.period_key},
            )
            return (
                Decimal(0),
                contributing,
                [f.concept.source_concept for f in contributing],
                [diag],
                "Preferred equity confidently absent: verified via itemized equity section.",
            )

        # Case 4: Insufficiently Disclosed
        diag = MetricDiagnostic(
            code=DiagnosticCode.PREFERRED_EQUITY_INSUFFICIENTLY_DISCLOSED,
            message="Preferred equity line is absent and balance sheet equity section lacks itemized breakdown; value cannot be determined defensibly.",
            details={"period": period.period_key},
        )
        return (None, [], [], [diag], "Preferred equity insufficiently disclosed.")

    @classmethod
    def resolve_minority_interest(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> tuple[
        Decimal | None, list[FinancialFact], list[str], list[MetricDiagnostic], str
    ]:
        """
        Resolve Minority Interest under the 4-Case Disclosure Taxonomy:
          Case 1: Reported Non-Zero -> use reported value.
          Case 2: Reported Zero -> 0.
          Case 3: Confidently Absent -> 0 under strict structural completeness criteria.
          Case 4: Insufficiently Disclosed -> None (UNAVAILABLE).

        Returns:
          (value, facts, concepts, diagnostics, note)
        """
        min_fact = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            [
                "Minority Interest",
                "Noncontrolling Interest",
                "Non Controlling Interest",
                "Minority Interest In Consolidation",
            ],
            period.period_key,
        )

        if min_fact is not None:
            if min_fact.value != Decimal(0):
                # Case 1: Explicitly Reported Non-Zero
                return (
                    abs(min_fact.value),
                    [min_fact],
                    [min_fact.concept.source_concept],
                    [],
                    f"Reported minority interest of {abs(min_fact.value)}.",
                )
            else:
                # Case 2: Explicitly Reported Zero
                return (
                    Decimal(0),
                    [min_fact],
                    [min_fact.concept.source_concept],
                    [],
                    "Explicitly reported zero minority interest.",
                )

        # Line item is absent: test for Case 3 ("Confidently Absent") vs Case 4 ("Insufficiently Disclosed")
        gross_equity = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            ["Total Equity Gross Minority Interest", "Gross Minority Interest"],
            period.period_key,
        )
        stockholders_eq = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.STOCKHOLDERS_EQUITY,
            period.period_key,
        )

        if (
            gross_equity is not None
            and stockholders_eq is not None
            and gross_equity.value == stockholders_eq.value
        ):
            diag = MetricDiagnostic(
                code=DiagnosticCode.MINORITY_INTEREST_CONFIDENTLY_ABSENT,
                message="Minority interest confidently absent: Total Equity Gross Minority Interest equals Stockholders Equity.",
                details={"period": period.period_key},
            )
            return (
                Decimal(0),
                [gross_equity, stockholders_eq],
                ["Total Equity Gross Minority Interest", "STOCKHOLDERS_EQUITY"],
                [diag],
                "Minority interest confidently absent: gross equity equals stockholders equity.",
            )

        # Check if classified balance sheet with stockholders' equity is present and ties without non-controlling interest
        net_liab_fact = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            [
                "Total Liabilities Net Minority Interest",
                "Liabilities Net Minority Interest",
            ],
            period.period_key,
        )
        if net_liab_fact is not None:
            # Stated as net of minority interest without reporting minority interest -> Case 4
            diag = MetricDiagnostic(
                code=DiagnosticCode.MINORITY_INTEREST_INSUFFICIENTLY_DISCLOSED,
                message="Balance sheet states liabilities net of minority interest but omits minority interest reconciliation.",
                details={"period": period.period_key},
            )
            return (
                None,
                [net_liab_fact],
                [net_liab_fact.concept.source_concept],
                [diag],
                "Minority interest insufficiently disclosed.",
            )

        if stockholders_eq is not None:
            diag = MetricDiagnostic(
                code=DiagnosticCode.MINORITY_INTEREST_CONFIDENTLY_ABSENT,
                message="Minority interest confidently absent: balance sheet liabilities and equity structure discloses 100% consolidated equity ownership.",
                details={"period": period.period_key},
            )
            return (
                Decimal(0),
                [stockholders_eq],
                ["STOCKHOLDERS_EQUITY"],
                [diag],
                "Minority interest confidently absent.",
            )

        # Case 4: Insufficiently Disclosed
        diag = MetricDiagnostic(
            code=DiagnosticCode.MINORITY_INTEREST_INSUFFICIENTLY_DISCLOSED,
            message="Minority interest line is absent and consolidation structure is insufficiently disclosed.",
            details={"period": period.period_key},
        )
        return (None, [], [], [diag], "Minority interest insufficiently disclosed.")

    # -------------------------------------------------------------------------
    # Enterprise Value Bridge
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_enterprise_value(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
        market_cap: Decimal | None,
    ) -> MetricResult:
        """
        Calculate Enterprise Value:
          EV = Market Cap + Gross Debt + Preferred Equity + Minority Interest
               - (Cash & Equivalents + Short-Term Investments)
        """
        diagnostics: list[MetricDiagnostic] = []
        source_fact_ids: list[str] = []
        source_concepts: list[str] = []
        missing_components: list[str] = []

        # 1. Market Capitalization
        if market_cap is None:
            missing_components.append("Market Capitalization")
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.MARKET_CAP_UNAVAILABLE,
                    message="Market capitalization is unavailable; Enterprise Value cannot be computed.",
                    details={"period": period.period_key},
                )
            )
        elif market_cap <= Decimal(0):
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.NON_POSITIVE_MARKET_CAP,
                    message="Market capitalization is zero or negative; Enterprise Value is distorted.",
                    details={
                        "market_cap": str(market_cap),
                        "period": period.period_key,
                    },
                )
            )
            return MetricResult(
                metric_id=FundamentalMetricId.ENTERPRISE_VALUE,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_ENTERPRISE_VALUE_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["Market Capitalization"],
                    source_periods=[period.period_key],
                    methodology_notes="Non-positive market capitalization renders Enterprise Value distorted.",
                ),
            )
        else:
            source_concepts.append("Market Capitalization")

        # 2. Gross Debt
        gross_debt_val, debt_facts, debt_formula, debt_notes, debt_diag = (
            SolvencyEngine.resolve_gross_debt(period, fact_store)
        )
        if gross_debt_val is None:
            missing_components.append("Gross Debt")
        else:
            source_fact_ids.extend(f.fact_id for f in debt_facts)
            source_concepts.append("GROSS_DEBT")

        if debt_diag is not None:
            diagnostics.append(debt_diag)

        # 3. Cash and Cash Equivalents
        cash_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
            period.period_key,
        )
        if cash_fact is None:
            missing_components.append("Cash & Equivalents")
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.MISSING_REQUIRED_FACT,
                    message="Cash and cash equivalents is missing from balance sheet.",
                    details={"period": period.period_key},
                )
            )
        else:
            source_fact_ids.append(cash_fact.fact_id)
            source_concepts.append("CASH_AND_EQUIVALENTS")

        # 4. Short-Term Investments
        sti_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.SHORT_TERM_INVESTMENTS,
            period.period_key,
        )
        sti_val = Decimal(0)
        if sti_fact is not None:
            sti_val = sti_fact.value
            source_fact_ids.append(sti_fact.fact_id)
            source_concepts.append("SHORT_TERM_INVESTMENTS")

        # 5. Preferred Equity (4-case taxonomy)
        pref_val, pref_facts, pref_concepts, pref_diags, pref_notes = (
            cls.resolve_preferred_equity(period, fact_store)
        )
        diagnostics.extend(pref_diags)
        source_fact_ids.extend(f.fact_id for f in pref_facts)
        source_concepts.extend(pref_concepts)
        if pref_val is None:
            missing_components.append("Preferred Equity")

        # 6. Minority Interest (4-case taxonomy)
        min_val, min_facts, min_concepts, min_diags, min_notes = (
            cls.resolve_minority_interest(period, fact_store)
        )
        diagnostics.extend(min_diags)
        source_fact_ids.extend(f.fact_id for f in min_facts)
        source_concepts.extend(min_concepts)
        if min_val is None:
            missing_components.append("Minority Interest")

        # Missing component guard: MISSING != ZERO
        if (
            missing_components
            or market_cap is None
            or gross_debt_val is None
            or cash_fact is None
        ):
            return MetricResult(
                metric_id=FundamentalMetricId.ENTERPRISE_VALUE,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=cash_fact.currency if cash_fact else None,
                period=period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_ENTERPRISE_VALUE_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=source_fact_ids,
                    source_concepts=source_concepts,
                    source_periods=[period.period_key],
                    methodology_notes=f"Missing required claims/deductions for Enterprise Value: {', '.join(missing_components)}.",
                ),
            )

        assert pref_val is not None
        assert min_val is not None

        # EV = Market Cap + Gross Debt + Preferred Equity + Minority Interest - Cash - STI
        total_cash_liquid = cash_fact.value + sti_val
        ev_val = market_cap + gross_debt_val + pref_val + min_val - total_cash_liquid

        # Negative Enterprise Value warning
        if ev_val < Decimal(0):
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.NEGATIVE_ENTERPRISE_VALUE_WARNING,
                    message="Negative enterprise value observed: cash and liquid investments exceed aggregate debt and equity market claims.",
                    details={
                        "enterprise_value": str(ev_val),
                        "period": period.period_key,
                    },
                )
            )

        return MetricResult(
            metric_id=FundamentalMetricId.ENTERPRISE_VALUE,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=ev_val,
            unit=Unit.CURRENCY,
            currency=cash_fact.currency or Currency.USD,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_ENTERPRISE_VALUE_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=list(dict.fromkeys(source_fact_ids)),
                source_concepts=list(dict.fromkeys(source_concepts)),
                source_periods=[period.period_key],
                methodology_notes=(
                    f"Enterprise Value = Market Cap ({market_cap}) + Gross Debt ({gross_debt_val}) "
                    f"+ Preferred Equity ({pref_val}) + Minority Interest ({min_val}) "
                    f"- Cash & STI ({total_cash_liquid}) = {ev_val}."
                ),
            ),
        )

    # -------------------------------------------------------------------------
    # Capital Structure Weights
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_total_capital(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
        market_cap: Decimal | None,
    ) -> MetricResult:
        """
        Calculate Total Capital:
          Total Capital = Market Capitalization + Gross Debt + Preferred Equity
        """
        diagnostics: list[MetricDiagnostic] = []
        source_fact_ids: list[str] = []
        source_concepts: list[str] = []
        missing_components: list[str] = []

        if market_cap is None:
            missing_components.append("Market Capitalization")
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.MARKET_CAP_UNAVAILABLE,
                    message="Market capitalization is unavailable; Total Capital cannot be computed.",
                    details={"period": period.period_key},
                )
            )
        elif market_cap <= Decimal(0):
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.NON_POSITIVE_MARKET_CAP,
                    message="Market capitalization is zero or negative.",
                    details={
                        "market_cap": str(market_cap),
                        "period": period.period_key,
                    },
                )
            )
            return MetricResult(
                metric_id=FundamentalMetricId.TOTAL_CAPITAL,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_TOTAL_CAPITAL_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["Market Capitalization"],
                    source_periods=[period.period_key],
                    methodology_notes="Non-positive market capitalization.",
                ),
            )
        else:
            source_concepts.append("Market Capitalization")

        gross_debt_val, debt_facts, debt_formula, debt_notes, debt_diag = (
            SolvencyEngine.resolve_gross_debt(period, fact_store)
        )
        if gross_debt_val is None:
            missing_components.append("Gross Debt")
        else:
            source_fact_ids.extend(f.fact_id for f in debt_facts)
            source_concepts.append("GROSS_DEBT")

        if debt_diag is not None:
            diagnostics.append(debt_diag)

        pref_val, pref_facts, pref_concepts, pref_diags, pref_notes = (
            cls.resolve_preferred_equity(period, fact_store)
        )
        diagnostics.extend(pref_diags)
        source_fact_ids.extend(f.fact_id for f in pref_facts)
        source_concepts.extend(pref_concepts)
        if pref_val is None:
            missing_components.append("Preferred Equity")

        if (
            missing_components
            or market_cap is None
            or gross_debt_val is None
            or pref_val is None
        ):
            return MetricResult(
                metric_id=FundamentalMetricId.TOTAL_CAPITAL,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_TOTAL_CAPITAL_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=source_fact_ids,
                    source_concepts=source_concepts,
                    source_periods=[period.period_key],
                    methodology_notes=f"Missing inputs for Total Capital: {', '.join(missing_components)}.",
                ),
            )

        total_cap_val = market_cap + gross_debt_val + pref_val

        if total_cap_val <= Decimal(0):
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.ZERO_OR_NEGATIVE_CAPITAL,
                    message="Total capital is zero or negative; capital claims cannot be weighted.",
                    details={
                        "total_capital": str(total_cap_val),
                        "period": period.period_key,
                    },
                )
            )
            return MetricResult(
                metric_id=FundamentalMetricId.TOTAL_CAPITAL,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_TOTAL_CAPITAL_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=source_fact_ids,
                    source_concepts=source_concepts,
                    source_periods=[period.period_key],
                    methodology_notes="Total capital is zero or negative.",
                ),
            )

        resolved_curr = (
            debt_facts[0].currency
            if debt_facts and debt_facts[0].currency
            else (
                pref_facts[0].currency
                if pref_facts and pref_facts[0].currency
                else Currency.USD
            )
        )

        return MetricResult(
            metric_id=FundamentalMetricId.TOTAL_CAPITAL,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=total_cap_val,
            unit=Unit.CURRENCY,
            currency=resolved_curr,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_TOTAL_CAPITAL_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=list(dict.fromkeys(source_fact_ids)),
                source_concepts=list(dict.fromkeys(source_concepts)),
                source_periods=[period.period_key],
                methodology_notes=(
                    f"Total Capital = Market Cap ({market_cap}) + Gross Debt ({gross_debt_val}) "
                    f"+ Preferred Equity ({pref_val}) = {total_cap_val}."
                ),
            ),
        )

    @classmethod
    def calculate_capital_structure_weights(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
        market_cap: Decimal | None,
    ) -> CapitalStructureResult:
        """
        Calculate Capital Structure Weights:
          Weight of Equity (We) = Market Cap / Total Capital
          Weight of Debt (Wd) = Gross Debt / Total Capital
          Weight of Preferred (Wp) = Preferred Equity / Total Capital
          Identity: We + Wd + Wp = 1.0 (100%)
        """
        tot_cap_res = cls.calculate_total_capital(period, fact_store, market_cap)

        # Base case: if total capital is unavailable or distorted
        if tot_cap_res.status != MetricStatus.VALID or tot_cap_res.value is None:
            unavailable_prov = tot_cap_res.provenance
            status = tot_cap_res.status
            return CapitalStructureResult(
                total_capital=tot_cap_res,
                weight_equity=MetricResult(
                    metric_id=FundamentalMetricId.WEIGHT_EQUITY,
                    category=MetricCategory.SOLVENCY,
                    status=status,
                    value=None,
                    unit=Unit.PERCENT,
                    currency=None,
                    period=period,
                    diagnostics=tot_cap_res.diagnostics,
                    provenance=unavailable_prov,
                ),
                weight_debt=MetricResult(
                    metric_id=FundamentalMetricId.WEIGHT_DEBT,
                    category=MetricCategory.SOLVENCY,
                    status=status,
                    value=None,
                    unit=Unit.PERCENT,
                    currency=None,
                    period=period,
                    diagnostics=tot_cap_res.diagnostics,
                    provenance=unavailable_prov,
                ),
                weight_preferred=MetricResult(
                    metric_id=FundamentalMetricId.WEIGHT_PREFERRED,
                    category=MetricCategory.SOLVENCY,
                    status=status,
                    value=None,
                    unit=Unit.PERCENT,
                    currency=None,
                    period=period,
                    diagnostics=tot_cap_res.diagnostics,
                    provenance=unavailable_prov,
                ),
            )

        total_cap_val = tot_cap_res.value
        assert market_cap is not None

        gross_debt_val, _, _, _, _ = SolvencyEngine.resolve_gross_debt(
            period, fact_store
        )
        assert gross_debt_val is not None

        pref_val, _, _, _, _ = cls.resolve_preferred_equity(period, fact_store)
        assert pref_val is not None

        # Weights
        we = market_cap / total_cap_val
        wd = gross_debt_val / total_cap_val
        wp = pref_val / total_cap_val

        prov_equity = MetricProvenance(
            formula_id="FORMULA_CAPITAL_STRUCTURE_WEIGHTS_V1",
            methodology_version=cls.METHODOLOGY_VERSION,
            source_fact_ids=tot_cap_res.provenance.source_fact_ids,
            source_concepts=tot_cap_res.provenance.source_concepts,
            source_periods=[period.period_key],
            methodology_notes=f"Weight of Equity = Market Cap ({market_cap}) / Total Capital ({total_cap_val}) = {we}.",
        )
        prov_debt = MetricProvenance(
            formula_id="FORMULA_CAPITAL_STRUCTURE_WEIGHTS_V1",
            methodology_version=cls.METHODOLOGY_VERSION,
            source_fact_ids=tot_cap_res.provenance.source_fact_ids,
            source_concepts=tot_cap_res.provenance.source_concepts,
            source_periods=[period.period_key],
            methodology_notes=f"Weight of Debt = Gross Debt ({gross_debt_val}) / Total Capital ({total_cap_val}) = {wd}.",
        )
        prov_pref = MetricProvenance(
            formula_id="FORMULA_CAPITAL_STRUCTURE_WEIGHTS_V1",
            methodology_version=cls.METHODOLOGY_VERSION,
            source_fact_ids=tot_cap_res.provenance.source_fact_ids,
            source_concepts=tot_cap_res.provenance.source_concepts,
            source_periods=[period.period_key],
            methodology_notes=f"Weight of Preferred = Preferred Equity ({pref_val}) / Total Capital ({total_cap_val}) = {wp}.",
        )

        return CapitalStructureResult(
            total_capital=tot_cap_res,
            weight_equity=MetricResult(
                metric_id=FundamentalMetricId.WEIGHT_EQUITY,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.VALID,
                value=we,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=tot_cap_res.diagnostics,
                provenance=prov_equity,
            ),
            weight_debt=MetricResult(
                metric_id=FundamentalMetricId.WEIGHT_DEBT,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.VALID,
                value=wd,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=tot_cap_res.diagnostics,
                provenance=prov_debt,
            ),
            weight_preferred=MetricResult(
                metric_id=FundamentalMetricId.WEIGHT_PREFERRED,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.VALID,
                value=wp,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=tot_cap_res.diagnostics,
                provenance=prov_pref,
            ),
        )
