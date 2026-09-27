# Thesis portfolio in NautilusTrader: run report

The GBP 200,000 two-sleeve book from `Portfolio_Report.pdf` (14 core lines, 80%; 40 moonshot lines, 20%; 54 instruments in `data/thesis/thesis_holdings.csv`) was traded through the pipeline's NautilusTrader engine under several weightings and three windows.
All three runs exited 0. An independent recomputation from the raw equity curves matched every headline metric to 5e-9 (verdicts: thesis5y minor, broad1y clean, all54 clean).
Every number below comes from `results/thesis/<preset>/thesis_summary.json` unless it is marked as a verifier figure or my own calculation.

## 1. What was run

**Own weights (`own_weights`).** The thesis's own `weight_total` per line, held as fixed targets. Names that cannot be priced over the whole window are dropped and their weight is spread pro rata over the survivors. In the 5-year window this makes the book core-heavier than the thesis (87.64% / 12.36%). A variant, `own_weights_8020`, renormalises within each sleeve instead, so core stays at 80% and moonshots at 20%.

**Equal weight (`equal_weight`).** 1/N over the same names, rebalanced on the same schedule. This is also the engine's own equal-weight benchmark: every scheme's run re-ran it, and its final equity was identical across all runs. A second benchmark, pandas buy-and-hold equal weight, buys 1/N once and never trades.

**Optimised (`hrp_optimised`).** skfolio's Hierarchical Risk Parity, refitted inside the event loop every 21 bars on the trailing lookback window only (no look-ahead). HRP is the pipeline's own choice because the Sizing study (README "Sizing: skfolio") found Max Sharpe concentrating into a few names on a noisy covariance and losing its walk-forward lead once 2022 was scored, while HRP held every name. **Max Sharpe** is shown only as the allocation stage's alternative: it is fitted in-sample on the whole window and never traded.

**Engine mechanics and assumptions**

- Rebalance every 21 trading days after the warm-up (lookback) window.
- Whole units only. The engine trades a 100,000,000 book so rounding stays small, then reports equity scaled by 0.002 to the GBP 200,000 book.
- Market-on-close fills at the signal bar's own close.
- No commissions, stamp duty, FX costs, spread or slippage; unlimited liquidity.
- 99% of equity invested at each rebalance (the thesis holds 0.376% cash).
- Prices are the thesis build's GBP total-return index (dividends reinvested, FX applied). Each column is rescaled so its window minimum is 100; returns are unchanged.

**Windows.** Many holdings listed recently, so no single window holds all 54 names for long. Names listed after a window's first bar are excluded.

| Preset | Price window | Warm-up | First fill | Traded | Names | Excluded (thesis weight) |
|---|---|---|---|---|---|---|
| thesis5y (primary) | 2020-12-10 to 2026-09-16 | 193 bars | 2021-09-16 | 4.999 yrs | 35 | 19 (11.0%) |
| broad1y | 2024-09-26 to 2026-09-16 | 252 bars | 2025-09-24 | 0.977 yrs | 50 | 4 (3.5%) |
| all54 | 2026-06-12 to 2026-09-16 | 21 bars | 2026-07-10 | 0.186 yrs (48 bars) | 54 | 0 |

- **thesis5y** starts on SMGB.L's first level (the largest line). The 193-bar warm-up puts the first fill on 2021-09-16, the thesis's own base date, so it covers the thesis's 5-year window. Excluded: SPCX (core, 2.0%) and 18 moonshots at 0.5% each: ONWD.BR, ARA.TO, NYXH, ALMU, GELN.L, CRBU, GUTS, PRME, CU6.AX, LAES, IMSR, SLDP, 2498.HK, GFUZ, LIS.AX, BIOA, AISP, BTQ.
- **broad1y** holds every name with a full 252-bar year of history (BIOA, listed 2024-09-26, sets the start). Excluded: SPCX, IMSR, GFUZ, BTQ.
- **all54** is the only window in which all 54 names have prices (SPCX lists 2026-06-12). It is a plumbing and weight check, not performance evidence. `own_weights_8020` is not run because nothing is excluded, so it equals `own_weights`.

