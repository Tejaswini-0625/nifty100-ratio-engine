import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "screener"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

import pandas as pd
import pytest
from engine import apply_filter, icr_passes_threshold
from peer import compute_peer_percentiles, find_unassigned_companies, peer_group_message


def make_df():
    return pd.DataFrame({
        "company_id": ["A", "B", "C", "D"],
        "return_on_equity_pct": [10, 20, 30, None],
        "debt_to_equity": [0, 1, 6, 2],
        "broad_sector": ["IT", "IT", "Financials", "IT"],
        "interest_coverage": [5, None, 10, 1.0],
        "icr_label": [None, "Debt Free", None, None],
    })


# ---- DQ / filter engine tests (14 total) ----

def test_min_filter_basic():
    df = make_df()
    mask = apply_filter(df, "return_on_equity_pct", {"min": 15})
    assert list(mask) == [False, True, True, False]

def test_max_filter_basic():
    df = make_df()
    mask = apply_filter(df, "interest_coverage", {"max": 6})
    assert mask.iloc[0] == True
    assert mask.iloc[2] == False

def test_equals_filter():
    df = make_df()
    mask = apply_filter(df, "debt_to_equity", {"equals": 0})
    assert list(mask) == [True, False, False, False]

def test_de_max_financial_carveout():
    df = make_df()
    mask = apply_filter(df, "debt_to_equity", {"max": 2})
    # Row C has D/E=6 but is Financials sector -> should pass via carveout
    assert mask.iloc[2] == True

def test_de_max_non_financial_fails():
    df = make_df()
    mask = apply_filter(df, "debt_to_equity", {"max": 0.5})
    # Row B (IT sector, D/E=1) should fail
    assert mask.iloc[1] == False

def test_missing_metric_passes_through():
    df = make_df()
    mask = apply_filter(df, "nonexistent_metric", {"min": 5})
    assert mask.all()

def test_nan_value_fails_min_filter():
    df = make_df()
    mask = apply_filter(df, "return_on_equity_pct", {"min": 5})
    assert mask.iloc[3] == False  # NaN

def test_icr_debt_free_passes_any_threshold():
    row = {"icr_label": "Debt Free", "interest_coverage": None}
    assert icr_passes_threshold(row, min_icr=100) == True

def test_icr_below_threshold_fails():
    row = {"icr_label": None, "interest_coverage": 1.0}
    assert icr_passes_threshold(row, min_icr=1.5) == False

def test_icr_none_no_label_fails():
    row = {"icr_label": None, "interest_coverage": None}
    assert icr_passes_threshold(row, min_icr=1.5) == False


# ---- Peer engine DQ tests ----

def test_peer_percentile_inverts_de():
    ratios = pd.DataFrame({
        "company_id": ["X", "Y", "Z"],
        "debt_to_equity": [0.1, 1.0, 5.0],
        "year": ["2024-03"] * 3,
    })
    peer_groups = pd.DataFrame({
        "company_id": ["X", "Y", "Z"],
        "peer_group_name": ["G1", "G1", "G1"],
        "is_benchmark": [True, False, False],
    })
    result = compute_peer_percentiles(ratios, peer_groups)
    de_result = result[result.metric == "debt_to_equity"].set_index("company_id")
    # Lowest D/E (X) should have highest percentile
    assert de_result.loc["X", "percentile_rank"] > de_result.loc["Z", "percentile_rank"]

def test_unassigned_companies_detected():
    ratios = pd.DataFrame({"company_id": ["X", "Y", "Z"]})
    peer_groups = pd.DataFrame({"company_id": ["X", "Y"], "peer_group_name": ["G1", "G1"]})
    unassigned = find_unassigned_companies(ratios, peer_groups)
    assert unassigned == ["Z"]

def test_peer_group_message_no_error():
    peer_groups = pd.DataFrame({"company_id": ["X"], "peer_group_name": ["G1"]})
    msg = peer_group_message("NOTINGROUP", peer_groups)
    assert msg == "No peer group assigned"

def test_peer_group_message_assigned_ok():
    peer_groups = pd.DataFrame({"company_id": ["X"], "peer_group_name": ["G1"]})
    msg = peer_group_message("X", peer_groups)
    assert msg == "OK"
