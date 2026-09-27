# Adversarial verification — lens: OPTIMISATION CORRECTNESS

Verifier ran independently of `scripts/analysis.py` (never opened). Inputs used: `data/expected_returns.csv`
(`blend` column), `data/cov_lw.csv`, `data/weights.csv`, `data/frontier.csv`, `data/risk_contribution.csv`,
`data/prices_gbp_daily_clean.csv`, `data/analysis_results.json` (`config`, `portfolios`, `asset_stats`),
`universe/core_universe.json`, and the constraint set in PROJECT_BRIEF / SPEC_ANALYSIS §5.
Python 3.9, numpy 2.0, scipy 1.13. Scripts under
`/private/tmp/claude-501/-Users-georgewilliams-Desktop-Claude-Projects-Investing-101/0a2ff4be-227a-46ed-8c9b-f9d54feff8e2/scratchpad/`.

Constraint model used for every re-solve (derived from `config.constraints` + SPEC §5):
long-only; per-asset cap by bucket (etf_equity/etf_bond/etc_commodity/gilt 0.20, trend 0.15, stock 0.05);
`sum(w_optimiser) = 0.975`; equity_etf >= 0.30; commodity in [0.05, 0.20]; bonds in [0.10, 0.40];
stocks <= 0.25 **including** the fixed SPCX 0.025 (so optimiser stocks <= 0.225); trend <= 0.15.

---

## 1. Constraint satisfaction — PASS

| portfolio | sum | opt part | equity_etf | commodity | bonds | stocks (incl SPCX) | trend | violations |
|---|---|---|---|---|---|---|---|---|
| MinVariance | 1.0000000000 | 0.9750000000 | 0.3000 | 0.1045 | 0.4000 | 0.0661 | 0.1294 | none |
| MaxSharpe | 1.0000000000 | 0.9750000000 | 0.3000 | 0.2000 | 0.1669 | 0.2500 | 0.0831 | none |
| Moderate12 | 1.0000000000 | 0.9750000000 | 0.3474 | 0.2000 | 0.1000 | 0.2500 | 0.1026 | none |
| MaxSortino | 1.0000000000 | 0.9750000000 | 0.3000 | 0.2000 | 0.2000 | 0.2500 | 0.0500 | none |
| EqualWeight | 1.0000000000 | 0.9750000000 | 0.3250 | 0.1625 | 0.1896 | 0.2958 | 0.0271 | stocks 0.29583 > 0.25 (declared reference portfolio, flagged in `optimiser_verification` and `limitations`) |
| NaiveReference | 1.0000000000 | 0.9750000000 | 0.6000 | 0.1000 | 0.1500 | 0.1000 | 0.0500 | none |

No negative weights; no per-asset cap breached (tol 1e-9); SPCX = 0.025 exactly in every column;
every weights.csv column reproduces `analysis_results.json` `weights_full` to < 1e-16.
All 30 frontier rows are feasible under the same constraint set (0 violations).

## 2. Recomputation of portfolio statistics

Reproduced **exactly** (max abs diff quoted):

