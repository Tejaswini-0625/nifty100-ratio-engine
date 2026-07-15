"""Sprint 2 pipeline: loads raw data, runs the Ratio Engine, populates SQLite `financial_ratios`,
generates capital_allocation.csv and ratio_edge_cases.log.
"""

import sys
import os
import sqlite3
import logging
from datetime import datetime

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from analytics.ratios import (
    net_profit_margin, operating_profit_margin, opm_cross_check,
    return_on_equity, return_on_capital_employed, return_on_assets,
    ebit_from_operating_profit, debt_to_equity, high_leverage_flag,
    interest_coverage_ratio, icr_warning_flag, net_debt, asset_turnover,
)
from analytics.cagr import cagr
from analytics.cashflow_kpis import (
    free_cash_flow, cfo_quality_score_numeric, capex_intensity,
    capex_intensity_label, fcf_conversion_rate, capital_allocation_pattern,
)

DATA_RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
DATA_SUP = os.path.join(os.path.dirname(__file__), "..", "data", "supporting")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "nifty100.db")

os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(OUTPUT_DIR, "ratio_edge_cases.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    filemode="w",
)
logger = logging.getLogger("ratio_engine")


def normalize_year(raw):
    """Normalise year labels like 'Mar-23', 'Dec-22', 2023, 'FY23' -> 'YYYY-MM'."""
    raw = str(raw).strip()
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    low = raw.lower().replace(" ", "")
    for m_name, m_num in months.items():
        if low.startswith(m_name):
            # extract trailing digits
            digits = "".join(ch for ch in low if ch.isdigit())
            if len(digits) == 2:
                yr = int(digits)
                yr_full = 2000 + yr if yr < 70 else 1900 + yr
            else:
                yr_full = int(digits)
            return f"{yr_full}-{m_num}"
    if raw.isdigit():
        return f"{raw}-03"
    if low.startswith("fy"):
        digits = "".join(ch for ch in raw if ch.isdigit())
        yr = int(digits)
        yr_full = 2000 + yr if yr < 70 else 1900 + yr
        return f"{yr_full}-03"
    return raw  # already normalised or unparseable


def normalize_ticker(t):
    return str(t).strip().upper()


def load_core(name):
    path = os.path.join(DATA_RAW, name)
    df = pd.read_excel(path, header=1)
    if "company_id" in df.columns:
        df["company_id"] = df["company_id"].apply(normalize_ticker)
    return df


def load_supporting(name):
    path = os.path.join(DATA_SUP, name)
    df = pd.read_excel(path, header=0)
    if "company_id" in df.columns:
        df["company_id"] = df["company_id"].apply(normalize_ticker)
    return df


