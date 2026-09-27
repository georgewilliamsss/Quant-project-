# Blind Excel verification — refresh round 1

Role: blind verifier. `scripts/build_excel.py` was **not** read. Verification was done by
copying `Portfolio_Model.xlsx` to `data/verify_copy_refresh.xlsx`, recalculating it with
LibreOffice (via a `recalc.py` + `office/soffice.py` shim already present from earlier agent
work in the session scratchpad, run under `/usr/bin/python3` with `soffice` symlinked onto
PATH from `/Applications/LibreOffice.app/Contents/MacOS/soffice`), and then reading the
recalculated file with `openpyxl` (`data_only=True` for values, `data_only=False` for
formula text) and cross-checking against the `data/` and `universe/` source files.

**Recalculation result: 0 errors across 38,685 formulas** (`status: success`).

## Checks performed and results

### 1. Tab order — PASS
Found: `README, Refresh_Log, Recent_News, Inputs, Universe, Prices_Local, FX, Dividends,
Prices_GBP, Prices_Monthly, Returns_Monthly, Stats_Monthly, Drawdown, Stats_Daily,
Covariance, Correlation, Cov_LW, Cov_Daily, Expected_Returns, Optimisation, Variants,
Frontier, Risk_Contribution, Backtest, Unicorns, Stock_Fundamentals, Combined_Portfolio,
Sources_Assumptions`.
This is exactly SPEC_ANALYSIS.md §3's 23-tab order, with `Refresh_Log` and `Recent_News`
inserted right after `README` and `Variants` inserted right after `Optimisation` (before
`Frontier`) — a sensible placement for the three refresh-specific tabs. All spec tabs present,
nothing missing, nothing extra beyond the three expected additions.

### 2. Inputs rf/ERP/dates vs `universe/market_params.json` — PASS
- rf (Inputs!B17) = 0.0375 = `boe_bank_rate.value` (3.75%, as_of 2026-09-16). Matches.
- ERP (Inputs!B18) = 0.0417 = `damodaran_erp.value` (4.17%, as_of 2026-07-01, explicitly
  unchanged in the refresh). Matches.
- T36N (10y gilt) YTM 0.0530 = `gilt_yield_10y.value` 5.30%. Matches.
- T56 (30y gilt) YTM 0.0587 vs `gilt_yield_30y.value` 5.89% — a small, **documented**
  difference: the Inputs note explains this is the individual gilt's own YTM at its clean
  price (5.870%, giltsyield.com) versus the generic 30y benchmark TradingEconomics figure
  (5.890%) used elsewhere; this distinction is required by SPEC_ANALYSIS.md §5 (individual
  gilt YTM vs benchmark yield are legitimately different numbers) and is disclosed in the cell
  note. Not a defect.
- Price-as-at (2026-09-16), analysis date (2026-09-17), 5y window (2021-09-16→2026-09-16), 10y
  window (2016-09-16→2026-09-16), benchmark VWRP.L / secondary ^FTAS — all match SPEC_ANALYSIS
  §6 and market_params.json.

### 3. Prices_Monthly / Returns_Monthly end date — PASS
- `Prices_Monthly` last row = `2026-09-16`, explicitly labelled in a tab note as "the as-of
  date... a part month, and is excluded from every statistic."
- `Returns_Monthly` last row = `2026-09-16` (a real, computed partial-month return), with the
  tab's own note stating the statistics window is `2021-10-31` to `2026-08-31` (59 monthly
  returns) — i.e. the Sept-2026 stub is present but correctly excluded from Stats_Monthly's
  formula ranges (`$B$66:$B$124`, confirmed row 66 = 2021-10-31, row 124 = 2026-08-31).
- `Prices_GBP` (daily) correctly ends on `2026-09-16` (row 2531), confirming the SPEC §7
  Yahoo-hole patch worked and the panel does not silently stop on 2026-09-15.

