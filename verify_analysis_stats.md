# Independent verification — per-asset statistics and Ledoit–Wolf shrinkage

Adversarial verifier, lens = PER-ASSET STATISTICS. `scripts/analysis.py` was **not** read.
Everything below was recomputed from `data/prices_gbp_daily.csv`, `data/prices_gbp_daily_clean.csv`,
`data/prices_gbp_monthly*.csv` and `universe/market_params.json`, and compared with
`data/stats_daily.csv`, `data/cov_lw.csv` and `data/analysis_results.json`.

Window 2021-09-13 → 2026-09-11. rf = BoE Bank Rate 3.75% (`market_params.json → boe_bank_rate.value`),
daily rf = (1.0375)^(1/252) − 1. Benchmark VWRP.L. Tolerances applied: 1e-3 on betas, 0.2pp (0.002) on
annualised returns; everything else judged on exact reproduction.

*Educational analysis, not advice.*

---

## 1. Verdict

| Item | Result |
|---|---|
| 9 tickers × 23 daily statistics vs `stats_daily.csv` | **Reproduced exactly** (max abs diff 1.8e-15) for 8 of 9 from `prices_gbp_daily.csv`; the 9th (DBMG.L) reproduces from `prices_gbp_daily_clean.csv` to within 1.0e-3 on the mean and 2.3e-4 on beta — inside tolerance |
| Monthly VaR/CVaR (95/99) and upside/downside capture | **Reproduced exactly** (0 mismatches, max abs diff < 1e-9) once the correct monthly sample is used |
| `^FTAS` beta / alpha / R² | **Reproduced exactly** |
| Ledoit–Wolf δ, r̄, π, ρ, γ, κ, T, N | **Reproduced exactly** — δ diff 6.2e-17 |
| Full 36×36 `cov_lw.csv` | **Reproduced exactly** — max abs diff 1.08e-16, max rel diff 6.3e-13 |
| Published price deliverable `data/prices_gbp_daily.csv` | **Defective** — still carries the 100× scale glitches (issue 1) |

No error was found that changes any portfolio weight, expected return, covariance or risk number.
Three issues are recorded below; the first is a deliverable-integrity problem, not a maths problem.

---

## 2. Exact reproductions

Recomputed from `data/prices_gbp_daily.csv`, 5y window, and compared field by field with
`data/stats_daily.csv`:

```python
import numpy as np, pandas as pd
from scipy import stats as sps
px = pd.read_csv('data/prices_gbp_daily.csv', index_col=0, parse_dates=True)
RF = 0.0375                        # market_params.json -> boe_bank_rate.value / 100
rf_d = (1+RF)**(1/252) - 1
s  = px[t].dropna(); s = s[(s.index>='2021-09-13') & (s.index<='2026-09-11')]
r  = s.pct_change().dropna()

mean_ann = r.mean()*252
cagr     = (s.iloc[-1]/s.iloc[0])**(365.25/(s.index[-1]-s.index[0]).days) - 1
vol      = r.std(ddof=1)*np.sqrt(252)
sharpe   = (mean_ann-RF)/vol
dd_ann   = np.sqrt((np.minimum(r-rf_d,0.0)**2).mean())*np.sqrt(252)   # mean over ALL obs
sortino  = (mean_ann-RF)/dd_ann
skew     = sps.skew(r.values, bias=False)
exkurt   = sps.kurtosis(r.values, fisher=True, bias=False)
dd       = s/s.cummax()-1; maxdd = dd.min()
var95    = -np.percentile(r.values,5)
cvar95   = -r[r<=np.percentile(r.values,5)].mean()
# betas: OLS of asset EXCESS daily return on benchmark EXCESS daily return
j  = pd.concat([r.rename('a'), br.rename('b')], axis=1).dropna()
xa, xb = j['a']-rf_d, j['b']-rf_d
X = np.column_stack([np.ones(len(xb)), xb.values]); b,*_ = np.linalg.lstsq(X, xa.values, rcond=None)
beta, alpha_ann = b[1], b[0]*252
beta_up   = ols(xa[xb>0], xb[xb>0])     # benchmark excess > 0
beta_down = ols(xa[xb<0], xb[xb<0])     # benchmark excess < 0
ret_ytd   = s_full[s_full.index<='2026-09-11'].iloc[-1] / s_full[s_full.index<='2025-12-31'].iloc[-1] - 1
```

