"""
tests.unit.domain.fundamental.test_dupont_engine
================================================
Unit tests for 3-Step and 5-Step DuPont ROE decomposition and reconciliation.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.dupont import DuPontEngine
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


def test_3step_and_5step_dupont_normal_reconciled():
    p_prior = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )
    p_curr = make_period("2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024)
    p_dur = make_period("2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024)

    # Balance Sheet:
    # 2023: Assets = 1000, Equity = 500
    # 2024: Assets = 1000, Equity = 500 -> Avg Assets = 1000, Avg Equity = 500
    # EM = 1000 / 500 = 2.0
    s_bs_23 = make_statement(
        StatementType.BALANCE_SHEET,
        p_prior,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "1000.0",
                p_prior,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "500.0",
                p_prior,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
        ],
    )
    s_bs_24 = make_statement(
        StatementType.BALANCE_SHEET,
        p_curr,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "1000.0",
                p_curr,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "500.0",
                p_curr,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
        ],
    )

    # Income Statement:
    # Rev = 2000 -> AT = 2000 / 1000 = 2.0
    # EBIT = 400 -> EBIT Margin = 400 / 2000 = 0.20
    # EBT = 300 -> Int Burden = 300 / 400 = 0.75
    # NI = 240 -> Tax Burden = 240 / 300 = 0.80, NPM = 240 / 2000 = 0.12
    # Direct ROE = 240 / 500 = 0.48
    s_is_24 = make_statement(
        StatementType.INCOME_STATEMENT,
        p_dur,
        [
            make_fact(
                StatementType.INCOME_STATEMENT,
                "2000.0",
                p_dur,
                CanonicalConcept.REVENUE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "400.0",
                p_dur,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "300.0",
                p_dur,
                CanonicalConcept.PRETAX_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "240.0",
                p_dur,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )

    store = MultiPeriodFactStore([s_bs_23, s_bs_24, s_is_24])

    # 1. 3-step DuPont
    # ROE = NPM (0.12) * AT (2.0) * EM (2.0) = 0.48
    res3 = DuPontEngine.calculate_3step_dupont(p_dur, p_prior, store)
    assert res3.net_profit_margin.status == MetricStatus.VALID
    assert res3.asset_turnover.status == MetricStatus.VALID
    assert res3.equity_multiplier.status == MetricStatus.VALID
    assert res3.reconstructed_roe.status == MetricStatus.VALID
    assert res3.reconstructed_roe.value == Decimal("0.48")
    assert res3.direct_roe.value == Decimal("0.48")
    assert res3.is_reconciled is True
    assert res3.reconciliation_discrepancy <= Decimal("0.0001")

    # 2. 5-step DuPont
    # ROE = TB (0.80) * IB (0.75) * EBIT Margin (0.20) * AT (2.0) * EM (2.0)
    # = 0.60 * 0.20 * 4.0 = 0.48
    res5 = DuPontEngine.calculate_5step_dupont(p_dur, p_prior, store)
    assert res5.tax_burden.status == MetricStatus.VALID
    assert res5.interest_burden.status == MetricStatus.VALID
    assert res5.ebit_margin.status == MetricStatus.VALID
    assert res5.reconstructed_roe.status == MetricStatus.VALID
    assert res5.reconstructed_roe.value == Decimal("0.48")
    assert res5.is_reconciled is True
    assert res5.reconciliation_discrepancy <= Decimal("0.0001")


def test_dupont_zero_ebt_and_ebit():
    p_dur = make_period("2024-12-31")

    # EBT = 0
    s_is_zero_ebt = make_statement(
        StatementType.INCOME_STATEMENT,
        p_dur,
        [
            make_fact(
                StatementType.INCOME_STATEMENT,
                "1000.0",
                p_dur,
                CanonicalConcept.REVENUE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "100.0",
                p_dur,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "0.0",
                p_dur,
                CanonicalConcept.PRETAX_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "0.0",
                p_dur,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )
    store = MultiPeriodFactStore([s_is_zero_ebt])

    res5 = DuPontEngine.calculate_5step_dupont(
        p_dur, None, store, allow_point_in_time_fallback=True
    )
    assert res5.tax_burden.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.ZERO_PRETAX_INCOME for d in res5.tax_burden.diagnostics
    )
    assert res5.reconstructed_roe.status == MetricStatus.UNAVAILABLE

    # EBIT = 0
    s_is_zero_ebit = make_statement(
        StatementType.INCOME_STATEMENT,
        p_dur,
        [
            make_fact(
                StatementType.INCOME_STATEMENT,
                "1000.0",
                p_dur,
                CanonicalConcept.REVENUE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "0.0",
                p_dur,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "50.0",
                p_dur,
                CanonicalConcept.PRETAX_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "40.0",
                p_dur,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )
    store2 = MultiPeriodFactStore([s_is_zero_ebit])
    res5_ebit0 = DuPontEngine.calculate_5step_dupont(
        p_dur, None, store2, allow_point_in_time_fallback=True
    )
    assert res5_ebit0.interest_burden.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.ZERO_OPERATING_INCOME
        for d in res5_ebit0.interest_burden.diagnostics
    )
    assert res5_ebit0.reconstructed_roe.status == MetricStatus.UNAVAILABLE


def test_dupont_negative_ebt_and_ebit_distorted():
    p_dur = make_period("2024-12-31")

    # EBT < 0
    s_is_neg_ebt = make_statement(
        StatementType.INCOME_STATEMENT,
        p_dur,
        [
            make_fact(
                StatementType.INCOME_STATEMENT,
                "1000.0",
                p_dur,
                CanonicalConcept.REVENUE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "50.0",
                p_dur,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "-20.0",
                p_dur,
                CanonicalConcept.PRETAX_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "-15.0",
                p_dur,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )
    s_bs = make_statement(
        StatementType.BALANCE_SHEET,
        p_dur,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "1000.0",
                p_dur,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "500.0",
                p_dur,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
        ],
    )
    store = MultiPeriodFactStore([s_is_neg_ebt, s_bs])

    res5 = DuPontEngine.calculate_5step_dupont(
        p_dur, None, store, allow_point_in_time_fallback=True
    )
    assert res5.tax_burden.status == MetricStatus.DISTORTED
    assert any(
        d.code == DiagnosticCode.DISTORTED_PRETAX_EARNINGS
        for d in res5.tax_burden.diagnostics
    )
    assert res5.reconstructed_roe.status == MetricStatus.DISTORTED


def test_dupont_non_positive_assets_and_equity():
    p_dur = make_period("2024-12-31")
    s_is = make_statement(
        StatementType.INCOME_STATEMENT,
        p_dur,
        [
            make_fact(
                StatementType.INCOME_STATEMENT,
                "1000.0",
                p_dur,
                CanonicalConcept.REVENUE,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "100.0",
                p_dur,
                CanonicalConcept.OPERATING_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "100.0",
                p_dur,
                CanonicalConcept.PRETAX_INCOME,
            ),
            make_fact(
                StatementType.INCOME_STATEMENT,
                "80.0",
                p_dur,
                CanonicalConcept.NET_INCOME,
            ),
        ],
    )

    # Negative equity
    s_bs_neg_eq = make_statement(
        StatementType.BALANCE_SHEET,
        p_dur,
        [
            make_fact(
                StatementType.BALANCE_SHEET,
                "500.0",
                p_dur,
                CanonicalConcept.TOTAL_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "-100.0",
                p_dur,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
            ),
        ],
    )
    store = MultiPeriodFactStore([s_is, s_bs_neg_eq])

    res3 = DuPontEngine.calculate_3step_dupont(
        p_dur, None, store, allow_point_in_time_fallback=True
    )
    assert res3.equity_multiplier.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.NON_POSITIVE_AVERAGE_EQUITY
        for d in res3.equity_multiplier.diagnostics
    )
    assert res3.reconstructed_roe.status == MetricStatus.UNAVAILABLE
