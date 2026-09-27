# Data refresh verification — 2026-09-16 close, moonshot sleeve

Blind data check of `data/raw`, `data/fx_daily.csv`, `data/prices_gbp_daily.csv`, `data/prices_local_daily.csv`,
`data/prices_gbp_monthly.csv`, `data/prices_gbp_weekly.csv`, `data/fundamentals.csv`, `data/fetch_log.json` against
`archive/2026-09-16-quality-sleeve/data/` (the pre-moonshot baseline used for core-reproduction diffs). `scripts/fetch_data.py`
was not read, per the brief for this pass. Educational analysis, not investment advice.

## Headline

Five of six checks pass cleanly. Check 2/3 (core reproduction / no new 100x glitches) turns up **one confirmed, severe
scale defect** in `SMEA.L` (iShares Core MSCI Europe UCITS ETF — a core-universe, optimiser-eligible instrument) that
breaks exact reproduction of the archived core panel and, taken at face value, would fabricate a +15,960% five-year
return for that line. The saving grace: `data/analysis_results.json`'s `asset_stats.SMEA.L` already looks correct
(CAGR 9.9%, vol 14.0%), which only happens because `analysis.py` carries its own undocumented compensating
`data_repairs.permanent_breaks` override (`{"date": "2024-04-25", "power_of_100": 1}`) that is not reflected back
into the canonical `data/` CSVs. Anything that reads the `data/` files directly and trusts them at face value —
an Excel `Prices_GBP` tab built by copying values, a chart, a future analysis pass — will not have that correction
and will silently ingest the fabricated jump. This is reported as a blocker for the data layer even though the one
current downstream consumer I could inspect (`analysis_results.json`) happens to be protected.

One further, much smaller finding: `SIE.DE`'s 2026-09-11 GBP TR level differs from the archive by 1.03e-6 relative
(not the requested 1e-9), traced to Yahoo re-serving very slightly different `Adj Close` floats for 1996-vintage bars
on separate pulls. Economically negligible; noted for completeness since the spec's tolerance is explicit.

---

## 1. Every column's last date is 2026-09-16 (or 2026-09-15 for early-closing exchanges)

**Pass — with a caveat worth recording.** Checked every column of `prices_gbp_daily.csv` (83 cols), `prices_local_daily.csv`
(81 cols) and `fx_daily.csv` (8 cols): all end exactly on **2026-09-16**, none lag. `data/fetch_log.json.as_of_completeness`
confirms `n_tickers_lagging_one_day: 0` — i.e. **no exchange is reported as early-closing / stuck on 2026-09-15** in this
refresh.

This is not "nothing needed patching" — it's that SPEC §7's Yahoo-hole handling was actively used and worked: the LSE
ETF/ETC daily-bar hole for 2026-09-16 (documented in the spec as affecting `SGLN.L, SMGB.L, VWRP.L, ISF.L, IBTM.L, DBMG.L, …`)
is fixed at source. `fetch_log.json.patched_bars_2026-09-16` lists **25 patched tickers**, each rebuilt from 60-minute
intraday bars with `close_source: "universe/core_universe.json last_price"` and `intraday_fetch_ok: true` — e.g.
`BRNT.L`, `COPA.L`, `CSP1.L`, `DBMG.L`, `EMIM.L`, `GHYS.L`, `GLTL.L`, `IBTM.L`, `ICOM.L`, `IEMB.L`, and 15 more. Spot
checks (`SGLN.L` etc.) show economically sane OHLC/volume for the patched bar. So: check (1) passes, and the reason
it passes cleanly (no exchange left on 2026-09-15) is that the required patch was applied, not that the hole didn't exist.

`data/prices_gbp_monthly.csv`'s last row is `2026-09-16` (a partial-month row, correctly labelled — see §4).

## 2. 12 tickers across regions: GBP TR level on 2026-09-11 vs archive (1e-9), and 11→16 Sept move = raw close × FX

Tickers checked, spanning UK/AIM, US, Europe, Australia, Canada and a commodity ETC/gilt proxy:
`RR.L, HSBA.L, MSFT, PLTR, ASML.AS, SIE.DE, SLX.AX, VUL.AX, ARA.TO, SGLN.L, IGLT.L, FTC.L`.

**2026-09-11 level vs `archive/2026-09-16-quality-sleeve/data/prices_gbp_daily.csv`:**

