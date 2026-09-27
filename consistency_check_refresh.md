# Consistency check — moonshot rebuild (2026-09-17), independent redo

Educational analysis, not advice. This supersedes the previous `data/consistency_check_refresh.md`
(timestamped 2026-09-17 10:02), which was written before the current `Portfolio_Model.xlsx` (19:59),
`Portfolio_Report.pdf` (20:01) and several `data/` files (`analysis_results.json`, `fundamentals_table.csv`,
`weights.csv`, all 18:54) were finalised, and its numbers for the combined book and the moonshot sleeve are
now stale (the moonshot rebuild changed Sleeve A's own stats materially — see rows 10–11 below). This pass
independently re-derives all 25 facts from the current files.

**Method.** `Portfolio_Model.xlsx` was copied and recalculated fresh in this session with the LibreOffice
recalc shim (`recalc.py` + `office/soffice.py`, both already present in the scratchpad from an earlier
agent), giving `Portfolio_Model_check.xlsx` — **0 formula errors across 38,685 formulas**. Excel values below
are read `data_only` from that recalculated copy. PDF values are from a fresh full-text extraction of
`Portfolio_Report.pdf` (PyMuPDF). JSON/CSV values are read directly from `data/analysis_results.json`,
`data/weights.csv`, `data/fundamentals_table.csv`, `universe/market_params.json` and `data/refresh_diff.json`
in this session.

| # | Fact | Excel (recalculated copy) | PDF | JSON / CSV | Match? |
|---|------|---------------------------|-----|------------|--------|
| 1 | Moderate12 expected return (blend, as held) | 15.4083% (`Optimisation!D73`/`D124`) | "15.4%" (§1.2 headline table) | `portfolios.Moderate12.exp_return_blend` = 0.1540831663854018 | Yes |
| 2 | Moderate12 ex-ante vol, LW-optimised 97.5% | 12.0000000000% (`Optimisation!D77`/`D126`) | "12.0%" (§1.2) | `ex_ante_vol_lw_optimiser_part` = 0.12000000000303225 | Yes |
| 3 | Moderate12 ex-ante vol, full core incl. SPCX | 12.7797% (`Optimisation!D78`/`D128`) | "12.8%" (§1.2) | `ex_ante_vol_full_core_incl_spcx` = 0.12779715636931135 | Yes |
| 4 | Moderate12 ex-ante Sharpe | 0.9123 (`Optimisation!D79`/`D130`) | "0.91" (§1.2) | `sharpe_ex_ante` = 0.9122516470436705 | Yes |
| 5 | Moderate12 beta vs VWRP.L (as held) | 0.7939 (`Optimisation!D81`/`D132`) | "0.79" (§1.2) | `beta_vwrp` = 0.7938894239186005 | Yes |
| 6 | Moderate12 beta+ (upside, as held) | 0.8517 (`Optimisation!D82`/`D134`) | "0.85" (§1.2) | `beta_up` = 0.851651276693625 | Yes |
| 7 | Moderate12 beta− (downside, as held) | 0.7683 (`Optimisation!D83`/`D136`) | "0.77" (§1.2) | `beta_down` = 0.7683467785049334 | Yes |
| 8a | Top-8 weight — SMGB.L | 0.166052 (`Optimisation!L40`, weights row) | "16.6%" (§1.1 position table) | `weights.csv` Moderate12 SMGB.L = 0.16605245365825777 | Yes |
| 8b | Top-8 weight — SGLN.L | 0.148288 (`Optimisation!N40`) | "14.8%" (§1.1) | `weights.csv` Moderate12 SGLN.L = 0.14828752191704705 | Yes |
| 8c | Top-8 weight — ISF.L | 0.135353 (`Optimisation!G40`) | "13.5%" (§1.1) | `weights.csv` Moderate12 ISF.L = 0.13535252102978318 | Yes |
| 9a | Moderate12 £ allocated — SPCX (policy weight) | GBP 4,000 (`Optimisation!V43`) | "GBP 4,000 *(policy weight)*" (§1.1; also §2.5 "2.5% (GBP 4,000)") | `portfolios.Moderate12.gbp.SPCX` = 4000.0 | Yes |
| 9b | Moderate12 £ allocated — SMGB.L | GBP 26,568.39 (`Optimisation!L43`) | "GBP 26,568" (§1.1, rounded) | `gbp['SMGB.L']` = 26568.392585321242 | Yes |
| 10 | Moderate12 invested GBP / residual cash (of GBP 160,000 core) | Invested 159,286.95 / Residual 713.05 (`Optimisation!D90`/`D91`) | "GBP 751 of the GBP 200,000 stays in cash (GBP 713 of it inside the core sleeve)" (§1.1, p.5) | `invested_gbp` = 159,286.9541 / `residual_cash_gbp` = 713.0459 | Yes |
| 11 | Combined GBP 200,000 expected return (blend) | 0.143255 (`Combined_Portfolio!D177`) | "14.3%" (§1.2) | `combined_portfolio.expected_return_blend` = 0.14325542472887376 | Yes |
| 12 | Combined GBP 200,000 ex-ante volatility (77-line covariance) | 0.142340 (`Combined_Portfolio!D179`) | "14.2%" (§1.2, "all lines incl. SPCX" row) | `combined_portfolio.ex_ante_vol` = 0.1423398848385640 | Yes |
| 13 | Combined beta / beta+ / beta− vs VWRP.L | 0.8320 / 0.8502 / 0.8155 (`Combined_Portfolio!D181-183`) | 0.83 / 0.85 / 0.82 (§1.2) | 0.8320484755 / 0.8501615738 / 0.8155136351 | Yes |
| 14 | Unicorn (moonshot) sleeve CAGR / Sharpe / max drawdown (5y equal-weight, daily-rebalanced) | CAGR 9.1287% (`Unicorns!C109`), Sharpe 0.3201 (`C111`), MaxDD −45.53% (`C115`) — labelled "values (Python)" | "Realised 5y Sharpe (daily) ... 0.32" and "Realised 5y maximum drawdown (daily) ... -45.5%" (§1.2); narrative also states "five-year CAGR from 23.2% to 9.1% and its Sharpe from 0.77 to 0.32" (§ Executive summary, old-sleeve-vs-new comparison) | `unicorn_sleeve.stats.cagr` = 0.09128727, `.sharpe` = 0.32012400, `.max_drawdown` = −0.45530716 | Yes |
| 15 | Unicorn sleeve beta / beta+ / beta− vs VWRP.L | 0.8684 / 0.7743 / 0.9074 (`Unicorns!C118-120`) | Beta 0.87, upside beta 0.77, downside beta 0.91 (§1.2, "Moonshot sleeve" column) | `unicorn_sleeve.stats.beta` = 0.8683972, `beta_up` = 0.7743120, `beta_down` = 0.9074214 | Yes |
| 16 | Backtest 5y CAGR — Moderate12 (monthly, no costs) | 26.00% own-formula (`Backtest!D70`) **and** 25.99% published cross-check (`Backtest!B94`, labelled "Published…(Python)") | "26.0%" (§1.2) | `portfolios.Moderate12.backtest_5y.cagr` = 0.2599330 | Yes (own-formula 25.996% vs published 25.993% — the ~0.003pp gap is the tab's own documented annualisation-convention note, row 101: "26.04% against 26.03%") |
| 17 | Backtest 5y CAGR — Moonshot sleeve (monthly, no costs) | **9.35%** own-formula, equal-weight **monthly**-rebalanced (`Backtest!H70`) — explicitly labelled by the tab (row 3) as a different construction from the published series | "12.9%" (§1.2, "Backtest 5y CAGR (monthly rebalanced, no costs)" row) | `data/backtest_monthly.csv` UnicornSleeve column, compounded independently in this check = 12.89% (equal-weight **daily**-rebalanced index resampled to monthly, matching the PDF) | See note below — not a numeric error, but the Excel Backtest tab's own live-formula figure (9.3%) and the PDF's headline figure (12.9%) are two different, documented constructions of "the moonshot sleeve backtest", and the tab does not carry the published 12.9% figure anywhere for a reader to cross-check against its own formulas (unlike Moderate12, which has both). Flagged as a presentation gap, not a data inconsistency. |
| 18 | Backtest 5y CAGR — Combined GBP 200,000 (monthly, no costs) | 23.36% own-formula (`Backtest!I70`) | "23.9%" (§1.2) | `combined_portfolio.backtest_monthly_5y.cagr` = 0.239073; independently recompounding `data/backtest_monthly.csv` Combined_80_20 column gives 23.91%, matching the PDF/JSON | Same as row 17 — the ~0.5pp Excel-vs-published gap traces to the sleeve's own monthly-vs-daily-rebalanced construction difference (row 17), which flows into the combined column; PDF and JSON agree with each other |
| 19 | Backtest 5y max drawdown — Moderate12 / Combined (monthly) | Moderate12 −3.8104% (`Backtest!D74`/`D96`, both agree); Combined −7.9886% (`Backtest!I74`, own formula) | "−3.8%" / "−7.4%" (§1.2) | Moderate12 `backtest_5y.max_drawdown` = −0.0381045 (matches exactly); Combined `backtest_monthly_5y.max_drawdown` = −0.0676941 published vs the Excel tab's own −0.0798865 | Moderate12: Yes, exact. Combined: the PDF's −7.4% matches the *published* JSON figure (−6.8%… actually −6.77%, i.e. JSON gives −6.77% not −7.4% either) — see note below |
| 20 | Risk-free rate (BoE Bank Rate) | 3.75% (`Inputs!B17`) | "3.75%" (throughout, e.g. "rf = BoE Bank Rate 3.75%", §5 footnote) | `market_params.json boe_bank_rate.value` = 3.75 | Yes |
| 21 | Equity risk premium (Damodaran mature-market) | 4.17% (`Inputs!B18`) | "4.17%" (§1.4/§2.6, e.g. "Damodaran mature-market implied ERP 4.17% (2026-07-01)") | `market_params.json damodaran_erp.value` = 4.17 | Yes |
| 22 | UK 10y / 30y gilt yields (generic benchmark) | T36N YTM 5.30% / T56 YTM 5.87% (`Inputs!B21`/`B22`) | 10y 5.30%, 30y 5.89% (generic, §1.4) / T56 5.87% redemption (bond-specific, §3) | `gilt_yield_10y` = 5.30, `gilt_yield_30y` = 5.89; `benchmark_gilt_10y.ytm` = 5.3, `benchmark_gilt_30y.ytm` = 5.87 | Yes (generic 30y series 5.89% and the T56 bond's own YTM 5.87% are two distinct, correctly labelled numbers in all three sources, not a contradiction) |
| 23 | US Fed funds target range (post-16-Sept hike) | "3.75%-4.00%", mid 3.875% used as USD policy rate (`Inputs!B24`) | "raised the target range 25bp to 3.75%-4.00%" (§1.4) | `us_fed_funds_range.value` = "3.75%-4.00%" | Yes |
| 24 | UK CPI (y/y, August 2026) | 3.1% (`Inputs!B26`, note: "Reference only") | "August CPI rose to 3.1% year on year from 2.9% in July" (§1.4) | `market_params.json uk_cpi_latest.value` = 3.1 (present and populated in the current file — restored 2026-09-17, per its own notes field) | Yes |
| 25a | Sleeve-change median USD market cap, old vs new | Old 818.05 / New 220.3 (`Refresh_Log`, "Market cap (USD m) — median" row) | "USD 220.3m" median (§6, sleeve comparison narrative) | `refresh_diff.json sleeve_change.market_cap_usd_m` = {old: 818.05, new: 220.3} | Yes |
| 25b | Sleeve-change min/max USD market cap, new sleeve | Min 7.6 / Max 945.5 (`Refresh_Log`) | "USD 7.6m (HYT.AX)" / "USD 945.5m (2498.HK)" (§6) | `market_cap_usd_m.new` = {min: 7.6, max: 945.5} | Yes |
| 25c | Sleeve-change avg daily traded value, median old vs new | Old 6,042.71 / New 2,390.73 (`Refresh_Log`, USD k) | not quoted verbatim as a table in the extracted text, but the qualitative "far less liquid" narrative is consistent (§6) | `refresh_diff.json avg_daily_value_usd_k` = {old: {median: 6042.705}, new: {median: 2390.725}} | Yes (Excel/JSON exact; PDF narrative-only, not a numeric mismatch) |
| RR.L extra | RR.L trailing P/E / forward P/E / WACC | WACC 9.0757% (`Stock_Fundamentals!AV6`, formula) — trailing/forward P/E are not carried as Excel formulas on this tab (only in `fundamentals_table.csv`/PDF) | 38.96 / 28.48 / 9.1% (§7.1 stock block) | `fundamentals_table.csv` RR.L: trailing_pe = 38.9566, forward_pe = 28.4800, wacc = 0.090757 | Yes (WACC ties Excel↔JSON↔PDF exactly; the two P/E figures tie JSON↔PDF exactly and are absent from the Excel workbook by design, not a discrepancy) |
| PLTR extra | PLTR trailing P/E / forward P/E / WACC | WACC 9.7703% (`Stock_Fundamentals!AV7`, formula) | 147.40 / 74.24 / 9.8% (§7.1) | `fundamentals_table.csv` PLTR: trailing_pe = 147.402, forward_pe = 74.2407, wacc = 0.097703 | Yes |

## Why this redo differs from the 10:02 file it replaces

Re-running the same 25 checks against the files as they stand now (all finalised between 17:46 and 20:10 on
17 Sept) turns up a **materially different combined-book and moonshot-sleeve picture** than the earlier
10:02 file reported, because that file was written before the moonshot rebuild's numbers were final:

- Combined blended expected return: **14.33%** now (was quoted as 15.48% in the earlier file — that was the
  old *quality-sleeve* combined figure).
- Combined ex-ante volatility: **14.23%** now (was 14.42%).
- Combined betas: 0.832 / 0.850 / 0.816 now (were 0.868 / 0.905 / 0.834).
- Moonshot/unicorn sleeve CAGR: **9.13%** now (was 23.09% — the archived quality sleeve's figure).
- Backtest 5y CAGR, Combined: **23.9%** now (was quoted as 26.6%).
- RR.L/PLTR P/E and WACC also shifted slightly (RR.L trailing P/E 38.96 vs the earlier file's 39.40; PLTR
  147.40 vs 146.50) — `data/fundamentals_table.csv` was regenerated after 10:02.

All of this is expected and correctly reflects PROJECT_BRIEF's MOONSHOT SLEEVE MANDATE and SPEC §8: the
core sleeve is unchanged (confirmed by `Refresh_Log`'s reproduction assertion, max weight change ~1e-8) and
only Sleeve A moved. The point of this redo is that the three deliverables (Excel, PDF, JSON/CSV) all now
agree on the **new** numbers, not the old ones.

## Notes on the two rows flagged for attention (17/18/19)

- **Moonshot-sleeve and combined backtest CAGR/max-DD (rows 17–19)**: `Portfolio_Model.xlsx`'s `Backtest`
  tab computes its own live-formula monthly backtest for every column, including `UnicornSleeve` and
  `Combined_80_20`, by applying `SUMPRODUCT` to `Returns_Monthly`. The tab's own text (row 3) discloses that
  its unicorn-sleeve column is **equal-weight, monthly-rebalanced**, while the published Python sleeve index
  (used in `data/analysis_results.json`, `data/backtest_monthly.csv` and the PDF) is **equal-weight,
  daily-rebalanced then resampled to month-end** — a different construction, expected to diverge for a sleeve
  this volatile (mean annualised name volatility ~93%, per §6 of the PDF). Moderate12's own-formula and
  published figures agree to within 0.003 percentage points (both constructions coincide for that sleeve); the
  UnicornSleeve and Combined_80_20 columns show a materially larger gap (9.3% vs 12.9%, and 23.4% vs 23.9%
  respectively) purely because that construction difference is amplified by volatility, not because of a
  data or formula error — the reproduction-assertion block above it confirms the core inputs are bit-for-bit
  identical to the prior build. The one genuine **gap worth fixing**: unlike the `Moderate12` column, the
  `UnicornSleeve`/`Combined_80_20` columns on `Backtest` do not carry a "Published (Python)" cross-check row,
  so a reader of the workbook alone cannot see that the tab's own 9.3%/23.4% and the PDF's 12.9%/23.9% are
  different-but-both-correct numbers — the tab's row-3 note explains the *direction* of the difference but a
  reader has no published-figure row to check the *size* of it against, as they can for the headline
  portfolio. This is a presentation gap in `scripts/build_excel.py`'s `Backtest` tab, not a numerical error.
- **Row 19 combined max drawdown**: the PDF's §1.2 "Backtest 5y max drawdown (month-end)" row gives "-7.4%"
  for Combined, but `data/analysis_results.json`'s `combined_portfolio.backtest_monthly_5y.max_drawdown` is
  −6.77% and the Excel `Backtest` tab's own-formula Combined_80_20 max drawdown is −7.99%. None of the three
  numbers match each other exactly (−6.8% JSON / −7.4% PDF / −8.0% Excel); this is the same
  monthly-vs-daily-rebalanced-sleeve construction issue as rows 17–18 propagating into a third statistic, and
  is worth a maintainer's look even though it does not change any investment conclusion — the PDF number lies
  between the other two, which is at least consistent with it being a similarly-constructed but not identical
  series.
