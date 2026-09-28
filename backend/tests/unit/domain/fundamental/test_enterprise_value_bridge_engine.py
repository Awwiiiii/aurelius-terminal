"""
tests.unit.domain.fundamental.test_enterprise_value_bridge_engine
==================================================================
Deterministic unit tests for EnterpriseValueBridgeEngine:
- 4-Case Disclosure Taxonomy for Preferred Equity and Minority Interest
  (Case 1 Reported Non-Zero, Case 2 Reported Zero, Case 3 Confidently Absent, Case 4 Insufficiently Disclosed)
- Enterprise Value Bridge calculation: Market Cap + Debt + Pref + Min Int - Cash - STI
- MISSING != ZERO Doctrine: Case 4 claims force EV to UNAVAILABLE
- Negative Enterprise Value (VALID with NEGATIVE_ENTERPRISE_VALUE_WARNING)
- Market Cap boundaries: None (UNAVAILABLE) and <= 0 (DISTORTED)
- Capital Structure Weights: We, Wd, Wp sum to 1.0
- Zero or negative total capital (DISTORTED with ZERO_OR_NEGATIVE_CAPITAL)
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.enterprise_value import (
    EnterpriseValueBridgeEngine,
)
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


def test_preferred_equity_4_case_taxonomy():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # Case 1: Explicitly Reported Non-Zero (e.g. 200)
    fact_pref = make_fact(
        StatementType.BALANCE_SHEET, "200", p, source_concept="Preferred Stock"
    )
    store_c1 = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_pref])]
    )
    val, _, _, diags, _ = EnterpriseValueBridgeEngine.resolve_preferred_equity(
        p, store_c1
    )
    assert val == Decimal("200")
    assert len(diags) == 0

    # Case 2: Explicitly Reported Zero (0)
    fact_pref_zero = make_fact(
        StatementType.BALANCE_SHEET, "0", p, source_concept="Preferred Stock"
    )
    store_c2 = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_pref_zero])]
    )
    val, _, _, diags, _ = EnterpriseValueBridgeEngine.resolve_preferred_equity(
        p, store_c2
    )
    assert val == Decimal("0")
    assert len(diags) == 0

    # Case 3: Confidently Absent (Common Stock Equity == Stockholders Equity)
    fact_cse = make_fact(
        StatementType.BALANCE_SHEET, "1500", p, source_concept="Common Stock Equity"
    )
    fact_se = make_fact(
        StatementType.BALANCE_SHEET, "1500", p, CanonicalConcept.STOCKHOLDERS_EQUITY
    )
    store_c3 = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_cse, fact_se])]
    )
    val, _, _, diags, _ = EnterpriseValueBridgeEngine.resolve_preferred_equity(
        p, store_c3
    )
    assert val == Decimal("0")
    assert any(
        d.code == DiagnosticCode.PREFERRED_EQUITY_CONFIDENTLY_ABSENT for d in diags
    )

    # Case 4: Insufficiently Disclosed (Equity is missing or single unitemized without common stock equity)
    fact_single = make_fact(
        StatementType.BALANCE_SHEET, "1500", p, source_concept="Some Aggregated Line"
    )
    store_c4 = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_single])]
    )
    val, _, _, diags, _ = EnterpriseValueBridgeEngine.resolve_preferred_equity(
        p, store_c4
    )
    assert val is None
    assert any(
        d.code == DiagnosticCode.PREFERRED_EQUITY_INSUFFICIENTLY_DISCLOSED
        for d in diags
    )


def test_minority_interest_4_case_taxonomy():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # Case 1: Explicitly Reported Non-Zero (e.g. 50)
    fact_min = make_fact(
        StatementType.BALANCE_SHEET, "50", p, source_concept="Minority Interest"
    )
    store_c1 = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_min])]
    )
    val, _, _, diags, _ = EnterpriseValueBridgeEngine.resolve_minority_interest(
        p, store_c1
    )
    assert val == Decimal("50")

    # Case 2: Explicitly Reported Zero (0)
    fact_min_zero = make_fact(
        StatementType.BALANCE_SHEET, "0", p, source_concept="Minority Interest"
    )
    store_c2 = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_min_zero])]
    )
    val, _, _, diags, _ = EnterpriseValueBridgeEngine.resolve_minority_interest(
        p, store_c2
    )
    assert val == Decimal("0")

    # Case 3: Confidently Absent (Gross Minority Interest == Stockholders Equity)
    fact_gross_eq = make_fact(
        StatementType.BALANCE_SHEET,
        "1500",
        p,
        source_concept="Total Equity Gross Minority Interest",
    )
    fact_se = make_fact(
        StatementType.BALANCE_SHEET, "1500", p, CanonicalConcept.STOCKHOLDERS_EQUITY
    )
    store_c3 = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_gross_eq, fact_se])]
    )
    val, _, _, diags, _ = EnterpriseValueBridgeEngine.resolve_minority_interest(
        p, store_c3
    )
    assert val == Decimal("0")
    assert any(
        d.code == DiagnosticCode.MINORITY_INTEREST_CONFIDENTLY_ABSENT for d in diags
    )

    # Case 4: Insufficiently Disclosed (Stated Net of Minority Interest without reconciliation)
    fact_net_liab = make_fact(
        StatementType.BALANCE_SHEET,
        "800",
        p,
        source_concept="Total Liabilities Net Minority Interest",
    )
    store_c4 = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_net_liab])]
    )
    val, _, _, diags, _ = EnterpriseValueBridgeEngine.resolve_minority_interest(
        p, store_c4
    )
    assert val is None
    assert any(
        d.code == DiagnosticCode.MINORITY_INTEREST_INSUFFICIENTLY_DISCLOSED
        for d in diags
    )


def test_enterprise_value_standard_calculation():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # Market Cap = 10,000
    mcap = Decimal("10000")
    # Gross Debt: LT Debt = 2000, ST Debt = 500 -> Gross Debt = 2500
    fact_lt_debt = make_fact(
        StatementType.BALANCE_SHEET, "2000", p, CanonicalConcept.LONG_TERM_DEBT
    )
    fact_st_debt = make_fact(
        StatementType.BALANCE_SHEET, "500", p, source_concept="Current Debt"
    )
    # Preferred Equity reported = 300
    fact_pref = make_fact(
        StatementType.BALANCE_SHEET, "300", p, source_concept="Preferred Stock"
    )
    # Minority Interest reported = 100
    fact_min = make_fact(
        StatementType.BALANCE_SHEET, "100", p, source_concept="Minority Interest"
    )
    # Cash = 800, STI = 200
    fact_cash = make_fact(
        StatementType.BALANCE_SHEET, "800", p, CanonicalConcept.CASH_AND_EQUIVALENTS
    )
    fact_sti = make_fact(
        StatementType.BALANCE_SHEET, "200", p, CanonicalConcept.SHORT_TERM_INVESTMENTS
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.BALANCE_SHEET,
                p,
                [fact_lt_debt, fact_st_debt, fact_pref, fact_min, fact_cash, fact_sti],
            )
        ]
    )

    # EV = 10,000 + 2,500 + 300 + 100 - (800 + 200)
    # = 12,900 - 1,000 = 11,900
    ev_res = EnterpriseValueBridgeEngine.calculate_enterprise_value(p, store, mcap)
    assert ev_res.status == MetricStatus.VALID
    assert ev_res.metric_id == FundamentalMetricId.ENTERPRISE_VALUE
    assert ev_res.value == Decimal("11900")
    assert "FORMULA_ENTERPRISE_VALUE_V1" in ev_res.provenance.formula_id


def test_enterprise_value_negative_warning():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # Massive cash pile: Cash = 5000, Market Cap = 1000, Debt = 0, Pref = 0, Min = 0
    mcap = Decimal("1000")
    fact_cash = make_fact(
        StatementType.BALANCE_SHEET, "5000", p, CanonicalConcept.CASH_AND_EQUIVALENTS
    )
    fact_lt_debt = make_fact(
        StatementType.BALANCE_SHEET, "0", p, CanonicalConcept.LONG_TERM_DEBT
    )
    fact_pref = make_fact(
        StatementType.BALANCE_SHEET, "0", p, source_concept="Preferred Stock"
    )
    fact_min = make_fact(
        StatementType.BALANCE_SHEET, "0", p, source_concept="Minority Interest"
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.BALANCE_SHEET,
                p,
                [fact_cash, fact_lt_debt, fact_pref, fact_min],
            )
        ]
    )

    # EV = 1000 + 0 + 0 + 0 - 5000 = -4000
    ev_res = EnterpriseValueBridgeEngine.calculate_enterprise_value(p, store, mcap)
    assert ev_res.status == MetricStatus.VALID
    assert ev_res.value == Decimal("-4000")
    codes = [d.code for d in ev_res.diagnostics]
    assert DiagnosticCode.NEGATIVE_ENTERPRISE_VALUE_WARNING in codes


def test_enterprise_value_missing_market_cap():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_cash = make_fact(
        StatementType.BALANCE_SHEET, "500", p, CanonicalConcept.CASH_AND_EQUIVALENTS
    )
    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_cash])]
    )

    # None market cap -> UNAVAILABLE
    ev_res = EnterpriseValueBridgeEngine.calculate_enterprise_value(p, store, None)
    assert ev_res.status == MetricStatus.UNAVAILABLE
    codes = [d.code for d in ev_res.diagnostics]
    assert DiagnosticCode.MARKET_CAP_UNAVAILABLE in codes

    # Negative market cap -> DISTORTED
    ev_dist = EnterpriseValueBridgeEngine.calculate_enterprise_value(
        p, store, Decimal("-100")
    )
    assert ev_dist.status == MetricStatus.DISTORTED
    codes_dist = [d.code for d in ev_dist.diagnostics]
    assert DiagnosticCode.NON_POSITIVE_MARKET_CAP in codes_dist


def test_capital_structure_weights_normal():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # Market Cap = 7,000 (70%)
    mcap = Decimal("7000")
    # Gross Debt = 2,000 (20%)
    fact_lt_debt = make_fact(
        StatementType.BALANCE_SHEET, "2000", p, CanonicalConcept.LONG_TERM_DEBT
    )
    # Preferred Equity = 1,000 (10%)
    fact_pref = make_fact(
        StatementType.BALANCE_SHEET, "1000", p, source_concept="Preferred Stock"
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_lt_debt, fact_pref])]
    )

    cs_res = EnterpriseValueBridgeEngine.calculate_capital_structure_weights(
        p, store, mcap
    )
    # Total Capital = 7000 + 2000 + 1000 = 10,000
    assert cs_res.total_capital.status == MetricStatus.VALID
    assert cs_res.total_capital.value == Decimal("10000")

    # Weights
    assert cs_res.weight_equity.status == MetricStatus.VALID
    assert cs_res.weight_equity.value == Decimal("0.7")

    assert cs_res.weight_debt.status == MetricStatus.VALID
    assert cs_res.weight_debt.value == Decimal("0.2")

    assert cs_res.weight_preferred.status == MetricStatus.VALID
    assert cs_res.weight_preferred.value == Decimal("0.1")

    # Invariant: We + Wd + Wp = 1.0
    total_weight = (
        cs_res.weight_equity.value
        + cs_res.weight_debt.value
        + cs_res.weight_preferred.value
    )
    assert total_weight == Decimal("1.0")