Result for the eight clean tickers (RR.L, VWRP.L, SGLN.L, IHYU.L, PLTR, T56, BKS.L, DRO.AX), all 23
fields each — `n_obs`, `first/last_date`, `mean_ann_arith`, `cagr_5y`, `vol_ann`, `sharpe`, `sortino`,
`downside_dev_ann`, `skew`, `excess_kurtosis`, `max_drawdown` + peak/trough dates, `var95_daily`,
`cvar95_daily`, `var99_daily`, `cvar99_daily`, `beta_vwrp`, `alpha_ann_vwrp`, `r2_vwrp`, `beta_up`,
`beta_down`, `beta_asymmetry`, `corr_benchmark`, `ret_ytd` — **largest absolute difference 1.8e-15**
(floating-point noise). Spot values:

| ticker | mean_ann | vol_ann | Sharpe | Sortino | skew | ex-kurt | maxDD | VaR95 | CVaR95 | beta | beta+ | beta− | YTD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RR.L | 0.603334 | 0.416886 | 1.357287 | 2.185052 | 1.17910 | 12.9806 | −0.550854 | 0.035587 | 0.053094 | 1.312399 | 1.409133 | 1.454703 | 0.275291 |
| VWRP.L | 0.116941 | 0.130262 | 0.609856 | 0.854452 | −0.38541 | 3.0577 | −0.176420 | 0.012686 | 0.019135 | 1.000000 | 1.000000 | 1.000000 | 0.130744 |
| SGLN.L | 0.196809 | 0.170660 | 0.933486 | 1.342626 | −0.33127 | 4.8608 | −0.248895 | 0.016094 | 0.025228 | 0.049194 | −0.032254 | 0.066304 | 0.008686 |
| IHYU.L | 0.045488 | 0.100165 | 0.079751 | 0.116740 | 0.33097 | 2.8854 | −0.105345 | 0.009615 | 0.013573 | 0.280232 | 0.272060 | 0.237838 | 0.008483 |
| PLTR | 0.599359 | 0.673124 | 0.834704 | 1.347397 | 1.16425 | 8.4290 | −0.761128 | 0.060463 | 0.083656 | 1.446765 | 1.423180 | 0.977015 | −0.062117 |
| T56 | −0.114377 | 0.197365 | −0.769525 | −1.144274 | 2.16124 | 31.9427 | −0.529925 | 0.017952 | 0.025552 | 0.067587 | 0.024298 | −0.049599 | −0.069069 |
| BKS.L | 0.174530 | 0.475066 | 0.288444 | 0.463391 | 1.39022 | 15.8757 | −0.574519 | 0.039735 | 0.059009 | 0.565053 | 0.282789 | 0.886090 | −0.045064 |
| DRO.AX | 0.799611 | 0.871210 | 0.874773 | 1.374688 | 0.35622 | 3.5573 | −0.779506 | 0.072171 | 0.112369 | 0.958174 | 1.110975 | 1.452265 | −0.425875 |

(Mine and `stats_daily.csv` agree to every digit shown and beyond.)

`^FTAS` betas also reproduce exactly (e.g. RR.L β_FTAS 1.69495861, α 0.50479159, R² 0.25766269),
including the shortened overlap caused by `^FTAS` ending 2026-07-22.

### Monthly VaR/CVaR and capture ratios

These are computed on **month-end GBP TR levels from 2021-09-30 to 2026-09-30, 60 monthly returns**
(`prices_gbp_monthly_clean.csv`), excess returns over rf_m = (1.0375)^(1/12) − 1, up/down months
split on the benchmark's **excess** monthly return. On that sample all six monthly fields
(`var95_monthly`, `cvar95_monthly`, `var99_monthly`, `cvar99_monthly`,
`upside_capture_monthly`, `downside_capture_monthly`) reproduce for all nine tickers with
**0 mismatches** at 1e-9. (See issue 2 for the stub last month.)

