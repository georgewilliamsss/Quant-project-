# Consistency check — Excel vs PDF vs JSON/CSV

Method: Excel = `Portfolio_Model.xlsx` copied to `data/consistency_copy.xlsx` and recalculated with LibreOffice
(`recalc.py`, 300s timeout — **0 formula errors across 38,930 formulas**), read with openpyxl `data_only=True`.
PDF = `Portfolio_Report.pdf` text extracted with pypdf. JSON/CSV = `data/analysis_results.json`,
`data/weights.csv`, `data/fundamentals_table.csv`, `data/combined_positions.csv`, `data/unicorn_stats.csv`
(the Python "published" values). Where the PDF rounds to 1–3 significant figures, "match" means the rounded
PDF figure is consistent with the higher-precision Excel/JSON value. Per the brief, Excel's **monthly**-formula
stats (`Stats_Monthly`) are not compared against the daily Python stats — only the tabs/values that are meant
to be identical are checked here (`Optimisation` vs JSON; the Python-values rows on `Backtest`, `Unicorns`,
`Combined_Portfolio`, `Stock_Fundamentals` vs JSON/CSV).

| # | Fact | Excel | PDF | JSON/CSV | Match? |
|---|---|---|---|---|---|
| 1 | Headline (Moderate12) E[R], 50/50 blend | 0.154974 (15.5%) | 15.5% | 0.154974 | Yes |
| 2 | Headline ex-ante vol (Ledoit-Wolf, optimised 97.5%) | 0.120000 (12.0%) | 12.0% | 0.120000 | Yes |
| 3 | Headline ex-ante vol (all 37 lines incl. SPCX) | 0.127942 (12.8%) | 12.8% | 0.127942 | Yes |
| 4 | Headline ex-ante Sharpe | 0.9182 | 0.92 | 0.9182 | Yes |
| 5 | Headline beta vs VWRP.L (as held) | 0.7880 | 0.79 | 0.7880 | Yes |
| 6 | Headline beta+ (as held) | 0.8464 | 0.85 | 0.8464 | Yes |
| 7 | Headline beta− (as held) | 0.7610 | 0.76 | 0.7610 | Yes |
| 8 | Top-8 core-sleeve weights (£) — SMGB.L | 17.07% / £27,317.69 | 17.1% / £27,318 | 0.170736 / £27,317.69 | Yes |
| 9 | — SGLN.L | 14.99% / £23,987.87 | 15.0% / £23,988 | 0.149924 / £23,987.87 | Yes |
| 10 | — ISF.L | 12.75% / £20,401.35 | 12.8% / £20,401 | 0.127508 / £20,401.35 | Yes |
| 11 | — DBMG.L | 10.26% / £16,414.35 | 10.3% / £16,414 | 0.102590 / £16,414.35 | Yes |
| 12 | — IBTM.L | 10.00% / £16,000.00 | 10.0% / £16,000 | 0.100000 / £16,000.00 | Yes |
| 13 | — BRNT.L | 5.01% / £8,012.13 | 5.0% / £8,012 | 0.050076 / £8,012.13 | Yes |
| 14 | — RR.L, PLTR (5.00% each / £8,000) | 5.00% / £8,000.00 each | 5.0% / £8,000 each | 0.050000 / £8,000.00 each | Yes |
| 15 | Combined £200k E[R] blend | 0.156140 (15.6%) | 15.6% | 0.156140 | Yes |
| 16 | Combined £200k ex-ante vol | 0.144464 (14.4%) | 14.4% | 0.144464 | Yes |
| 17 | Combined £200k ex-ante Sharpe | 0.8212 | 0.82 | 0.8212 | Yes |
| 18 | Unicorn sleeve CAGR (equal-weight, daily-rebalanced) | 0.235870 (23.6%) | 23.6% | 0.235870 | Yes |
| 19 | Unicorn sleeve volatility (ann.) | 0.268421 (26.8%) | 26.8% | 0.268421 | Yes |
| 20 | Unicorn sleeve max drawdown | −0.401732 (−40.2%) | −40.2% | −0.401732 | Yes |
| 21 | Headline (core) 5y backtest CAGR, monthly rebalanced | 0.260388 (26.0%) | 26.0% | 0.260388 | Yes |
| 22 | Headline (core) 5y backtest max drawdown | −0.037528 (−3.8%) | −3.8% | −0.037528 | Yes |
| 23 | Risk-free rate (BoE Bank Rate) | 3.75% (2026-07-30) | 3.75% | 0.0375 (market_params) | Yes |
| 24 | Equity risk premium (Damodaran, mature market) | 4.17% (2026-07-01) | 4.17% | 0.0417 (market_params) | Yes |
| 25 | T36N (10y gilt, 4 7/8% 2036) redemption yield | 5.466% | 5.466% | 0.05466 (core_universe.json / expected_returns) | Yes |
| 26 | T56 (30y gilt, 5 3/8% 2056) redemption yield | 6.003% | 6.003% | 0.06003 (core_universe.json / expected_returns) | Yes |
| 27 | RR.L trailing P/E | 40.4056 | 40.41 | 40.4056 (fundamentals_table.csv) | Yes |
| 28 | RR.L WACC | 9.10% | 9.1% | 0.091027 | Yes |
| 29 | RR.L YTD return (GBP) | 27.53% | 27.5% | 0.275291 | Yes |
| 30 | PLTR trailing P/E | 142.9316 | 142.93 | 142.9316 | Yes |
| 31 | PLTR WACC | 9.78% | 9.8% | 0.097785 | Yes |
| 32 | PLTR YTD return (GBP) | −6.21% | −6.2% | −0.062117 | Yes |
| 33 | SPCX £ allocation (fixed policy weight, 2.5% of core) | £4,000.00 (35 shares, £3,917.56 invested) | £4,000 (35 shares, £3,918 invested, rounded) | £4,000.00 / 35 shares / £3,917.56 (weights.csv, combined_positions.csv) | Yes |
| 34 | Total invested £ (combined £200,000, whole shares) | £199,004.169344 | £199,004 | £199,004.169344 (combined_positions.csv sum) | Yes |
| 35 | Residual cash £ (combined) | £995.830656 | ~£996 (text: "GBP 996 ... stays in cash") | £995.830656 (200,000 − 199,004.169344) | Yes |

