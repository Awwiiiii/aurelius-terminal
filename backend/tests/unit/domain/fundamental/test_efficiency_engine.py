"""
tests.unit.domain.fundamental.test_efficiency_engine
====================================================
Deterministic tests for EfficiencyEngine: Turnovers, DSO, DIO, DPO, CCC,
and verification that Inventory Turnover strictly uses Cost of Revenue.
"""

from datetime import date
from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FiscalPeriodLabel,
    FiscalPeriodType,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.efficiency import EfficiencyEngine
from aurelius.domain.fundamental.enums import DiagnosticCode, MetricStatus
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)


def test_efficiency_turnovers_and_ccc_normal():
    p_prior = make_period("2023-12-31", fiscal_year=2023)
    # Set explicit 365-day start_date: 2024-01-02 to 2024-12-31 (in leap year 2024, 364 + 1 = 365)
    p_curr = make_period(
        "2024-12-31",
        fiscal_year=2024,
        start_date=date(2024, 1, 2),
    )

    p_prior_inst = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )
    p_curr_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )

    # Income statement duration facts: Revenue = 1460, Cost of Revenue = 730
    fact_rev = make_fact(
        StatementType.INCOME_STATEMENT, "1460", p_curr, CanonicalConcept.REVENUE
    )
    fact_cogs = make_fact(
        StatementType.INCOME_STATEMENT, "730", p_curr, CanonicalConcept.COST_OF_REVENUE
    )

    # Balance sheet instant facts:
    # AR: prior = 100, curr = 100 => avg = 100
    fact_ar_prior = make_fact(
        StatementType.BALANCE_SHEET,
        "100",
        p_prior_inst,
        CanonicalConcept.ACCOUNTS_RECEIVABLE,
    )
    fact_ar_curr = make_fact(
        StatementType.BALANCE_SHEET,
        "100",
        p_curr_inst,
        CanonicalConcept.ACCOUNTS_RECEIVABLE,
    )

    # Inv: prior = 50, curr = 50 => avg = 50
    fact_inv_prior = make_fact(
        StatementType.BALANCE_SHEET, "50", p_prior_inst, CanonicalConcept.INVENTORY
    )
    fact_inv_curr = make_fact(
        StatementType.BALANCE_SHEET, "50", p_curr_inst, CanonicalConcept.INVENTORY
    )

    # AP: prior = 70, curr = 70 => avg = 70
    fact_ap_prior = make_fact(
        StatementType.BALANCE_SHEET,
        "70",
        p_prior_inst,
        CanonicalConcept.ACCOUNTS_PAYABLE,
    )
    fact_ap_curr = make_fact(
        StatementType.BALANCE_SHEET,
        "70",
        p_curr_inst,
        CanonicalConcept.ACCOUNTS_PAYABLE,
    )

    # Assets: prior = 1000, curr = 1000 => avg = 1000
    fact_assets_prior = make_fact(
        StatementType.BALANCE_SHEET, "1000", p_prior_inst, CanonicalConcept.TOTAL_ASSETS
    )
    fact_assets_curr = make_fact(
        StatementType.BALANCE_SHEET, "1000", p_curr_inst, CanonicalConcept.TOTAL_ASSETS
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.INCOME_STATEMENT, p_curr, [fact_rev, fact_cogs]
            ),
            make_statement(
                StatementType.BALANCE_SHEET,
                p_prior_inst,
                [fact_ar_prior, fact_inv_prior, fact_ap_prior, fact_assets_prior],
            ),
            make_statement(
                StatementType.BALANCE_SHEET,
                p_curr_inst,
                [fact_ar_curr, fact_inv_curr, fact_ap_curr, fact_assets_curr],
            ),
        ]
    )

    # Asset Turnover = 1460 / 1000 = 1.46x
    at_res = EfficiencyEngine.calculate_asset_turnover(p_curr, p_prior, store)
    assert at_res.status == MetricStatus.VALID
    assert at_res.value == Decimal("1.46")

    # Receivables Turnover = 1460 / 100 = 14.6x; DSO = 365 / 14.6 = 25.0 days
    rt_res = EfficiencyEngine.calculate_receivables_turnover(p_curr, p_prior, store)
    assert rt_res.status == MetricStatus.VALID
    assert rt_res.value == Decimal("14.6")
    dso_res = EfficiencyEngine.calculate_dso(p_curr, p_prior, store)
    assert dso_res.status == MetricStatus.VALID
    assert dso_res.value == Decimal("25")

    # Inventory Turnover = 730 / 50 = 14.6x (Using COGS, not Revenue!); DIO = 365 / 14.6 = 25.0 days
    it_res = EfficiencyEngine.calculate_inventory_turnover(p_curr, p_prior, store)
    assert it_res.status == MetricStatus.VALID
    assert it_res.value == Decimal("14.6")
    assert it_res.provenance.formula_id == "FORMULA_INVENTORY_TURNOVER_COGS"
    dio_res = EfficiencyEngine.calculate_dio(p_curr, p_prior, store)
    assert dio_res.status == MetricStatus.VALID
    assert dio_res.value == Decimal("25")

    # Payables Turnover = 730 / 70 = 10.42857...; DPO = (70 / 730) * 365 = 35.0 days
    dpo_res = EfficiencyEngine.calculate_dpo(p_curr, p_prior, store)
    assert dpo_res.status == MetricStatus.VALID
    assert dpo_res.value == Decimal("35")

    # Cash Conversion Cycle = DIO (25) + DSO (25) - DPO (35) = 15.0 days
    ccc_res = EfficiencyEngine.calculate_ccc(p_curr, p_prior, store)
    assert ccc_res.status == MetricStatus.VALID
    assert ccc_res.value == Decimal("15")