### 4. Stats_Monthly β/β+/β− for RR.L, SGLN.L, SMGB.L, T56 vs numpy — PASS (< 1e-6, mostly < 1e-10)
Reconstructed the weighted-OLS-slope formula exactly as documented on the tab (`SUMPRODUCT`
weighted by the Up/Down flag columns, `n·Sxy − Sx·Sy)/(n·Sxx − Sx²)`) in numpy from the same
`Returns_Monthly` monthly data (asset column, benchmark column CI, Up flag CK, Down flag CL,
rows 66–124), pairwise-complete for missing months:

| Ticker | Excel β (full) | numpy β | Excel β+ | numpy β+ | Excel β− | numpy β− |
|---|---|---|---|---|---|---|
| SMGB.L | 2.29235909000776 | 2.2923590900077584 | 2.04832589980012 | 2.0483258998001213 | 2.31068459491334 | 2.310684594913342 |
| SGLN.L | 0.116298855613071 | 0.1162988556130706 | -0.179999018820043 | -0.17999901882004565 | 0.0767076758945885 | 0.07670767589458764 |
| RR.L | 1.23193957040971 | 1.2319395704097083 | 0.950292403296793 | 0.950292403296797 | 1.97420144797044 | 1.9742014479704344 |
| T56 | 0.704017550544905 | 0.7040175505449052 | 0.323568283005622 | 0.32356828300562146 | 0.524993888329873 | 0.5249938883298751 |

All four names reproduce to well under 1e-6 (most agree to ~1e-13–1e-16, i.e. floating-point
noise only).

### 5. Covariance / Cov_LW — PASS
- `Covariance` (37×37, monthly ×12 formulas): present, `_xlfn.COVARIANCE.S(...)*MonthsPerYear`
  formulas, SPCX correctly excluded from the 36-instrument optimiser universe per SPEC §5.
- `Correlation`: `CORREL` formulas, colour-scaled (conditional formatting confirmed present,
  no separate chart object — consistent with "heat-map" via conditional formatting).
- `Cov_LW`: documents δ derivation, `Sigma_LW = δ·F + (1-δ)·S`, top block rebuilt live from
  the monthly sample covariance.
- `Cov_Daily`: two blocks — 37×37 (core incl. SPCX, pairwise-complete, PSD-repaired) and 77×77
  (core + 40 unicorns) as required for Combined_Portfolio.

### 6. Optimisation — PASS
- Solver weights (row+1 of each block, "weight of the core sleeve (LIVE)") reproduce
  `data/weights.csv` to float precision (max abs diff ≈ 7.8e-16) across all six portfolios
  (MinVariance, MaxSharpe, Moderate12, MaxSortino, EqualWeight, NaiveReference) and all 37
  tickers. Row above ("solver weight, share of the optimised part") correctly renormalises by
  dividing by `(1 − SPCXWeight)` so the 36-instrument optimiser weights sum to 1 — verified
  algebraically (e.g. IBTM.L MinVariance: csv 0.2 = xlsx 0.205128205128205 × 0.975).
- Portfolio Summary block (ExpRet/Vol/Sharpe/betas) matches `data/analysis_results.json
  → portfolios.<name>` to ~1e-10 or better for every field checked (expected return blend,
  ex-ante LW vol, vol incl. SPCX, Sharpe ex-ante, β, β+, β−, β-asymmetry) — spot-checked in
  full for Moderate12, spot-checked for the other five via the tab's own built-in "PUBLISHED
  VALUES" cross-check block (rows 122–137), where every "difference (workbook − published)"
  row reads 0 (or ~1e-16, floating-point noise) for all six portfolios and all seven metrics.
- Constraint-check block (rows 94–118): all bucket caps, single-asset caps, group min/max and
  the ex-ante-vol-≤-target check read **TRUE** for the four solver-optimised portfolios
  (MinVariance, MaxSharpe, Moderate12, MaxSortino) and for NaiveReference. **One FALSE**: the
  `EqualWeight` "naive" reference portfolio fails the `stocks` group cap (29.58% weight vs a
  25% max) — this is correct behaviour, not a defect: EqualWeight/NaiveReference are
  reference-only equal-weight or user-suggested baskets, not solver output, so they are not
  bound by the optimiser's own constraints; the checkbox correctly flags that a naive 1/N
  weighting would in fact breach the stock-concentration limit. Sum of weights = 1 (to
  float precision) for all six portfolios.
