"""Profitability, leverage, and efficiency ratio functions for the Nifty 100 Ratio Engine."""

from typing import Optional


# ---------------------------------------------------------------------------
# Day 8 — Profitability Ratios
# ---------------------------------------------------------------------------

def net_profit_margin(net_profit: float, sales: float) -> Optional[float]:
    """Net Profit Margin % = net_profit / sales * 100. None if sales = 0."""
    if sales == 0:
        return None
    return (net_profit / sales) * 100


def operating_profit_margin(operating_profit: float, sales: float) -> Optional[float]:
    """Operating Profit Margin % = operating_profit / sales * 100. None if sales = 0."""
    if sales == 0:
        return None
    return (operating_profit / sales) * 100


def opm_cross_check(computed_opm: Optional[float], source_opm: float, tolerance: float = 1.0) -> bool:
    """Return True if computed OPM differs from source opm_percentage by more than `tolerance` points."""
    if computed_opm is None:
        return False
    return abs(computed_opm - source_opm) > tolerance


def return_on_equity(net_profit: float, equity_capital: float, reserves: float) -> Optional[float]:
    """ROE % = net_profit / (equity_capital + reserves) * 100. None if equity+reserves <= 0."""
    total_equity = equity_capital + reserves
    if total_equity <= 0:
        return None
    return (net_profit / total_equity) * 100


def return_on_capital_employed(ebit: float, equity_capital: float, reserves: float,
                                 borrowings: float) -> Optional[float]:
    """ROCE % = EBIT / (equity_capital + reserves + borrowings) * 100. None if capital employed <= 0."""
    capital_employed = equity_capital + reserves + borrowings
    if capital_employed <= 0:
        return None
    return (ebit / capital_employed) * 100


def return_on_assets(net_profit: float, total_assets: float) -> Optional[float]:
    """ROA % = net_profit / total_assets * 100. None if total_assets = 0."""
    if total_assets == 0:
        return None
    return (net_profit / total_assets) * 100


def ebit_from_operating_profit(operating_profit: float, depreciation: float) -> float:
    """EBIT = operating_profit - depreciation."""
    return operating_profit - depreciation


# ---------------------------------------------------------------------------
# Day 9 — Leverage & Efficiency Ratios
# ---------------------------------------------------------------------------

def debt_to_equity(borrowings: float, equity_capital: float, reserves: float) -> Optional[float]:
    """D/E = borrowings / (equity_capital + reserves). Returns 0 (not None) if borrowings = 0."""
    total_equity = equity_capital + reserves
    if borrowings == 0:
        return 0.0
    if total_equity <= 0:
        return None
    return borrowings / total_equity


def high_leverage_flag(de_ratio: Optional[float], is_financial_sector: bool, threshold: float = 5.0) -> bool:
    """True if D/E > threshold AND company is NOT in the Financials broad_sector."""
    if de_ratio is None or is_financial_sector:
        return False
    return de_ratio > threshold


def interest_coverage_ratio(operating_profit: float, other_income: float, interest: float):
    """ICR = (operating_profit + other_income) / interest.
    Returns (icr_value, icr_label). icr_value is None and icr_label is 'Debt Free' if interest = 0.
    """
    if interest == 0:
        return None, "Debt Free"
    icr = (operating_profit + other_income) / interest
    return icr, None


def icr_warning_flag(icr: Optional[float], threshold: float = 1.5) -> bool:
    """True if ICR < threshold (risk of not covering interest payments). False for debt-free (icr=None)."""
    if icr is None:
        return False
    return icr < threshold


def net_debt(borrowings: float, investments: float) -> float:
    """Net Debt = borrowings - investments (investments used as liquid asset proxy)."""
    return borrowings - investments


def asset_turnover(sales: float, total_assets: float) -> Optional[float]:
    """Asset Turnover = sales / total_assets. None if total_assets = 0."""
    if total_assets == 0:
        return None
    return sales / total_assets