## 2. Headline results

Sharpe at rf = 0 is mean/std x sqrt(252) of daily returns. The rf = 3.75% column is the runner's (CAGR - 3.75%) / vol. See section 4 for why that is not the thesis's own Sharpe convention. Final equity is on the GBP 200,000 book. Turnover is one-way per year.

### thesis5y (2021-09-16 to 2026-09-16)

| Scheme | CAGR | Ann. vol | Sharpe rf=0 | Sharpe rf=3.75% | Max DD | Final £ | Turnover | Fills |
|---|---|---|---|---|---|---|---|---|
| Own weights | 23.40% | 12.39% | 1.76 | 1.59 | 15.11% | 572,254 | 43.8% | 2,132 |
| Own weights 80/20 | 22.10% | 13.09% | 1.59 | 1.40 | 16.69% | 542,700 | 49.4% | 2,130 |
| Equal weight (engine benchmark) | 15.13% | 20.29% | 0.80 | 0.56 | 29.29% | 404,584 | 80.4% | 2,135 |
| HRP | 3.75% | 13.80% | 0.35 | 0.00 | 28.20% | 240,452 | 115.5% | 2,134 |
| Equal weight, buy-and-hold | 18.14% | 21.51% | 0.88 | 0.67 | 24.54% | 460,174 | none | none |

- **Own weights won clearly.** It ended at £572,254, £167,670 above engine equal weight and £331,803 above HRP, with the lowest volatility and half equal weight's drawdown (15.11%, 2025-02-19 to 2025-04-07, against 29.29%, 2021-11-08 to 2022-06-16).
- **HRP's result is dominated by one bad print.** At the first rebalance HRP put 45.2% of the book in HYT.AX (a sub-cent ASX microcap, thesis weight 0.5%). It held 41.6% to 53.9% there until 2022-06-20. On 2022-07-05 HYT.AX falls 69.75% in the panel and HRP loses 27.42% in one day (verifier figure; the data plan lists this move as unverified). HRP loaded onto HYT.AX because its price barely moved: 7.2% annualised volatility before the drop (verifier), implausible for such a stock and consistent with a stale local price moved only by FX. Its zero-return share is only 1.2%, so the stale-print flag (FTC.L, BGO.L) misses it. A crude adjustment that removes only that day's loss, ignoring knock-on effects, would put HRP near £331,271, about 10.6% CAGR (my calculation). That is still well behind own weights.
- **After July 2022 HRP is a low-volatility bond-and-gold book.** Core averaged 90.2% from 2022-07-19, with IBTM.L (US Treasury 7-10yr) at 34.95% on average. That missed the equity rally. HRP also traded most (115.5% turnover).
- **Own vs 80/20.** Holding the thesis's 20% moonshot share instead of 12.36% cost 1.30 points of CAGR, added 0.69 points of volatility and deepened the drawdown by 1.58 points. The 22 surviving moonshots detracted over this window.
- **Rebalancing hurt equal weight.** Monthly 1/N returned 15.13% a year against 18.14% for buy-and-hold 1/N. Rebalancing kept topping up losing moonshots and trimming winners.

### broad1y (2025-09-24 to 2026-09-16, about one year)

| Scheme | CAGR | Ann. vol | Sharpe rf=0 | Sharpe rf=3.75% | Max DD | Final £ | Turnover | Fills |
|---|---|---|---|---|---|---|---|---|
| Own weights | 26.62% | 14.08% | 1.74 | 1.62 | 7.47% | 251,903 | 88.0% | 600 |
| Own weights 80/20 | 26.18% | 14.19% | 1.71 | 1.58 | 7.63% | 251,045 | 88.6% | 600 |
| Equal weight (engine benchmark) | -1.73% | 24.05% | 0.05 | -0.23 | 21.34% | 196,616 | 119.8% | 599 |
| HRP | 10.00% | 5.89% | 1.64 | 1.06 | 4.71% | 219,529 | 167.3% | 599 |
| Equal weight, buy-and-hold | -9.52% | 25.20% | -0.27 | -0.53 | 24.51% | 181,376 | none | none |