### Ledoit–Wolf constant-correlation shrinkage

Re-implemented from Ledoit & Wolf (2004), *Honey, I Shrunk the Sample Covariance Matrix*,
JPM 30(4), independently of the project code:

```python
Xc = X - X.mean(0);  T,N = Xc.shape
S  = Xc.T @ Xc / T                          # MLE (1/T) sample covariance
s  = np.sqrt(np.diag(S)); R = S/np.outer(s,s)
r_bar = R[~np.eye(N,dtype=bool)].mean()
F  = r_bar*np.outer(s,s); np.fill_diagonal(F, np.diag(S))
pi_mat[i,j] = ((Xc[:,i]*Xc[:,j] - S[i,j])**2).mean();          pi = pi_mat.sum()
theta[i,j]  = ((Xc[:,i]**2 - S[i,i])*(Xc[:,i]*Xc[:,j] - S[i,j])).mean()
rho = trace(pi_mat) + sum_{i!=j} (r_bar/2)*( sqrt(S[j,j]/S[i,i])*theta[i,j]
                                           + sqrt(S[i,i]/S[j,j])*theta[j,i] )
gamma = ((F-S)**2).sum();  kappa = (pi-rho)/gamma;  delta = clip(kappa/T, 0, 1)
Sigma_LW = (delta*F + (1-delta)*S) * 252
```

Input: complete-case daily returns of the 36 optimiser names over the 5y window, taken from
`prices_gbp_daily_clean.csv` with `pct_change(fill_method=None)` (**important** — pandas 2.x still
forward-fills by default, which silently turns the masked SMEA.L/DBMG.L bars into zero returns and
changes T from 1135 to 1259).

| quantity | mine | `analysis_results.json` | diff |
|---|---|---|---|
| T | 1135 | 1135 | 0 |
| N | 36 | 36 | 0 |
| r̄ | 0.23223406317643142 | 0.23223406317643136 | 5.6e-17 |
| π | 1.934159653786302e-04 | 1.9341596537863018e-04 | 2.7e-20 |
| ρ | 7.022857339185345e-05 | 7.022857339185367e-05 | −2.2e-19 |
| γ | 3.0359425624726745e-06 | 3.035942562472674e-06 | 4.2e-22 |
| κ | 40.57632496394948 | 40.57632496394941 | 7.1e-14 |
| **δ** | **0.035750066047532586** | **0.035750066047532524** | **6.2e-17** |

Off-diagonal `Cov_LW` entries (annualised) against `data/cov_lw.csv`:

| pair | mine | cov_lw.csv | abs diff | rel diff |
|---|---|---|---|---|
| IITU.L / VMID.L | 1.8027579710e-02 | 1.8027579710e-02 | 9.4e-17 | 5.2e-15 |
| SGLN.L / RR.L | 1.8342991166e-03 | 1.8342991166e-03 | 6.7e-17 | 3.6e-14 |
| T56 / IHYU.L | 2.0607567970e-03 | 2.0607567970e-03 | 3.0e-18 | 1.5e-15 |
| PLTR / VWRP.L | 2.5421749352e-02 | 2.5421749352e-02 | 8.0e-17 | 3.1e-15 |
| DBMG.L / SGLN.L | 2.7522263175e-03 | 2.7522263175e-03 | 1.7e-17 | 6.2e-15 |
| MSFT / IWQU.L | 2.1712877061e-02 | 2.1712877061e-02 | 2.1e-17 | 9.6e-16 |

Whole matrix: max abs diff **1.08e-16**, max rel diff **6.3e-13**, symmetric. `δ = 0.0357` is a light
shrink, consistent with T/N = 1135/36 ≈ 32 observations per asset — plausible, not a bug.

---

## 3. Issues

### Issue 1 (major) — the published price deliverable `data/prices_gbp_daily.csv` is still un-repaired

