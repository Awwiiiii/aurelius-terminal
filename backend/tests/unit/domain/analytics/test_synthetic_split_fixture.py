"""
Synthetic split-invariance test fixture
=======================================
Verifies that corporate-action adjustments (e.g. 2-for-1 stock split) maintain
return and drawdown continuity on provider adj_close, while technical levels
and extremes reflect nominal raw close execution prices.

Synthetic Data Scenario:
  - Day 1: Raw Close = 100.0, Adj Close = 50.0
  - Day 2: Raw Close = 102.0, Adj Close = 51.0 (+2.0% return)
  - 2-for-1 Stock Split occurs between Day 2 and Day 3
  - Day 3: Raw Close = 51.0,  Adj Close = 51.0 (0.0% return)
  - Day 4: Raw Close = 52.0,  Adj Close = 52.0 (+1.96% return)
"""

from datetime import date
from decimal import Decimal

from aurelius.domain.analytics.drawdowns import compute_drawdown_metrics
from aurelius.domain.analytics.indicators import compute_historical_extremes
from aurelius.domain.analytics.returns import (
    calculate_simple_daily_returns,
    compute_return_metrics,
)


def test_synthetic_split_invariance_returns_and_drawdowns():
    """
    Synthetic split-invariance test fixture:
    Verifies that returns and drawdowns computed on adj_close do NOT suffer
    an artificial 50% drawdown collapse due to the 2-for-1 split.
    """
    dates = [
        date(2023, 6, 1),
        date(2023, 6, 2),
        date(2023, 6, 5),  # Post-split
        date(2023, 6, 6),
    ]
    raw_close = [Decimal("100.0"), Decimal("102.0"), Decimal("51.0"), Decimal("52.0")]
    adj_close = [Decimal("50.0"), Decimal("51.0"), Decimal("51.0"), Decimal("52.0")]

    # 1. Daily returns on adj_close
    returns = calculate_simple_daily_returns(adj_close)
    assert returns[0] is None
    assert returns[1] == Decimal("0.02000000")  # (51 - 50) / 50 = +2%
    assert returns[2] == Decimal(
        "0.00000000"
    )  # (51 - 51) / 51 = 0% (NO -50% collapse!)
    assert returns[3] == Decimal("0.01960784")  # (52 - 51) / 51 ≈ +1.96%

    # 2. Return metrics on adj_close
    return_metrics = compute_return_metrics(adj_close, dates)
    # Total adjusted price return = (52 - 50) / 50 = +4.0%
    assert return_metrics.adjusted_price_return == Decimal("0.040000")
    assert return_metrics.positive_days == 2
    assert return_metrics.negative_days == 0
    assert return_metrics.zero_days == 1

    # 3. Drawdown on adj_close: prices never decline below running peak (50 -> 51 -> 51 -> 52)
    dd_metrics = compute_drawdown_metrics(adj_close, dates)
    assert dd_metrics.max_drawdown == Decimal("0.000000")
    assert dd_metrics.current_drawdown == Decimal("0.000000")

    # 4. Period extremes on raw_close: reflects actual nominal execution prices
    extremes = compute_historical_extremes(raw_close, dates)
    assert extremes.period_high == Decimal("102.0")
    assert extremes.period_high_date == date(2023, 6, 2)
    assert extremes.period_low == Decimal("51.0")
    assert extremes.period_low_date == date(2023, 6, 5)
    # Last raw price = 52.0
    # distance from high = (52 - 102) / 102 * 100 ≈ -49.02%
    assert extremes.distance_from_high == Decimal("-49.02")
    # distance from low = (52 - 51) / 51 * 100 ≈ +1.96%
    assert extremes.distance_from_low == Decimal("1.96")
