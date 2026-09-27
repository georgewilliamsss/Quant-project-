# Refresh diff -- 2026-09-16 quality sleeve vs 2026-09-17 MOONSHOT rebuild

*Educational analysis, not personalised investment advice. Nobody on this project is a licensed adviser. Every figure below is a model output, not a certainty.*

| | Old build | New build |
|---|---|---|
| Build | 2026-09-16 quality sleeve | **2026-09-17 moonshot rebuild** |
| As-of (last full trading day) | 2026-09-16 | **2026-09-16 -- unchanged** |
| 5y window | 2021-09-16 -> 2026-09-16 | **2021-09-16 -> 2026-09-16 -- unchanged** |
| 10y window from | 2016-09-16 | **2016-09-16 -- unchanged** |
| Return days in the 5y window | 1261 | **1261 -- unchanged** |
| Panel rows / trading calendar | 2526 | **2526, identical date index** |
| rf (BoE Bank Rate) / ERP | 3.75% / 4.17% | **3.75% / 4.17% -- same file** |
| Core universe | 37 instruments | **37 -- unchanged** |
| Sleeve A | 40 quality-tilted names | **40 moonshot names (34 replaced)** |
| Sleeve A source | `universe/unicorn_final_quality_2026-09-16.json` | `universe/unicorn_final.json` |
| Source | `archive/2026-09-16-quality-sleeve/data/analysis_results.json` | `data/analysis_results.json` |

> **Read this first -- this diff has exactly one driver.** Unlike the previous refresh (2026-09-11 -> 2026-09-16), **nothing about the date, the window, the calendar, the rates or the yields changed here.** Both builds are priced at the same 2026-09-16 close and read the same `universe/market_params.json`. There is no three-day window roll to attribute anything to, and no 12-16 September market move: those drivers belong to the previous refresh and are documented in `archive/2026-09-16-quality-sleeve/data/REFRESH_DIFF.md`. The only input that changed in this rebuild is the 40-name Sleeve A list, and it changed by 34 of 40 names.

**CONFIG edits required: none.** Every value the rebuild brief specifies -- `as_of` 2026-09-16, `win5y` 2021-09-16 -> 2026-09-16, `win10y_start` 2016-09-16, rf = the Bank Rate in the new `market_params.json` (3.75%), ERP = its `damodaran_erp` (4.17%), the T36N/T56 redemption yields (5.30% / 5.87%) and the 2.5% SPCX policy weight -- was already in force in `scripts/analysis.py`'s CONFIG block, which reads the rate, premium, yield and clean-price fields from `market_params.json` at runtime. Each field was verified against the archived run's `config` block before re-running rather than assumed. No estimator, constraint, window or optimiser setting was touched. **One defect was fixed** after blind verification: the total-return LEVEL of a return series is now based on the day before the first return rather than on it, which corrects `total_return`, `cagr` and the drawdown path of the sleeve index, the combined book and every portfolio's realised/backtest series (section 6 and note 10.5). The archived figures are restated on the same basis before any old-vs-new number below is formed, so the comparison stays like-for-like.

## 1. Assertion: the core portfolios are unchanged

The core optimiser never sees Sleeve A. Its universe is the 36 core lines with >= 3 years of history, its covariance is the core-only Ledoit-Wolf matrix and its expected returns are the core-only blend, so replacing the moonshot names must leave it untouched. It does:

| Portfolio | max abs weight change | max abs GBP change (on GBP 160,000) | <= 1e-9? |
|---|---|---|---|
| MinVariance | 5.55e-16 | 8.91e-11 | yes |
| MaxSharpe | 2.15e-08 | 3.44e-03 | **no (see below)** |
| Moderate12 | 2.97e-15 | 4.80e-10 | yes |
| MaxSortino | 9.01e-09 | 1.44e-03 | **no (see below)** |
| EqualWeight | 0.00e+00 | 0.00e+00 | yes |
| NaiveReference | 0.00e+00 | 0.00e+00 | yes |

Optimiser inputs, old vs new (they are what actually has to be identical):

| File | Shape | Max abs difference |
|---|---|---|
| `cov_lw.csv` | 36x36 | 3.05e-16 |
| `cov_annual.csv` | 36x36 | 3.05e-16 |
| `corr.csv` | 36x36 | 1.50e-15 |
| `expected_returns.csv` | 37x6 | 1.33e-15 |

**Verdict: PASS for the headline and every convex problem; two non-convex portfolios miss the literal 1e-9 bar.** MinVariance, Moderate12 (the headline), EqualWeight and NaiveReference reproduce to 3e-15 or better on every weight. MaxSharpe (max |dw| 2.1e-08) and MaxSortino (9.0e-09) do not, and the cause is arithmetic, not data: the optimiser inputs agree only to ~3e-16 (last-bit float noise between two runs of threaded BLAS -- see optimiser_inputs), and the Sharpe and Sortino surfaces are very flat near their optimum, so SLSQP stopping at ftol 1e-12 lands a few 1e-8 away. The money impact is GBP 0.0034 on a GBP 160,000 sleeve and no reported statistic moves in the 4th decimal. Re-running this build twice is bit-identical (max |dw| = 0.0), so the difference is between the two RUNS, not between two answers.

