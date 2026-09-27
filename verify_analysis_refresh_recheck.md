# Re-check — level-base fix for the moonshot sleeve (as-of 2026-09-16)

*Educational analysis, not personalised investment advice. Recheck only: `scripts/analysis.py` was NOT read.
All figures below were recomputed independently from the regenerated `data/analysis_results.json`,
`data/refresh_diff.json`, `data/REFRESH_DIFF.md`, `data/stats_daily.csv` and the archived counterparts in
`archive/2026-09-16-quality-sleeve/data/`, using `/usr/bin/python3` (pandas/numpy).*

**Scope:** re-verify the single MAJOR finding from `data/verify_analysis_refresh.md` section 5.1 (sleeve
level based at 1.0 ON the first return date instead of the day before, losing the first day's return from
`total_return`/`cagr` while every other statistic stayed right) against the regenerated data files only —
not against `scripts/analysis.py`.

## 1. The reported bug is fixed, and the corrected numbers match the finding's own recomputation

`data/analysis_results.json -> unicorn_sleeve.stats`:

| Field | Pre-fix (as flagged) | Now | Finding's "correct" value | Match |
|---|---|---|---|---|
| `total_return` | 0.5285281599 | **0.547638349519344** | 0.5476383495 | exact |
| `cagr` | 0.0886291 | **0.09128727248850588** | 0.0911986 (252-day) | see §2 |

`total_return` now equals `prod(1+r)-1` exactly: independently recomputed `expm1(sum(log1p(r)))` over the
1261-day sleeve return series reproduces `0.547638349519344` bit-for-bit. `level_base_date` is now published
as `2021-09-16` (the day before the first return, `first_period_return = 0.012502347112174576`) — the
structural fix the finding asked for.

Every other sleeve statistic (mean, vol, Sharpe, Sortino, skew, kurtosis, max drawdown, VaR/CVaR, betas,
correlation) is byte-identical before and after, confirming the fix touched only the level base and the CAGR
denominator, as claimed.

## 2. The CAGR convention differs from the finding's by 0.9 bp — disclosed, not an error

The finding annualised on 252 trading days (`(1+total_return)^(252/1261)-1 = 0.0911986`). The regenerated
file instead annualises on calendar days from `level_base_date` using the same 365.25-day convention already
used for every per-asset CAGR in this build:

```
days(2021-09-16 -> 2026-09-16) = 1826
cagr = (1.547638349519344) ** (365.25/1826) - 1 = 0.09128727248850588
```

This recomputation reproduces the published `cagr` field exactly (`0.09128727248850588`), and the 252-day
alternative is separately published in `data/refresh_diff.json -> level_base_correction.cagr_convention` /
`...cagr_restated_252day_convention`, which gives 0.09119863527133476 for the new sleeve — a 0.086 pp (0.9 bp)
difference, exactly as the convention note states. Both figures are internally consistent with their own
stated method; this is a disclosed convention choice, not a residual defect. No action needed.

## 3. Archive restatement (old sleeve) also reproduces exactly

| | Published (pre-fix) | Restated | Finding said | Match |
|---|---|---|---|---|
| Old sleeve total return | 1.8236513505 | **1.8370928353** | 1.8370930 | exact |
| Old sleeve CAGR (252-day) | 0.2309034 | **0.2316941585** (`cagr_restated_252day_convention`) | 0.2316940 | exact |
| Old sleeve CAGR (365.25-day, as published in REFRESH_DIFF §6) | — | **0.2319331** | — | internally consistent |

`data/refresh_diff.json -> level_base_correction.rebuild_validation.unicorn_sleeve.max_abs_diff_vs_published`
= `0.0`, confirming the archive rebuild (used to license the restatement) reproduces the archived mean,
volatility and pre-fix total return exactly, not just "to 1e-9" as claimed — actual residual is 0.0 for the
sleeve and 4.44e-16 for the combined 200k series (both well inside the 1e-9 guard the script asserts on).

## 4. `REFRESH_DIFF.md` sections 6 and 9 were regenerated with the corrected figures

