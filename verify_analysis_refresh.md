# Blind verification — moonshot rebuild analysis layer (as-of 2026-09-16)

*Educational analysis, not personalised investment advice. Nobody on this project is a licensed adviser. Every figure below is a model output or an own recomputation, not a certainty.*

**Verifier role:** blind. `scripts/analysis.py` was NOT read. Everything below was recomputed from
`data/prices_gbp_daily.csv`, `data/expected_returns.csv`, `data/cov_lw.csv`, `data/cov_daily_full.csv`,
`data/weights.csv`, `universe/market_params.json` and `universe/unicorn_final.json`, with
`/usr/bin/python3` (pandas 2.3 / numpy 2.0 / scipy 1.13), and compared against
`data/stats_daily.csv`, `data/analysis_results.json` and `data/REFRESH_DIFF.md`.
Archive used for diffs: `archive/2026-09-16-quality-sleeve/data/`.

Window: 2021-09-16 -> 2026-09-16, 1262 panel rows / 1261 return days, last panel date 2026-09-16 (SPEC section 7 satisfied).
Risk-free 3.75% (BoE Bank Rate, `market_params.boe_bank_rate`); ERP 4.17% (`damodaran_erp`).

---

## 1. Per-asset statistics — 6 of the 7 requested tickers reproduce EXACTLY

`BKS.L` is **not in this build**. It was a 2026-09-16 quality-sleeve name, one of the 34 dropped in the
moonshot swap (`REFRESH_DIFF.md` section 5). It is correctly absent from both `prices_gbp_daily.csv` and
`stats_daily.csv`; the only surviving mention is a Yahoo-trap note in `core_universe.json`. Nothing to fix —
the ticker list in the verification brief is simply one name ahead of the rebuilt sleeve.

Own recomputation vs `data/stats_daily.csv` (annualised x252 / sqrt(252); Sharpe = (mean_ann - rf)/vol;
beta/beta+/beta- = OLS of excess daily return on VWRP.L excess, split on the sign of the benchmark excess;
YTD from the 2025-12-31 close):

| Ticker | mean_ann | vol | Sharpe | skew | maxDD | beta | beta+ | beta- | YTD | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| RR.L | 0.605216 | 0.415701 | 1.365683 | 1.188838 | -0.550854 | 1.305990 | 1.412409 | 1.450982 | 0.263017 | exact |
| VWRP.L | 0.116115 | 0.130244 | 0.603599 | -0.383898 | -0.176420 | 1.000000 | 1.000000 | 1.000000 | 0.126322 | exact |
| SGLN.L | 0.199667 | 0.170576 | 0.950706 | -0.324202 | -0.248895 | 0.054907 | -0.032253 | 0.072328 | 0.008525 | exact |
| SMGB.L | 0.331869 | 0.323963 | 0.908651 | -0.158827 | -0.362393 | 1.907077 | 1.803611 | 1.710788 | 0.660826 | exact |
| IBTM.L | -0.008984 | 0.093748 | -0.495838 | 0.281446 | -0.162892 | -0.034380 | -0.028434 | -0.139297 | -0.028574 | exact |
| DBMG.L | 0.103346 | 0.152655 | 0.431342 | -0.163375 | -0.316330 | 0.128529 | -0.097377 | 0.203575 | 0.141458 | exact |

All agree to at least 6 decimal places — far inside the 1e-3 beta / 0.2pp return tolerances.

DBMG.L note: n_obs = 1258, not 1261, because the spliced series (DBMF -> DBMG at 2025-04-22, SPEC section 5)
has a two-day hole at 2025-04-22/23. `pct_change(fill_method=None)` therefore voids three returns.
Reproducing that convention reproduces every DBMG figure exactly (beta 0.128529, beta+ -0.097377);
bridging the gap instead gives beta 0.128758 / beta+ -0.097676 — still inside tolerance, so the choice is
immaterial, but the two-day hole at the splice point is worth closing in `fetch_data.py`.

Secondary benchmark: `^FTAS` still has no history after **2026-07-22** (Yahoo), so every `beta_ftas`,
`alpha_ftas` and `r2_ftas` is estimated on ~1218 days ending two months before the as-of date. Reproduced
exactly (RR.L 1.689134, SGLN.L 0.026616, DBMG.L 0.049782). Disclosed in `REFRESH_DIFF.md` section 10.2.

---

## 2. Constraints — every optimised portfolio is feasible

Constraint set read from `analysis_results.config.constraints` (matches PROJECT_BRIEF: long-only; ETF/ETC/gilt
<= 20% each, trend <= 15%, single stock <= 5%; equity ETFs >= 30%; commodities 5-20%; bonds 10-40%;
all stocks <= 25%; SPCX fixed at 2.5% outside the optimiser, counted inside the stocks group).