- Own weights won again: +25.95% total return against -1.69% for equal weight. Equal weight is 74% moonshots by name count and fell 21.34% from 2026-06-01 to the last bar.
- HRP had the lowest volatility (5.89%) and drawdown (4.71%). Its rf=0 Sharpe (1.64) was close to own weights (1.74), but it earned less than half the return. It averaged 48.57% in IBTM.L and 89.9% in core.
- Own and 80/20 differ by only 0.44 points of CAGR, because only 3.5% of weight is excluded (split 80.83% / 19.17%).
- One year of data. None of these differences is statistically meaningful.

### all54 (2026-07-10 to 2026-09-16, 48 bars)

| Scheme | CAGR | Ann. vol | Sharpe rf=0 | Sharpe rf=3.75% | Max DD | Final £ | Turnover | Fills |
|---|---|---|---|---|---|---|---|---|
| Own weights | -2.63% | 12.82% | -0.15 | -0.50 | 3.81% | 199,010 | 297.5% | 162 |
| Equal weight (engine benchmark) | -52.12% | 19.65% | -3.64 | -2.84 | 12.81% | 174,371 | 337.8% | 162 |
| HRP | -5.30% | 4.77% | -1.12 | -1.90 | 1.96% | 197,981 | 507.3% | 162 |
| Equal weight, buy-and-hold | -51.81% | 19.48% | -3.64 | -2.85 | 12.71% | 174,582 | none | none |

- The plumbing works. All 54 names traded at all 3 rebalances (162 fills per scheme, 0 denied, 0 rejected), and every name was still held at the end.
- Own weights reproduce the thesis exactly: 80% core / 20% moonshot. Achieved at the first rebalance: core 79.20%, moonshot 19.80%, 99.00% invested (verifier). The largest target-vs-achieved gap is 0.00025% (WBT.AX).
- Annualised figures over 0.19 years are not meaningful. In total returns: own -0.50%, HRP -1.01%, equal -12.81%.
- HRP here is fitted on 20 returns of 54 names: noise by construction. The allocation-stage HRP refused to fit (needs at least 108 rows, had 67).

## 3. Weights (thesis5y)

The 13 core lines, then the two moonshots where HRP differs most. The other 20 moonshots all have the same thesis weight (0.50%). HRP first is the 2021-09-16 target; HRP mean is the average over 61 rebalances. Max Sharpe is the in-sample allocation-stage fit and was never traded.

| Ticker | Thesis | Renormalised | 80/20 | Equal | HRP first | HRP mean | Max Sharpe |
|---|---|---|---|---|---|---|---|
| SMGB.L | 13.28% | 14.93% | 13.62% | 2.86% | 1.12% | 1.10% | 0.03% |
| SGLN.L | 11.86% | 13.33% | 12.17% | 2.86% | 8.44% | 12.41% | 22.14% |
| ISF.L | 10.83% | 12.17% | 11.11% | 2.86% | 3.15% | 7.12% | 0.00% |
| IBTM.L | 8.00% | 8.99% | 8.21% | 2.86% | 22.29% | 34.95% | 13.02% |
| DBMG.L | 7.57% | 8.51% | 7.77% | 2.86% | 2.12% | 9.51% | 0.21% |
| IITU.L | 4.32% | 4.85% | 4.43% | 2.86% | 2.34% | 2.34% | 3.88% |
| BRNT.L | 4.14% | 4.65% | 4.24% | 2.86% | 0.75% | 1.20% | 10.82% |
| SHEL.L | 4.00% | 4.49% | 4.10% | 2.86% | 0.68% | 2.46% | 0.00% |
| HSBA.L | 4.00% | 4.49% | 4.10% | 2.86% | 0.88% | 1.88% | 14.15% |
| RR.L | 4.00% | 4.49% | 4.10% | 2.86% | 0.27% | 0.77% | 6.17% |
| PLTR | 4.00% | 4.49% | 4.10% | 2.86% | 0.15% | 0.31% | 2.72% |
| BRK-B | 1.14% | 1.28% | 1.17% | 2.86% | 2.52% | 5.05% | 10.49% |
| AZN.L | 0.86% | 0.97% | 0.88% | 2.86% | 3.92% | 3.79% | 3.59% |
| HYT.AX | 0.50% | 0.56% | 0.91% | 2.86% | 45.16% | 8.04% | 0.00% |
| BGO.L | 0.50% | 0.56% | 0.91% | 2.86% | 0.78% | 1.13% | 0.00% |
| **Core total** | 78.0% | 87.64% | 80.00% | 37.14% | 48.62% | 82.88% | 87.23% |
| **Moonshot total** | 11.0% | 12.36% | 20.00% | 62.86% | 51.38% | 17.12% | 12.77% |