- `SPCXWeight` flows through correctly: the Inputs lever (B32 = 0.025) reappears as the "core
  sleeve weight (LIVE)" for SPCX in every one of the six portfolio blocks (all read exactly
  0.025), and the tab's row-3 note plus the README both correctly describe the renormalisation
  mechanism.

### 7. Unicorns tab — PASS
- 40 data rows (rank 1–40), every one at exactly £1,000 allocated (Inputs!B12 lever).
- Header row carries every SPEC §8-required column: key backers, catalysts (12–24m),
  confidence (1–10), the three judge scores (asymmetry/backing/timing) plus a weighted score,
  10x end-state market cap ($bn), "100x possible?", avg daily value ($k), dossier file, plus
  the standard identity/price/beta/return columns.
- Sector-mix COUNTIF table sums to 40 across 22 sector labels; max-in-any-sector = 4, matching
  the Inputs sector cap lever (4 of 40), flagged "Within the moonshot sector cap? YES".
  Region-mix COUNTIF table (Europe 5 / Other 12 / UK 3 / US 20) also sums to 40, spanning 4
  regions.
- Payoff arithmetic block (rows 78–102): with the stated outcome mix (24 zero / 10 flat / 5 at
  10x / 1 at 30x = 40 names, matching the sleeve size — "Check: counts equal the sleeve size"
  reads OK), the arithmetic is internally consistent: terminal value
  0 + 10,000 + 50,000 + 30,000 = £90,000; sleeve cost £40,000; profit £50,000; multiple 2.25×;
  4 winners needed at 10x to break even (£40,000/£10,000); total book £250,000 (core held flat
  at £160,000 + sleeve £90,000); effect on the £200,000 book = 25%; sleeve share of book
  afterwards = 36%. The sensitivity row (0–6 winners at 10x) reads 0, 0.25, 0.5, …, 1.5× —
  correct arithmetic (n × £10,000 / £40,000).
- Sleeve-index statistics block cross-checked against `data/analysis_results.json →
  unicorn_sleeve` (mean/CAGR/vol/Sharpe/Sortino/skew/kurtosis/drawdown/VaR/CVaR/betas all
  match to displayed precision) and against `data/refresh_diff.json → unicorn_sleeve.new.*`
  (identical figures, confirming Refresh_Log's "new" column is sourced correctly).

### 8. Stock_Fundamentals WACC vs `data/fundamentals_table.csv` — PASS
Checked all 51 individual-stock rows on the tab (far more than the nominal 6), including the
6 "named" core stocks from PROJECT_BRIEF (RR.L, PLTR, plus AZN.L, SHEL.L, HSBA.L, MSFT as
core-universe examples) and all 40 unicorn-sleeve stocks with fundamentals. Every WACC value
matches `fundamentals_table.csv`'s `wacc` column to within ~1e-16 (floating-point noise only),
e.g. RR.L 0.0907565233005365 vs 0.09075652330053645; PLTR 0.0977030953673957 vs
0.0977030953673955; SPCX 0.156279943114179 vs 0.1562799431141792. The tab's documentation
rows correctly disclose the WACC formula (`E/(D+E)·Ke + D/(D+E)·Kd·(1−t)`), the Kd/tax-rate
bounding rules, and — usefully — a named list of tickers whose interest-expense figure is a
stale vintage relative to the latest balance-sheet debt figure, with a materiality flag
(CRBU 16.6% debt weight, GUTS 40.4% debt weight called out as the two cases where this
actually matters).

### 9. Combined_Portfolio total — PASS
- Sum of weights = 1 (to float precision); Total GBP allocated = £200,000; invested (whole
  shares) = £199,248.68.
- Combined statistics block (rows 172–186): expected return, volatility, Sharpe, β, β+, β−,
  β-asymmetry and both sleeves' risk-contribution shares all show "Workbook formula" vs
  "Published (Python)" with a `Difference` column reading 0 (or ~1e-16) in every row —
  matches `data/analysis_results.json → combined_portfolio`. Risk contribution: core sleeve
  68.1% / unicorn sleeve 31.9% of total risk, summing to 100% as documented (Euler
  decomposition).

### 10. Refresh_Log vs `data/refresh_diff.json` — PASS
Confirmed this refresh's `Refresh_Log` documents the **moonshot-sleeve rebuild** (old
quality sleeve vs new moonshot sleeve, both priced at the same 2026-09-16 close), which is
what `data/refresh_diff.json` itself contains (`sleeve_change`, `unicorn_sleeve`,
`combined_200k`, `portfolios`, etc.) — this is the correct source per SPEC §8, distinct from
the earlier 2026-09-11→2026-09-16 data refresh (`data/REFRESH_DIFF.md`). Spot-checked the
"SLEEVE A INDEX ... OLD QUALITY SLEEVE vs NEW MOONSHOT SLEEVE" section line-by-line against
`refresh_diff.json → unicorn_sleeve`: mean_ann_arith, CAGR, vol, Sharpe, Sortino, skew,
kurtosis, max drawdown, all VaR/CVaR, all betas — every "new" figure in the Excel tab matches
the JSON to full precision (e.g. mean_ann_arith new = 0.122350001783185 in both).