| Portfolio | sum | equity ETF | commodity | bonds | stocks | trend | per-asset caps | LW vol |
|---|---|---|---|---|---|---|---|---|
| MinVariance | 1.0000000000 | 30.00% | 10.47% | 40.00% | 6.63% | 12.90% | OK | 5.54% |
| MaxSharpe | 1.0000000000 | 30.00% | 20.00% | 16.34% | 25.00% | 8.66% | OK | 9.58% |
| **Moderate12** | 1.0000000000 | 35.53% | 20.00% | 10.00% | 25.00% | 9.47% | OK | **12.0000%** |
| MaxSortino | 1.0000000000 | 30.00% | 20.00% | 16.19% | 25.00% | 8.81% | OK | 9.66% |
| EqualWeight | 1.0000000000 | 32.50% | 16.25% | 18.96% | **29.58%** | 2.71% | OK | 10.63% |
| NaiveReference | 1.0000000000 | 60.00% | 10.00% | 15.00% | 10.00% | 5.00% | OK | 10.79% |

No negative weights anywhere (minimum weight is 0.0 exactly, with a handful of 1e-16 float dust).
**EqualWeight breaches the 25% all-stocks group at 29.58%** — but it is a reference portfolio, not an optimiser
output, and the build already records the breach verbatim in
`analysis_results.optimiser_verification.EqualWeight.violations` alongside `is_reference_portfolio: 1`.
Correctly handled; no action.

**Moderate12 ex-ante Ledoit-Wolf vol = 0.120000000 — 12.00% confirmed.**

---

## 3. Re-solved optimisations — both reproduce to solver precision

Re-solved independently with SLSQP from 400 starts (equal-weight, the three published portfolios, and 396
random feasible points), using only `expected_returns.csv` (blend column) and `cov_lw.csv`.