| Ticker | New (2026-09-11) | Archive (2026-09-11) | Relative diff |
|---|---|---|---|
| RR.L | 2511.5403302449 | 2511.5403302449 | 0.0 |
| HSBA.L | 14750.0552059256 | 14750.0552059256 | 0.0 |
| MSFT | 3996.6841627049 | 3996.6841627049 | 0.0 |
| PLTR | 1676.5591772823 | 1676.5591772823 | 0.0 |
| ASML.AS | 8373.9850351694 | 8373.9850351694 | 0.0 |
| **SIE.DE** | 1361.0810006863 | 1361.0824087706 | **-1.035e-06** |
| SLX.AX | 1576.4912227216 | 1576.4912227216 | 0.0 |
| VUL.AX | 780.3492000428 | 780.3492000428 | 0.0 |
| ARA.TO | 185.9956536294 | 185.9956536294 | 0.0 |
| SGLN.L | 213.3733486337 | 213.3733486337 | 0.0 |
| IGLT.L | 127.2047990009 | 127.2047990009 | 0.0 |
| FTC.L | 0.0765348330992 | 0.0765348330992 | 0.0 |

11/12 reproduce **exactly** (better than 1e-9 — bit-identical). `SIE.DE` misses the 1e-9 bar by three orders of
magnitude (1.03e-6 relative, i.e. about £0.0014 on a ~1361 level). Root-caused it to Yahoo itself: `data/raw/SIE.DE.csv`'s
1996-vintage `Adj Close` values differ in the 7th significant digit between this pull and the archived pull (e.g.
1996-11-08 `Adj Close` is `9.506244659423828` now vs `9.506243705749512` archived) even though `Close` is bit-identical —
a Yahoo floating-point re-serving quirk on very old bars, not a pipeline bug. It compounds through ~30 years of the
TR chain to the 1e-6 level seen by 2026. Economically meaningless (≈0.0001%) but technically fails the letter of the
1e-9 ask, so flagged rather than silently waved through. A full sweep of all 49 tickers common to both builds found
**no other ticker misses exact (0.0) reproduction at 2026-09-11 except SIE.DE and SMEA.L** (SMEA.L covered in the
next section — its 2026-09-11 value actually *does* match exactly; its defect is earlier in history).

**11→16 Sept move vs raw close × FX:** for all 12 tickers, `GBP_TR(16)/GBP_TR(11)` was checked against
`local_close(16)/local_close(11) × FX(11)/FX(16)` (no dividend events fell in the window for any of the 12).
All 12 matched to 8 decimal places, e.g.:

| Ticker | GBP TR ratio (16/11) | Local price ratio × FX ratio |
|---|---|---|
| MSFT | 0.99187866 | 0.99187866 |
| PLTR | 1.04529075 | 1.04529075 |
| ASML.AS | 0.94109125 | 0.94109125 |
| SIE.DE | 0.98087105 | 0.98087105 |
| SLX.AX | 0.94264280 | 0.94264280 |
| ARA.TO | 1.10174303 | 1.10174303 |
| RR.L / HSBA.L / SGLN.L / IGLT.L / FTC.L (GBP-native, FX ratio = 1) | matches local price ratio exactly | — |

**Pass**, with the SIE.DE precision note above.

## 3. No new 100x glitches — scan of every column for day-to-day |return| > 60%

Scanned `prices_gbp_daily.csv`, `prices_local_daily.csv` and `fx_daily.csv` in full (all columns, full 2016–2026
history). `fx_daily.csv`: zero hits. The two price panels: **45 hits each**, all but one attributable to genuine
micro-/nano-cap volatility in the new moonshot names, confirmed against raw volume:

- `GSIT` +213% (2023-05-12, volume 104.6m vs a normal ~60–100k) — GSI Technology's real May-2023 AI-chip short-squeeze rally.
- `AISP` +199% (2024-03-05, volume 217.6m) — Airship AI's real 2024 run.
- `ALCLS.PA` +191% (2023-11-01, volume 6.55m vs ~90–100k) — Cellectis's real Nov-2023 news-driven rally.
- `QSI` +177% (2024-12-27), +116% (2021-02-18), etc. — Quantum-Si, large real volume spikes each time.
- `HYT.AX`, `MSCL.TO`, `WBT.AX`, `AXE.AX`, `LTBR`, `IPWR`, `LAES`, `IDN`, `GELN.L`, `EDIT`, `PRQR`, `ALMDT.PA`, `ALMU`,
  `2498.HK`, `BIOA`, `GUTS` — smaller (60–130%) one-day moves, all in thin/illiquid moonshot names with matching
  volume evidence (including some genuinely zero-volume bounce days on `HYT.AX`, consistent with a £1,000-ticket-sized
  microcap, not a data artefact). None of these carry the >>100x signature of a scale error.