### 11. Recent_News vs the news JSON — PASS
- Row 2's claim "109 items from [3 files]" is exactly right: 37 + 32 + 40 = 109 items across
  `news_geopolitics-energy_2026-09-16.json`, `news_rates-inflation_2026-09-16.json`,
  `news_sectors-holdings_2026-09-16.json`.
- Counted 109 data rows in the tab (rows 6–114), matching exactly. The footer's own tally
  (negative 36 + positive 36 + unclear 1 = "total items 109") is internally consistent too.

### 12. Zero errors / no 'nan'/'None' / Arial — PASS
- Recalc: 0 Excel errors across 38,685 formulas (see above).
- Searched every sheet for cell values exactly equal (case-insensitively, trimmed) to `nan` or
  `none`: found **one** match, `Refresh_Log!D14` = `"none"`, which is legitimate English
  ("CONFIG edits required: none" — no code changes were needed for this rebuild), not a data
  artifact. A broader substring search for `\bnan\b` found 4 more hits, all in documentation
  prose ("Non-NaN rows...", "non-NaN annual interest-expense cell...") — not data leakage.
- Font: every populated cell across all 28 sheets uses `Arial` — confirmed by iterating every
  cell's `font.name` and finding only `{'Arial'}` in the resulting set.
- Freeze panes: set on all 28 sheets.
- Charts: `Frontier` (frontier scatter), `Optimisation` (weights bar chart), `Backtest` (line
  chart) each have 1 chart object; `Correlation` has a conditional-formatting colour scale
  (heat-map) instead of a chart object, consistent with the spec's "colour scale: red=-1,
  white=0, blue=+1" instruction on that tab.

## Overall
No blocking or major defects found. The one "FALSE" constraint-check cell (EqualWeight vs the
stocks-group cap) and the one literal string "none" are both correct, intentional workbook
behaviour rather than errors, and are called out above for transparency. The workbook
recalculates cleanly, is internally self-consistent (multiple own "workbook vs published"
cross-check blocks all read ~0 difference), and reproduces the independent Python outputs
(`data/analysis_results.json`, `data/weights.csv`, `data/fundamentals_table.csv`,
`data/refresh_diff.json`) to floating-point precision everywhere checked.

## Files
- Recalculated copy used for this verification:
  `/Users/georgewilliams/Desktop/Claude/Projects/Investing 101/24-unicorn-core-portfolio/data/verify_copy_refresh.xlsx`
- This report:
  `/Users/georgewilliams/Desktop/Claude/Projects/Investing 101/24-unicorn-core-portfolio/data/verify_excel_refresh_round1.md`
