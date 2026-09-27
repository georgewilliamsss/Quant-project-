# Blind Excel verification — round 2

`scripts/build_excel.py` was **not** read. `Portfolio_Model.xlsx` was copied to `data/verify_copy.xlsx`,
recalculated headlessly with LibreOffice via the xlsx skill's `recalc.py` (patched in the scratchpad only —
dropped a `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)` kwarg that needs Python ≥3.10; `/usr/bin/python3`
here is 3.9.6 — the patch touches only that cleanup-error flag, not recalculation logic), then re-opened twice
with openpyxl (`data_only=False` for formulas, `data_only=True` for cached values) and cross-checked against
`data/*.csv`, `data/analysis_results.json` and independent numpy/pandas recomputation.

**One verification bug of my own was found and corrected before it became a false finding**, in the same family
as round 1's warnings: recomputing Covariance off-diagonals by doing `prices.reindex(<59-date window>).pct_change()`
drops the first return in the window, because the row before the window's first date isn't present once you've
already reindexed to just the window — `pct_change()` then has no prior price to divide by for that first date and
returns NaN, silently shrinking n from 59 to 58 and shifting every subsequent covariance by a few 1e-4. Computing
`pct_change()` on the FULL price series first and only THEN subsetting to the 59-month window fixes it — all four
values then matched to full float precision. Logged here so a third reviewer doesn't rediscover it.

## Recalculation

```
{
  "status": "success",
  "total_errors": 0,
  "error_summary": {},
  "total_formulas": 38930
}
```

Zero formula errors across 38,930 formulas (round 1 reported 38,932 on a slightly earlier build; the two-formula
difference is immaterial and not investigated further since both runs are error-free). A full `data_only=True`
scan for `#REF!/#VALUE!/#DIV/0!/#NAME?/#NULL!/#NUM!/#N/A`, literal `"None"`/`"nan"`/`"NaN"` strings, and
lowercase-formula-text cells (the LibreOffice-parse-failure tell) found **zero** of all three, workbook-wide.

## 1. Structure, names, styling, font

- Tab order (26 tabs): README, Inputs, Universe, Prices_Local, FX, Dividends, Prices_GBP, Prices_Monthly,
  Returns_Monthly, Stats_Monthly, Drawdown, Stats_Daily, Covariance, Correlation, Cov_LW, Cov_Daily,
  Expected_Returns, Optimisation, **Variants**, Frontier, Risk_Contribution, Backtest, Unicorns,
  Stock_Fundamentals, Combined_Portfolio, Sources_Assumptions — matches SPEC §3 exactly plus Variants.
- Defined names confirmed pointing at Inputs and holding sane values: `rf`=B17=0.0375, `ERP`=B18=0.0417,
  `Capital`=B7=200000, `CoreCapital`=B10=160000 (formula `=$B$7*$B$8`), `UnicornCapital`=B11=40000
  (`=$B$7*$B$9`), `TargetVol`=B31=0.12, `SPCXWeight`=B32=0.025 — plus `BlendWeight`, `GBPPerUnicorn`,
  `MonthsPerYear`, `TradingDays`.
- Inputs styling: the raw levers (Capital, rf, ERP, TargetVol, SPCXWeight) carry yellow fill (`FFFFFF00`) and
  blue font (`FF0000FF`); the two derived cells (CoreCapital, UnicornCapital) are correctly black-font formulas
  with no fill, consistent with the blue-input/black-formula convention.
- README `A10` = "COLOUR LEGEND"; `B17` names the editable defined names; `B21` documents that weights do not
  re-optimise on lever changes — legend and tab map present.
- Font: sampled 200 non-empty cells at random across all 26 sheets — 100% Arial, 0 exceptions.

## 2. Returns_Monthly

5 random formula cells, checked against `P_t/P_{t-1}-1` computed independently from `data/prices_gbp_monthly.csv`:

| Cell | Ticker | Date | Formula | Cached | My calc | Diff |
|---|---|---|---|---|---|---|
| CG56 | ^GSPC | 2020-12-31 | `=Prices_Monthly!CG57/Prices_Monthly!CG56-1` | 0.0143902328792884 | 0.0143902328792889 | 4.7e-16 |
| K12 | IJPA.L | 2017-04-30 | `=Prices_Monthly!K13/Prices_Monthly!K12-1` | -0.0211891511452408 | -0.0211891511452408 | 1.7e-17 |
| BR111 | NVTS | 2025-07-31 | `=Prices_Monthly!BR112/Prices_Monthly!BR111-1` | 0.158081799031463 | 0.158081799031464 | 8.0e-16 |
| I80 | WLDS.L | 2022-12-31 | `=Prices_Monthly!I81/Prices_Monthly!I80-1` | -0.0293774665568022 | -0.0293774665567990 | 3.2e-15 |
| BN122 | IMSR | 2026-06-30 | `=Prices_Monthly!BN123/Prices_Monthly!BN122-1` | -0.213389353699555 | -0.213389353699557 | 6.9e-16 |

All 5 correct: right two `Prices_Monthly` cells, cached value = `P_t/P_{t-1}-1` to floating-point precision.

## 3. Stats_Monthly, Drawdown

Window: `Returns_Monthly!$*$66:$*$124` = 2021-10-31 to 2026-08-31 (59 months). Recomputed independently with
numpy (sample-bias-corrected SKEW reproducing Excel's exact formula, OLS slope for beta, the explicit
weighted-OLS-slope identity for β+/β− over the Up/Down flags) for **RR.L, SGLN.L, IBTM.L, SMGB.L, T56**:

| Ticker | Mean×12 diff | Vol diff | Sharpe diff | Skew diff | β diff | β+ diff | β− diff |
|---|---|---|---|---|---|---|---|
| RR.L | 0 | 1.7e-16 | ~1e-14 | ~4e-15 | ~5e-14 | ~7e-14 | ~2e-14 |
| SGLN.L | 3.3e-16 | 1.9e-15 | ~1e-14 | ~5e-15 | ~5e-14 | ~2.6e-14 | ~7.7e-14 |
| IBTM.L | 3.5e-18 | 3.9e-16 | ~2e-14 | ~1.7e-13 | ~7e-14 | ~2.4e-13 | ~4.4e-13 |
| SMGB.L | 1.8e-15 | 2.2e-15 | ~2e-15 | ~8e-14 | ~1e-14 | ~1.2e-13 | ~7e-13 |
| T56 | 1.4e-17 | 2.5e-16 | ~3e-14 | ~5.5e-13 | ~2.3e-13 | ~8.2e-13 | ~8.2e-14 |

All well inside the requested 1e-6 tolerance (most inside 1e-13). β+/β− formula text is the explicit
SUMPRODUCT-weighted-OLS-slope construction over the `Up`/`Down` flags defined on Returns_Monthly, matching spec
(not a filtered SLOPE).

Drawdown helper for VWRP.L: `Stats_Monthly` cell `=IFERROR(MIN(Drawdown!$I$6:$I$65),"")` = **-0.114583374383364**,
matching my own independent `cummax`-based recomputation from the same 59-month window exactly (max drawdown at
2025-04-30).

## 4. Covariance / Correlation / Cov_LW

- **Covariance** (monthly `COVARIANCE.S(...)×MonthsPerYear`): IITU.L–VMID.L, RR.L–SGLN.L, IBTM.L–T56 (all
  off-diagonal) plus the T56 diagonal, recomputed on the FULL monthly price series then subset to the 59-month
  window (see note above on my own reindexing artifact) — all 4 match the cached values to ≤6e-17.