Independent check on the price panel: data/prices_gbp_daily_clean.csv: of the 44 shared core columns only SIE.DE differs, and only in the base level of its total-return index (constant ratio 0.99999897); its daily returns are identical to 8.9e-16.

## 2. Rate, premium and yield inputs -- all unchanged

| Input | Old | New | Change | Source |
|---|---|---|---|---|
| BoE Bank Rate (model rf) | 3.75% | **3.75%** | +0.00 pp | https://www.bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate |
| Damodaran mature-market ERP (CAPM) | 4.17% | **4.17%** | +0.00 pp | https://aswathdamodaran.substack.com/p/data-update-2-for-2026-a-testing |
| UK 10y gilt yield (reported) | 5.3% | **5.3%** | +0.00 pp | https://tradingeconomics.com/united-kingdom/government-bond-yield |
| UK 30y gilt yield (reported) | 5.89% | **5.89%** | +0.00 pp | https://tradingeconomics.com/united-kingdom/30-year-bond-yield |
| US 10y Treasury yield (IBTM.L input) | 5.01% | **5.01%** | +0.00 pp | yfinance ^TNX (CBOE 10-Year Treasury Note Yield Index), pulled 2026-09-16 |
| T36N redemption yield (E[R] input) | 5.3% | **5.3%** | +0.000 pp | https://www.hl.co.uk/shares/corporate-bonds-gilts/bond-prices/uk-gilts |
| T56 redemption yield (E[R] input) | 5.87% | **5.87%** | +0.000 pp | https://www.hl.co.uk/shares/corporate-bonds-gilts/bond-prices/uk-gilts |
| SPCX fixed policy weight | 2.5% | **2.5%** | 0.00 pp | SPEC section 5 |

No change at all. Both builds read the same universe/market_params.json (compiled 2026-09-16): Bank Rate 3.75%, Damodaran mature-market ERP 4.17%, T36N 5.30% at a 96.75 clean price, T56 5.87% at 93.155, US 10y 5.01%, fed funds mid 3.875%. Every CAPM intercept, every yield-based estimate #2 and every Sharpe denominator is therefore identical.

Ledoit-Wolf shrinkage: delta 0.035840 -> 0.035840 (change 0.0e+00), r-bar 0.232380 -> 0.232380, T = 1135, N = 36 -- identical, because the shrinkage is estimated on the core optimiser universe only.

## 3. Portfolios -- old vs new

`E[R]` is the blend estimate for the core sleeve as held (the 2.5% SPCX policy weight included at its CAPM estimate). `Vol` is the ex-ante Ledoit-Wolf volatility of the optimised 97.5%; `VolFull` includes SPCX from the pairwise-complete sample covariance. Betas are the as-held core-sleeve betas vs VWRP.L. Turnover is one-way, 0.5 x sum |w_new - w_old| over the full 37-line core weight vector.

| Portfolio | E[R] old | E[R] new | d | Vol old | Vol new | VolFull old | VolFull new | Sharpe old | Sharpe new | beta | beta+ | beta- | Turnover |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GMV | 6.31% | 6.31% | 0.00 pp | 5.54% | 5.54% | 6.10% | 6.10% | 0.419 | 0.419 | 0.357 | 0.466 | 0.320 | 1.4e-15 |
| MaxSharpe | 13.37% | 13.37% | 0.00 pp | 9.58% | 9.58% | 10.31% | 10.31% | 0.933 | 0.933 | 0.630 | 0.708 | 0.614 | 5.4e-08 |
| **Moderate12 (headline)** | 15.41% | 15.41% | 0.00 pp | 12.00% | 12.00% | 12.78% | 12.78% | 0.912 | 0.912 | 0.794 | 0.852 | 0.768 | 5.4e-15 |
| MaxSortino | 13.40% | 13.40% | 0.00 pp | 9.66% | 9.66% | 10.43% | 10.43% | 0.925 | 0.925 | 0.614 | 0.699 | 0.593 | 2.2e-08 |
| Variant A - Moderate12 (gilts at YTM) | 14.90% | 14.90% | 0.00 pp | 12.00% | 12.00% | 12.80% | 12.80% | 0.872 | 0.872 | 0.781 | 0.834 | 0.748 | 5.5e-15 |
| Variant A - MaxSharpe | 12.85% | 12.85% | 0.00 pp | 9.63% | 9.63% | 10.31% | 10.31% | 0.882 | 0.882 | 0.636 | 0.721 | 0.621 | 2.3e-08 |
| Variant B - Moderate12 (diversified caps) | 14.88% | 14.88% | 0.00 pp | 12.00% | 12.00% | 12.63% | 12.63% | 0.882 | 0.882 | 0.813 | 0.872 | 0.810 | 2.9e-15 |
| Variant B - MaxSharpe | 13.58% | 13.58% | 0.00 pp | 10.23% | 10.23% | 10.92% | 10.92% | 0.901 | 0.901 | 0.682 | 0.745 | 0.671 | 9.8e-09 |

