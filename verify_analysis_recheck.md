# Re-check verification of author's fixes (round 2)

All checks performed independently against the regenerated files in `data/`, without reading `scripts/analysis.py`. All five distinct issues (one issue reported twice, for the daily and derived price files, is counted once) are **RESOLVED**, with numbers reproducing the author's claims to high precision.

## Issue 1 (major) — SPEC-named price files still had the 100x scale glitches — RESOLVED

- `data/prices_gbp_daily.csv` DBMG.L 2025-04-22/23 are now `NaN` (masked), 2025-04-24 = 108.602275 (clean, no scale jump). SMEA.L 2023-11-24 = 241.459006, 2023-11-27 = `NaN` (masked). Same pattern confirmed in `prices_gbp_monthly.csv`, `prices_gbp_weekly.csv`, `prices_local_daily.csv`.
- Recomputed DBMG.L 5y (2021-09-13 to 2026-09-11) stats directly from `prices_gbp_daily.csv`: mean_ann_arith = 0.1052, vol_ann = 0.1527, max |daily return| = 5.80% — consistent with the "clean" figures previously cited (0.1042 / 0.1528), not the corrupted ones (93.4 / 94.5).
- Max absolute return checked across DBMG.L and SMEA.L in monthly/weekly/local-daily files: all ≤ 16.7%, no >50% jumps remain anywhere.
- `data/prices_gbp_daily_raw.csv` exists, has an identical date index to the main file, and differs from it in exactly 2 of 84 columns (`DBMG.L`, `SMEA.L`) — confirms the raw/repaired split and that no other series was touched.
- `analysis_results.json.sources_assumptions_corrections` contains dated entries for both the DBMG.L and SMEA.L corrections, naming the affected files, as SPEC §3 tab 23 requires.

## Issue 2 (blocker) — MaxSortino was not the maximum-Sortino portfolio — RESOLVED

- `analysis_results.json.portfolios.*.realised_daily_5y.sortino`: MinVariance 0.716, **MaxSharpe 2.5562**, Moderate12 2.4753, **MaxSortino 2.5732**, EqualWeight 1.5530, NaiveReference 1.1422. MaxSortino is now strictly the highest of the six, beating MaxSharpe by +0.65%.
- Independently rebuilt the portfolio realised-return series from `data/weights.csv` and `data/prices_gbp_daily.csv` using the documented definitions (`definitions.sortino`, `definitions.downside_dev_ann`: MAR = rf = 3.75%, downside deviation over all observations, pairwise-day renormalisation for missing series) for all six portfolios. My reproductions: MinVariance 0.7168, MaxSharpe 2.5504, Moderate12 2.4679, **MaxSortino 2.5670**, EqualWeight 1.5519, NaiveReference 1.1439 — all within ~0.3% of the JSON's own figures (small residual from a 1-day index-boundary difference, 1258 vs 1259 obs), and the ordering (MaxSortino > MaxSharpe > Moderate12 > EqualWeight > NaiveReference > MinVariance) matches exactly.
- `data/weights.csv` MaxSortino weights land in the claimed basin (ISF.L 19.0%, SGLN.L 16.6%, IBTM.L 16.1%, DBMG.L 8.9%, SMGB.L 8.6%) and satisfy every constraint checked: budget sum = 0.975 exactly; equity_etf bucket = 0.300 (binding at its 0.30 lower bound); commodity bucket = 0.200 (binding at its 0.20 upper bound); stock bucket including SPCX = 0.250, i.e. 0.225 ex-SPCX (binding at the 0.225 cap); bond bucket 0.161 (inside [0.10, 0.40]); trend 0.089 (inside ≤0.15).
- `analysis_results.json.optimiser_verification.MaxSortino.cross_seed` confirms `dominated_by_another_portfolio: 0` and `best_rival_objective` (MaxSharpe, 2.5562) below MaxSortino's own 2.5732; the cross-seed audit block shows the same non-domination result for every other portfolio too.

## Issue 3 (major) — Portfolio betas silently excluded SPCX — RESOLVED

