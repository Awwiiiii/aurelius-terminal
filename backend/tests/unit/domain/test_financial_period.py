"""
tests.unit.domain.test_financial_period
========================================
Unit tests for FinancialPeriod domain entity and temporal boundary validation.
"""

from datetime import date

import pytest

from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FiscalPeriodLabel,
    PeriodType,
)


def test_instant_period_valid():
    """
    INSTANT period represents a point in time (e.g. Balance sheet date).
    Requires instant_date and forbids end_date/start_date.
    """
    cutoff = date(2024, 9, 30)
    period = FinancialPeriod(
        period_type=PeriodType.INSTANT,
        instant_date=cutoff,
        calendar_year=2024,
    )
    assert period.period_type == PeriodType.INSTANT
    assert period.instant_date == cutoff
    assert period.end_date is None
    assert period.start_date is None
    assert period.period_key == "2024-09-30"


def test_instant_period_missing_instant_date_raises():
    with pytest.raises(ValueError, match="requires instant_date"):
        FinancialPeriod(
            period_type=PeriodType.INSTANT,
            instant_date=None,
        )


def test_instant_period_with_end_date_raises():
    with pytest.raises(ValueError, match="cannot have end_date"):
        FinancialPeriod(
            period_type=PeriodType.INSTANT,
            instant_date=date(2024, 9, 30),
            end_date=date(2024, 9, 30),
        )


def test_duration_period_valid():
    """
    DURATION period represents an interval (e.g. Income Statement / Cash Flow).
    Requires end_date and forbids instant_date.
    """
    start = date(2023, 10, 1)
    end = date(2024, 9, 30)
    period = FinancialPeriod(
        period_type=PeriodType.DURATION,
        start_date=start,
        end_date=end,
        fiscal_year=2024,
        fiscal_period=FiscalPeriodLabel.FY,
        is_period_label_source_reported=True,
    )
    assert period.period_type == PeriodType.DURATION
    assert period.start_date == start
    assert period.end_date == end
    assert period.instant_date is None
    assert period.fiscal_period == FiscalPeriodLabel.FY
    assert period.is_period_label_source_reported is True
    assert period.period_key == "2024-09-30"


def test_duration_period_missing_end_date_raises():
    with pytest.raises(ValueError, match="requires end_date"):
        FinancialPeriod(
            period_type=PeriodType.DURATION,
            start_date=date(2023, 10, 1),
            end_date=None,
        )


def test_duration_period_with_instant_date_raises():
    with pytest.raises(ValueError, match="cannot have instant_date"):
        FinancialPeriod(
            period_type=PeriodType.DURATION,
            instant_date=date(2024, 9, 30),
            end_date=date(2024, 9, 30),
        )


def test_duration_period_start_after_end_raises():
    with pytest.raises(ValueError, match="start_date .* cannot be after end_date"):
        FinancialPeriod(
            period_type=PeriodType.DURATION,
            start_date=date(2024, 10, 1),
            end_date=date(2024, 9, 30),
        )


def test_source_reported_vs_derived_period_label():
    """
    Distinguishes whether fiscal period label was reported by source or derived.
    """
    # Derived period
    p_derived = FinancialPeriod(
        period_type=PeriodType.DURATION,
        end_date=date(2024, 9, 30),
        fiscal_period=FiscalPeriodLabel.FY,
        is_period_label_source_reported=False,
    )
    assert p_derived.is_period_label_source_reported is False

    # Source-reported period
    p_reported = FinancialPeriod(
        period_type=PeriodType.DURATION,
        end_date=date(2024, 9, 30),
        fiscal_period=FiscalPeriodLabel.Q3,
        is_period_label_source_reported=True,
    )
    assert p_reported.is_period_label_source_reported is True