Every column above is unchanged to the printed precision, and the beta / beta+ / beta- columns are printed once because old and new agree to at least 8 decimal places (largest change 8.9e-09). The largest turnover anywhere in the eight portfolios is 5.4e-08 of the sleeve -- **GBP 0.009 on GBP 160,000**.

### Top-8 weights, headline Moderate12 (old vs new)

| Ticker | Old weight | New weight | Change |
|---|---|---|---|
| SMGB.L | 16.61% | 16.61% | 1.7e-13 pp |
| SGLN.L | 14.83% | 14.83% | 8.3e-15 pp |
| ISF.L | 13.54% | 13.54% | 3.0e-13 pp |
| IBTM.L | 10.00% | 10.00% | 6.9e-15 pp |
| DBMG.L | 9.47% | 9.47% | 2.6e-13 pp |
| IITU.L | 5.39% | 5.39% | 5.3e-14 pp |
| BRNT.L | 5.17% | 5.17% | 6.9e-15 pp |
| RR.L | 5.00% | 5.00% | 1.5e-14 pp |


### Top-8 weights, the other seven portfolios (old -> new)

| Portfolio | Top 8 by new weight (old weight -> new weight) | Largest single weight change |
|---|---|---|
| GMV | IBTM.L 20.00% -> 20.00%; ISF.L 14.66% -> 14.66%; DBMG.L 12.90% -> 12.90%; GHYS.L 12.77% -> 12.77%; T36N 7.23% -> 7.23%; SGLN.L 5.58% -> 5.58%; VMID.L 4.91% -> 4.91%; ICOM.L 4.89% -> 4.89% | 5.6e-14 pp |
| MaxSharpe | SGLN.L 16.41% -> 16.41%; IBTM.L 16.34% -> 16.34%; ISF.L 15.88% -> 15.88%; DBMG.L 8.66% -> 8.66%; IITU.L 7.72% -> 7.72%; SMGB.L 6.40% -> 6.40%; RR.L 5.00% -> 5.00%; HSBA.L 5.00% -> 5.00% | 2.1e-06 pp |
| MaxSortino | ISF.L 19.62% -> 19.62%; SGLN.L 16.47% -> 16.47%; IBTM.L 16.19% -> 16.19%; DBMG.L 8.81% -> 8.81%; SMGB.L 7.54% -> 7.54%; RR.L 5.00% -> 5.00%; PLTR 5.00% -> 5.00%; HSBA.L 5.00% -> 5.00% | 9.0e-07 pp |
| Variant A - Moderate12 (gilts at YTM) | SMGB.L 17.65% -> 17.65%; T36N 16.42% -> 16.42%; SGLN.L 13.89% -> 13.89%; DBMG.L 8.58% -> 8.58%; ISF.L 6.91% -> 6.91%; BRNT.L 6.11% -> 6.11%; IITU.L 5.44% -> 5.44%; PLTR 5.00% -> 5.00% | 3.8e-13 pp |
| Variant A - MaxSharpe | T36N 18.56% -> 18.56%; SGLN.L 16.07% -> 16.07%; ISF.L 14.64% -> 14.64%; IITU.L 11.19% -> 11.19%; DBMG.L 6.44% -> 6.44%; RR.L 5.00% -> 5.00%; SHEL.L 5.00% -> 5.00%; HSBA.L 5.00% -> 5.00% | 1.4e-06 pp |
| Variant B - Moderate12 (diversified caps) | IITU.L 10.00% -> 10.00%; SMGB.L 10.00% -> 10.00%; ISF.L 10.00% -> 10.00%; SGLN.L 10.00% -> 10.00%; CSP1.L 8.62% -> 8.62%; BRNT.L 8.54% -> 8.54%; DBMG.L 6.38% -> 6.38%; IHYU.L 5.56% -> 5.56% | 9.5e-14 pp |
| Variant B - MaxSharpe | SGLN.L 10.00% -> 10.00%; IBTM.L 10.00% -> 10.00%; DBMG.L 10.00% -> 10.00%; ISF.L 10.00% -> 10.00%; IITU.L 8.91% -> 8.91%; SMGB.L 7.72% -> 7.72%; BRNT.L 7.25% -> 7.25%; GHYS.L 5.00% -> 5.00% | 4.7e-07 pp |

Every per-portfolio top-8 table and the five largest weight changes per portfolio are in `data/refresh_diff.json` under `portfolios`.

## 4. Per-asset 5y statistics -- the 14 held lines

The headline Moderate-12% portfolio holds 14 of the 37 core lines. None of their 5-year statistics moved, because none of their price history moved:

| Ticker | w (Moderate12) | mean 5y old | mean 5y new | vol old | vol new | beta old | beta new | n obs | E[R] blend old | E[R] blend new |
|---|---|---|---|---|---|---|---|---|---|---|
| SMGB.L | 16.61% | 33.19% | 33.19% | 32.40% | 32.40% | 1.907 | 1.907 | 1261 | 22.44% | 22.44% |
| SGLN.L | 14.83% | 19.97% | 19.97% | 17.06% | 17.06% | 0.055 | 0.055 | 1261 | 11.97% | 11.97% |
| ISF.L | 13.54% | 12.61% | 12.61% | 12.47% | 12.47% | 0.653 | 0.653 | 1261 | 9.54% | 9.54% |
| IBTM.L | 10.00% | -0.90% | -0.90% | 9.37% | 9.37% | -0.034 | -0.034 | 1261 | 1.99% | 1.99% |
| DBMG.L | 9.47% | 10.33% | 10.33% | 15.27% | 15.27% | 0.129 | 0.129 | 1258 | 7.31% | 7.31% |
| IITU.L | 5.39% | 22.11% | 22.11% | 22.57% | 22.57% | 1.477 | 1.477 | 1261 | 16.01% | 16.01% |
| BRNT.L | 5.17% | 30.11% | 30.11% | 37.01% | 37.01% | 0.108 | 0.108 | 1261 | 17.16% | 17.16% |
| RR.L | 5.00% | 60.52% | 60.52% | 41.57% | 41.57% | 1.306 | 1.306 | 1261 | 34.86% | 34.86% |
| SHEL.L | 5.00% | 24.74% | 24.74% | 24.40% | 24.40% | 0.468 | 0.468 | 1261 | 15.22% | 15.22% |
| PLTR | 5.00% | 58.64% | 58.64% | 67.20% | 67.20% | 1.445 | 1.445 | 1261 | 34.21% | 34.21% |
| HSBA.L | 5.00% | 37.25% | 37.25% | 24.74% | 24.74% | 0.852 | 0.852 | 1261 | 22.28% | 22.28% |
| SPCX | 2.50% | 13.72% | 13.72% | 90.29% | 90.29% | 2.946 | 2.946 | 67 | 14.88% | 14.88% |
| BRK-B | 1.42% | 14.86% | 14.86% | 18.81% | 18.81% | 0.344 | 0.344 | 1261 | 10.02% | 10.02% |
| AZN.L | 1.08% | 13.14% | 13.14% | 24.74% | 24.74% | 0.429 | 0.429 | 1261 | 9.34% | 9.34% |

Largest change across all 14 lines: mean 0.0e+00, volatility 0.0e+00, beta 0.0e+00 -- i.e. zero to float precision. SPCX still carries its 67-bar 'insufficient history' warning and its fixed 2.5% policy weight.

## 5. What actually changed: Sleeve A

| | Old (quality sleeve) | New (moonshot sleeve) |
|---|---|---|
| Names | 40 | 40 |
| Kept | - | 6 (ARA.TO, SLX.AX, VUL.AX, IMSR, BIOA, FTC.L) |
| Replaced | - | 34 |
| Median market cap (USD m) | 818.0 | **220.3** |
| Market cap range (USD m) | 190.9 - 2864.5 | **7.6 - 945.5** |
| Median avg daily traded value (USD k) | 6043 | **2391** |
| Thinnest name (USD k/day) | 261 | **19** |
| Regions | Europe 7, Other 11, UK 6, US 16 | Europe 5, Other 12, UK 3, US 20 |
| Sectors used | 21 | 22 |
| Live names on the sleeve index's first date | 28 of 40 | 27 of 40 |

*Traded-value footnote: NEW: fetch_log.json tickers[t].avg_daily_value_usd_k_3m -- mean(Close x Volume) over the 63 trading rows to 2026-09-16, GBp /100 then converted to USD (scripts/fetch_data.py section 4b). OLD: the quality-sleeve fetch predates that field, so the same statistic is RE-COMPUTED HERE from that build's own archived raw bars and FX file by the identical method (own calculation; the method reproduces all 40 new names' fetch_log values exactly, so old and new are like-for-like). Yahoo volume, not venue-reported ADV.*

**Dropped (34):** BKS.L, NCH2.DE, ERII, 1833.HK, NEO.TO, GNS.L, PRL.TO, NET.L, ALFEN.AS, WVE, AIP, CVO.TO, GPCR, AVIO.MI, CRNC, BSL.DE, AMSC, NXL.AX, ASPN, BEAM, IQE.L, INOD, NTLA, OVH.PA, 0863.HK, EXOD, NVTS, ONT.L, DRO.AX, AMPX, SGL.DE, EVT.DE, SIFY, A4N.AX

**Added (34):** IPWR, VYGR, AL3.AX, ONWD.BR, LTBR, NYXH, ALMU, WBT.AX, IDN, GELN.L, EDIT, SEYE.ST, QSI, CRBU, ALCLS.PA, GUTS, PRME, PRQR, ALMDT.PA, CU6.AX, LAES, EMV.AX, SLDP, HYT.AX, MSCL.TO, 2498.HK, GFUZ, AXE.AX, MOLN.SW, LIS.AX, GSIT, AISP, BTQ, BGO.L

**Short histories (fewer than 252 trading days inside the 5y window) -- 3 names:**

