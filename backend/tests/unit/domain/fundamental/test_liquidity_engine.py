"""
tests.unit.domain.fundamental.test_liquidity_engine
===================================================
Deterministic tests for LiquidityEngine: Working Capital, Current Ratio,
Quick Ratio, Cash Ratio, unclassified balance sheets, and zero liabilities.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.liquidity import LiquidityEngine
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    MetricStatus,
)
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)


def test_liquidity_ratios_normal():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    fact_ca = make_fact(
        StatementType.BALANCE_SHEET, "500", p, CanonicalConcept.CURRENT_ASSETS
    )
    fact_cl = make_fact(
        StatementType.BALANCE_SHEET, "250", p, CanonicalConcept.CURRENT_LIABILITIES
    )
    fact_cash = make_fact(
        StatementType.BALANCE_SHEET, "100", p, CanonicalConcept.CASH_AND_EQUIVALENTS
    )
    fact_st_inv = make_fact(
        StatementType.BALANCE_SHEET, "50", p, CanonicalConcept.SHORT_TERM_INVESTMENTS
    )
    fact_ar = make_fact(
        StatementType.BALANCE_SHEET, "150", p, CanonicalConcept.ACCOUNTS_RECEIVABLE
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.BALANCE_SHEET,
                p,
                [fact_ca, fact_cl, fact_cash, fact_st_inv, fact_ar],
            )
        ]
    )

    # Working Capital: 500 - 250 = 250
    wc_res = LiquidityEngine.calculate_working_capital(p, store)
    assert wc_res.status == MetricStatus.VALID
    assert wc_res.value == Decimal("250")

    # Current Ratio: 500 / 250 = 2.0x
    cr_res = LiquidityEngine.calculate_current_ratio(p, store)
    assert cr_res.status == MetricStatus.VALID
    assert cr_res.value == Decimal("2")
    assert cr_res.formatted_value == "2.00x"

    # Quick Ratio: (100 + 50 + 150) / 250 = 300 / 250 = 1.2x
    qr_res = LiquidityEngine.calculate_quick_ratio(p, store)
    assert qr_res.status == MetricStatus.VALID
    assert qr_res.value == Decimal("1.2")
    assert qr_res.formatted_value == "1.20x"

    # Cash Ratio: (100 + 50) / 250 = 150 / 250 = 0.6x
    cash_res = LiquidityEngine.calculate_cash_ratio(p, store)
    assert cash_res.status == MetricStatus.VALID
    assert cash_res.value == Decimal("0.6")
    assert cash_res.formatted_value == "0.60x"


def test_unclassified_balance_sheet():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    # Bank with no current assets/liabilities
    fact_assets = make_fact(
        StatementType.BALANCE_SHEET, "10000", p, CanonicalConcept.TOTAL_ASSETS
    )
    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_assets])]
    )

    cr_res = LiquidityEngine.calculate_current_ratio(p, store)
    assert cr_res.status == MetricStatus.NOT_APPLICABLE
    assert any(
        d.code == DiagnosticCode.UNCLASSIFIED_BALANCE_SHEET for d in cr_res.diagnostics
    )


def test_zero_current_liabilities_distorted():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_ca = make_fact(
        StatementType.BALANCE_SHEET, "500", p, CanonicalConcept.CURRENT_ASSETS
    )
    fact_cl = make_fact(
        StatementType.BALANCE_SHEET, "0", p, CanonicalConcept.CURRENT_LIABILITIES
    )
    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_ca, fact_cl])]
    )

    cr_res = LiquidityEngine.calculate_current_ratio(p, store)
    assert cr_res.status == MetricStatus.DISTORTED
    assert any(d.code == DiagnosticCode.ZERO_DIVISION for d in cr_res.diagnostics)