`analysis.py` detects and repairs the 100× scale glitches, but writes the repaired series **only** to
`prices_gbp_daily_clean.csv` / `prices_gbp_monthly_clean.csv`. The files SPEC §1 names as the pipeline
output — `prices_gbp_daily.csv`, `prices_gbp_monthly.csv`, `prices_gbp_weekly.csv` — still contain the
broken bars:

```
prices_gbp_daily.csv, DBMG.L        prices_gbp_daily_clean.csv, DBMG.L
2025-04-22   142.180579             2025-04-22          NaN
2025-04-23     1.419818   <- /100   2025-04-23          NaN
2025-04-24   108.602275             2025-04-24   108.602275

prices_gbp_daily.csv, SMEA.L        prices_gbp_daily_clean.csv, SMEA.L
2023-11-24     2.414590             2023-11-24   241.459006
2023-11-27   276.717050  <- x100    2023-11-27          NaN
```

In the raw file DBMG.L has 10 bars with |daily return| > 50% (max +9932%, min −99.0%) and an
annualised vol of **7795%**; SMEA.L has a +11360% bar. The monthly file is equally affected
(DBMG.L raw monthly max |return| 9779%, annualised monthly vol 3612%, vs 16.6% / 15.4% clean).

Recomputing the 5y statistics for DBMG.L **from `prices_gbp_daily.csv`** therefore gives:

| field | from `prices_gbp_daily.csv` | `stats_daily.csv` |
|---|---|---|
| mean_ann_arith | 93.3752284974 | 0.1041662755 |
| vol_ann | 94.5485496452 | 0.1527617257 |
| sortino | 93.6722887406 | 0.6146572127 |
| skew | 15.9991577777 | −0.1640231190 |
| excess_kurtosis | 256.1375383643 | 2.7578009670 |
| max_drawdown | −0.9948005116 | −0.3163295644 |
| beta_vwrp | 2.0362645621 | 0.1296997869 |
| beta_up / beta_down | −36.6816 / +29.8552 | −0.0966 / +0.2050 |

The analysis itself is unaffected — it used the clean file, and the repairs are fully documented in
`analysis_results.json → data_repairs` with evidence. The exposure is **downstream**: SPEC §3 tab 7
`Prices_GBP` and tab 8 `Prices_Monthly` are specified to hold "the daily/month-end GBP TR index", and
tabs 9–13 (`Returns_Monthly`, `Stats_Monthly`, `Covariance`, `Correlation`) are live formulas over
those tabs. If `build_excel.py` loads the SPEC-named file rather than the `_clean` one, the DBMG.L and
SMEA.L rows of every formula tab will be nonsense, and tab 11's Stats_Daily-vs-Stats_Monthly
difference column — which exists precisely to catch this — will show differences in the thousands of
percent for those two names while everything else ties.

**Fix**: write the repaired series back over `prices_gbp_daily.csv` / `prices_gbp_monthly.csv` /
`prices_gbp_weekly.csv` (keeping the un-repaired versions as `*_raw.csv` for audit), or make
`build_excel.py` read only the `_clean` files and say so in the `Prices_GBP` method note. Whichever is
chosen, `Sources_Assumptions` should carry the DBMG.L/SMEA.L correction, as SPEC §3 tab 23 requires.

### Issue 2 (minor) — the last "month" of the monthly statistics is an 11-day stub

The month-end resample stamps the 2026-09-11 level as `2026-09-30`, and the monthly statistics use it
as a full observation. The 60-month sample that reproduces `var95_monthly`, `cvar95_monthly`,
`var99_monthly`, `cvar99_monthly`, `upside_capture_monthly` and `downside_capture_monthly` runs
2021-09-30 → 2026-09-30, so its final return is the 7-trading-day move 2026-08-31 → 2026-09-11
(benchmark −0.69%), counted alongside 59 genuine calendar months. It is a benchmark-down month, so it
does not touch upside capture but it does enter every downside capture number and the VaR/CVaR tails:
e.g. VWRP.L `downside_capture_monthly` = 1.0 by construction, but RR.L moves from −0.6675 (60 months
ending 2026-08-31) to −0.2373 (the published figure) depending on which 60-month sample is used —
these ratios are sensitive to exactly one or two months, so the stub genuinely matters for them.
Separately, the monthly sample's base is 2021-09-30, so the monthly statistics cover 2021-09-30 →
2026-09-11 rather than the declared 5y window 2021-09-13 → 2026-09-11.

