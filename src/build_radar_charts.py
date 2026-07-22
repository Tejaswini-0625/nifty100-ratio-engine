"""Generates a radar/polar chart PNG for each company, showing its values across 8 axes
overlaid with its peer group average. Companies with no peer group get a simplified
standalone chart vs the Nifty 100 average.
"""

import sqlite3
import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "analytics"))
from peer import load_latest_ratios, load_peer_groups

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "nifty100.db")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports", "radar_charts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

AXES = [
    "return_on_equity_pct", "return_on_capital_employed_pct", "net_profit_margin_pct",
    "debt_to_equity", "free_cash_flow_cr", "pat_cagr_5yr", "revenue_cagr_5yr",
    "composite_quality_score",
]
AXES_LABELS = ["ROE", "ROCE", "NPM", "D/E", "FCF Score", "PAT CAGR 5yr", "Rev CAGR 5yr", "Composite Score"]


def normalize_for_radar(df: pd.DataFrame) -> pd.DataFrame:
    """Min-max scale each axis to 0-100 across the full universe so all axes are comparable on one chart.
    D/E is inverted (lower is better) before scaling.
    """
    scaled = pd.DataFrame(index=df.index)
    for axis in AXES:
        series = df[axis].copy()
        if axis == "debt_to_equity":
            series = -series
        lo, hi = series.min(), series.max()
        if hi == lo:
            scaled[axis] = 50.0
        else:
            scaled[axis] = (series - lo) / (hi - lo) * 100
    return scaled


def plot_radar(company_id: str, company_values: np.ndarray, peer_avg_values: np.ndarray, title_suffix: str):
    n = len(AXES)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    company_plot = np.append(company_values, company_values[0])
    peer_plot = np.append(peer_avg_values, peer_avg_values[0])

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.plot(angles, company_plot, color="#1f77b4", linewidth=2, label=company_id)
    ax.fill(angles, company_plot, color="#1f77b4", alpha=0.25)
    ax.plot(angles, peer_plot, color="#888888", linewidth=1.5, linestyle="dashed", label=title_suffix)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(AXES_LABELS, fontsize=9)
    ax.set_yticklabels([])
    ax.set_title(f"{company_id} vs {title_suffix}", fontsize=12, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8)

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, f"{company_id}_radar.png")
    plt.savefig(out_path, dpi=100)
    plt.close(fig)
    return out_path


def main():
    conn = sqlite3.connect(DB_PATH)
    ratios = load_latest_ratios(conn)
    peer_groups = load_peer_groups()
    conn.close()

    ratios = ratios.dropna(subset=[a for a in AXES if a != "debt_to_equity"], how="all")
    scaled = normalize_for_radar(ratios)
    scaled["company_id"] = ratios["company_id"].values

    company_to_group = dict(zip(peer_groups["company_id"], peer_groups["peer_group_name"]))
    nifty_avg = scaled[AXES].mean().values

    count = 0
    for _, row in scaled.iterrows():
        cid = row["company_id"]
        company_vals = row[AXES].values.astype(float)

        group_name = company_to_group.get(cid)
        if group_name:
            group_members = peer_groups.loc[peer_groups["peer_group_name"] == group_name, "company_id"]
            group_scaled = scaled[scaled["company_id"].isin(group_members)]
            peer_avg = group_scaled[AXES].mean().values.astype(float)
            title_suffix = f"{group_name} avg"
        else:
            peer_avg = nifty_avg
            title_suffix = "Nifty 100 avg"

        plot_radar(cid, company_vals, peer_avg, title_suffix)
        count += 1

    print(f"Generated {count} radar charts in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
