"""
tests.unit.domain.fundamental.test_diagnostics_engine
=====================================================
Unit tests for Sloan Accruals and Operating Quality Ratio with multi-period persistence.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FiscalPeriodType,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.diagnostics_engine import DiagnosticsEngine
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


def test_sloan_accruals_normal_and_warning_threshold():
    p_prior = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )
    p_curr = make_period("2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024)
    p_dur = make_period("2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024)

    # Assets: 2023 = 1000, 2024 = 1000 -> Avg Assets = 1000
    # 2023 BS: CA = 400, Cash = 100, CL = 200, STD = 50
    # 2024 BS: CA = 600 (ΔCA = 200), Cash = 100 (ΔCash = 0)
    #          CL = 200 (ΔCL = 0), STD = 50 (ΔSTD = 0)
    # Dep = 50
    # Accruals = [(200 - 0) - (0 - 0) - 50] / 1000 = (200 - 50) / 1000 = 150 / 1000 = +0.15 (> +0.10)
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
                "400.0",
                p_prior,
                CanonicalConcept.CURRENT_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "100.0",
                p_prior,
                CanonicalConcept.CASH_AND_EQUIVALENTS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "200.0",
                p_prior,
                CanonicalConcept.CURRENT_LIABILITIES,
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
                "600.0",
                p_curr,
                CanonicalConcept.CURRENT_ASSETS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "100.0",
                p_curr,
                CanonicalConcept.CASH_AND_EQUIVALENTS,
            ),
            make_fact(
                StatementType.BALANCE_SHEET,
                "200.0",
                p_curr,
                CanonicalConcept.CURRENT_LIABILITIES,
            ),
        ],
    )

    f_dep = make_fact(
        StatementType.CASH_FLOW,
        "50.0",
        p_dur,
        source_concept="Depreciation And Amortization",
    )
    s_cf_24 = make_statement(StatementType.CASH_FLOW, p_dur, [f_dep])

    store = MultiPeriodFactStore([s_bs_23, s_bs_24, s_cf_24])

    res = DiagnosticsEngine.calculate_sloan_accruals(p_dur, p_prior, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("0.15")
    # Verified threshold > +0.10 triggers WARNING
    assert any(d.code == DiagnosticCode.SLOAN_ACCRUALS_WARNING for d in res.diagnostics)
    warning = next(
        d for d in res.diagnostics if d.code == DiagnosticCode.SLOAN_ACCRUALS_WARNING
    )
    assert (
        "Requires further investigation: High accruals relative to total assets."
        in warning.message
    )


def test_sloan_accruals_missing_prior_period():
    p_dur = make_period("2024-12-31")
    store = MultiPeriodFactStore([])
    res = DiagnosticsEngine.calculate_sloan_accruals(p_dur, None, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert any(d.code == DiagnosticCode.MISSING_PRIOR_PERIOD for d in res.diagnostics)


def test_oqr_single_period_positive_and_non_positive_ebit():
    p = make_period("2024-12-31")

    # Positive EBIT
    f_cfo = make_fact(
        StatementType.CASH_FLOW, "90.0", p, CanonicalConcept.OPERATING_CASH_FLOW
    )
    f_ebit = make_fact(
        StatementType.INCOME_STATEMENT, "100.0", p, CanonicalConcept.OPERATING_INCOME
    )
    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.CASH_FLOW, p, [f_cfo]),
            make_statement(StatementType.INCOME_STATEMENT, p, [f_ebit]),
        ]
    )

    res = DiagnosticsEngine.calculate_single_period_oqr(p, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("0.90")

    # Non-positive EBIT
    f_ebit_neg = make_fact(
        StatementType.INCOME_STATEMENT, "-50.0", p, CanonicalConcept.OPERATING_INCOME
    )
    store_neg = MultiPeriodFactStore(
        [
            make_statement(StatementType.CASH_FLOW, p, [f_cfo]),
            make_statement(StatementType.INCOME_STATEMENT, p, [f_ebit_neg]),
        ]
    )

    res_neg = DiagnosticsEngine.calculate_single_period_oqr(p, store_neg)
    assert res_neg.status == MetricStatus.UNAVAILABLE
    assert any(d.code == DiagnosticCode.NON_POSITIVE_EBIT for d in res_neg.diagnostics)


def test_oqr_persistence_one_period_vs_two_periods():
    p23 = make_period("2023-12-31", fiscal_year=2023)
    p24 = make_period("2024-12-31", fiscal_year=2024)

    # 2023: CFO = 90, EBIT = 100 -> OQR = 0.90 (>= 0.80)
    # 2024: CFO = 70, EBIT = 100 -> OQR = 0.70 (< 0.80)
    f_cfo_23 = make_fact(
        StatementType.CASH_FLOW, "90.0", p23, CanonicalConcept.OPERATING_CASH_FLOW
    )
    f_ebit_23 = make_fact(
        StatementType.INCOME_STATEMENT, "100.0", p23, CanonicalConcept.OPERATING_INCOME
    )
    f_cfo_24 = make_fact(
        StatementType.CASH_FLOW, "70.0", p24, CanonicalConcept.OPERATING_CASH_FLOW
    )
    f_ebit_24 = make_fact(
        StatementType.INCOME_STATEMENT, "100.0", p24, CanonicalConcept.OPERATING_INCOME
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.CASH_FLOW, p23, [f_cfo_23]),
            make_statement(StatementType.INCOME_STATEMENT, p23, [f_ebit_23]),
            make_statement(StatementType.CASH_FLOW, p24, [f_cfo_24]),
            make_statement(StatementType.INCOME_STATEMENT, p24, [f_ebit_24]),
        ]
    )

    # 1 period below threshold -> INFORMATIONAL only, NO warning!
    res_1period = DiagnosticsEngine.evaluate_oqr_with_persistence(
        p24, [p23, p24], FiscalPeriodType.ANNUAL, store
    )
    assert res_1period.status == MetricStatus.VALID
    assert res_1period.value == Decimal("0.70")
    assert not any(
        d.code == DiagnosticCode.CFO_EBIT_DIVERGENCE_WARNING
        for d in res_1period.diagnostics
    )

    # Now make 2023 also below threshold: CFO = 60, EBIT = 100 -> OQR = 0.60
    f_cfo_23_low = make_fact(
        StatementType.CASH_FLOW, "60.0", p23, CanonicalConcept.OPERATING_CASH_FLOW
    )
    store2 = MultiPeriodFactStore(
        [
            make_statement(StatementType.CASH_FLOW, p23, [f_cfo_23_low]),
            make_statement(StatementType.INCOME_STATEMENT, p23, [f_ebit_23]),
            make_statement(StatementType.CASH_FLOW, p24, [f_cfo_24]),
            make_statement(StatementType.INCOME_STATEMENT, p24, [f_ebit_24]),
        ]
    )

    # Exactly 2 consecutive periods -> WARNING!
    res_2period = DiagnosticsEngine.evaluate_oqr_with_persistence(
        p24, [p23, p24], FiscalPeriodType.ANNUAL, store2
    )
    assert res_2period.status == MetricStatus.VALID
    assert any(
        d.code == DiagnosticCode.CFO_EBIT_DIVERGENCE_WARNING
        for d in res_2period.diagnostics
    )
    warning = next(
        d
        for d in res_2period.diagnostics
        if d.code == DiagnosticCode.CFO_EBIT_DIVERGENCE_WARNING
    )
    assert (
        "Requires further investigation: Operating cash flow has lagged EBIT for 2 consecutive periods."
        in warning.message
    )


def test_oqr_persistence_sequence_break_by_negative_ebit():
    p22 = make_period("2022-12-31", fiscal_year=2022)
    p23 = make_period("2023-12-31", fiscal_year=2023)
    p24 = make_period("2024-12-31", fiscal_year=2024)

    # 2022: OQR = 0.60 (< 0.80)
    # 2023: EBIT = -50 (negative -> breaks sequence, resets streak)
    # 2024: OQR = 0.70 (< 0.80)
    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.CASH_FLOW,
                p22,
                [
                    make_fact(
                        StatementType.CASH_FLOW,
                        "60.0",
                        p22,
                        CanonicalConcept.OPERATING_CASH_FLOW,
                    )
                ],
            ),
            make_statement(
                StatementType.INCOME_STATEMENT,
                p22,
                [
                    make_fact(
                        StatementType.INCOME_STATEMENT,
                        "100.0",
                        p22,
                        CanonicalConcept.OPERATING_INCOME,
                    )
                ],
            ),
            make_statement(
                StatementType.CASH_FLOW,
                p23,
                [
                    make_fact(
                        StatementType.CASH_FLOW,
                        "60.0",
                        p23,
                        CanonicalConcept.OPERATING_CASH_FLOW,
                    )
                ],
            ),
            make_statement(
                StatementType.INCOME_STATEMENT,
                p23,
                [
                    make_fact(
                        StatementType.INCOME_STATEMENT,
                        "-50.0",
                        p23,
                        CanonicalConcept.OPERATING_INCOME,
                    )
                ],
            ),
            make_statement(
                StatementType.CASH_FLOW,
                p24,
                [
                    make_fact(
                        StatementType.CASH_FLOW,
                        "70.0",
                        p24,
                        CanonicalConcept.OPERATING_CASH_FLOW,
                    )
                ],
            ),
            make_statement(
                StatementType.INCOME_STATEMENT,
                p24,
                [
                    make_fact(
                        StatementType.INCOME_STATEMENT,
                        "100.0",
                        p24,
                        CanonicalConcept.OPERATING_INCOME,
                    )
                ],
            ),
        ]
    )

    res = DiagnosticsEngine.evaluate_oqr_with_persistence(
        p24, [p22, p23, p24], FiscalPeriodType.ANNUAL, store
    )
    assert res.status == MetricStatus.VALID
    # Streak was reset by 2023 negative EBIT -> NO warning!
    assert not any(
        d.code == DiagnosticCode.CFO_EBIT_DIVERGENCE_WARNING for d in res.diagnostics
    )