Source: `results/thesis/thesis5y/allocation/thesis_allocation_weights.csv` and `hrp_optimised/execution_weights_hrp.csv`. The thesis column is the raw book weight, so it sums to 89% over the 35 included names.

- **Largest HRP overweights (mean vs renormalised):** IBTM.L +25.96 points, HYT.AX +7.47, BRK-B +3.77, AZN.L +2.82, DBMG.L +1.00. HRP favours whatever looks least volatile over its lookback: a Treasury ETF, gold, a managed-futures fund, and a stale-priced microcap.
- **Largest HRP underweights:** SMGB.L -13.82 points (the thesis's largest line, a semiconductor ETF), ISF.L -5.05, PLTR -4.18, RR.L -3.73, BRNT.L -3.45. The high-volatility growth names that drove the thesis's return are the ones HRP cuts.
- **Implied sleeve split.** HRP's mean split is 82.9% core / 17.1% moonshot. That average hides two regimes: 45.8% core before July 2022 (because of HYT.AX), then 90.2% core from 2022-07-19. Outside HYT.AX, HRP keeps moonshots near 9 to 10%.
- **Max Sharpe** is fitted in-sample and zeroes 15 of 35 names. It concentrates in SGLN.L, HSBA.L, IBTM.L, BRNT.L and BRK-B. Its in-sample Sharpe of 2.55 is hindsight, not a forecast.

## 4. Comparison with the thesis's own figures

Thesis figures are from its `analysis_results.json`, realised daily over 2021-09-16 to 2026-09-16 (data_plan.md section 5). The engine rows cover the same window: 1,261 daily returns, the same count as the thesis.

| Series | CAGR | Vol | Sharpe, thesis convention | Max DD |
|---|---|---|---|---|
| Engine own weights (87.6/12.4) | 23.40% | 12.39% | 1.46 | 15.11% |
| Engine own weights 80/20 | 22.10% | 13.09% | 1.30 | 16.69% |
| Thesis core (Moderate12) | 26.07% | 12.06% | 1.67 | 13.38% |
| Thesis combined 80/20 book | 23.02% | 13.03% | 1.37 | 16.85% |
| VWRP.L (FTSE All-World) | 11.37% | 13.02% | 0.60 | 17.64% |

- **Sharpe convention.** The thesis's Sharpe fits (arithmetic mean daily return x 252 - 3.75%) / vol. That formula gives about 1.67 for its core row and 0.60 for VWRP.L (my check). The runner's "rf = 3.75%" column uses (CAGR - 3.75%) / vol instead, which reads higher (1.59 for own weights). The table above uses the thesis's convention for the engine rows: 1.4553 own weights (verifier figure), 1.3041 for 80/20 (my calculation). The engine's rf = 0 Sharpe (1.76) is higher still and should not be set against the thesis's figures.
- **What the numbers show.** The 80/20 engine run is close to the thesis's combined book: CAGR 0.92 points lower, vol 0.06 higher, drawdown 0.16 smaller, Sharpe 0.07 lower. The own-weights run has about the same CAGR (+0.38 points) with lower vol. Both engine runs trail the thesis's core-only figures, which is expected, because they carry moonshots. Both beat VWRP.L by about 11 to 12 points a year with a similar or smaller drawdown.
- **Three structural reasons they differ.** (1) The engine rebalances every 21 trading days; the thesis's realised-daily figures hold weights constant daily. (2) 19 names (11% of weight: SPCX and 18 moonshots) are excluded here, so the moonshot sleeve is the 22 older listings, not 40. (3) The thesis's moonshot statistics are equal-weight over all 40 names, daily-rebalanced. They are not the adopted "let winners run" rule, which no one has modelled.
- The run does not reproduce the thesis's monthly-backtest drawdowns (core -3.81%, combined -7.40%). Those are month-end marks; daily marks show 13 to 17%.

## 5. Data notes

- **Panel check.** `prices_gbp_daily.csv` (2,526 x 84) sha256 `29d68ea2690130b7be2ec3863961aff545a0d8cb27e92e31e59e1aa5976f2a52` matches `_price_panel_manifest.json` (as of 2026-09-16). The verifiers recomputed it independently.
- **Repairs** (applied in the loader; the raw file is unchanged):

| Ticker | Date | Levels before the date divided by | Return that day | Status |
|---|---|---|---|---|
| MSCL.TO | 2026-02-02 | 12 (1:12 consolidation) | -91.40% to +3.23% | plausible |
| MSCL.TO | 2021-08-19 | 21.29439554 | -95.30% to 0.00% | unverified |

  The 2021 break falls in thesis5y's warm-up, so it only affects HRP's first covariance window. Both dates precede the all54 window.
- **Forward fills.** DBMG.L on 2025-04-22 and 2025-04-23 (2 cells) in thesis5y and broad1y; none in all54. Gaps of at most 3 bars; nothing back-filled.
- **Rescaling.** Each column x (100 / its window minimum), rounded to 6 decimals. Daily returns move by at most 2e-8.
- **Stale-print flags** (share of unchanged days): thesis5y FTC.L 34%, BGO.L 29%; broad1y GELN.L 54%, BGO.L 42%; all54 GELN.L 67%, BGO.L 54%. **Not flagged, but should be:** HYT.AX in 2021-22 (see section 2).
- **Other unverified large moves** (data plan): HYT.AX -69.7% (2022-07-05), -72.7% (2022-12-02), -57.1% (2026-08-04); 2498.HK -68.6% (2024-07-05). GUTS -68% (2026-01-29) is genuine.
- **DBMG.L** before April 2025 is its proxy (DBMF): 3.6 of its 5 years in thesis5y.
- **As-of patch.** The 2026-09-16 closes for 7 core holdings come from a file not in the repo. This affects the last day only.
- **Rounding artefacts** (verifier, not defects). HRP weight CSV rows sum to 1 within 5e-6 because of 6-decimal storage. The GBP columns of `thesis_equity.csv` are rounded to the penny.
- **Thesis caveats that carry over.** SPCX's 2.0% of the book (2.5% of core) is a policy weight, not an optimiser output, with only 67 bars of history; it is held only in all54. GUTS received a Nasdaq delisting determination on 2026-09-10 (stayed pending appeal), which affects the forward path, not this history. Thin names (HYT.AX, LIS.AX, GELN.L, EMV.AX) and phone-dealt names (SEYE.ST, MOLN.SW, GBP 49 each way) carry costs and spreads that the engine ignores. The thesis estimates a day-one build cost of GBP 907.08 (0.45%), with spread not modelled.

## 6. Caveats: what the numbers can and cannot support

- **Look-ahead.** The thesis picked its names and weights in September 2026 with hindsight over this whole window. The own-weights backtests describe the chosen book; they are not evidence that the choice would have worked in 2021. HRP's weights use no future data, but every scheme shares the hindsight in which names were picked.
- **Survivorship.** Only names that exist and are listed today were selected, and thesis5y holds only the 22 moonshots listed before 2020-12-10. The thesis says this bias cannot be quantified.
- **Optimistic fills.** Every trade fills at the same close that sized it, at zero cost and with unlimited liquidity. Real returns will be lower, most of all for turnover-heavy schemes (HRP 115.5% a year) and the smallest moonshots.
- **Short windows.** broad1y (0.98 years) and all54 (48 bars) support no statistical claim. all54 is a plumbing check.
- **HRP is sensitive to bad data.** Its thesis5y result rests largely on one unverified print. Read "HRP 3.75% CAGR" as "HRP on this panel", not as a verdict on HRP. Without HYT.AX it returns 11.36% (section 7).
- **In-sample allocation stats** (`allocation/`) are fitted on the returns they are scored on. For example, HRP's in-sample Sharpe is 1.46 against 0.35 out of sample.
- Per-scheme engine files label GBP amounts as USD/$, in engine units (x 0.002 for the book).

**What the numbers can support.** On this panel and window, the thesis's own weights delivered about 22 to 23% a year with 12 to 13% volatility, close to the thesis's own combined-book figures. Both naive 1/N and the pipeline's HRP did materially worse.

## 7. Sensitivity: HRP without the suspect prints

Two reruns of thesis5y leave out the names with unverified prints: HYT.AX alone (34 names), then HYT.AX and MSCL.TO (33 names). They use `--exclude`, which records each name as `excluded_by_user`. Everything else matches the main run: window, 193-bar warm-up, first fill 2021-09-16, schedule, cash and engine settings. Both exited 0 with no denied or rejected orders. An independent recomputation from each scheme's `execution_equity.csv` matched every CAGR, volatility and drawdown below to 5e-9, and every final £ to the penny.

| Run | Own CAGR | Own vol | Own max DD | Equal CAGR | Equal vol | Equal max DD | HRP CAGR | HRP vol | HRP max DD |
|---|---|---|---|---|---|---|---|---|---|
| Main run (35 names) | 23.40% | 12.39% | 15.11% | 15.13% | 20.29% | 29.29% | 3.75% | 13.80% | 28.20% |
| Ex HYT.AX (34) | 23.78% | 12.42% | 15.07% | 16.73% | 20.64% | 30.14% | 11.36% | 6.71% | 6.77% |
| Ex HYT.AX + MSCL.TO (33) | 23.80% | 12.44% | 15.08% | 16.68% | 20.89% | 28.95% | 11.29% | 6.69% | 6.05% |

Own is `own_weights`, Equal is `equal_weight` (engine benchmark), HRP is `hrp_optimised`. The HRP top 5 below is the mean target over 61 rebalances.

| Run | HRP final £ | HRP Sharpe rf=0 | HRP top 5 (mean weight) | HRP largest daily loss |
|---|---|---|---|---|
| Main run (35) | 240,452 | 0.35 | IBTM.L 34.95%, SGLN.L 12.41%, DBMG.L 9.51%, HYT.AX 8.04%, ISF.L 7.12% | -27.42% (2022-07-05) |
| Ex HYT.AX (34) | 342,455 | 1.64 | IBTM.L 37.57%, SGLN.L 13.79%, DBMG.L 10.09%, ISF.L 7.92%, BRK-B 5.08% | -2.10% (2025-04-04) |
| Ex HYT.AX + MSCL.TO (33) | 341,420 | 1.63 | IBTM.L 37.94%, SGLN.L 13.25%, DBMG.L 9.54%, ISF.L 8.54%, BRK-B 5.16% | -1.94% (2022-06-16) |

- **One name cost HRP about 7.6 points a year.** Without HYT.AX, HRP returns 11.36% a year (£342,455) instead of 3.75% (£240,452). Its volatility halves (13.80% to 6.71%), its drawdown falls from 28.20% to 6.77%, and its worst day is -2.10% instead of -27.42%. That closes 7.2 of the 19.6-point CAGR gap to own weights (37%). The crude one-day adjustment in section 2 (about 10.6%) was close.
- **What HRP holds instead.** HYT.AX's 45.16% first-rebalance weight moves mostly to core (39.3 of the 45.2 points). IBTM.L takes the largest share (39.92%, was 22.29%), then SGLN.L (15.22%, was 8.44%). The book averages 88.5% core before 2022-07-19 and 90.5% after, instead of 45.8% and 90.2%. No other stale series takes over: the top five have 0.6% to 2.7% unchanged days, and the two flagged names, FTC.L (34%) and BGO.L (29%), average only 1.01% and 1.32%. It is still concentrated: IBTM.L peaks at 59.80% (2026-08-14).
- **MSCL.TO changes little.** Dropping it as well moves HRP by -0.07 points of CAGR and own weights by +0.02. HRP held it at 0.35% on average. Its unverified 2021 repair falls in the warm-up and its 2026 repair is plausible, so neither was driving a result.
- **Own weights barely move.** HYT.AX is 0.56% of the own-weights book. Removing it adds 0.38 points of CAGR (23.40% to 23.78%); volatility and drawdown move by under 0.05 points. Equal weight gains more (15.13% to 16.73%), because 1/N held 2.86% in HYT.AX and topped it up at every rebalance. The CAGR ranking is unchanged: own weights, equal weight, HRP. On rf=0 Sharpe, HRP (1.64) is now close to own weights (1.78) and well ahead of equal weight (0.85).
- **What the optimiser is doing.** HRP minimises estimated risk. On this universe it rewards whatever looked least volatile over its lookback: a Treasury ETF, gold, a managed-futures proxy and, while the data allowed it, a thin microcap whose stale local price looked like a bond. That is a data-quality problem, not an argument for or against HRP. Cleaned, HRP is a coherent low-risk book (6.7% vol, 6% to 7% drawdown). It still trails own weights by about 12.4 points a year, a gap flattered by the thesis's hindsight in picking the names. Before relying on any optimiser here, screen thin names for implausibly low volatility or thin volume, not only for unchanged days (1.2% for HYT.AX).

## 8. Where everything is

```text
results/thesis/
  THESIS_RUN_REPORT.md             this report
  <preset>/                        thesis5y | broad1y | all54
    thesis_summary.json            config, panel check, repairs, universe, exclusions, per-scheme metrics, benchmarks
    thesis_comparison.md           the runner's per-preset report
    thesis_equity.csv              equity per scheme (GBP 200k book) and *_engine columns
    data_availability.csv          per holding: first/last level, gaps, largest move, included or why not
    figures/                       thesis_equity.png (log equity + drawdown), thesis_weights.png
    allocation/                    thesis_allocation_weights.csv, thesis_allocation_summary.json (in-sample)
    own_weights/ own_weights_8020/ equal_weight/ hrp_optimised/
      execution_summary.json, execution_equity.csv, execution_fills.csv, execution_positions.csv,
      execution_weights_<fixed|equal|hrp>.csv (+ _achieved.csv), dashboard_summary.json, figures/execution_equity.png
```

(all54 has no `own_weights_8020/`.) Two sensitivity folders (section 7) have the same layout, without `dashboard_summary.json` (run with `--no-dashboard`):

```text
results/thesis/
  thesis5y_ex_hytax/               thesis5y without HYT.AX (34 names)
  thesis5y_ex_hytax_mscl/          thesis5y without HYT.AX and MSCL.TO (33 names)
```

**Re-run** from the repository root (outputs go to `results/thesis/<preset>/` by default):

```bash
make thesis                                                    # thesis5y, 4 schemes, dashboard replays (~40 s)
.venv/bin/python -m quantstack.thesis.run --preset thesis5y    # same as make thesis
.venv/bin/python -m quantstack.thesis.run --preset broad1y     # ~22 s
.venv/bin/python -m quantstack.thesis.run --preset all54       # ~9 s
make thesis-quick                                              # 6-name smoke run -> results/quick/thesis/
.venv/bin/python -m quantstack.thesis.run --preset thesis5y --no-dashboard --exclude HYT.AX --results results/thesis/thesis5y_ex_hytax
.venv/bin/python -m quantstack.thesis.run --preset thesis5y --no-dashboard --exclude HYT.AX,MSCL.TO --results results/thesis/thesis5y_ex_hytax_mscl
```

Overrides: `--start`, `--end`, `--lookback`, `--rebalance-every`, `--schemes`, `--cash`, `--investment-cap`, `--max-ffill-gap`, `--strict-calendar`, `--no-rescale`, `--no-repairs`, `--no-dashboard`, `--prices`, `--holdings`, `--results`, `--exclude`.
`--exclude TICKER,TICKER` leaves named holdings out for a sensitivity run. They are recorded as `excluded_by_user`, and without `--results` the output goes to `<preset>_ex_<tickers>/`, never over the preset's own folder.
