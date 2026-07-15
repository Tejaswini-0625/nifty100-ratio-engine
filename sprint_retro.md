cat > sprint2\_retro.md << 'EOF'

\# Sprint 2 Retrospective — Financial Ratio Engine



\*\*Sprint:\*\* Days 8–14 | \*\*Focus:\*\* Ratio Engine (Epic 02)



\## What Was Built



\- src/analytics/ratios.py — Profitability ratios (Net Profit Margin, Operating Profit Margin, ROE, ROCE, ROA) and leverage/efficiency ratios (Debt-to-Equity, Interest Coverage Ratio, Net Debt, Asset Turnover)

\- src/analytics/cagr.py — CAGR engine for Revenue, PAT, and EPS across 3yr/5yr/10yr windows, handling all 6 edge cases

\- src/analytics/cashflow\_kpis.py — Free Cash Flow, CFO Quality Score, CapEx Intensity, FCF Conversion Rate, and the 8-pattern Capital Allocation classifier

\- src/run\_pipeline.py — Full ETL and ratio computation pipeline that loads all raw datasets, computes every KPI for all 92 companies across all available years, and writes results into the financial\_ratios and capital\_allocation tables in SQLite



\## Data Quality Issue Found and Fixed



While validating the output, we discovered the raw balancesheet.xlsx and profitandloss.xlsx files contained duplicate rows for the same company and year (138 duplicate rows in the balance sheet alone), and a non-standard year label ("TTM") that did not match the expected year format. Both issues were silently corrupting downstream ratio calculations such as ROE by misaligning company-year records during merging. We added a year-format validation step and a deduplication step on (company\_id, year), keeping the last occurrence. After the fix, all spot-checked values matched manual calculations exactly.



\## Validation Performed



\- 23 unit tests written and passing (exceeds the 20-test requirement), covering normal cases and edge cases for every KPI

\- Manual spot-check: ROE and 5-year Revenue CAGR for TCS, INFY, and MARUTI were recomputed by hand and compared against the database, matching to 0.0% difference

\- Screener sanity check: filtering for ROE greater than 15% and D/E less than 1 (latest year per company) returned 39 companies, within the expected 15 to 50 range



\## Results



\- financial\_ratios table populated with 1,118 company-year rows (exceeds the 1,100 minimum)

\- output/capital\_allocation.csv generated with pattern labels for every company-year

\- output/ratio\_edge\_cases.log generated, logging every anomaly with a category: data source issue, formula discrepancy, or version difference



\## Next Steps



\- Review bank/NBFC sector carve-out logic against the 19 Financials-sector companies

\- Demo the financial\_ratios table to the team lead with sample companies

EOF