- **Cov_LW**: formula text confirmed: `F_ij = r̄·σ_i·σ_j` (e.g. `=$B$15*$B$18*$B$19`, diagonal pulled straight
  from Covariance's own variance), `Sigma_LW = δ·F + (1−δ)·S` (e.g.
  `=$B$6*$B57+(1-$B$6)*Covariance!$B$6`). Hand-computed IITU.L–VMID.L from the cached δ=0.0357500660475325,
  r̄=0.22332121472207, σ_IITU=0.222657741105113, σ_VMID=0.151994819332427 and the cached sample covariance
  0.0137606762472012 → **0.013538923739962112**, matching the cached Sigma_LW cell (0.0135389237399621) to full
  float precision. The DAILY Ledoit-Wolf block that actually feeds the optimiser (rows 133+, "values (Python) —
  THIS is the optimiser input") reproduces `data/cov_lw.csv` exactly for the IITU.L/VMID.L 2×2 block checked.

## 5. Optimisation

- **Weights**: MinVariance, MaxSharpe, Moderate12, MaxSortino compared cell-by-cell (all 36 optimiser tickers)
  against `data/weights.csv`'s core-share row — max diff across all four portfolios = 5.0e-16.
- **ExpRet** = `SUMPRODUCT(w, blend)`: all four portfolios' `Optimisation!C73` ("Expected return, as held") match
  `analysis_results.json → portfolios.<name>.exp_return_blend` exactly (e.g. Moderate12: workbook
  0.154973826245909 = JSON 0.1549738262459087).
- **Vol formula**: the tab exposes both. Row 77 ("Volatility, Ledoit-Wolf optimised part") sums against the
  **DAILY Ledoit-Wolf matrix** (Cov_LW's Python-values block, excludes SPCX) and reproduces **0.12000000000346**
  for Moderate12 — the 12% headline does reproduce (residual is SLSQP solver tolerance). Row 78 ("as held, 37
  lines incl. SPCX") sums against `Cov_Daily` and is higher (12.79% for Moderate12), correctly reflecting SPCX's
  extra volatility once included. The workbook's own built-in cross-check block (rows 122–137, "PUBLISHED VALUES
  FROM scripts/analysis.py") shows every "difference (workbook − published)" row at 0 (or ~1e-16 float noise) for
  ExpRet, both vol variants, Sharpe, β, β+, β− across all six portfolios — a stronger check than I could run by
  hand, and it passes.
- **β/β+/β−** = `SUMPRODUCT(w, β-column)`, confirmed by formula text (`=SUMPRODUCT($B32:$AL32,$B13:$AL13)` etc.)
  and by the zero-diff cross-check rows above.
- **£ = w×CoreCapital, shares = INT**: formula text confirmed (`=B40*CoreCapital`, `=IF(B12>0,INT(B43/B12),0)`).
- **Constraint-check block**: all bucket, single-asset-cap, group-min/max and target-vol checks are `TRUE` for
  MinVariance/MaxSharpe/Moderate12/MaxSortino. EqualWeight correctly shows `FALSE` on the stocks-group cap
  (29.58% > 25% max) — the naive reference isn't meant to satisfy the constraints, so this is the check working
  as intended, not a defect.
- **SPCXWeight sensitivity**: wrote 0.05 into a fresh copy's `Inputs!B32`, recalculated (0 formula errors, 38,930
  formulas). Moderate12's SPCX £ doubled £4,000→£8,000 exactly; "as held" volatility moved 12.79%→13.84% and
  ExpRet moved 15.4974%→15.4984%, matching round 1's documented sensitivity behaviour (weights don't
  re-optimise; only £/shares/betas/vol-as-held rescale).

## 6. Unicorns, Stock_Fundamentals, Combined_Portfolio

- **Unicorns**: exactly 40 rows. `GBP allocated` = `=GBPPerUnicorn` (1000) on every row; `Shares = INT` formula
  `=IF(K6>0,INT(L6/K6),0)` matches independently-computed `INT(1000/price_gbp)` for all 40 — zero mismatches.
  Sector-mix COUNTIF table sums to 40 (max any one sector = 4, ≤5 limit respected); region-mix COUNTIF table
  sums to 40 across 4 regions (≥3 required).
- **Stock_Fundamentals**: WACC formula (`E/(D+E)·Ke + D/(D+E)·Kd·(1−t)`) reproduces
  `data/fundamentals_table.csv`'s `wacc` column exactly for all 6 checked stocks (RR.L, PLTR, ASML.AS, BRK-B,
  1833.HK, SLX.AX) — diffs ≤1e-13. The round-1 blocker on PLTR/NVTS's stale interest-expense vintage is
  resolved as the author's account describes: all 9 affected rows (PLTR, NVTS, GNS.L, NXL.AX, INOD, OVH.PA,
  AMPX, WVE, ARA.TO) carry cell comments on both the Interest-expense and Kd cells naming the period used, the
  latest annual column on file, and — for OVH.PA specifically — the MATERIAL flag with its 36.7% debt weight and
  the ~0.37pp WACC sensitivity, correctly distinguishing it from PLTR/NVTS's immaterial (<0.2% of
  debt+equity) cases. Row 4's header note states the fallback fires only when the cell is empty or zero, not
  merely stale.