def test_efficiency_missing_duration_dates():
    p_curr = make_period("2024-12-31", fiscal_year=2024, start_date=None)
    store = MultiPeriodFactStore([])

    dso_res = EfficiencyEngine.calculate_dso(p_curr, None, store)
    assert dso_res.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.MISSING_REQUIRED_FACT for d in dso_res.diagnostics
    )


def test_efficiency_quarterly_90_day_quarter():
    # Q1: 2025-01-01 to 2025-03-31 = 90 days
    p_q1 = make_period(
        "2025-03-31",
        fiscal_year=2025,
        fiscal_period=FiscalPeriodLabel.Q1,
        start_date=date(2025, 1, 1),
    )
    p_q1_inst = make_period(
        "2025-03-31",
        period_type=PeriodType.INSTANT,
        fiscal_year=2025,
        fiscal_period=FiscalPeriodLabel.Q1,
    )

    # Rev = 900, COGS = 450
    fact_rev = make_fact(
        StatementType.INCOME_STATEMENT, "900", p_q1, CanonicalConcept.REVENUE
    )
    fact_cogs = make_fact(
        StatementType.INCOME_STATEMENT, "450", p_q1, CanonicalConcept.COST_OF_REVENUE
    )

    # Point-in-time fallback mode for balance sheet instant items
    fact_ar = make_fact(
        StatementType.BALANCE_SHEET,
        "100",
        p_q1_inst,
        CanonicalConcept.ACCOUNTS_RECEIVABLE,
    )
    fact_inv = make_fact(
        StatementType.BALANCE_SHEET, "50", p_q1_inst, CanonicalConcept.INVENTORY
    )
    fact_ap = make_fact(
        StatementType.BALANCE_SHEET, "90", p_q1_inst, CanonicalConcept.ACCOUNTS_PAYABLE
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.INCOME_STATEMENT,
                p_q1,
                [fact_rev, fact_cogs],
                frequency=FiscalPeriodType.QUARTERLY,
            ),
            make_statement(
                StatementType.BALANCE_SHEET,
                p_q1_inst,
                [fact_ar, fact_inv, fact_ap],
                frequency=FiscalPeriodType.QUARTERLY,
            ),
        ]
    )

    # DSO = (100 / 900) * 90 = 10.0 days
    dso_res = EfficiencyEngine.calculate_dso(
        p_q1, None, store, allow_point_in_time_fallback=True
    )
    assert dso_res.status == MetricStatus.VALID
    assert dso_res.value == Decimal("10")

    # DIO = (50 / 450) * 90 = 10.0 days
    dio_res = EfficiencyEngine.calculate_dio(
        p_q1, None, store, allow_point_in_time_fallback=True
    )
    assert dio_res.status == MetricStatus.VALID
    assert dio_res.value == Decimal("10")

    # DPO = (90 / 450) * 90 = 18.0 days
    dpo_res = EfficiencyEngine.calculate_dpo(
        p_q1, None, store, allow_point_in_time_fallback=True
    )
    assert dpo_res.status == MetricStatus.VALID
    assert dpo_res.value == Decimal("18")

    # CCC = 10 + 10 - 18 = 2.0 days
    ccc_res = EfficiencyEngine.calculate_ccc(
        p_q1, None, store, allow_point_in_time_fallback=True
    )
    assert ccc_res.status == MetricStatus.VALID
    assert ccc_res.value == Decimal("2")


