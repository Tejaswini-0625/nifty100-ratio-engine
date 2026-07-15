"""CAGR engine — Revenue, PAT, EPS growth for 3yr/5yr/10yr windows with edge-case handling."""

from typing import Optional, Tuple


def cagr(start: float, end: float, n: int, years_available: int) -> Tuple[Optional[float], Optional[str]]:
    """Compute CAGR % = ((end/start)^(1/n) - 1) * 100.

    Returns (cagr_value, flag). cagr_value is None whenever a flag is set.

    Edge cases (checked in order):
      - years_available < n                -> (None, 'INSUFFICIENT')
      - start == 0                         -> (None, 'ZERO_BASE')
      - start > 0 and end < 0              -> (None, 'DECLINE_TO_LOSS')
      - start < 0 and end > 0              -> (None, 'TURNAROUND')
      - start < 0 and end < 0              -> (None, 'BOTH_NEGATIVE')
      - start > 0 and end > 0              -> compute normally
    """
    if years_available < n:
        return None, "INSUFFICIENT"

    if start == 0:
        return None, "ZERO_BASE"

    if start > 0 and end < 0:
        return None, "DECLINE_TO_LOSS"

    if start < 0 and end > 0:
        return None, "TURNAROUND"

    if start < 0 and end < 0:
        return None, "BOTH_NEGATIVE"

    # start > 0 and end > 0
    value = ((end / start) ** (1.0 / n) - 1) * 100
    return value, None


def revenue_cagr(sales_series: dict, latest_year_index: int, n: int) -> Tuple[Optional[float], Optional[str]]:
    """sales_series: {year_offset_from_latest: sales_value}, e.g. {0: latest, n: n_years_ago}."""
    years_available = len(sales_series)
    if (latest_year_index - n) not in sales_series or latest_year_index not in sales_series:
        return None, "INSUFFICIENT"
    start = sales_series[latest_year_index - n]
    end = sales_series[latest_year_index]
    return cagr(start, end, n, years_available)


def compute_all_cagr_windows(start_end_pairs: dict) -> dict:
    """start_end_pairs: {'revenue_cagr_3yr': (start, end, years_available), ...}
    Returns {'revenue_cagr_3yr': value, 'revenue_cagr_3yr_flag': flag, ...}
    """
    result = {}
    window_years = {"3yr": 3, "5yr": 5, "10yr": 10}
    for key, (start, end, years_available) in start_end_pairs.items():
        # key format e.g. 'revenue_3yr'
        suffix = key.split("_")[-1]
        n = window_years.get(suffix, 5)
        value, flag = cagr(start, end, n, years_available)
        result[f"{key}"] = value
        result[f"{key}_flag"] = flag
    return result
