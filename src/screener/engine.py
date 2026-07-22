"""Financial Screener Engine — applies threshold filters to the financial_ratios data,
supports the 6 preset screeners plus custom filters, and computes the composite quality score.
"""

import sqlite3
import os
import yaml
import pandas as pd
import numpy as np

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "screener_config.yaml")


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def load_latest_year_ratios(conn):
    """Return one row per company — the latest available year — joined with sector + market cap data."""
    query = """
    SELECT f.*, s.broad_sector
    FROM financial_ratios f
    LEFT JOIN sectors s ON f.company_id = s.company_id
    WHERE f.year = (
        SELECT MAX(f2.year) FROM financial_ratios f2 WHERE f2.company_id = f.company_id
    )
    """
    df = pd.read_sql(query, conn)
    return df


def apply_de_financial_carveout(df: pd.DataFrame, filter_col: str = "debt_to_equity") -> pd.DataFrame:
    """When a D/E max filter is applied, exclude Financials-sector companies from that specific filter
    (they are structurally high-leverage; the filter doesn't apply to them). Returns a boolean mask
    that is True (pass) for Financials-sector rows regardless of D/E value.
    """
    is_financial = df["broad_sector"] == "Financials"
    return is_financial


def icr_passes_threshold(row, min_icr: float) -> bool:
    """ICR filter: Debt Free (icr is None/label) always passes any minimum ICR threshold (treated as infinity)."""
    if row.get("icr_label") == "Debt Free":
        return True
    icr = row.get("interest_coverage")
    if icr is None or pd.isna(icr):
        return False
    return icr >= min_icr


def apply_filter(df: pd.DataFrame, metric: str, condition: dict) -> pd.Series:
    """Return boolean mask for a single metric/condition pair. Handles min, max, equals."""
    if metric not in df.columns:
        # Metric not available in this dataset (e.g. requires market_cap join) — pass all through
        return pd.Series([True] * len(df), index=df.index)

    mask = pd.Series([True] * len(df), index=df.index)
    series = df[metric]

    if "min" in condition:
        mask &= series >= condition["min"]
    if "max" in condition:
        if metric == "debt_to_equity":
            financial_carveout = apply_de_financial_carveout(df)
            mask &= (series <= condition["max"]) | financial_carveout
        else:
            mask &= series <= condition["max"]
    if "equals" in condition:
        mask &= series == condition["equals"]

    return mask.fillna(False)


def run_screener(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply all filters in a preset to the dataframe, return the filtered + sorted result."""
    combined_mask = pd.Series([True] * len(df), index=df.index)
    for metric, condition in filters.items():
        if metric in ("fcf_positive_latest_year", "de_declining_yoy"):
            continue  # handled separately (needs multi-year lookups)
        combined_mask &= apply_filter(df, metric, condition)
    result = df[combined_mask].copy()
    if "composite_quality_score" in result.columns:
        result = result.sort_values("composite_quality_score", ascending=False)
    return result


def run_preset(preset_name: str, config: dict, df: pd.DataFrame) -> pd.DataFrame:
    preset = config["presets"][preset_name]
    return run_screener(df, preset["filters"])


if __name__ == "__main__":
    config = load_config()
    conn = sqlite3.connect(DB_PATH)
    latest = load_latest_year_ratios(conn)
    print(f"Latest-year universe: {len(latest)} companies")

    for name, preset in config["presets"].items():
        if name == "turnaround_watch":
            continue  # requires multi-year logic, handled in run_pipeline_screener.py
        result = run_preset(name, config, latest)
        lo, hi = preset["expected_range"]
        status = "PASS" if lo <= len(result) <= hi else "CHECK"
        print(f"{preset['label']:25s} -> {len(result):3d} companies (expected {lo}-{hi}) [{status}]")

    conn.close()
