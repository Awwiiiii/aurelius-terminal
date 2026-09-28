"""
tests.unit.domain.fundamental.test_free_cash_flow_engine
=========================================================
Deterministic unit tests for FreeCashFlowEngine:
- Primary FCFF (NOPAT-based): NOPAT + D&A - CapEx - Delta NWC
- Reconciled FCFF (CFO-based): CFO + [Gross Interest * (1 - ETR)] - CapEx
- Prohibition of double-counting: CFO - CapEx - Delta NWC is forbidden
- FCFF Reconciliation and divergence analysis
- Fallback promotion of FCFF_CFO when Primary FCFF is unavailable
- FCFE: CFO - CapEx + Net Borrowing - Preferred Dividends
- Net Borrowing resolution hierarchy (Tiers 1-4)
- Preferred Dividends deduction logic
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.free_cash_flow import FreeCashFlowEngine
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricStatus,
)
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)


def test_fcff_nopat_primary_calculation():
    p_curr = make_period(
        "2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024
    )
    p_curr_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )
    p_prior_inst = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )

    # NOPAT inputs: EBIT = 1000, Pretax = 1000, Tax = 250 -> ETR = 25% -> NOPAT = 750
    fact_ebit = make_fact(
        StatementType.INCOME_STATEMENT,
        "1000",
        p_curr,
        CanonicalConcept.OPERATING_INCOME,
    )
    fact_ebt = make_fact(
        StatementType.INCOME_STATEMENT, "1000", p_curr, CanonicalConcept.PRETAX_INCOME
    )
    fact_tax = make_fact(
        StatementType.INCOME_STATEMENT,
        "250",
        p_curr,
        CanonicalConcept.INCOME_TAX_EXPENSE,
    )

    # D&A = 150
    fact_da = make_fact(
        StatementType.CASH_FLOW,
        "150",
        p_curr,
        source_concept="Depreciation And Amortization",
    )

    # CapEx = -200 (magnitude 200)
    fact_capex = make_fact(
        StatementType.CASH_FLOW, "-200", p_curr, CanonicalConcept.CAPITAL_EXPENDITURES
    )

    # Delta NWC: Current NWC = 300, Prior NWC = 200 -> Delta NWC = 100
    fact_ca_curr = make_fact(
        StatementType.BALANCE_SHEET, "600", p_curr_inst, CanonicalConcept.CURRENT_ASSETS
    )
    fact_cash_curr = make_fact(
        StatementType.BALANCE_SHEET,
        "100",
        p_curr_inst,
        CanonicalConcept.CASH_AND_EQUIVALENTS,
    )
    fact_cl_curr = make_fact(
        StatementType.BALANCE_SHEET,
        "200",
        p_curr_inst,
        CanonicalConcept.CURRENT_LIABILITIES,
    )

    fact_ca_prior = make_fact(
        StatementType.BALANCE_SHEET,
        "450",
        p_prior_inst,
        CanonicalConcept.CURRENT_ASSETS,
    )
    fact_cash_prior = make_fact(
        StatementType.BALANCE_SHEET,
        "100",
        p_prior_inst,
        CanonicalConcept.CASH_AND_EQUIVALENTS,
    )
    fact_cl_prior = make_fact(
        StatementType.BALANCE_SHEET,
        "150",
        p_prior_inst,
        CanonicalConcept.CURRENT_LIABILITIES,
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.INCOME_STATEMENT, p_curr, [fact_ebit, fact_ebt, fact_tax]
            ),
            make_statement(StatementType.CASH_FLOW, p_curr, [fact_da, fact_capex]),
            make_statement(
                StatementType.BALANCE_SHEET,
                p_curr_inst,
                [fact_ca_curr, fact_cash_curr, fact_cl_curr],
            ),
            make_statement(
                StatementType.BALANCE_SHEET,
                p_prior_inst,
                [fact_ca_prior, fact_cash_prior, fact_cl_prior],
            ),
        ]
    )

    # FCFF = NOPAT (750) + D&A (150) - CapEx (200) - Delta NWC (100) = 600
    res = FreeCashFlowEngine.calculate_fcff_nopat(p_curr, p_prior_inst, store)
    assert res.status == MetricStatus.VALID
    assert res.metric_id == FundamentalMetricId.FCFF
    assert res.value == Decimal("600")
    assert "FORMULA_FCFF_NOPAT_V1" in res.provenance.formula_id


def test_fcff_cfo_accrual_interest_convention():
    p = make_period("2024-12-31", period_type=PeriodType.DURATION)

    # CFO = 700
    fact_cfo = make_fact(
        StatementType.CASH_FLOW, "700", p, CanonicalConcept.OPERATING_CASH_FLOW
    )
    # Gross Interest Expense = 80
    fact_int = make_fact(
        StatementType.INCOME_STATEMENT, "80", p, source_concept="Interest Expense"
    )
    # Pretax = 500, Tax = 100 -> ETR = 20%
    fact_ebt = make_fact(
        StatementType.INCOME_STATEMENT, "500", p, CanonicalConcept.PRETAX_INCOME
    )
    fact_tax = make_fact(
        StatementType.INCOME_STATEMENT, "100", p, CanonicalConcept.INCOME_TAX_EXPENSE
    )
    # CapEx = -200 (magnitude 200)
    fact_capex = make_fact(
        StatementType.CASH_FLOW, "-200", p, CanonicalConcept.CAPITAL_EXPENDITURES
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.CASH_FLOW, p, [fact_cfo, fact_capex]),
            make_statement(
                StatementType.INCOME_STATEMENT, p, [fact_int, fact_ebt, fact_tax]
            ),
        ]
    )

    # FCFF_CFO = CFO (700) + [Interest (80) * (1 - 0.20)] - CapEx (200)
    # = 700 + 64 - 200 = 564
    res = FreeCashFlowEngine.calculate_fcff_cfo(p, store)
    assert res.status == MetricStatus.VALID
    assert res.metric_id == FundamentalMetricId.FCFF_CFO
    assert res.value == Decimal("564")
    assert "FORMULA_FCFF_CFO_ACCRUAL_INTEREST_V1" in res.provenance.formula_id
    codes = [d.code for d in res.diagnostics]
    assert DiagnosticCode.ACCRUAL_INTEREST_CFO_RECONCILIATION_NOTE in codes


def test_fcff_reconciliation_fallback_promotion():
    p_curr = make_period("2024-12-31", period_type=PeriodType.DURATION)

    # No D&A or balance sheets provided, so Primary NOPAT FCFF is unavailable
    # CFO = 800, Interest = 100, Pretax = 400, Tax = 100 (ETR = 25%), CapEx = 250
    fact_cfo = make_fact(
        StatementType.CASH_FLOW, "800", p_curr, CanonicalConcept.OPERATING_CASH_FLOW
    )
    fact_capex = make_fact(
        StatementType.CASH_FLOW, "-250", p_curr, CanonicalConcept.CAPITAL_EXPENDITURES
    )
    fact_int = make_fact(
        StatementType.INCOME_STATEMENT, "100", p_curr, source_concept="Interest Expense"
    )
    fact_ebt = make_fact(
        StatementType.INCOME_STATEMENT, "400", p_curr, CanonicalConcept.PRETAX_INCOME
    )
    fact_tax = make_fact(
        StatementType.INCOME_STATEMENT,
        "100",
        p_curr,
        CanonicalConcept.INCOME_TAX_EXPENSE,
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.CASH_FLOW, p_curr, [fact_cfo, fact_capex]),
            make_statement(
                StatementType.INCOME_STATEMENT, p_curr, [fact_int, fact_ebt, fact_tax]
            ),
        ]
    )

    rec = FreeCashFlowEngine.calculate_fcff_reconciliation(p_curr, None, store)
    # Primary FCFF promoted from CFO fallback
    assert rec.fcff_primary.status == MetricStatus.VALID
    # 800 + [100 * (1 - 0.25)] - 250 = 800 + 75 - 250 = 625
    assert rec.fcff_primary.value == Decimal("625")
    codes = [d.code for d in rec.fcff_primary.diagnostics]
    assert DiagnosticCode.FCFF_PROMOTED_CFO_FALLBACK in codes


def test_fcfe_with_tier1_net_borrowing_and_preferred_dividends():
    p = make_period("2024-12-31", period_type=PeriodType.DURATION)

    # CFO = 1000, CapEx = -300
    fact_cfo = make_fact(
        StatementType.CASH_FLOW, "1000", p, CanonicalConcept.OPERATING_CASH_FLOW
    )
    fact_capex = make_fact(
        StatementType.CASH_FLOW, "-300", p, CanonicalConcept.CAPITAL_EXPENDITURES
    )

    # Debt Issued = 200, Debt Repaid = -50 -> Net Borrowing = 150
    fact_d_iss = make_fact(
        StatementType.CASH_FLOW, "200", p, source_concept="Issuance Of Debt"
    )
    fact_d_rep = make_fact(
        StatementType.CASH_FLOW, "-50", p, source_concept="Repayment Of Debt"
    )

    # Preferred Dividends = -40 (magnitude 40)
    fact_pref_div = make_fact(
        StatementType.CASH_FLOW,
        "-40",
        p,
        source_concept="Preferred Stock Dividends Paid",
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.CASH_FLOW,
                p,
                [fact_cfo, fact_capex, fact_d_iss, fact_d_rep, fact_pref_div],
            )
        ]
    )

    # FCFE = CFO (1000) - CapEx (300) + Net Borrowing (150) - Preferred Divs (40)
    # = 1000 - 300 + 150 - 40 = 810
    res = FreeCashFlowEngine.calculate_fcfe(p, store)
    assert res.status == MetricStatus.VALID
    assert res.metric_id == FundamentalMetricId.FCFE
    assert res.value == Decimal("810")
    assert "FORMULA_FCFE_COMMON_V1" in res.provenance.formula_id


def test_fcfe_verified_debt_free_firm():
    p = make_period("2024-12-31", period_type=PeriodType.DURATION)
    p_inst = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # CFO = 500, CapEx = -100
    fact_cfo = make_fact(
        StatementType.CASH_FLOW, "500", p, CanonicalConcept.OPERATING_CASH_FLOW
    )
    fact_capex = make_fact(
        StatementType.CASH_FLOW, "-100", p, CanonicalConcept.CAPITAL_EXPENDITURES
    )

    # Balance sheet has zero debt
    fact_st_debt = make_fact(
        StatementType.BALANCE_SHEET, "0", p_inst, source_concept="Current Debt"
    )
    fact_lt_debt = make_fact(
        StatementType.BALANCE_SHEET, "0", p_inst, CanonicalConcept.LONG_TERM_DEBT
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.CASH_FLOW, p, [fact_cfo, fact_capex]),
            make_statement(
                StatementType.BALANCE_SHEET, p_inst, [fact_st_debt, fact_lt_debt]
            ),
        ]
    )

    # FCFE = 500 - 100 + 0 - 0 = 400 with ZERO_NET_BORROWING_VERIFIED
    res = FreeCashFlowEngine.calculate_fcfe(p, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("400")
    codes = [d.code for d in res.diagnostics]
    assert DiagnosticCode.ZERO_NET_BORROWING_VERIFIED in codes