- **`SMEA.L` +10,810% (108.1x) on 2024-04-25 — this one is a glitch, and it is new.**

### `SMEA.L`: confirmed new 100x scale break, not present in the archived build

`SMEA.L` (iShares Core MSCI Europe UCITS ETF, a **core-universe, optimiser-eligible instrument**, not a unicorn) carries
a documented mask in `fetch_log.json.scale_glitch_repairs` for 2023-11-27→2024-04-24 ("an unflagged ~1-for-100
consolidation... masked... matching the archived 2026-09-11 build"). The mask itself (NaN-ing the bad transition
bars) is fine and matches the archive. **The problem is the segment before the mask**: comparing `prices_gbp_daily.csv`
column-by-column against `archive/2026-09-16-quality-sleeve/data/prices_gbp_daily.csv` for all 49 tickers common to
both, `SMEA.L` is the only one that fails to reproduce, and it fails everywhere before 2023-11-27 (max relative
diff 0.99 — i.e. exactly 100x — first appearing at 2016-09-19, the second trading day of its history):

| Date | New build | Archived build | Ratio |
|---|---|---|---|
| 2023-11-20 | 2.415595 | 241.559479 | 100.00x |
| 2023-11-24 | 2.414590 | 241.459006 | 100.00x |
| 2024-04-25 (first bar after mask) | 263.444534 | 263.444534 | **identical** |
| 2024-04-26 | 266.479100 | 266.479100 | identical |

The raw source file is not the cause — `data/raw/SMEA.L.csv` is byte-identical to
`archive/2026-09-16-quality-sleeve/data/raw/SMEA.L.csv` around both boundaries (checked 2023-11-15→2023-11-30 and
2024-04-20→2024-04-30: every Close/Adj Close/Stock Splits value matches to the last digit). So this is not a
re-fetch giving different raw data; it is the GBP-TR-construction step in this refresh handling the same raw data
differently from the archived build. The archived build evidently rescaled the pre-2023-11-27 segment ×100 to sit
on the same basis as the post-mask segment (241.46 → 263.44 is a plausible +9.1% move over the gap, matching the raw
close ratio 6554.5/60.075/100 = 1.091 exactly). This refresh's pre-mask segment was left at raw scale, 100x too low,
so the *entire* history from `SMEA.L`'s 2009-09-25 start through 2023-11-24 is under-scaled by 100x relative to the
(correct) archived build and to the (correct) post-mask segment.

**Confirmed to propagate into every derived file**, at the same 100x/0.99 relative magnitude:
`prices_local_daily.csv` (max diff at 2016-09-23), `prices_gbp_monthly.csv` (2017-09-30), `prices_gbp_weekly.csv`
(2016-10-21).

**Impact if taken at face value:** the 5-year core-optimisation window (2021-09-16→2026-09-16) starts inside the
under-scaled segment and ends inside the correctly-scaled segment, so `TR(2026-09-16)/TR(2021-09-16)` for `SMEA.L`
computed straight off `prices_gbp_daily.csv` is `356.71 / 2.221 = 160.6x`, i.e. a fabricated **+15,960% five-year
return** (naive CAGR ≈176%/yr) and a naive annualised volatility of **4,833%** (vs a sane ~15.9% once the one
transition-day "return" is excluded) — entirely an artefact of the internal scale break, not real MSCI Europe
performance.