The build's max-Sharpe objective is `(w.mu - rf*sum(w)) / sqrt(w' Sigma_LW w)` on the 36-line optimiser part
with `sum(w) = 0.975` (i.e. excess return over the sleeve's own cash budget). Recovered by inference from
`optimiser_verification.MaxSharpe.cross_seed.objective_final`, then confirmed:

| Problem | my objective | published objective | recorded in JSON | max abs weight diff |
|---|---|---|---|---|
| Max Sharpe | 0.972777648 | 0.972777648 | 0.972777648 | 2.9e-08 |
| Max return s.t. vol <= 12% | E[R] 0.150073973 @ vol 0.120000000 | 0.150073973 @ 0.120000000 | 0.1500739730 | 1.4e-06 |

No feasible point beating either published solution was found. Both are optimal to solver tolerance.

Supporting reconstructions, all exact:
- `expected_returns.csv`: blend = 0.5 x historical + 0.5 x CAPM/yield (max diff 5.6e-17); CAPM = rf + beta x ERP
  (max diff 9.7e-17); historical column = `stats_daily.mean_ann_arith` (diff 0.0); `beta_used` = `beta_vwrp` (diff 0.0).
- **Ledoit-Wolf shrinkage recomputed from scratch** on the complete-case panel: T = 1135, N = 36,
  r_bar = 0.2323800189, pi = 1.914589e-04, rho = 6.958796e-05, gamma = 2.995937e-06,
  **delta = 0.0358403012** — identical to the published delta to 10 decimals; the full 36x36 matrix matches
  `cov_lw.csv` to 1.1e-16 absolute.
- Combined GBP 200k **ex-ante volatility 0.142340** reproduced exactly from `cov_daily_full.csv` and the
  published 77-line combined weight vector.

---

## 4. `REFRESH_DIFF.md` — is each material change explained by the inputs?

The diff's central claim is right: **there is no window roll and no market move in this rebuild.** Both builds
price at the same 2026-09-16 close, read the same `market_params.json` (rf 3.75%, ERP 4.17%, T36N 5.30%,
T56 5.87%, US 10y 5.01%) and share an identical 2526-row calendar. The single driver is the 34-of-40
Sleeve A swap. Verified independently against the archive:

| Claim | Diff says | Own check | Verdict |
|---|---|---|---|
| Core optimiser inputs unchanged | cov_lw 3.05e-16, cov_annual 3.05e-16, corr 1.50e-15, E[R] 1.33e-15 | 3.053e-16 / 3.053e-16 / 1.499e-15 / 1.332e-15 | exact |
| Core weights unchanged | max \|dw\| 2.15e-08 (MaxSharpe) | 2.149e-08 | exact |
| Per-asset 5y stats unchanged | zero change | stats_daily, 46 shared rows x 46 cols, max 2.3e-14 | exact |
| Kept / replaced | 6 kept / 34 replaced | ARA.TO, SLX.AX, VUL.AX, IMSR, BIOA, FTC.L kept; 34 in, 34 out | exact |
| Median market cap | 220.3 vs 818.0 USD m | 220.3 vs 818.0 | exact |
| Market-cap range | 7.6-945.5 vs 190.9-2864.5 | identical | exact |
| Regions | Europe 5, Other 12, UK 3, US 20 | identical | exact |
| Sector cap (4 of 40, SPEC section 8 / brief) | 22 sectors used | max 4 in any sector (RNA/cell therapy) | satisfied |
| Live names on sleeve index day 1 | 27 of 40 | 27 (2021-09-17) | exact |
| Short histories (< 1y) | IMSR 219, GFUZ 243, BTQ 245 | identical; no other name below 252 obs | exact |
| Thinnest ten by traded value | LIS.AX 18.7 ... ARA.TO 261.1 USD k | identical (`fetch_log.avg_daily_value_usd_k_3m`) | exact |
| Mean sleeve-name vol | 93.1% vs 80.3% | 93.06% vs 80.20% | agrees |
| Mean pairwise corr in sleeve | 0.0635 vs 0.0933 | 0.0660 vs 0.0935 (raw pandas corr) | agrees to method |
| 77x77 core block moved by the PSD repair | max cell change 0.0115 on the SPCX row; SGLN.L implied vol +0.85pp | 0.01150 at (SPCX, SPCX) over the 37 core lines; SGLN.L 0.00850 | exact |

Sleeve statistics recomputed from scratch (equal weight, daily rebalanced across live names, first date with
>= 20 live names = 2021-09-17, 1261 days): mean 12.235%, vol 26.505%, Sharpe 0.3201, Sortino 0.4646,
downside dev 18.264%, skew 0.1080, excess kurtosis 1.3204, max DD -45.531% (2021-11-05 -> 2023-10-27),
VaR95 2.594%, CVaR95 3.438%, beta 0.8684, beta+ 0.7743, beta- 0.9074, corr 0.4267, R2 0.1821 —
**every one of these matches `analysis_results.unicorn_sleeve.stats` to 4+ decimals.** The sleeve's
-12.2pp mean / -0.45 Sharpe / -0.133 beta-asymmetry move is fully explained by the constituent swap.

Combined book: ex-ante figures exact (see section 3). The realised daily series reproduces to 4e-05 on the
annualised mean and **exactly on max drawdown (-0.1684515)**, with residuals of 0.035pp on volatility and
0.012 on skew that come from the exact live-name renormalisation convention, which is not recoverable
blind. Not treated as a defect.

**Nothing in the diff moved more than the input change justifies** — with the one exception in section 5.1,
which is a level-series bug rather than an unexplained move.

---

## 5. Findings

### 5.1 MAJOR — the sleeve index's `total_return` and `cagr` drop the first day's return

Provable to 10 decimal places. The sleeve level is based at 1.0 **on** the first return date instead of the
day before, so the 2021-09-17 return (+1.2502347%) is counted in every distributional statistic but lost
from the compounded level:

- reported `total_return` 0.5285281599 = `lvl[-1] / lvl[0] - 1`, where `lvl[0]` = 1.0125023471
- correct `total_return` = `lvl[-1] - 1` = **0.5476383495** (confirmed two ways: cumprod and expm1(sum(log1p)))
- reported `cagr` 0.0886291; correct (252/1261) = **0.0911986**

The same bug is in the archived quality-sleeve build: reported 1.8236510 is exactly its drop-first-day value;
correct 1.8370930, CAGR 0.2309031 reported vs 0.2316940 correct. Because both sides share it, the
diff's *direction* survives, but the published numbers do not:

| | published | corrected |
|---|---|---|
| Old sleeve total return | 182.37% | **183.71%** |
| New sleeve total return | 52.85% | **54.76%** |
| Old sleeve CAGR | 23.09% | **23.17%** |
| New sleeve CAGR | 8.86% | **9.12%** |
| CAGR change quoted in sections 6 and 9 | -14.23 pp | **-14.05 pp** |

Secondary symptom: the reported CAGR is not even the annualisation of the reported total return. Implied
year count is 4.99450 for the new build and 4.99699 for the old, although both cover the identical 1261 days
from 2021-09-17 to 2026-09-16 — so the annualisation denominator is unstable as well as the numerator.

Everything else about the sleeve index is right; only the level base and the CAGR denominator are wrong.
Fix the base, re-emit `unicorn_sleeve.stats`, and re-run the diff's sections 6 and 9 before the Excel, PDF,
deck and coursework builds quote 8.86% / 52.85%.

### 5.2 MINOR — SPCX enters every portfolio's expected return at its CAPM estimate, in all three columns

`expected_return_total_core` exceeds `expected_return_optimiser_part` by a constant **+0.0040091934** in
every portfolio and in all three columns (historical, CAPM, blend). That constant is
0.025 x 0.16036774 — SPCX's **CAPM** estimate. But `expected_returns.csv` publishes SPCX at
historical 0.13718344 and blend 0.14877559.

Using CAPM for a line with 67 daily bars is defensible, arguably better than its historical mean. The problem
is that it is undocumented and inconsistent with the CSV the Excel tabs will read. Effect on the headline
Moderate12: blend E[R] 15.408% published vs **15.379%** on the CSV's own blend (-2.9bp); the
`historical_5y` column is overstated by 5.8bp. Identical in all six portfolios, so rankings are unaffected.
Either apply each column's own SPCX estimate, or state the policy in `definitions` and in
`Sources_Assumptions`.

### 5.3 MINOR — the optimiser covariance and the statistics table are built on different samples

`cov_lw.csv` / `cov_annual.csv` use a **complete-case** panel of 1135 of the 1261 return days
(disclosed as `covariance.n_complete_case_days`), while `stats_daily.csv` uses each asset's own 1261-day
history. Because the complete-case filter drops the single-day returns adjacent to any market's holiday but
keeps the multi-day catch-up return that follows, the covariance diagonal runs systematically **1.5-2.9%
relative above** the reported volatilities:

| Ticker | sqrt(diag Cov_LW) | `stats_daily.vol_ann` | gap |
|---|---|---|---|
| RR.L | 42.64% | 41.57% | +1.07 pp |
| BRNT.L | 38.01% | 37.01% | +1.00 pp |
| SIE.DE | 31.65% | 30.76% | +0.90 pp |
| MSFT | 30.00% | 29.20% | +0.80 pp |

Consequence for the headline: the Moderate12 weights measure **12.00%** on the complete-case LW matrix
but **11.75%** on a pairwise-complete sample covariance over all 1261 days (realised, renormalised:
12.10%). The 12% target therefore binds on slightly inflated inputs — conservative in direction, but SPEC
section 3 tab 11 asks Stats_Daily to sit beside the covariance-derived figures with a difference column, and
that column will show this gap with no explanation attached. Add a note, or build the covariance
pairwise-complete.

### 5.4 MINOR — "moderate risk = 12%" describes 97.5% of the core, not the core as held

The 12% constraint binds on `ex_ante_vol_lw_optimiser_part` (SPCX contributes no variance because it is
outside the matrix). The core **as held** is `ex_ante_vol_full_core_incl_spcx` = **12.78%**. Both numbers are
published and the definitions block says so plainly, so this is disclosure hygiene rather than an error: the
Excel `Inputs`/`Optimisation` tabs and the PDF must not present 12% as the volatility of the GBP 160,000
sleeve the client actually buys.

### 5.5 MINOR — two disagreeing liquidity series for the sleeve

`universe/unicorn_final.json.avg_daily_value_usd_k` gives median 2008 / minimum 18.1 USD k;
`fetch_log.json.tickers[].avg_daily_value_usd_k_3m` gives median **2391** / minimum **18.7**.
`REFRESH_DIFF.md` cites the fetch_log field (correctly footnoted), but SPEC section 8's Excel `Unicorns` tab
naturally reads the universe file. Most names agree within a few percent; **GFUZ differs 3.7x**
(1350 vs 5040 USD k/day), which is what moves the median. Pick one series for every deliverable and say which.

---

## 6. Checks that passed

1. Panel ends 2026-09-16 with a value in every column except `^FTAS`; 25 patched bars recorded under
   `fetch_log.patched_bars_2026-09-16` (SPEC section 7).
2. All 40 moonshot tickers present in `prices_gbp_daily.csv`; none of the 34 dropped quality names remain
   (SPEC section 8).
3. `prices_gbp_daily.csv`, `_clean.csv` and `_raw.csv` agree (max 5.7e-14) — the stale-panel hazard in
   `REFRESH_DIFF.md` section 10.1 did not recur.
4. `cov_lw.csv` is symmetric to 0.0 and positive definite (min eigenvalue 6.754e-04);
   `cov_daily_full.csv` min eigenvalue 1.0e-12 after the PSD repair, as designed.
5. 6 of the 7 requested per-asset stat sets exact; the 7th (`BKS.L`) correctly absent.
6. Every optimised portfolio feasible; the one reference-portfolio breach already self-reported.
7. Moderate12 LW vol exactly 12.00%.
8. Max-Sharpe and 12%-vol problems independently re-solved to the same objective values and weights.
9. Ledoit-Wolf delta and the full shrunk matrix independently reproduced.
10. Sleeve index: 1261 days, 27 live names on day 1, exactly 3 names under one year — all as reported.

---

*Own calculations throughout; no figure here is taken from `scripts/analysis.py`, which was not read.
Educational analysis, not advice.*