- **Combined_Portfolio**: total = £200,000 exactly (`=SUM(K6:K82)`); residual cash (whole shares only) =
  £995.83 (matching round 1's £995.83, i.e. invested = £199,004.17). Weights sum to 1 (by-sleeve, by-bucket,
  by-listing-region SUMIF pivots each sum to 1.000000000000001). **By-currency pivot — the round-1 MAJOR fix
  confirmed resolved**: it no longer uses SUMIF. Column F still carries both `GBP` and `GBp` labels (GBp is a
  quotation unit, not a currency, for the 20 pence-quoted LSE lines), but the pivot now folds them via
  `=SUMPRODUCT(--EXACT(UPPER(Combined_Portfolio!$F$6:$F$82),$M89),Combined_Portfolio!$J$6:$J$82)` — a
  case-sensitive match against the upper-cased range — giving 6 currency rows (AUD 2.5%, CAD 2.0%, EUR 3.5%, GBP
  71.903405989318%, HKD 1.0%, USD 19.0965940106821%) that sum to **exactly 1.0**, not 1.719 as in round 1. A
  visible note at row 96 explains the fold and why the other three pivots keep plain SUMIF (no case collision in
  those columns).

## 7. Zero errors, no nan/None, charts, Sources_Assumptions

- **Formula errors**: 0 across 38,930 formulas (recalc) and 0 across a full manual scan for
  `#REF!/#VALUE!/#DIV/0!/#NAME?/#NULL!/#NUM!/#N/A`.
- **`"None"`/`"nan"`/`"NaN"` strings**: 0, workbook-wide — the round-1 MINOR fix (an `sval()` helper rendering
  Python `None`/NaN as "not found") is confirmed resolved; `Sources_Assumptions` C8/C35/C43 no longer read
  literal "None".
- **Lowercased-formula cells** (LibreOffice-parse-failure tell): 0 found across every formula cell in the
  workbook (regex-matched for lowercase built-in function names).
- **Charts**: 3 chart objects (Optimisation — weights bar chart; Frontier — frontier scatter with the four
  portfolios and individual assets; Backtest — growth-of-£ line chart), plus the "correlation heat-map"
  implemented as a 3-colour-scale conditional-formatting rule on `Correlation!B6:AK41` (confirmed present) —
  matching the spec's four chart requirements exactly as round 1 found.
- **Sources_Assumptions**: 140 populated rows, 46 URLs found across the sheet — non-empty with sources, as
  required.

## Summary vs round-1 issues

All three round-1 findings are confirmed resolved on re-verification:

1. **MAJOR — Combined_Portfolio currency pivot double-counting (171.9%→100%)**: fixed, confirmed — case-sensitive
   `SUMPRODUCT(--EXACT(UPPER(...)))` formula now sums to exactly 1.0 across 6 currency rows.
2. **MINOR — PLTR/NVTS (and 7 more) stale interest-expense vintage**: fixed, confirmed — all 9 rows carry
   explanatory cell comments; OVH.PA is correctly flagged MATERIAL (36.7% debt weight) rather than lumped in
   with the immaterial PLTR/NVTS cases.
3. **MINOR — literal `"None"` strings in Sources_Assumptions**: fixed, confirmed — 0 found workbook-wide.

No new defects were found in this round. Zero formula errors, zero error-value cells, zero nan/None strings,
zero lowercased-formula cells, all structural/naming/styling requirements met, all recomputed statistics and
optimisation outputs matched independent recalculation to well inside the requested tolerances, and the
SPCXWeight sensitivity lever behaves as documented.