**This did not make it into the delivered analysis**, but only by luck of an undocumented patch: `data/analysis_results.json`
carries its own `data_repairs.permanent_breaks.SMEA.L: [{"date": "2024-04-25", "power_of_100": 1}]`, and
`asset_stats.SMEA.L` shows sane numbers (CAGR 9.94%, vol 14.03%, Sharpe 0.40, max drawdown -15.8%) — i.e.
`analysis.py` already knows about and independently corrects this exact break. That correction lives only in the
analysis layer's config, is not written back into `data/prices_gbp_daily.csv` / `prices_local_daily.csv` /
`prices_gbp_monthly.csv` / `prices_gbp_weekly.csv`, and is not mentioned in `fetch_log.json`'s per-ticker `issues`
list for `SMEA.L` (which flags the AS_OF patch and a genuine raw-data calendar gap, but not this scale break). Any
consumer of the canonical `data/` price files that doesn't independently know to reapply a ×100 correction before
2024-04-25 — a spreadsheet tab built by copying `prices_gbp_daily.csv` values (as the Excel spec's `Prices_GBP` tab
is meant to be), a chart, a future script, a person eyeballing the CSV — will get the fabricated numbers above.

**Recommendation:** fix the GBP-TR (and local/monthly/weekly) construction for `SMEA.L` so the pre-2023-11-27
segment is rescaled ×100 to match the post-mask segment, matching both the archived build and `analysis.py`'s own
`permanent_breaks` correction, then regenerate `prices_gbp_daily.csv`, `prices_local_daily.csv`,
`prices_gbp_monthly.csv` and `prices_gbp_weekly.csv`. Until that happens, treat every `SMEA.L` price before
2024-04-25 in the raw `data/` CSVs as wrong by a factor of 100.

## 4. Month-end file: last row labelled correctly, not a fabricated full month