Nothing here feeds the optimiser (which is daily), and the daily VaR/CVaR are unaffected.
**Fix**: drop the stub month from the monthly return matrix (use month-ends 2021-09-30 → 2026-08-31,
59 returns), or state in `definitions` and on the Excel `Stats_Monthly` tab that the final monthly
observation is a partial month.

### Issue 3 (minor) — DBMG.L's `n_obs = 1256` is unexplained in the stats table

Every other 5y name has `n_obs = 1259`. DBMG.L has 1256 because the two masked bars (2025-04-22/23)
remove two observations and the gap-crossing 2025-04-21 → 2025-04-24 return is dropped as well. That
is the right call — keeping a 3-day return in a daily sample would inflate vol and distort the beta —
but neither `stats_daily.csv` nor the `definitions` block says gap-crossing returns are dropped, and
the reader has to reverse-engineer it. Recomputing on the same cleaned series but *keeping* the
gap-crossing return gives mean_ann 0.1052136100 vs 0.1041662755 (0.105pp, inside the 0.2pp tolerance),
vol 0.1527188154 vs 0.1527617257, beta 0.1299281663 vs 0.1296997869 (2.3e-4, inside the 1e-3
tolerance), skew −0.1652009008 vs −0.1640231190. So the choice is immaterial to the result, but it
should be stated. **Fix**: add one line to `definitions` ("returns spanning a masked bar are dropped,
not computed across the gap") and a footnote wherever DBMG.L's statistics are printed.

---

## 4. Checks that passed

- rf used by `stats_daily.csv` is 3.75%, matching `market_params.json → boe_bank_rate.value` and
  `analysis_results.json → config.rf_annual`; `sharpe` and `sortino` reconcile to it exactly.
- `sortino` uses downside deviation averaged over **all** observations (not just losing days), as the
  `definitions` block states; reproduced exactly.
- `skew` / `excess_kurtosis` are bias-corrected (scipy `bias=False`, Fisher); reproduced exactly.
- `cagr_5y` uses (level_end/level_start)^(365.25/calendar_days) − 1 from the window's own endpoints;
  reproduced exactly, and `ret_5y` is consistent with it (ret_5y is measured from the window start
  2021-09-13, not from a calendar 5-years-back date — self-consistent).
- `var95/99_daily` use the plain (linear-interpolation) percentile of the daily sample and
  `cvar95/99_daily` the mean of the observations at or below that cut-off; reproduced exactly.
- `beta_up` / `beta_down` split on the **benchmark's excess** return (> 0 / < 0), as documented, and
  are OLS slopes on the sub-sample, not filtered full-sample slopes; reproduced exactly for all nine.
- `max_drawdown` peak and trough dates reproduce exactly for all nine.
- `ret_ytd` bases on the 2025-12-31 level (which is present in the index) — reproduced exactly.
- `^FTAS` alpha/beta/R² reproduce exactly on the shortened overlap (`^FTAS` ends 2026-07-22), which the
  analysis log already flags.
- Ledoit–Wolf F has S's diagonal (F_ii = S_ii), so shrinkage leaves variances untouched and only pulls
  correlations toward r̄ — correct per the paper; `Cov_LW` diagonal equals the sample diagonal.
- `cov_lw.csv` is symmetric; T = 1135 complete-case days matches the 1259 window days minus the masked
  SMEA.L stretch and the GHYS.L January-2026 hole, as the analysis log states.
- Only DBMG.L and SMEA.L differ between `prices_gbp_daily.csv` and `prices_gbp_daily_clean.csv`
  (82 of 84 columns are bit-identical), so no silent repair was applied to any other series.