## Notes on scope and method

- Facts 1–7, 15–22 are drawn from the `Optimisation`, `Combined_Portfolio`, `Unicorns` and `Backtest` tabs'
  **"values (Python) — see Sources_Assumptions"** rows, which the workbook itself cross-checks against
  `scripts/analysis.py`'s published output with an explicit "difference (workbook − published)" row — every
  one of those differences is exactly 0 (or ~1e-15, floating-point noise) in the recalculated copy. This
  confirms the workbook's live formulas reproduce the JSON to machine precision, and the JSON in turn is what
  the PDF's tables cite.
- The residual-cash figure sits inside "Whole shares only, so GBP 996 of the GBP 200,000 stays in cash (GBP 818
  of it inside the core sleeve)" in the PDF's prose (§1.1) rather than a table cell; £996 is the correct
  rounding of £995.83, and £818 correctly rounds the core-only residual of £817.88 (Optimisation row 91,
  Moderate12 column) — both consistent.
- Per the brief, `Stats_Monthly` (Excel formula-based) was **not** compared line-for-line against
  `Stats_Daily`/JSON: the two use different (monthly vs daily) return series by design and are expected to
  differ (the workbook's own `Stats_Daily` tab already carries a "difference" column against the monthly
  figures, which is out of scope for this fact list).
- No mismatches were found. All 25 requested facts (expanded to 35 line-items where a fact has several
  components, e.g. the six top-8 weight/£ pairs) agree across Excel, PDF and JSON/CSV to the precision each
  document reports at.

## Overall verdict

**Fully consistent.** Zero discrepancies found across all 25 facts (35 line-items) checked between the
recalculated Excel workbook, the PDF report text, and the underlying JSON/CSV data. The Excel recalculation
completed with 0 formula errors over 38,930 formulas, and the workbook's own built-in "difference
(workbook − published)" cross-check rows confirm exact agreement with `scripts/analysis.py`'s output.