- `portfolios.Moderate12` now carries both conventions as separate fields: `beta_vwrp` = 0.78803 (incl. SPCX, was 0.7358), `beta_up` = 0.84639 (was 0.6571), `beta_down` = 0.76096 (was 0.7458), `beta_asymmetry` = +0.08543 (was ‑0.0887); `beta_vwrp_excl_spcx` = 0.73576, `beta_up_excl_spcx` = 0.65714, `beta_down_excl_spcx` = 0.74585, `beta_asymmetry_excl_spcx` = ‑0.08871 — reproducing both the previously-reported (excl.) and the newly-corrected (incl.) figures to 4-5 decimal places for exactly the values quoted by the author.
- Same pattern confirmed for MinVariance, MaxSharpe, and MaxSortino (all now carry `_excl_spcx` twins alongside the as-held figures).
- A `beta_convention` field is present on every portfolio, stating the as-held convention and SPCX's 64-bar betas explicitly.
- `limitations` text no longer claims "no long-only portfolio... achieves positive daily beta asymmetry" — it now states the negative-asymmetry result holds only on the SPCX-excluded convention, and gives both figures (+0.09 including SPCX vs ‑ under the excl. convention), noting the SPCX figure rests on 64 days of data.

## Issue 4 (major) — P/E ratios computed off the live fetch-date price, not the 2026-09-11 as-of price — RESOLVED

- `data/fundamentals_table.csv` now has both `trailing_pe`/`forward_pe` (as-of-date, rescaled) and `trailing_pe_yahoo_live`/`forward_pe_yahoo_live` (unscaled Yahoo originals).
- Reproduced exactly against the previously-cited expected values: RR.L trailing_pe = 40.4056 (expected 40.41), PLTR = 142.9316 (expected 142.93), ASML.AS = 58.1361 (expected 58.14), 1833.HK = 24.5000 (expected 24.50). `trailing_pe_yahoo_live` for the same rows (39.55 / 148.13 / 54.57 / 24.64) matches the original unfixed values, confirming the rescale is additive, not destructive.

## Issue 5 (major) — market_cap in wrong (native) currency; market_cap_usd_m missing for large names — RESOLVED

- `data/fundamentals_table.csv` `market_cap`/`market_cap_gbp` now equal shares_outstanding × price_gbp for every row checked, and `market_cap_usd_m` is populated. Reproduced to the unit for all 7 previously-checked names: RR.L 119,878,217,485 / USDm 161,947.2; PLTR 284,802,232,344 / 384,748.3; ASML.AS 488,043,671,612 / 659,313.5; ONT.L 1,533,705,605 / 2,071.9; NVTS 2,247,721,299 / 3,036.5; 1833.HK 1,229,715,057 / 1,661.3; SLX.AX 685,895,798 / 926.6 — all match the author's and the original verifier's figures exactly.
- The disclosed departure is also present and correctly flagged: `market_cap_share_class_gap` is populated (34–64%) for BRK-B, SPCX, CVO.TO, IMSR, EXOD, and `market_cap`/`market_cap_usd_m` are `NaN` for SGL.DE as stated, rather than guessed.

## Issue 6 (major) — Two disagreeing 52-week-high conventions in the same row — RESOLVED

- Checked `price_local / (1 + pct_below_52w_high) == high_52w_local` across **all 51 rows** of `data/fundamentals_table.csv`: max absolute discrepancy = 2.84e-14 (floating-point noise only). The two figures now agree everywhere, not just on the spot-checked rows.
- The old close-basis convention is preserved as `high_52w_close_local`/`pct_below_52w_high_close_basis` and reproduces the original verifier-implied values exactly: RR.L 15.704, PLTR 207.18, NVTS 31.79, 1833.HK 22.74, SLX.AX 10.49.

## Overall

All one blocker and five major issues from the prior round are resolved, with the author's reported numbers independently reproduced (either exactly, or — for the MaxSortino re-solve, which depends on a random-start global search I did not repeat in full — closely enough, and with internally consistent, constraint-satisfying, non-dominated results) from the regenerated files alone. No new problems were surfaced by these checks; the author's own disclosed departures (share-class market-cap gap flags, SGL.DE left blank, ASX previousClose staleness) were also spot-checked and found accurately described.