def main():
    print("Loading raw datasets...")
    companies = load_core("companies.xlsx")
    pl = load_core("profitandloss.xlsx")
    bs = load_core("balancesheet.xlsx")
    cf = load_core("cashflow.xlsx")

    sectors = load_supporting("sectors.xlsx")

    for df, col in [(pl, "year"), (bs, "year"), (cf, "year")]:
        df["year_norm"] = df["year"].apply(normalize_year)

    year_pattern = r"^\d{4}-\d{2}$"
    for name, df in [("profitandloss", pl), ("balancesheet", bs), ("cashflow", cf)]:
        bad_mask = ~df["year_norm"].str.match(year_pattern)
        n_bad = int(bad_mask.sum())
        if n_bad:
            bad_vals = df.loc[bad_mask, "year"].unique().tolist()
            logger.info(f"DQ-07 year format rejects | {name} | {n_bad} rows | raw values: {bad_vals} | category=data source issue")
        df.drop(df[bad_mask].index, inplace=True)

    for name, df in [("profitandloss", pl), ("balancesheet", bs), ("cashflow", cf)]:
        n_before = len(df)
        df.drop_duplicates(subset=["company_id", "year_norm"], keep="last", inplace=True)
        n_after = len(df)
        if n_before != n_after:
            logger.info(f"DQ-02 deduplication | {name} | removed {n_before - n_after} duplicate rows | category=data source issue")

    financial_sector_ids = set(
        sectors.loc[sectors["broad_sector"] == "Financials", "company_id"]
    )

    # Merge P&L + BS + CF on (company_id, year_norm)
    merged = pl.merge(bs, on=["company_id", "year_norm"], suffixes=("_pl", "_bs"))
    merged = merged.merge(cf, on=["company_id", "year_norm"], suffixes=("", "_cf"))
    merged = merged.sort_values(["company_id", "year_norm"]).reset_index(drop=True)

    print(f"Merged company-year rows: {len(merged)}")

    rows = []
    capital_alloc_rows = []

    # Group by company for CAGR / rolling calcs
    for company_id, grp in merged.groupby("company_id"):
        grp = grp.sort_values("year_norm").reset_index(drop=True)
        is_financial = company_id in financial_sector_ids
        n_years = len(grp)

        sales_series = grp["sales"].tolist()
        pat_series = grp["net_profit"].tolist()
        eps_series = grp["eps"].tolist()
        cfo_series = grp["operating_activity"].tolist()

        for i, row in grp.iterrows():
            sales = row["sales"]
            expenses = row["expenses"]
            operating_profit = row["operating_profit"]
            opm_pct_source = row["opm_percentage"]
            other_income = row["other_income"] if not pd.isna(row["other_income"]) else 0
            interest = row["interest"] if not pd.isna(row["interest"]) else 0
            depreciation = row["depreciation"] if not pd.isna(row["depreciation"]) else 0
            net_profit = row["net_profit"]
            eps = row["eps"]
            dividend_payout = row["dividend_payout"] if not pd.isna(row["dividend_payout"]) else None

            equity_capital = row["equity_capital"]
            reserves = row["reserves"] if not pd.isna(row["reserves"]) else 0
            borrowings = row["borrowings"] if not pd.isna(row["borrowings"]) else 0
            total_assets = row["total_assets"]
            investments = row["investments"] if not pd.isna(row["investments"]) else 0
            face_value = companies.loc[companies["id"] == company_id, "face_value"]
            face_value = face_value.iloc[0] if len(face_value) else 1

            cfo = row["operating_activity"]
            cfi = row["investing_activity"]
            cff = row["financing_activity"]

            ebit = ebit_from_operating_profit(operating_profit, depreciation)

            npm = net_profit_margin(net_profit, sales)
            opm = operating_profit_margin(operating_profit, sales)
            if opm_cross_check(opm, opm_pct_source):
                logger.info(
                    f"OPM mismatch | {company_id} {row['year_norm']} | computed={opm:.2f} source={opm_pct_source} "
                    f"| category=formula discrepancy"
                )

            roe = return_on_equity(net_profit, equity_capital, reserves)
            if roe is None:
                logger.info(f"ROE None (negative/zero equity) | {company_id} {row['year_norm']} | category=data source issue")

            roce = return_on_capital_employed(ebit, equity_capital, reserves, borrowings)
            roa = return_on_assets(net_profit, total_assets)

            de = debt_to_equity(borrowings, equity_capital, reserves)
            lev_flag = high_leverage_flag(de, is_financial)
            if lev_flag:
                logger.info(f"High leverage flag | {company_id} {row['year_norm']} D/E={de:.2f} | category=formula discrepancy")

            icr, icr_label = interest_coverage_ratio(operating_profit, other_income, interest)
            icr_risk = icr_warning_flag(icr)
            if icr_label:
                logger.info(f"ICR label={icr_label} | {company_id} {row['year_norm']} | category=data source issue")

            nd = net_debt(borrowings, investments)
            at = asset_turnover(sales, total_assets)

            fcf = free_cash_flow(cfo, cfi)
            capex = abs(cfi)
            capex_int = capex_intensity(cfi, sales)
            capex_lbl = capex_intensity_label(capex_int)
            fcf_conv = fcf_conversion_rate(fcf, operating_profit)

            # 5-year trailing CFO/PAT for quality score
            idx = i
            start_idx = max(0, idx - 4)
            cfo_window = cfo_series[start_idx: idx + 1]
            pat_window = pat_series[start_idx: idx + 1]
            cfo_pat_ratio = cfo_quality_score_numeric(cfo_window, pat_window)

            capital = capital_allocation_pattern(cfo, cfi, cff, cfo_pat_ratio)
            capital_alloc_rows.append({
                "company_id": company_id,
                "year": row["year_norm"],
                "cfo_sign": capital["cfo_sign"],
                "cfi_sign": capital["cfi_sign"],
                "cff_sign": capital["cff_sign"],
                "pattern_label": capital["pattern_label"],
            })

            # CAGR (revenue, PAT, EPS) for 3/5/10yr windows
            cagr_results = {}
            for label, n in [("3yr", 3), ("5yr", 5), ("10yr", 10)]:
                if idx - n >= 0:
                    start_val_rev, end_val_rev = sales_series[idx - n], sales_series[idx]
                    cagr_results[f"revenue_cagr_{label}"], flag = cagr(start_val_rev, end_val_rev, n, n_years)
                    if flag:
                        logger.info(f"Revenue CAGR {label} flag={flag} | {company_id} {row['year_norm']} | category=formula discrepancy")

                    start_val_pat, end_val_pat = pat_series[idx - n], pat_series[idx]
                    cagr_results[f"pat_cagr_{label}"], flag = cagr(start_val_pat, end_val_pat, n, n_years)

                    start_val_eps, end_val_eps = eps_series[idx - n], eps_series[idx]
                    cagr_results[f"eps_cagr_{label}"], flag = cagr(start_val_eps, end_val_eps, n, n_years)
                else:
                    cagr_results[f"revenue_cagr_{label}"] = None
                    cagr_results[f"pat_cagr_{label}"] = None
                    cagr_results[f"eps_cagr_{label}"] = None

            book_value_per_share = None
            if face_value and face_value != 0 and equity_capital:
                num_shares_proxy = equity_capital / face_value
                if num_shares_proxy != 0:
                    book_value_per_share = (equity_capital + reserves) / num_shares_proxy

            # Composite quality score (simplified 0-100 blend; winsorised inputs would need full-population stats,
            # here a bounded linear blend is used per KPI reference formula weights)
            def score01(x, lo, hi):
                if x is None:
                    return 50.0
                x = max(lo, min(hi, x))
                return (x - lo) / (hi - lo) * 100

            roe_score = score01(roe, -20, 40)
            fcf_score = 100.0 if fcf > 0 else 0.0
            roce_score = score01(roce, -20, 40)
            de_score = score01(-(de if de is not None else 0), -5, 0)
            composite_quality_score = round(
                0.30 * roe_score + 0.25 * fcf_score + 0.25 * roce_score + 0.20 * de_score, 2
            )

            rows.append({
                "company_id": company_id,
                "year": row["year_norm"],
                "net_profit_margin_pct": npm,
                "operating_profit_margin_pct": opm,
                "return_on_equity_pct": roe,
                "return_on_capital_employed_pct": roce,
                "return_on_assets_pct": roa,
                "debt_to_equity": de,
                "high_leverage_flag": lev_flag,
                "interest_coverage": icr,
                "icr_label": icr_label,
                "icr_risk_flag": icr_risk,
                "net_debt_cr": nd,
                "asset_turnover": at,
                "free_cash_flow_cr": fcf,
                "capex_cr": capex,
                "capex_intensity_pct": capex_int,
                "capex_intensity_label": capex_lbl,
                "fcf_conversion_rate_pct": fcf_conv,
                "earnings_per_share": eps,
                "book_value_per_share": book_value_per_share,
                "dividend_payout_ratio_pct": dividend_payout,
                "total_debt_cr": borrowings,
                "cash_from_operations_cr": cfo,
                "revenue_cagr_3yr": cagr_results["revenue_cagr_3yr"],
                "revenue_cagr_5yr": cagr_results["revenue_cagr_5yr"],
                "revenue_cagr_10yr": cagr_results["revenue_cagr_10yr"],
                "pat_cagr_3yr": cagr_results["pat_cagr_3yr"],
                "pat_cagr_5yr": cagr_results["pat_cagr_5yr"],
                "pat_cagr_10yr": cagr_results["pat_cagr_10yr"],
                "eps_cagr_3yr": cagr_results["eps_cagr_3yr"],
                "eps_cagr_5yr": cagr_results["eps_cagr_5yr"],
                "eps_cagr_10yr": cagr_results["eps_cagr_10yr"],
                "composite_quality_score": composite_quality_score,
            })

    ratios_df = pd.DataFrame(rows)
    capital_df = pd.DataFrame(capital_alloc_rows)

    print(f"financial_ratios rows: {len(ratios_df)}")
    print(f"capital_allocation rows: {len(capital_df)}")

    # Write to SQLite
    conn = sqlite3.connect(DB_PATH)
    ratios_df.to_sql("financial_ratios", conn, if_exists="replace", index=False)
    capital_df.to_sql("capital_allocation", conn, if_exists="replace", index=False)
    companies.to_sql("companies", conn, if_exists="replace", index=False)
    sectors.to_sql("sectors", conn, if_exists="replace", index=False)
    conn.commit()

    row_count = conn.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]
    print(f"SELECT COUNT(*) FROM financial_ratios -> {row_count}")

    conn.close()

    capital_df.to_csv(os.path.join(OUTPUT_DIR, "capital_allocation.csv"), index=False)
    ratios_df.to_csv(os.path.join(OUTPUT_DIR, "financial_ratios_export.csv"), index=False)

    print("Pipeline complete.")
    print(f"Row count check (>=1100): {'PASS' if row_count >= 1100 else 'FAIL'} ({row_count})")


if __name__ == "__main__":
    main()