| Ticker | First bar | Obs in window | Years |
|---|---|---|---|
| IMSR | 2024-10-10 | 219 | 0.87 |
| GFUZ | 2025-09-30 | 243 | 0.96 |
| BTQ | 2025-09-26 | 245 | 0.97 |

**Thinnest ten by average daily traded value** (a GBP 1,000 ticket is about USD 1.34k, so the last column is the ticket as a share of a day's turnover):

| Ticker | Avg daily value (USD k) | Market cap (USD m) | GBP 1,000 as % of a day |
|---|---|---|---|
| LIS.AX | 18.7 | 68.3 | 7.17% |
| HYT.AX | 19.5 | 7.6 | 6.87% |
| GELN.L | 34.8 | 44.4 | 3.85% |
| EMV.AX | 39.7 | 109.0 | 3.38% |
| MOLN.SW | 65.6 | 152.0 | 2.04% |
| AXE.AX | 113.3 | 37.3 | 1.18% |
| BGO.L | 151.4 | 64.3 | 0.89% |
| MSCL.TO | 200.8 | 203.1 | 0.67% |
| AL3.AX | 220.5 | 54.6 | 0.61% |
| ARA.TO | 261.1 | 670.2 | 0.51% |

## 6. Unicorn (moonshot) sleeve -- old vs new

Equal weight, daily rebalanced across the names live on each date, 1261 days (2021-09-17 -> 2026-09-16) in both builds (old: 1261 days, 2021-09-17 -> 2026-09-16).

**Level-base correction (2026-09-17).** Both builds compounded a return series' total-return level from 1.0 ON the date of the first return instead of the day before it, so that first return was counted in every distributional statistic but lost from the compounded level. `total_return` was therefore level[-1]/level[0]-1 over 1260 of the 1261 returns, and `cagr` annualised it over the span between the first and last RETURN dates, which is not the span the level covers. Found by blind verification (data/verify_analysis_refresh.md section 5.1), reproduced to 10 decimal places, and fixed in scripts/analysis.py on 2026-09-17: series_stats now bases the level at 100 on the panel observation before the first return and publishes that date as level_base_date. No other statistic was affected -- mean, volatility, Sharpe, Sortino, skew, kurtosis, VaR/CVaR, the betas and the correlation all reproduce unchanged.

**How the OLD column below is formed:** the archived JSON still carries the pre-fix figures, so the OLD column of every total_return / cagr / max_drawdown comparison below is the RESTATED archive figure, rebuilt from archive/2026-09-16-quality-sleeve/data/prices_gbp_daily.csv and the archived Moderate12 weights. The rebuild reproduces the archived mean, volatility and (pre-fix) total return to better than 1e-9, which is what licenses the restatement.

| Figure | As published | Restated | |
|---|---|---|---|
| Old (quality) sleeve total return | 182.37% | **183.71%** | first return 0.476%, now compounded in |
| Old combined 200k total return | 217.38% | **217.22%** | first return -0.050%, now compounded in |
| Old (quality) sleeve CAGR | 23.09% | **23.19%** | annualised over 2021-09-16 -> 2026-09-16 |
| Old combined 200k CAGR | 26.00% | **25.98%** | annualised over 2021-09-16 -> 2026-09-16 |
| New (moonshot) sleeve total return | 52.85% | **54.76%** | first release -> this file |
| New (moonshot) sleeve CAGR | 8.86% | **9.13%** | first release -> this file |

CAGR convention: (1 + total_return) ^ (365.25 / calendar days from level_base_date to the last return) - 1 -- the same convention analysis.py uses for every per-asset CAGR, now applied to a level that starts on the same date the return series' first return is earned from. The alternative 252-trading-day annualisation is reported alongside for completeness (cagr_restated_252day_convention): it moves the new sleeve from 9.13% to 9.12% and the old sleeve from 23.19% to 23.17%, i.e. both conventions round to the same 2 decimals on the new sleeve.

| Statistic | Old (quality) | New (moonshot) | Change |
|---|---|---|---|
| Mean return (annualised, arithmetic) | 24.43% | **12.24%** | -12.19 pp |
| CAGR | 23.19% | **9.13%** | -14.06 pp |
| Volatility | 26.83% | **26.51%** | -0.32 pp |
| Sharpe | 0.771 | **0.320** | -0.451 |
| Sortino | 1.170 | **0.465** | -0.706 |
| Downside deviation | 17.67% | **18.26%** | +0.59 pp |
| Skew | 0.289 | **0.108** | -0.181 |
| Excess kurtosis | 1.149 | **1.320** | +0.171 |
| Max drawdown | -40.17% | **-45.53%** | -5.36 pp |
| Beta vs VWRP | 1.112 | **0.868** | -0.244 |
| Beta+ (up days) | 1.067 | **0.774** | -0.292 |
| Beta- (down days) | 1.064 | **0.907** | -0.157 |
| Beta asymmetry (b+ - b-) | 0.003 | **-0.133** | -0.136 |
| VaR 95% (daily) | 2.44% | **2.59%** | +0.15 pp |
| CVaR 95% (daily) | 3.26% | **3.44%** | +0.18 pp |
| Total return over the window | 183.71% | **54.76%** | -128.95 pp |
| R2 vs VWRP | 0.292 | **0.182** | -0.109 |
| Correlation with VWRP | 0.540 | **0.427** | -0.113 |
| Max drawdown window | 2021-11-12 -> 2022-05-12 | **2021-11-05 -> 2023-10-27** | |

Expected returns (the sleeve's input to the combined book):

| Estimate | Old | New | Change |
|---|---|---|---|
| Historical 5y mean | 22.94% | 12.13% | -10.81 pp |
| CAPM (rf + beta x ERP) | 8.60% | 7.86% | -0.75 pp |
| **Blend (50/50, the one used)** | 15.77% | 9.99% | -5.78 pp |

Everything moved, because 34 of the 40 constituents are different names. The new sleeve is deliberately earlier-stage: median market cap USD 220m vs 818m, and it is the first five years of a set of pre-revenue/early-revenue moonshots rather than a quality-tilted small-cap basket. Its realised 5y CAGR falls 14.1 pp (23.2% -> 9.1%) and its historical-mean input falls 10.8 pp, which is what drags the sleeve's blended expected return from 15.77% to 9.99%. Volatility is almost unchanged (26.8% -> 26.5%) because the equal-weight sleeve index diversifies 40 idiosyncratic names either way, but the DISTRIBUTION changed: skew 0.29 -> 0.11, max drawdown -40.2% -> -45.5%, and beta asymmetry flips from about zero (0.003) to clearly negative (-0.133) -- the new sleeve captures less of the benchmark's up days (beta+ 1.07 vs 0.77) than of its down days (beta- 1.06 vs 0.91). That is the honest cost of the mandate: these are lottery-ticket payoffs whose 5y history is mostly the 2022-2023 small-cap drawdown, not evidence about the next 5-10 years.

## 7. Combined GBP 200,000 book -- old vs new

80% headline Moderate-12% core (unchanged) + 20% sleeve.

| Statistic | Old | New | Change |
|---|---|---|---|
| Ex-ante E[R] (blend) | 15.48% | **14.33%** | -1.16 pp |
| Ex-ante volatility | 14.42% | **14.23%** | -0.19 pp |
| Ex-ante Sharpe | 0.813 | **0.743** | -0.070 |
| Beta vs VWRP | 0.868 | **0.832** | -0.036 |
| Beta+ | 0.905 | **0.850** | -0.055 |
| Beta- | 0.834 | **0.816** | -0.018 |
| Beta asymmetry | 0.071 | **0.035** | -0.037 |

Realised 5-year daily backtest of the combined book (fixed weights, no costs):

| Statistic | Old | New | Change |
|---|---|---|---|
| CAGR | 25.98% | **23.02%** | -2.96 pp |
| Volatility | 13.50% | **13.03%** | -0.47 pp |
| Sharpe | 1.499 | **1.366** | -0.133 |
| Sortino | 2.195 | **1.971** | -0.224 |
| Skew | -0.384 | **-0.486** | -0.102 |
| Excess kurtosis | 1.978 | **2.232** | +0.254 |
| Max drawdown | -15.91% | **-16.85%** | -0.93 pp |
| Beta | 0.814 | **0.765** | -0.049 |
| Beta+ | 0.743 | **0.684** | -0.058 |
| Beta- | 0.815 | **0.783** | -0.031 |
| Total return | 217.22% | **181.67%** | -35.54 pp |

The CAGR, total-return and max-drawdown rows above are on the corrected level base on BOTH sides (section 6); the archived combined book's published total return was 217.38%, restated 217.22%.

**Risk split:** core 67.8% -> **68.1%** of total portfolio risk; sleeve 32.2% -> **31.9%**.

The combined GBP 200k book is 80% unchanged core + 20% new sleeve, so it inherits the sleeve change at a fifth of the size: ex-ante E[R] 15.48% -> 14.33% (-1.16 pp, i.e. 0.2 x the sleeve's -5.78 pp), ex-ante vol 14.42% -> 14.23%, ex-ante Sharpe 0.813 -> 0.743. The realised 5y backtest CAGR falls 3.0 pp. The sleeve's share of total portfolio risk barely moves (32.2% -> 31.9%): the new names are individually more volatile (mean name vol 93% vs 80%) but LESS correlated with each other (mean pairwise correlation 0.063 vs 0.093), and the two effects almost cancel at sleeve level.

## 8. The 77x77 combined covariance

| | Old | New |
|---|---|---|
| Dimension | 77x77 | 77x77 |
| Rows/columns replaced | - | 34 of 77 |
| Mean sleeve-name volatility (annualised) | 80.3% | **93.1%** |
| Median sleeve-name volatility | 74.8% | **87.2%** |
| Most volatile sleeve name | 247.2% | **172.6%** |
| Mean pairwise correlation inside the sleeve | 0.0933 | **0.0635** |
| Mean core-to-sleeve covariance | 0.02134 | **0.01806** |
| Min eigenvalue before the PSD repair | -0.1463 | **-0.1032** |
| Complete-case days (core optimiser matrix) | 1135 | 1135 |

The new sleeve names are individually far more volatile (mean 93% vs 80% a year) but much less correlated with each other (0.063 vs 0.093) and slightly less correlated with the core. That is the moonshot design working as intended at the covariance level: more idiosyncratic risk, less shared factor risk.

**One honest wrinkle:** the CORE block of this 77x77 matrix is not quite identical between the builds (max cell change 0.0115, on the SPCX row; the largest implied core volatility change is SGLN.L at 0.85 pp). The pairwise-complete 77x77 matrix is made positive semi-definite by eigenvalue clipping applied to the WHOLE matrix. Replacing 34 of the 40 sleeve rows changes the negative eigenvalues that have to be clipped (-0.1463 -> -0.1032), so the repair redistributes slightly differently across the core block too. The OPTIMISER's covariance (cov_lw.csv, 36 core lines, complete-case) is untouched: max abs change 3.1e-16. So the core WEIGHTS are untouched, but the combined book's ex-ante volatility, betas and risk split are computed from a matrix whose core block has moved slightly. That is a property of the PSD repair, not a market event, and it is disclosed rather than smoothed over.

## 9. Why each change happened

A consolidated recap: the six paragraphs below are the same explanations quoted in sections 1, 2 and 6 to 8, gathered in one place, and they are the `why_each_material_change_happened` block of `data/refresh_diff.json`.

**Core sleeve -- nothing moved.** Nothing moved. The core optimiser never sees Sleeve A: its universe is the 36 core lines with >= 3y history, its covariance is the core-only Ledoit-Wolf matrix and its expected returns are the core-only blend. Same as-of, same window, same rf/ERP/yields, same constraints => same weights.

**Rates, premia and yields -- nothing moved.** No change at all. Both builds read the same universe/market_params.json (compiled 2026-09-16): Bank Rate 3.75%, Damodaran mature-market ERP 4.17%, T36N 5.30% at a 96.75 clean price, T56 5.87% at 93.155, US 10y 5.01%, fed funds mid 3.875%. Every CAPM intercept, every yield-based estimate #2 and every Sharpe denominator is therefore identical.

**Window and market moves -- not applicable.** Not applicable to this rebuild. There is no window shift and no 12-16 September repricing in this diff: both builds end on the 2026-09-16 close with the identical 2526-row calendar and 1261 return days. Those drivers belong to the previous refresh and are documented in archive/2026-09-16-quality-sleeve/data/REFRESH_DIFF.md.

**Sleeve A -- everything moved.** Everything moved, because 34 of the 40 constituents are different names. The new sleeve is deliberately earlier-stage: median market cap USD 220m vs 818m, and it is the first five years of a set of pre-revenue/early-revenue moonshots rather than a quality-tilted small-cap basket. Its realised 5y CAGR falls 14.1 pp (23.2% -> 9.1%) and its historical-mean input falls 10.8 pp, which is what drags the sleeve's blended expected return from 15.77% to 9.99%. Volatility is almost unchanged (26.8% -> 26.5%) because the equal-weight sleeve index diversifies 40 idiosyncratic names either way, but the DISTRIBUTION changed: skew 0.29 -> 0.11, max drawdown -40.2% -> -45.5%, and beta asymmetry flips from about zero (0.003) to clearly negative (-0.133) -- the new sleeve captures less of the benchmark's up days (beta+ 1.07 vs 0.77) than of its down days (beta- 1.06 vs 0.91). That is the honest cost of the mandate: these are lottery-ticket payoffs whose 5y history is mostly the 2022-2023 small-cap drawdown, not evidence about the next 5-10 years.

**Combined book -- inherits the sleeve at a fifth of the size.** The combined GBP 200k book is 80% unchanged core + 20% new sleeve, so it inherits the sleeve change at a fifth of the size: ex-ante E[R] 15.48% -> 14.33% (-1.16 pp, i.e. 0.2 x the sleeve's -5.78 pp), ex-ante vol 14.42% -> 14.23%, ex-ante Sharpe 0.813 -> 0.743. The realised 5y backtest CAGR falls 3.0 pp. The sleeve's share of total portfolio risk barely moves (32.2% -> 31.9%): the new names are individually more volatile (mean name vol 93% vs 80%) but LESS correlated with each other (mean pairwise correlation 0.063 vs 0.093), and the two effects almost cancel at sleeve level.

**The 77x77 covariance.** The pairwise-complete 77x77 matrix is made positive semi-definite by eigenvalue clipping applied to the WHOLE matrix. Replacing 34 of the 40 sleeve rows changes the negative eigenvalues that have to be clipped (-0.1463 -> -0.1032), so the repair redistributes slightly differently across the core block too. The OPTIMISER's covariance (cov_lw.csv, 36 core lines, complete-case) is untouched: max abs change 3.1e-16.

## 10. Data-handling notes

1. **Stale `*_raw.csv` panels removed.** scripts/analysis.py reads data/prices_gbp_daily_raw.csv (the pristine fetch output) in preference to the SPEC-named file, so that its repairs are idempotent. The four *_raw.csv files left on disk after the quality-sleeve build still carried the OLD 40 names; had they been left in place this rebuild would silently have re-analysed the old sleeve. The data stage cleared them before the moonshot fetch and analysis.py has rebuilt them from it. Verified in this run (raw_panel_membership_check): the current data/prices_gbp_daily_raw.csv carries 40/40 moonshot tickers and 0 of the 34 dropped ones, while the preserved copy in archive/2026-09-16-quality-sleeve/data/ carries 40/40 quality-sleeve tickers and 0 of the 34 added ones, so no history was lost either way.

2. **`^FTAS` column restored again.** Yahoo still does not serve ^FTAS history: the 2026-09-17 moonshot re-fetch again returned a single post-as-of row (data/fetch_log.json tickers['^FTAS']), so the freshly fetched panel had no ^FTAS column and analysis.py's secondary-benchmark step failed outright. ^FTAS is the SECONDARY benchmark (beta_ftas / alpha_ftas / r2_ftas only); it is not in the optimiser universe and enters no covariance, expected return or weight. The restored column is byte-identical, on every overlapping date, to the one the 2026-09-16 quality-sleeve build used and to the 2026-09-11 build's pristine fetch cache before it. Effect: beta_ftas and friends are estimated on 2021-09-16 -> 2026-07-22 (the overlapping sample), exactly as in the previous two builds; analysis.py logs this automatically. Nothing else in either panel is touched.

3. **`unicorn_final.json` schema change.** universe/unicorn_final.json now carries weighted_score / judge_scores / confidence / key_backers / catalysts instead of the old judge_mean. analysis.py reads judge_mean with .get(), so analysis_results.json's judge_mean field is null for all 40 names. That field is metadata only -- it enters no statistic, weight or covariance -- but the Excel Unicorns tab and the PDF should be pointed at weighted_score / judge_scores (SPEC section 8) rather than at analysis_results.judge_mean.

4. **One core price column differs in level, not in returns.** data/prices_gbp_daily_clean.csv: of the 44 shared core columns only SIE.DE differs, and only in the base level of its total-return index (constant ratio 0.99999897); its daily returns are identical to 8.9e-16. It is a rebuilt total-return index base from the re-fetch, and it changes no statistic.

5. **Level-base bug fixed and the archive restated.** Both builds compounded a return series' total-return level from 1.0 ON the date of the first return instead of the day before it, so that first return was counted in every distributional statistic but lost from the compounded level. `total_return` was therefore level[-1]/level[0]-1 over 1260 of the 1261 returns, and `cagr` annualised it over the span between the first and last RETURN dates, which is not the span the level covers. Found by blind verification (data/verify_analysis_refresh.md section 5.1), reproduced to 10 decimal places, and fixed in scripts/analysis.py on 2026-09-17: series_stats now bases the level at 100 on the panel observation before the first return and publishes that date as level_base_date. No other statistic was affected -- mean, volatility, Sharpe, Sortino, skew, kurtosis, VaR/CVaR, the betas and the correlation all reproduce unchanged. The archived JSON still carries the pre-fix figures, so sections 6 and 7 restate them from the archived price panel and the archived Moderate12 weights; that rebuild reproduces the archived mean, volatility and pre-fix total return to better than 1e-9, which is what licenses the restatement. Effect on the headline numbers: the moonshot sleeve's 5y total return is **54.76%**, not the 52.85% of the first moonshot release, and its CAGR is **9.13%**, not 8.86%; the archived quality sleeve restates from 182.37% to **183.71%** (CAGR 23.09% to **23.19%**). Because both sides moved the same way, the DIRECTION of every sleeve comparison in this file is unchanged. Every downstream deliverable (Excel, PDF, deck, NotebookLM, coursework) must be rebuilt from the corrected data/analysis_results.json before it quotes a total return or a CAGR.

## 11. Limitations

- Five-year statistics on a sleeve whose whole point is a 5-10 year, mostly-zeros payoff distribution are close to meaningless as a forecast; they are reported because the combined-book covariance needs them, not because they predict anything.
- 27 of the 40 names are live on the sleeve index's first date; 13 start later, so the early index is a different (smaller) portfolio from the late one.
- The sleeve's realised 5y numbers are survivorship-clean for these 40 tickers but not for the strategy: names that de-listed or went to zero before 2026-09-16 were never candidates for selection.
- Thin liquidity: the sleeve's median name trades about USD 2.4m a day but the thinnest trades about USD 19k, so a GBP 1,000 ticket is fillable but exit at size is not assumed anywhere in this model.
- No dealing costs, spreads, FX charges, stamp duty or taxes anywhere in these numbers.

---

*Generated by `scripts/make_refresh_diff_moonshot.py` from `data/analysis_results.json`, `data/analysis_variants.json` and their archived counterparts. Educational analysis, not advice.*
