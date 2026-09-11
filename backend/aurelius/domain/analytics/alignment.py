"""
aurelius.domain.analytics.alignment
===================================
Multi-series chronological date alignment algorithms.

Financial Standards:
  - Strict Inner Date Alignment: Only trading session dates common to all
    participating securities are retained.
  - Zero Forward-Filling Policy: Missing dates are never forward-filled with
    stale prices, preventing the creation of artificial zero returns and
    distorted cross-asset correlations.
  - Chronological Ascending Order: Output series are strictly sorted (t_0 < t_1 < ... < t_{K-1}).
"""

from datetime import date
from decimal import Decimal


def inner_align_date_series(
    series_dict: dict[str, dict[date, Decimal]],
) -> tuple[list[date], dict[str, list[Decimal]]]:
    """
    Perform an inner date join across multiple date-keyed numerical series.

    Arguments:
      series_dict: Dictionary mapping series identifier (e.g. ticker) to
                   a dictionary of {date: value}.

    Returns:
      (common_dates, aligned_series_dict) where common_dates is sorted ascending
      and each list in aligned_series_dict contains values matching common_dates.
      If series_dict is empty or no common dates exist, returns ([], {k: []}).
    """
    if not series_dict:
        return [], {}

    # Identify common dates across all keys
    tickers = list(series_dict.keys())
    common_set = set(series_dict[tickers[0]].keys())
    for t in tickers[1:]:
        common_set &= set(series_dict[t].keys())

    if not common_set:
        return [], {t: [] for t in tickers}

    common_dates = sorted(common_set)

    aligned: dict[str, list[Decimal]] = {
        t: [series_dict[t][d] for d in common_dates] for t in tickers
    }

    return common_dates, aligned