Section 6's table now reads: new sleeve total return 52.85% -> 54.76%, new sleeve CAGR 8.86% -> 9.13%
(365.25-day convention), old sleeve 182.37% -> 183.71% / 23.09% -> 23.19%, CAGR change -14.06 pp. This is the
same restatement the finding asked for; the only numerical difference from the finding's own -14.05 pp change
figure is the 0.9 bp annualisation-convention gap in section 2 above (finding used 252-day throughout: -14.05
pp; the shipped file uses 365.25-day throughout: -14.06 pp — both self-consistent). Section 9's prose
("Sleeve A — everything moved") quotes 23.2% -> 9.1% and -14.1 pp, consistent with the table. File mtimes
confirm order: `scripts/analysis.py` (18:54:21) and `data/analysis_results.json` (18:54:35) were updated
before `data/REFRESH_DIFF.md` / `data/refresh_diff.json` (19:00:41), so the diff was regenerated from the
already-corrected results.

## 5. The fix propagated to every portfolio's realised/backtest series, as the author states

Diffed every field of `portfolios.*.realised_daily_5y` and `portfolios.*.backtest_5y` between
`data/analysis_results.json` and the archive:

- **Only `total_return` and `cagr` moved materially** in MinVariance, Moderate12, EqualWeight and
  NaiveReference (no other field differs by more than 0 in MinVariance/Moderate12/EqualWeight/NaiveReference).
- MaxSharpe and MaxSortino additionally carry pre-existing ~1e-8–1e-9 differences in `mean_ann_arith`,
  `sharpe`, `sortino`, `skew`, `excess_kurtosis`, betas, `r2`, `corr_benchmark` etc. — consistent with the
  author's description of "pre-existing SLSQP weight residuals," not a new symptom of this bug.
- Moderate12: realised total return 218.99% -> **218.41%** (JSON: 2.1899114271 -> 2.1841144164, matches
  author's quoted figures exactly); backtest_5y total return 205.49% -> **211.48%** (2.0549208588 ->
  2.1147730336, matches exactly — confirms "the first backtest month is now compounded in" increases rather
  than decreases the monthly-backtest total return, as stated).
- Per-asset `stats_daily.csv.cagr_5y` is unaffected: max abs diff vs archive across all 44 shared tickers is
  2.2e-16 (float noise on `SIE.DE` only) — confirms the bug and its fix are scoped to the sleeve/portfolio
  `series_stats` path, not the per-asset stats path, as the author implies by not listing per-asset figures
  among the affected outputs.

## 6. Stale downstream deliverables are correctly flagged, not silently wrong

`data/consistency_check_refresh.md` (mtime 10:02, i.e. written *before* the 18:54 fix) still quotes the
pre-fix sleeve CAGR (23.09%, 26.3% for the separate monthly-backtest series). This is exactly what
`REFRESH_DIFF.md` section 10 note 5 and the author's own account say is still outstanding: Excel, PDF, deck,
NotebookLM, coursework and this consistency-check file all need to be rebuilt from the now-corrected
`data/analysis_results.json` before publication. Confirmed as a disclosed to-do, not a new discrepancy.

## 7. Archive-restatement script guard

`scripts/make_refresh_diff_moonshot.py` contains the asserted guard the author describes: line 396 asserts
`max_abs_diff_vs_published < 1e-9` per restated series (`n_obs` equality asserted on line 395), keyed off
`core_reproduction_assertion` (lines 666, 905–906). This will fail loudly rather than silently drift if the
archive panel is ever re-fetched, as claimed.

## 8. Outstanding items from the original review, unchanged

5.2 (SPCX CAPM constant), 5.3 (complete-case vs full-sample covariance), 5.4 (12% describes the optimiser
part, 12.78% as held) and 5.5 (two disagreeing liquidity series, GFUZ 1350 vs 5040 USD k/day) were out of
scope for this round and remain open, as the author's account states. Not rechecked here.

---

## Verdict

The MAJOR finding (5.1) is **fixed and correctly propagated**: `unicorn_sleeve.stats.total_return`/`cagr`,
the archive restatement, `REFRESH_DIFF.md` sections 6 and 9, and every other portfolio's realised/backtest
`total_return`/`cagr` all reproduce the corrected values to floating-point precision from the regenerated
data files. The one apparent discrepancy versus the original finding — CAGR annualised on calendar days
(365.25) rather than trading days (252), a 0.9 bp difference — is a disclosed, internally consistent
convention choice (both conventions are published), not a residual bug. No new issues found in the files
this recheck covers.

*Educational analysis, not advice. Nobody on this project is a licensed adviser.*
