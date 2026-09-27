# Blind Excel verification — round 1

`scripts/build_excel.py` was **not** read. `Portfolio_Model.xlsx` was copied to `data/verify_copy.xlsx`,
recalculated headlessly with LibreOffice via the xlsx skill's `recalc.py` (patched locally only to drop a
`tempfile.TemporaryDirectory(ignore_cleanup_errors=True)` kwarg that needs Python ≥3.10 — `/usr/bin/python3` here
is 3.9.6; the patch touches only that cleanup-error flag, not recalculation logic), then re-opened twice with
openpyxl (`data_only=False` for formulas, `data_only=True` for cached values) and cross-checked against
`data/*.csv`, `data/analysis_results.json` and independent numpy/pandas recomputation from
`data/prices_gbp_monthly.csv`.

**Two independent verification bugs of my own were found and corrected during this pass before they became false
findings** — noted below so the trail is honest: (1) pandas' `pct_change()` default `fill_method='pad'` silently
forward-fills genuine data gaps (e.g. SMEA.L, blank Dec-2023–Mar-2024 in the workbook), which first produced a
spurious ~0.15 correlation mismatch; re-run with `fill_method=None` matched the workbook to 1e-14 on all 630
pairs. (2) An off-by-one column range (`range(2,38)` instead of `range(2,39)`) silently dropped the 37th
column — DBMG.L / column AL — from three separate checks (Optimisation weight sums, the "trend" bucket, and
Risk_Contribution's total), each of which produced an apparent shortfall that vanished once the correct range was
used. Both are logged so a second reviewer doesn't need to rediscover them; neither is a workbook defect.

## Recalculation

```
{
  "status": "success",
  "total_errors": 0,
  "error_summary": {},
  "total_formulas": 38932
}
```

Zero formula errors across 38,932 formulas. A full `data_only=True` scan of all 459,656 non-empty cells found
**zero** `#REF!/#VALUE!/#DIV/0!/#NAME?/#NULL!/#NUM!/#N/A` errors and zero literal `"nan"` strings.

## 1. Structure, names, styling, font

- Tab order: README, Inputs, Universe, Prices_Local, FX, Dividends, Prices_GBP, Prices_Monthly, Returns_Monthly,
  Stats_Monthly, Drawdown, Stats_Daily, Covariance, Correlation, Cov_LW, Cov_Daily, Expected_Returns,
  Optimisation, **Variants**, Frontier, Risk_Contribution, Backtest, Unicorns, Stock_Fundamentals,
  Combined_Portfolio, Sources_Assumptions — matches SPEC §3 exactly plus Variants, in the right place.
- Defined names present and pointing at Inputs: `rf` (B17), `ERP` (B18), `Capital` (B7), `CoreCapital` (B10),
  `UnicornCapital` (B11), `TargetVol` (B31), `SPCXWeight` (B32) — plus `BlendWeight`, `GBPPerUnicorn`,
  `MonthsPerYear`, `TradingDays` (not required but consistent).
- README has the colour legend, tab map (all 26 tabs described), "how to change the model", and a limitations
  section (survivorship, estimation error, SPCX's 64 bars, no true 10y backtest, etc.).
- Inputs: yellow fill (`FFFFFF00`) on every editable lever (capital, sleeve split, £/unicorn, rf, ERP, T36N/T56
  yields, blend weight, haircut, target vol, SPCXWeight), each with a source note in column D.
- Font: sampled 520 cells at random across all 26 sheets (well over the requested 200) — 100% Arial, 0 exceptions.
- No lowercased-formula-text cells found anywhere (the LibreOffice-parse-failure tell) — scanned all formula
  cells in the same 520-cell sample and separately grepped for `XLOOKUP/FILTER(/LET(/LAMBDA(` workbook-wide: 0 hits.
- Freeze panes present on all 26 sheets. Number formats spot-checked: `£#,##0` on GBP cells, `0.00%`/`0.0%` on
  rates and vols, `0.00` on betas — matches spec.

## 2. Returns_Monthly

5 random formula cells checked (ticker, date, formula, cached value vs my own `P_t/P_{t-1}-1` from
`data/prices_gbp_monthly.csv`):

| Cell | Ticker | Date | Formula | Cached | My calc | Diff |
|---|---|---|---|---|---|---|
| G86 | ISF.L | 2023-06-30 | `=Prices_Monthly!G87/Prices_Monthly!G86-1` | 0.0139954263782589 | 0.0139954263782607 | 1.8e-15 |
| AP47 | 1833.HK | 2020-03-31 | `=Prices_Monthly!AP48/Prices_Monthly!AP47-1` | -0.00560212211199762 | -0.00560212211199973 | 2.1e-15 |
| AR100 | GNS.L | 2024-08-31 | `=Prices_Monthly!AR101/AR100-1` | -0.0230010952902533 | -0.0230010952902523 | 1.0e-15 |
| AO20 | ERII | 2017-12-31 | `=Prices_Monthly!AO21/AO20-1` | -0.222206471672095 | -0.222206471672095 | 1.7e-16 |
| AA27 | MSFT | 2018-07-31 | `=Prices_Monthly!AA28/AA27-1` | 0.0708158835636403 | 0.0708158835636381 | 2.2e-15 |

All 5 correct: right two `Prices_Monthly` cells (numerator row = denominator row + 1, and the numerator row's own
date matches the Returns_Monthly row's label date), cached value = `P_t/P_{t-1}-1` to floating-point precision.

## 3. Stats_Monthly, Drawdown

Window: `Returns_Monthly!$*$66:$*$124` = 2021-10-31 to 2026-08-31 (59 months), matching the spec's 5y window.
Recomputed independently with numpy (sample-bias-corrected SKEW/KURT reproducing Excel's exact formulas, OLS
slope for beta, and the same up/down-flag-masked weighted-OLS identity the workbook uses for β+/β−) for **RR.L,
SGLN.L, IBTM.L, SMGB.L, T56**:

| Ticker | Mean×12 | Vol(ann) | Sharpe | Skew | β | β+ | β− | CAGR | VaR95 | CVaR95 |
|---|---|---|---|---|---|---|---|---|---|---|
| SMGB.L | match | match | match | match | match | match | match | match | match | match |
| SGLN.L | match | match | match | match | match | match | match | match | match | match |
| RR.L | match | match | match | match | match | match | match | match | match | match |
| IBTM.L | match | match | match | match | match | match | match | match | match | match |
| T56 | match | match | match | match | match | match | match | match | match | match |

Every one of these 50 values matched the workbook's cached value to ≤1e-6 (most to 1e-15) once I fixed my own
Prices_Monthly-row-offset misreading (CAGR uses `Prices_Monthly!row66/row125`, where row66 is the month **before**
the stats window starts — 2021-09-30 — and row125 is 2026-08-31, not the partial-month as-of date; this is
correctly documented behaviour, not a bug). β+/β− formula text is the explicit SUMPRODUCT-based weighted-OLS-slope
construction the spec calls for (not a filtered SLOPE), built on `Up`/`Down` flags defined as
`IF(bench_excess>0,1,0)` / `IF(bench_excess<0,1,0)` in Returns_Monthly — exactly per spec.

Drawdown helper for VWRP.L: `MIN(Drawdown!$AM$6:$AM$65)` (cell referenced by `Stats_Monthly!Z9`) = **-0.114583374383364**,
matching both my own `cummax`-based recomputation from the same monthly series and the Drawdown tab's own cached
minimum in that column exactly (max drawdown at 2025-04-30).

## 4. Covariance / Correlation / Cov_LW

- **Covariance** (36×36, monthly `COVARIANCE.S(...)×12`): 3 off-diagonal pairs + 1 diagonal
  (IITU.L–VMID.L, RR.L–SGLN.L, IBTM.L–T56, VWRP.L–VWRP.L) recomputed with `np.cov(...,ddof=1)*12` on the same
  monthly window — all 4 match to full float precision.
- **Correlation**: recomputing `r̄` (average off-diagonal correlation used by Cov_LW) initially disagreed with the
  workbook by ~0.003 — traced to my own script's pandas `pct_change()` default forward-fill silently bridging a
  genuine 4-month gap in SMEA.L (Dec-2023–Mar-2024, correctly blank in `Prices_Monthly`). Re-run with
  `fill_method=None`: all 630 off-diagonal pairs match to ~1e-14, and `r̄` matches the workbook's `Cov_LW!B15`
  (0.22332121472207) exactly.
- **Cov_LW**: formula text confirmed — `F_ij = r̄·σ_i·σ_j` (`=$B$15*$B$18*$B$19` etc., diagonal = the actual
  variance from Covariance) and `Sigma_LW = δ·F + (1−δ)·S` (`=$B$6*$B57+(1-$B$6)*Covariance!$B$6` etc.), both on
  the monthly-formula reconstruction. Spot-checked IITU.L–VMID.L: `δ·F+(1−δ)·S` computed by hand from the cached
  δ/F/S = 0.013538923739962114, matching the cached `Sigma_LW` cell (0.0135389237399621) exactly. The DAILY
  Ledoit-Wolf matrix that actually feeds the optimiser (Cov_LW rows 133+, "values (Python) — THIS is the
  optimiser input") matches `data/cov_lw.csv` exactly on the cell checked (IITU.L row/col).

## 5. Optimisation

- **Weights**: MinVariance, MaxSharpe, Moderate12, MaxSortino compared cell-by-cell (all 36 optimizer tickers +
  SPCX) against `data/weights.csv`. Row 24 ("weight of the core sleeve (LIVE)" = row23 solver weight ×
  `(1-SPCXWeight)`) matches `weights.csv` to ≤5e-16 for every ticker in every portfolio, and each portfolio's
  36-name core-share weights plus the 2.5% SPCX policy weight sum to exactly 1.0. (My first attempt compared the
  wrong row — row 23, "share of the optimised part", which by definition sums to 1.0 over the 36 names *before*
  the SPCXWeight scaling — against `weights.csv`'s core-share convention; that mismatch was my error, not the
  workbook's, and is resolved by using row 24 as intended.)
- **ExpRet** = `SUMPRODUCT(w, blend)`: MinVariance/MaxSharpe/Moderate12/MaxSortino all match
  `data/analysis_results.json → portfolios.<name>.exp_return_blend` exactly (e.g. Moderate12: workbook
  0.154973826245909 = JSON 0.1549738262459087).
- **Vol formula**: `=SQRT(SUMPRODUCT(w, Sigma·w))`. The tab uses **two different Σ** depending on the row: row 77
  ("Volatility (Ledoit-Wolf, optimised part)") sums `Sigma_LW·w` built from the **DAILY** Ledoit-Wolf matrix
  (Cov_LW's Python-values block, `=data/cov_lw.csv`, excluding SPCX) — this is the one the 12% target binds on,
  and it reproduces **0.12000000000346** for Moderate12 (i.e. the headline 12% does reproduce, to 9 decimal
  places — residual noise is SLSQP's solver tolerance). Row 78 ("as held", incl. SPCX) instead sums against
  `Cov_Daily` (the full 37×37 daily sample covariance including SPCX's 63-bar row/column) and is higher
  (12.79%), correctly reflecting SPCX's outsized volatility once it's included.
- **β/β+/β−** = `SUMPRODUCT(w, β-column)` including SPCX at its policy weight in the "as held" rows: confirmed by
  formula text and by matching `analysis_results.json`'s `beta_vwrp`/`beta_up`/`beta_down` for all four portfolios
  exactly.
- **£ = w×CoreCapital, shares = INT**: formula text confirmed (`=B24*CoreCapital`, `=IF(B12>0,INT(B27/B12),0)`).
- **Constraint-check block**: all bucket/group/single-asset/target-vol checks are `TRUE` for the four solver
  portfolios; the naive `EqualWeight` reference correctly shows `FALSE` on the stocks-bucket cap (29.6% >
  25% max) — this is the check working as intended on a portfolio that was never meant to satisfy the
  constraints, not a defect.
- **SPCXWeight sensitivity**: wrote 0.05 into a fresh copy's `Inputs!B32`, recalculated (0 formula errors, 38,932
  formulas). SPCX's £ doubled from £4,000 → £8,000 for every portfolio; the core-sleeve weight for SPCX's column
  changed from 0.025 → 0.05 exactly; the "as held" volatility and expected return of Moderate12 moved
  (12.79%→13.84% vol, ExpRet 15.497%→15.498%) while the Ledoit-Wolf "optimised part" vol necessarily drifted off
  the 12% target (12.00%→11.69%) because — as README explicitly documents — **weights do not re-optimise** when a
  lever changes; only £/shares/betas/vol-as-held rescale. This is the documented, correct behaviour, not a bug.
  The Variants tab is the mechanism the workbook actually provides for genuine re-solved sensitivities.

## 6. Unicorns, Stock_Fundamentals, Combined_Portfolio

- **Unicorns**: 40 rows (ranks 1–40), each `GBP allocated` (col L) = exactly `GBPPerUnicorn` (1000) via
  `=GBPPerUnicorn`, `shares` (col M) = `IF(K>0,INT(L/K),0)` verified against price_gbp for all 40 — zero
  mismatches. Sector-mix COUNTIF table (rows 51–71, over `$G$6:$G$45`) sums to 40, max any one sector = 4 (≤5
  limit respected). Region-mix COUNTIF table (columns E:G, rows 51–56, over `$F$6:$F$45`) sums to 40 across 4
  regions (≥3 required) — found at columns E:G rather than A:C on first pass (my error in an initial narrow scan,
  corrected). Sleeve index stats (equal-weight, daily-rebalanced, values from Python) match
  `analysis_results.json → unicorn_sleeve.stats` exactly on every field checked (mean_ann_arith, CAGR, vol,
  Sharpe, max_drawdown all identical to the last displayed digit).
- **Stock_Fundamentals**: WACC formula (`=AN/(AM+AN)*AS+AM/(AM+AN)*AT*(1-AU)`, i.e.
  `E/(D+E)·Ke + D/(D+E)·Kd·(1−t)`), Ke (`=rf+β·ERP`), Kd (bounded 0–30%, falls back to `rf+2%` when no usable
  interest expense/debt), and tax rate (bounded 0–35%, falls back to 25%) all confirmed by formula text and
  reproduce `data/fundamentals_table.csv` for the 6 stocks checked (RR.L, PLTR, ASML.AS, BRK-B, 1833.HK, SLX.AX).
  Notably, this tab's own documentation (rows 58–60) **proactively corrects two currency/labelling issues flagged
  in the prior fundamentals verification round**: equity (E) and debt (D) in the WACC calculation are both
  rebuilt in GBP (`AM`=total debt GBP, `AN`=equity market value GBP = shares×GBP price) rather than reusing
  Yahoo's `info['marketCap']` in the company's own reporting currency, and the D/E column explicitly documents
  where it disagrees with the published `fundamentals_table.csv` value and why. One issue **does carry through
  unchanged from the prior round**: PLTR's and NVTS's `cost_of_debt` (1.64%, 2.92%) trace to a **stale, non-latest-FY**
  Interest Expense figure (PLTR: FY2023's £3.47m — FY2025 and FY2024 are both NaN in `data/fin/PLTR_income_annual.csv`;
  NVTS: FY2024's £150k — FY2025 is NaN) divided by a **different-vintage** total-debt figure (latest quarter), rather
  than triggering the documented `rf+2%` fallback for "no usable interest expense." Financially immaterial (debt
  is <0.2% of enterprise value for both names, per the prior round), but worth a one-line footnote since the
  formula's own IF-condition (`AND(N(Y)<>0,N(AB)<>0)`) was clearly written to catch a *blank* cell, not a
  populated-but-stale one, and the row 58 note as written ("falls back to rf+2%") over-promises what the formula
  actually does for these two names.
- **Combined_Portfolio**: total = £200,000 exactly (`=$K$83`), invested (whole shares) = £199,004.17, implied
  residual = £995.83. Weights sum to 1 (`B171`). Combined ExpRet (0.156139754449162), Vol (0.144463696381643),
  Sharpe (0.821242688791102) and risk-contribution-by-sleeve (core 67.80% / unicorn 32.20%) all match
  `analysis_results.json → combined_portfolio` exactly. SUMIF pivots: **by sleeve** sums to 1.0, **by bucket**
  sums to 1.0, **by listing region** sums to 1.0 — all correct. **By currency does not**: it sums to **1.719**,
  not 1.0. Root cause: column F holds both `"GBP"` and `"GBp"` as distinct currency labels for different rows, but
  Excel's `SUMIF` text-criteria matching is case-insensitive, so the criteria `"GBP"` (row 92) and `"GBp"` (row 93)
  both silently match the *same* underlying cells and each independently sum the full ~71.9% GBP+GBp weight —
  double-counting it. This is a genuine, confirmed formula defect (not one of my own verification bugs): fix by
  merging the GBP/GBp rows into one currency-pivot bucket, or by using a case-sensitive match (e.g.
  `SUMPRODUCT(--EXACT($F$6:$F$82,$M92),$J$6:$J$82)`) instead of `SUMIF`.

## 7. Zero errors, no nan/None, charts, Sources_Assumptions

- **Formula errors**: 0 across 38,932 formulas (recalc) and 0 across all 459,656 non-empty cells (manual scan for
  `#REF!` etc.).
- **`"nan"` strings**: 0.
- **`"None"` strings**: 3, all on `Sources_Assumptions` (C8 `gilt_yield_2y`, C35 `damodaran_uk_country_risk_premium`,
  C43 `ii_gilts_rule/minimum_deal_size`) — each row's own note column (F) explains the figure could not be
  confirmed from primary sources this session; the "value" cell should read something like "not found" rather
  than Python's literal `None`, but this is cosmetic (each row is self-documenting) rather than a data-integrity
  problem.
- **Lowercased-formula cells** (the LibreOffice-parse-failure tell): 0 found in the 520-cell random sample or in
  any formula string worldwide matched by a lowercase-function-name regex.
- **Charts**: 3 chart objects found — Optimisation (weights bar chart), Frontier (frontier scatter with the four
  portfolios and individual assets), Backtest (growth-of-£ line chart) — matching the spec's three chart
  requirements; the fourth ("correlation heat-map") is implemented as 3-colour-scale conditional formatting on
  `Correlation!B6:AK41` (red −1 / white 0 / blue +1), exactly as the spec calls for and as the tab's own note
  describes, not a fourth chart object.
- **Sources_Assumptions**: non-empty (139 populated rows), 46 URL-bearing cells.
- **Frontier**: 30 points confirmed present; the formula re-check block (5 points: 1, 8, 15, 22, 30) shows zero
  difference between the solver's stored return/vol and the live `SUMPRODUCT`/`SQRT(SUMPRODUCT(...))`
  recomputation for every one of the 5 points and both metrics.
- **Risk_Contribution**: Euler decomposition holds exactly — `SUM(RC_i)` over all 37 rows (36 optimizer names +
  DBMG.L, which I initially miscounted due to an off-by-one range in my own check) = **0.12000000000346**,
  identical to the headline portfolio's own volatility cell, and `% of portfolio risk` sums to exactly 1.0.

## Summary

No formula-execution defects: the recalculation is clean (0/38,932), and every one of the ~15 independent
numerical cross-checks against `data/*.csv` / `data/analysis_results.json` / from-scratch numpy recomputation
matched to floating-point precision once my own verification-script bugs (pandas' `pct_change` autofill, and two
off-by-one column/row ranges that both happened to drop the 37th core instrument, DBMG.L) were found and
corrected. Two genuine workbook issues survive:

1. **`Combined_Portfolio`'s "by currency" SUMIF pivot double-counts** because `"GBP"` and `"GBp"` are both present
   as literal text in column F and `SUMIF` criteria matching is case-insensitive — the pivot sums to 171.9%
   instead of 100%. This is informational-only (the combined ExpRet/Vol/Sharpe/risk-contribution figures use
   `SUMPRODUCT` elsewhere and are unaffected), but it is a genuine, reproducible defect in the currency-mix table.
2. **PLTR's and NVTS's `Kd` (Stock_Fundamentals)** are computed from a stale (non-latest-FY) Interest Expense
   figure mixed with a different-vintage total-debt figure, rather than triggering the documented `rf+2%`
   fallback — inherited unchanged from the upstream `fundamentals_table.csv` (previously flagged, financially
   immaterial given <0.2% debt/EV for both names), but the row-58 README note on this tab overstates what the
   fallback formula actually catches.

Everything else checked — tab structure/names/styling/fonts, Returns_Monthly, Stats_Monthly (mean/vol/Sharpe/
skew/beta/β±/VaR/CVaR/CAGR/drawdown), Covariance/Correlation/Cov_LW, all four solver portfolios' weights/ExpRet/
Vol/β/£/shares/constraints and the SPCXWeight sensitivity, the Unicorns sleeve (£1,000/shares/sector+region
COUNTIFs/sleeve stats), Stock_Fundamentals' WACC/Ke chain, Combined_Portfolio's totals/sleeve+bucket+region pivots
and combined stats, Frontier's 30 points and formula re-check, Risk_Contribution's Euler identity, charts, and
Sources_Assumptions — reproduces independently to the precision requested (≤1e-6, mostly ≤1e-14).