def test_efficiency_quarterly_91_and_92_day_quarter():
    # 91-day quarter: 2025-04-01 to 2025-06-30 (30 + 31 + 30 = 91 days)
    p_91 = make_period(
        "2025-06-30",
        fiscal_year=2025,
        fiscal_period=FiscalPeriodLabel.Q2,
        start_date=date(2025, 4, 1),
    )
    p_91_inst = make_period(
        "2025-06-30", period_type=PeriodType.INSTANT, fiscal_year=2025
    )

    fact_rev_91 = make_fact(
        StatementType.INCOME_STATEMENT, "910", p_91, CanonicalConcept.REVENUE
    )
    fact_ar_91 = make_fact(
        StatementType.BALANCE_SHEET,
        "100",
        p_91_inst,
        CanonicalConcept.ACCOUNTS_RECEIVABLE,
    )

    store_91 = MultiPeriodFactStore(
        [
            make_statement(StatementType.INCOME_STATEMENT, p_91, [fact_rev_91]),
            make_statement(StatementType.BALANCE_SHEET, p_91_inst, [fact_ar_91]),
        ]
    )
    # DSO = (100 / 910) * 91 = 10.0 days
    dso_91 = EfficiencyEngine.calculate_dso(
        p_91, None, store_91, allow_point_in_time_fallback=True
    )
    assert dso_91.status == MetricStatus.VALID
    assert dso_91.value == Decimal("10")

    # 92-day quarter: 2025-07-01 to 2025-09-30 (31 + 31 + 30 = 92 days)
    p_92 = make_period(
        "2025-09-30",
        fiscal_year=2025,
        fiscal_period=FiscalPeriodLabel.Q3,
        start_date=date(2025, 7, 1),
    )
    p_92_inst = make_period(
        "2025-09-30", period_type=PeriodType.INSTANT, fiscal_year=2025
    )

    fact_rev_92 = make_fact(
        StatementType.INCOME_STATEMENT, "920", p_92, CanonicalConcept.REVENUE
    )
    fact_ar_92 = make_fact(
        StatementType.BALANCE_SHEET,
        "100",
        p_92_inst,
        CanonicalConcept.ACCOUNTS_RECEIVABLE,
    )

    store_92 = MultiPeriodFactStore(
        [
            make_statement(StatementType.INCOME_STATEMENT, p_92, [fact_rev_92]),
            make_statement(StatementType.BALANCE_SHEET, p_92_inst, [fact_ar_92]),
        ]
    )
    # DSO = (100 / 920) * 92 = 10.0 days
    dso_92 = EfficiencyEngine.calculate_dso(
        p_92, None, store_92, allow_point_in_time_fallback=True
    )
    assert dso_92.status == MetricStatus.VALID
    assert dso_92.value == Decimal("10")
