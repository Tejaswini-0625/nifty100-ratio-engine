import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest
from analytics.ratios import (
    net_profit_margin, operating_profit_margin, opm_cross_check,
    return_on_equity, return_on_capital_employed, return_on_assets,
    debt_to_equity, high_leverage_flag, interest_coverage_ratio,
    icr_warning_flag, net_debt, asset_turnover,
)
from analytics.cagr import cagr
from analytics.cashflow_kpis import (
    free_cash_flow, cfo_quality_score_numeric, capex_intensity,
    capex_intensity_label, fcf_conversion_rate, capital_allocation_pattern,
)


# ---- Day 8: Profitability (8 tests) ----

def test_npm_normal():
    assert net_profit_margin(100, 1000) == pytest.approx(10.0)

def test_npm_zero_sales():
    assert net_profit_margin(100, 0) is None

def test_opm_normal():
    assert operating_profit_margin(200, 1000) == pytest.approx(20.0)

def test_opm_cross_check_mismatch():
    assert opm_cross_check(21.5, 19.0) is True

def test_opm_cross_check_ok():
    assert opm_cross_check(21.5, 21.0) is False

def test_roe_positive():
    assert return_on_equity(100, 400, 100) == pytest.approx(20.0)

def test_roe_negative_equity():
    assert return_on_equity(100, 100, -150) is None

def test_roa_zero_assets():
    assert return_on_assets(100, 0) is None


# ---- Day 9: Leverage & Efficiency (8 tests) ----

def test_de_debt_free():
    assert debt_to_equity(0, 400, 100) == 0

def test_de_normal():
    assert debt_to_equity(500, 400, 100) == pytest.approx(1.0)

def test_high_leverage_flag_true_non_financial():
    assert high_leverage_flag(6.0, is_financial_sector=False) is True

def test_high_leverage_flag_suppressed_financial():
    assert high_leverage_flag(6.0, is_financial_sector=True) is False

def test_icr_interest_zero():
    icr, label = interest_coverage_ratio(500, 50, 0)
    assert icr is None
    assert label == "Debt Free"

def test_icr_normal():
    icr, label = interest_coverage_ratio(500, 50, 100)
    assert icr == pytest.approx(5.5)
    assert label is None

def test_icr_warning_flag_low():
    assert icr_warning_flag(1.2) is True

def test_asset_turnover_zero_assets():
    assert asset_turnover(1000, 0) is None


# ---- Day 10: CAGR (4 tests, representative of 10) ----

def test_cagr_normal():
    val, flag = cagr(100, 161.05, 5, 6)
    assert flag is None
    assert val == pytest.approx(10.0, abs=0.1)

def test_cagr_turnaround():
    val, flag = cagr(-100, 200, 5, 6)
    assert val is None
    assert flag == "TURNAROUND"

def test_cagr_decline_to_loss():
    val, flag = cagr(100, -50, 5, 6)
    assert val is None
    assert flag == "DECLINE_TO_LOSS"

def test_cagr_zero_base():
    val, flag = cagr(0, 100, 5, 6)
    assert val is None
    assert flag == "ZERO_BASE"


# ---- Extra: cashflow / capital allocation (bonus coverage) ----

def test_capex_intensity_asset_light():
    assert capex_intensity_label(capex_intensity(-20, 1000)) == "Asset Light"

def test_capital_allocation_reinvestor():
    result = capital_allocation_pattern(cfo=100, cfi=-50, cff=-20, cfo_pat_ratio=0.6)
    assert result["pattern_label"] == "Reinvestor"

def test_capital_allocation_shareholder_returns():
    result = capital_allocation_pattern(cfo=100, cfi=-50, cff=-20, cfo_pat_ratio=1.5)
    assert result["pattern_label"] == "Shareholder Returns"
