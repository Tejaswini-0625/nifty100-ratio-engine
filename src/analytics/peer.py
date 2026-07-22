"""Peer Comparison Engine — computes percentile rank for each company within its peer group,
across 10 metrics. Handles the D/E inversion (lower D/E = higher percentile) and companies
with no assigned peer group.
"""

import sqlite3
import os
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db")
DATA_SUP = os.path.join(os.path.dirname(__file__), "..", "..", "data", "supporting")

METRICS = [
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "debt_to_equity",  # inverted — lower is better
    "free_cash_flow_cr",
    "pat_cagr_5yr",
    "revenue_cagr_5yr",
    "eps_cagr_5yr",
    "interest_coverage",
    "asset_turnover",
]

INVERT_METRICS = {"debt_to_equity"}


def load_latest_ratios(conn) -> pd.DataFrame:
    query = """
    SELECT * FROM financial_ratios f
    WHERE year = (SELECT MAX(f2.year) FROM financial_ratios f2 WHERE f2.company_id = f.company_id)
    """
    return pd.read_sql(query, conn)


def load_peer_groups() -> pd.DataFrame:
    pg = pd.read_excel(os.path.join(DATA_SUP, "peer_groups.xlsx"), header=0)
    pg["company_id"] = pg["company_id"].str.strip().str.upper()
    return pg


def compute_peer_percentiles(ratios: pd.DataFrame, peer_groups: pd.DataFrame) -> pd.DataFrame:
    """Returns long-format table: company_id, peer_group_name, metric, value, percentile_rank, year."""
    merged = peer_groups.merge(ratios, on="company_id", how="left")

    records = []
    for group_name, grp in merged.groupby("peer_group_name"):
        for metric in METRICS:
            if metric not in grp.columns:
                continue
            valid = grp.dropna(subset=[metric])
            if len(valid) == 0:
                continue
            ranks = valid[metric].rank(pct=True, method="average")
            if metric in INVERT_METRICS:
                ranks = 1 - ranks
            for idx, cid in valid["company_id"].items():
                records.append({
                    "company_id": cid,
                    "peer_group_name": group_name,
                    "metric": metric,
                    "value": valid.loc[idx, metric],
                    "percentile_rank": round(ranks.loc[idx], 4),
                    "year": valid.loc[idx, "year"] if "year" in valid.columns else None,
                })

    return pd.DataFrame(records)


def find_unassigned_companies(ratios: pd.DataFrame, peer_groups: pd.DataFrame) -> list:
    """Companies present in financial_ratios but not in any peer group."""
    assigned = set(peer_groups["company_id"])
    all_companies = set(ratios["company_id"])
    unassigned = sorted(all_companies - assigned)
    return unassigned


def peer_group_message(company_id: str, peer_groups: pd.DataFrame) -> str:
    """Return 'No peer group assigned' message for companies not in any group — never raises an error."""
    if company_id not in peer_groups["company_id"].values:
        return "No peer group assigned"
    return "OK"


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    ratios = load_latest_ratios(conn)
    peer_groups = load_peer_groups()

    percentiles = compute_peer_percentiles(ratios, peer_groups)
    print(f"Peer percentile rows: {len(percentiles)}")
    print(f"Peer groups covered: {percentiles['peer_group_name'].nunique()} (expected 11)")

    unassigned = find_unassigned_companies(ratios, peer_groups)
    print(f"Companies with no peer group: {len(unassigned)}")
    for c in unassigned[:10]:
        print(f"  {c}: {peer_group_message(c, peer_groups)}")

    percentiles.to_sql("peer_percentiles", conn, if_exists="replace", index=False)
    print("Saved to peer_percentiles table.")

    # Spot-check: IT Services — highest ROE should have highest ROE percentile
    it_roe = percentiles[(percentiles.peer_group_name == "IT Services") & (percentiles.metric == "return_on_equity_pct")]
    if len(it_roe):
        top_by_value = it_roe.sort_values("value", ascending=False).iloc[0]
        top_by_pct = it_roe.sort_values("percentile_rank", ascending=False).iloc[0]
        match = top_by_value["company_id"] == top_by_pct["company_id"]
        print(f"IT Services spot-check: highest ROE={top_by_value['company_id']}, highest percentile={top_by_pct['company_id']} -> {'PASS' if match else 'FAIL'}")

    conn.close()