- `ex_ante_vol_lw_optimiser_part` = sqrt(w' Sigma_LW w) — all six portfolios, diff < 1e-12.
- `expected_return_optimiser_part` for all three estimate columns — diff < 1e-15.
- `sharpe_ex_ante` = (expected_return_total_core.blend - rf) / `ex_ante_vol_full_core_incl_spcx` — diff < 1e-9.
- Frontier `vol` and `ret_optimiser_part` recomputed from cov_lw / blend mu — max diff 3.1e-16 / 1.8e-16.
- `cov_lw.csv` is exactly delta*F + (1-delta)*S_mle with delta = 0.03575007, r_bar = 0.23223406, T = 1135
  rebuilt from `cov_annual.csv` — max abs diff 1.4e-16. Symmetric, min eigenvalue +6.75e-4 (PSD).
- Per-asset `mean_ann_arith`, `vol_ann`, `skew` reproduce from `prices_gbp_daily_clean.csv` exactly for the
  33 assets with no masked days.

Mismatches found — see findings 2 and 3 below:
- `expected_return_total_core` (historical_5y and blend) prices SPCX at its CAPM number, not at the
  column's own estimate.
- `beta_vwrp` / `beta_up` / `beta_down` / `beta_ftas` for every portfolio equal
  `sum_{36} w_i beta_i / 0.975`, i.e. SPCX is dropped and the rest rescaled.

## 3. Independent re-solve (SLSQP + trust-constr, 65 starts incl. 60 random, 2 solvers)

| problem | objective | my best | reported | gap |
|---|---|---|---|---|
| Global min variance | min w'Sw | vol 0.0554233884 (SLSQP) / 0.0554233892 (trust-constr) | 0.0554233884 | 0.000000 pp |
| Max Sharpe | (w'mu - 0.975 rf)/vol | SR 0.9781191251 | 0.9781191271 | -0.0000000% |
| Moderate (max ret s.t. vol <= 12%) | max w'mu | 0.1510895400 (SLSQP) / 0.1510895395 (t-c) | 0.1510895400 | 0.000000 pp |

All three reproduce to solver tolerance. **No improvement found** — these three solves are correct.
(An alternative Sharpe objective that also credits the SPCX 2.5% in the numerator,
`(w'mu + 0.025*mu_SPCX - rf)/vol`, gives +0.027% — far below the 0.2% materiality bar, and the
no-SPCX objective the code actually used is reproduced to 2e-9, so the definition is internally consistent.)

## 4. Frontier — PASS

- 30 points, vol strictly increasing (min step 2.70e-4), return strictly increasing (min step 4.26e-3).
- Concave: dRet/dVol strictly decreasing across all 28 consecutive segment pairs; 0 non-concave segments.
- Endpoints correct: point 1 return = GMV return = 0.05885066; point 30 return = 0.18228339, which equals
  the LP maximum feasible return under the full constraint set (independent `scipy.linprog` solve) to 1e-8.
- GMV, MaxSharpe and Moderate12 all lie on the frontier: interpolated frontier return at each portfolio's
  vol is 0.0000 / -0.0010 / -0.0030 pp *below* the portfolio's own return, i.e. each sits on (marginally
  above the piecewise-linear chord of) the concave curve, as it must. Nearest frontier weight vectors
  differ by 2.4e-6 / 1.4e-3 / 1.0e-2.
- MaxSortino sits 0.165 pp *below* the frontier at its vol — expected, it is not a mean-variance optimum.

## 5. Risk contributions — PASS

`risk_contribution.csv` is the headline (Moderate12) portfolio, 36 rows (SPCX excluded, as documented).
Recomputed MCR_i = (Sigma_LW w)_i / sigma_p and RC_i = w_i MCR_i:
- max |MCR difference| 4.1e-16, max |RC difference| 7.9e-17;
- sum(RC) = 0.12000000000088644 vs sigma_p = 0.12000000000088669 (difference -2.5e-16) — Euler holds;
- sum(pct_of_risk) = 1.0000000000 (0.9999999999999993).

## 6. Max-Sortino — FAIL (see finding 1)

## Findings

### F1 (BLOCKER) — the "MaxSortino" portfolio is not the max-Sortino portfolio

SPEC §2(d) requires the skew-tilted sleeve to be the maximum-Sortino portfolio on the historical daily
matrix. It is not, on the project's own numbers and on two independent reconstructions of the return panel:

- **The project's own `realised_daily_5y.sortino`**: MaxSharpe **2.556249** > MaxSortino **2.519319**.
  The MaxSharpe weights are feasible for the Sortino problem (identical constraint set), so a portfolio
  already sitting in `weights.csv` beats the one labelled max-Sortino by +1.47%.
- **My re-solve** on the daily GBP panel 2021-09-14 -> 2026-09-11 (1259 obs, `prices_gbp_daily_clean.csv`,
  weights/0.975, MAR = rf daily, downside deviation over all observations — the project's own definition):
  best feasible Sortino **2.568167** vs reported MaxSortino **2.516705** = **+2.045%**.
- **Robustness**: on a complete-case panel (1137 obs, forward-filled days removed) the improvement is
  still **+1.177%** (2.398004 vs 2.370120).

My solution: ISF.L 0.1916, IBTM.L 0.1703, SGLN.L 0.1646, SMGB.L 0.0854, DBMG.L 0.0797, RR.L 0.0500,
HSBA.L 0.0500, PLTR 0.0500, SHEL.L 0.0428, BRNT.L 0.0354, IITU.L 0.0230, BRK-B 0.0191, ULVR.L 0.0116,
AZN.L 0.0015 (sums to 0.975; all bounds and group constraints satisfied).

The reported point sits in a worse local basin (bonds 0.2000 and trend 0.0500 are interior, not at a
bound — nothing is binding there). `optimiser_verification.MaxSortino.best_0.5pct_transfer_gain = 0`
only tests single 0.5% pairwise transfers, which cannot escape that basin.

The reported point is not optimal under any plausible Sortino variant either — MaxSharpe beats it on
daily MAR=rf (all obs and losing-obs-only), daily MAR=0 (all obs), monthly MAR=rf (both) — 5 of 6
variants tested.

Fix: re-solve (d) with many random starts (and/or seed from the MaxSharpe weights) and keep the best
feasible point; then re-derive its reported stats, £ sizing, shares, backtest row and the PDF/Excel
copy that describes it.

### F2 (MAJOR) — portfolio beta, beta+ and beta- silently exclude SPCX and rescale

`portfolios[*].beta_vwrp / beta_up / beta_down / beta_ftas` are all exactly
`sum over the 36 optimiser assets of w_i * beta_i, divided by 0.975` (verified to 1e-9 for all six
portfolios). That imputes to the 2.5% SPCX holding the *portfolio's own* beta instead of SPCX's.
Because beta is linear in weights, the correct figure for the portfolio as actually held is
`sum over all 37 lines`:

| portfolio | beta reported -> incl. SPCX | beta+ reported -> incl. SPCX | beta- reported -> incl. SPCX | beta+ - beta- reported -> incl. SPCX |
|---|---|---|---|---|
| MinVariance | 0.2910 -> 0.3544 | 0.2635 -> 0.4626 | 0.2947 -> 0.3211 | -0.0312 -> **+0.1415** |
| MaxSharpe | 0.5796 -> 0.6358 | 0.5224 -> 0.7150 | 0.5990 -> 0.6178 | -0.0766 -> **+0.0972** |
| **Moderate12 (headline)** | **0.7358 -> 0.7880** | **0.6571 -> 0.8464** | **0.7458 -> 0.7610** | **-0.0887 -> +0.0854** |
| MaxSortino | 0.5643 -> 0.6209 | 0.5113 -> 0.7042 | 0.5839 -> 0.6031 | -0.0726 -> +0.1012 |

The headline beta+ is understated by 0.189 (29%) and the sign of the beta asymmetry flips. That matters
because `limitations` asserts "on DAILY data the headline core has beta+ 0.66 below beta- 0.75 (negative
asymmetry) ... no long-only portfolio drawn from this universe achieves positive daily beta asymmetry" —
a claim that holds only under the undocumented SPCX-excluded convention.

Note the convention is also internally inconsistent: `sharpe_ex_ante` *does* include SPCX (numerator uses
the SPCX-inclusive core return, denominator uses `ex_ante_vol_full_core_incl_spcx`), while the betas in the
same block do not.

SPCX's 64-bar beta+ of 8.23 is indefensible as an estimate, so excluding it may well be the right choice —
but it must be stated. Fix: either label these as "beta of the optimised 97.5%" and add the SPCX-inclusive
figure alongside, or state the convention in `definitions` and in the limitation about beta asymmetry.

### F3 (MINOR) — `expected_return_total_core` prices SPCX with CAPM in all three columns

`expected_returns.csv` gives SPCX historical_5y 0.13359500, capm 0.15537145, blend 0.14448323.
Every portfolio's `expected_return_total_core` is `optimiser_part + 0.025 * 0.15537145`, i.e. the CAPM
number is used in the historical and blend columns too (reproduced to 1e-16 for all six portfolios).
Consistently +0.0544 pp in the historical column and +0.0272 pp in the blend column, e.g. headline
Moderate12 blend reported 0.15497383 vs 0.15470162, historical reported 0.23810681 vs 0.23756240.
The same applies to `frontier.csv` `ret_core` (max |reported - (opt + 0.025*SPCX_blend)| = 2.72e-4,
max |reported - (opt + 0.025*SPCX_capm)| = 1.9e-16), and it feeds `sharpe_ex_ante`
(Moderate12 0.918180 as reported vs 0.916111 with the blend estimate for SPCX).
Defensible as a judgement (SPCX has 64 bars, so a 5y historical mean is meaningless) but undocumented.
Fix: either use each column's own SPCX estimate, or add a line to `definitions` saying SPCX is always
priced at CAPM.

### F4 (MINOR) — two different Sharpe definitions for the same weights

`frontier.csv` `sharpe` = (ret_optimiser_part - 0.975*rf)/vol (reproduced to 1e-15), while
`portfolios[*].sharpe_ex_ante` = (expected_return_total_core.blend - rf)/ex_ante_vol_full_core_incl_spcx.
The GMV portfolio therefore appears twice with two different Sharpe ratios: **0.402144** as frontier
point 1 and **0.413779** in the portfolios block, for identical weights. Same for MaxSharpe
(0.978119 vs 0.935741) and Moderate12 (0.954392 vs 0.918180). Nothing is wrong
arithmetically, but the CSV puts `ret_core` and `sharpe` side by side and they do not correspond
((ret_core - rf)/vol differs from the printed sharpe by up to 0.0532). Fix: label the frontier column
`sharpe_optimiser_part` or add the matching return column.

### F5 (MINOR) — limitation text names the wrong binding constraint for SMGB.L

`limitations` says "SMGB.L (semiconductors) takes 17.1% of the headline core weight and contributes 36.8%
of its ex-ante risk. The 20% single-ETF cap is what stops it going further." The weight is 0.170734 and
the cap is 0.20, so the cap is slack. I re-solved Moderate12 with the SMGB.L cap lifted to 1.00: the
optimum is unchanged (return 0.15108954 both ways, SMGB.L 0.170735). What stops it is the 12% volatility
ceiling. The 36.8% risk-contribution figure is correct (verified above). Fix: reword.

### F6 (COSMETIC) — SPCX bar count inconsistent across documents

SPEC §5 says 63 daily bars, `definitions` says "65 overlapping bars", `asset_stats.SPCX.n_obs` = 64,
`limitations` says 64. Pick one (asset_stats says 64 returns from 2026-06-12 to 2026-09-11).

## Checks that passed (summary)

1. Bounds, group constraints and budget for all 6 portfolios and all 30 frontier points.
2. Weights sum to 1 = 0.975 optimiser + 0.025 SPCX, exactly, in every column; weights.csv == JSON.
3. Ex-ante vol, all three expected-return columns for the optimiser part, and sharpe_ex_ante reproduce exactly.
4. Cov_LW is symmetric, PSD, and exactly reconstructible from cov_annual + the recorded delta/r_bar/T.
5. GMV, MaxSharpe and Moderate-12% re-solved independently with SLSQP and trust-constr from 65 starts —
   no improvement (0.000000 pp / -0.0000000%).
6. Frontier monotone, concave, correct endpoints (LP-verified max return), all points feasible,
   GMV/MaxSharpe/Moderate on it.
7. Risk contributions satisfy the Euler identity to 2.5e-16 and sum to 100%.