**Pass.** `prices_gbp_monthly.csv`'s last five index rows are `2026-05-31, 2026-06-30, 2026-07-31, 2026-08-31,
2026-09-16`. The final row is honestly labelled with the actual as-of date (**2026-09-16**, a Wednesday, partial
month), not stretched to a fictitious `2026-09-30` month-end. `prices_gbp_daily.csv`'s own last date (2026-09-16)
matches, so the monthly file's tail is consistent with the daily panel.

## 5. Fundamentals priced at the 2026-09-16 close; 52-week high/low updated

**Pass, fully verified.** `data/fundamentals.csv` carries an explicit `price_asof_native` / `fundamentals_priced_as_of`
pair per ticker. Checked 8 stocks (more than the requested 6) across currencies/exchanges — `RR.L` (GBp), `MSFT`,
`PLTR`, `IPWR`, `QSI` (USD), `2498.HK` (HKD), `ASML.AS` (EUR), `SLDP` (USD) — against `data/raw/<ticker>.csv`'s
2026-09-16 `Close`:

| Ticker | raw close (2026-09-16) | fundamentals `price_asof_native` | match |
|---|---|---|---|
| RR.L | 1440.5999755859375 | 1440.5999755859375 | exact |
| MSFT | 490.2999877929687 | 490.2999877929687 | exact |
| PLTR | 174.33999633789062 | 174.33999633789062 | exact |
| IPWR | 3.890000104904175 | 3.890000104904175 | exact |
| QSI | 0.7300000190734863 | 0.7300000190734863 | exact |
| 2498.HK | 16.09000015258789 | 16.09000015258789 | exact |
| ASML.AS | 1396.199951171875 | 1396.199951171875 | exact |
| SLDP | 2.390000104904175 | 2.390000104904175 | exact |

All eight match bit-for-bit; all carry `fundamentals_priced_as_of: 2026-09-16`. Separately, `fetch_log.json` shows
the pipeline explicitly detecting and correcting the case where Yahoo's `.info` snapshot was priced off a later/live
session rather than the 2026-09-16 close (e.g. `2498.HK`'s `.info` was priced at 16.27 vs the as-of close of 16.09;
`marketCap`/`enterpriseValue`/PE/P-B/EV-EBITDA/`dividendYield` were repriced by the ratio 0.988937 to freeze them
at the 2026-09-16 close) — the right behaviour per SPEC §1/§7.

**52-week high/low** are computed from `data/raw`'s intraday **High/Low**, not from Close-only or from Yahoo's
`info` field (`fiftyTwoWeekLow`/`fiftyTwoWeekHigh` are known-unreliable per the brief). Recomputing independently
from `raw High/Low` over the trailing 365 calendar days for the same 6 of the 8 tickers matched `fundamentals.csv`'s
`52w_high_local` / `52w_low_local` **exactly** (a first attempt using Close-only, as a naive check, did *not* match —
confirming the file genuinely uses the full trading range, not just closes, which is the correct/harder-to-get-right
implementation):

| Ticker | computed 52w high (raw High) | file 52w_high_local | computed 52w low (raw Low) | file 52w_low_local |
|---|---|---|---|---|
| RR.L | 15.8600 | 15.8600 | 9.9000 | 9.9000 |
| MSFT | 553.7200 | 553.7200 | 349.2000 | 349.2000 |
| IPWR | 9.3000 | 9.3000 | 2.6150 | 2.6150 |
| QSI | 3.1000 | 3.1000 | 0.6900 | 0.6900 |
| 2498.HK | 46.5000 | 46.5000 | 15.6000 | 15.6000 |
| SLDP | 8.8600 | 8.8600 | 1.9800 | 1.9800 |

## 6. Columns match the NEW `universe/unicorn_final.json` exactly

**Pass.** `universe/unicorn_final.json` holds the 40 new moonshot names (`yahoo_ticker` field). Checked against
`prices_gbp_daily.csv`, `prices_local_daily.csv`, `prices_gbp_monthly.csv` (all 3 have all 40 tickers as columns,
zero missing) and `fundamentals.csv` (all 40 present as rows). Checked the reverse direction against
`universe/unicorn_final_quality_2026-09-16.json` (the old quality sleeve, 40 names): of its 40 tickers, **34 are
genuinely retired** (`BKS.L, NCH2.DE, ERII, 1833.HK, NEO.TO, GNS.L, PRL.TO, NET.L, ALFEN.AS, WVE, AIP, CVO.TO, GPCR,
AVIO.MI, CRNC, BSL.DE, AMSC, NXL.AX, ASPN, BEAM, IQE.L, INOD, NTLA, OVH.PA, 0863.HK, EXOD, NVTS, ONT.L, DRO.AX, AMPX,
SGL.DE, EVT.DE, SIFY, A4N.AX`) and **none of these 34 appear anywhere** in `data/raw/`, `prices_gbp_daily.csv`,
`prices_local_daily.csv` or `fundamentals.csv` — confirmed clean, no stale quality-sleeve columns left behind.
The other 6 old-sleeve tickers (`ARA.TO, BIOA, FTC.L, IMSR, SLX.AX, VUL.AX`) legitimately survive into the new
40 (present in both JSON files) and are correctly still there — not stale, intentional overlap.

---

## Summary table

| # | Check | Result |
|---|---|---|
| 1 | Every column's last date = 2026-09-16 | **Pass.** 0 tickers lagging (LSE ETF hole patched via SPEC §7 intraday rebuild, 25 tickers patched). |
| 2 | 12-ticker archive reproduction (2026-09-11) + 11→16 move = raw × FX | **Pass, 1 minor exception.** 11/12 exact; `SIE.DE` off by 1.03e-6 relative (Yahoo float-serving noise on 1996 bars, immaterial). Move-matches-FX check: 12/12 exact. |
| 3 | No new 100x glitches | **Fail — 1 confirmed blocker.** `SMEA.L`'s entire pre-2023-11-27 history is scaled 100x too low across `prices_gbp_daily.csv`, `prices_local_daily.csv`, `prices_gbp_monthly.csv`, `prices_gbp_weekly.csv`, vs. the archived build and vs. `analysis.py`'s own compensating override. Fabricates a +15,960% 5y return / 4,833% vol for a core optimiser instrument if the data files are trusted as-is. All other >60% one-day moves are genuine moonshot-name volatility, volume-confirmed. |
| 4 | Month-end file labelling | **Pass.** Last row honestly labelled 2026-09-16, not stretched to a fake 2026-09-30. |
| 5 | Fundamentals priced at 2026-09-16 close; 52w H/L | **Pass.** 8/8 stocks match raw close exactly; 52w H/L independently recomputed from raw High/Low matches file exactly for all 6 checked. |
| 6 | Columns = new 40-name universe, no stale quality-sleeve tickers | **Pass.** All 40 present everywhere; all 34 retired-only tickers absent everywhere; 6 legitimate overlaps correctly retained. |

## Bottom line for downstream builders

Fix `SMEA.L`'s pre-2024-04-25 GBP/local/monthly/weekly TR scale (×100) before regenerating anything from these
files directly. Everything else in `data/` for this refresh is in good order: the as-of close handling, the FX/GBP
conversion arithmetic, the fundamentals-pricing freeze, the 52-week range computation, and the universe swap from
the quality sleeve to the 40 new moonshot names are all correct and independently verified above.
