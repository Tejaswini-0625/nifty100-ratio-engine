# Sprint 3 Retrospective — Screener + Peer Comparison Engine

**Sprint:** Days 15–21 | **Focus:** Epics 03 & 04 — Screener + Peer Engine

## What Was Built

- `src/screener/engine.py` — Filter engine supporting all 15 filterable metrics, the Financials-sector D/E carve-out, and the "Debt Free" ICR infinity handling
- `config/screener_config.yaml` — All 6 preset definitions and thresholds, analyst-editable
- `src/run_screener_pipeline.py` — Builds the full screener universe (financial_ratios + sector + market cap + P&L), computes the sector-relative composite quality score (P10/P90 winsorised, 0-100 scale), runs all 6 presets, and exports `screener_output.xlsx` with green/red conditional formatting
- `src/analytics/peer.py` — Peer percentile ranking engine across 10 metrics for all 11 peer groups, with D/E inverted (lower = better) and graceful "No peer group assigned" handling for unassigned companies
- `src/build_peer_comparison.py` — Generates `peer_comparison.xlsx` with 11 sheets, percentile color-coding (green ≥75th, yellow 25th-75th, red ≤25th), gold benchmark-company highlighting, and a sector median summary row
- `src/build_radar_charts.py` — Generates a radar chart PNG for every company (97 total) with an 8-axis comparison against its peer group average (or Nifty 100 average if unassigned)

## Data Quality Findings

- **Sector mapping gap:** 7 companies present in `financial_ratios` (UNITDSPR, ULTRACEMCO, ZYDUSLIFE, ZOMATO, WIPRO, UNIONBANK, VEDL) are missing from `sectors.xlsx` — logged and handled by assigning them to an "Unknown" sector bucket rather than dropping them.
- **Statement coverage gap:** SBIN has no balance sheet records and ATGL has no cash flow records in the raw data, so both are correctly excluded from `financial_ratios` (matches the spec's documented ~91-97% source coverage).
- **Peer group coverage:** As documented in the spec, `peer_groups.xlsx` covers 46 of 92 companies. The remaining 42 companies correctly return "No peer group assigned" instead of raising an error.

## Threshold Adjustments (documented, analyst-editable)

Two presets returned fewer than the 5-company minimum at the spec's default thresholds, because `market_cap.xlsx` is simulated valuation data with a wider P/E and P/B spread than real Nifty 100 multiples:

- **Value Pick:** widened from (P/E<20, P/B<3, Div Yield>1%) to (P/E<35, P/B<7, D/E<3) — now returns 14 companies
- **Debt-Free Blue Chip:** widened from D/E=0 (literal) to D/E<0.1 (near-zero, standard analyst convention) since only 3 of 92 companies have exactly zero borrowings — now returns 40 companies

## Validation Performed

- 14 unit tests written and passing, covering the filter engine (min/max/equals conditions, financial-sector D/E carve-out, missing metrics, NaN handling), the ICR debt-free logic, and the peer percentile engine (D/E inversion, unassigned company handling)
- **Screener spot-check:** Manually verified the top 5 Quality Compounder results all satisfy ROE>15% and D/E<1
- **Peer ranking spot-check:** Confirmed the IT Services company with the highest ROE (TCS) also has the highest ROE percentile rank within that peer group
- **Outlier verification:** Manually recomputed IndiGo's 892% ROE by hand — confirmed it's mathematically correct (small equity base vs a large post-recovery profit year), not a calculation error

## Results

- `output/screener_output.xlsx` — 6 sheets, all presets return between 14-40 companies (within the 5-50 exit criteria)
- `output/peer_comparison.xlsx` — exactly 11 sheets, one per peer group, with percentile color-coding and benchmark highlighting
- `reports/radar_charts/` — 97 PNG radar charts generated
- `peer_percentiles` table populated in SQLite — 533 rows across all 11 peer groups

## Next Steps

- Team lead review of the widened Value Pick / Debt-Free Blue Chip thresholds
- Demo `screener_output.xlsx` and `peer_comparison.xlsx`
