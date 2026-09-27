# Data Verification — Round 1 (Blind Verifier)

Scope: verified independently from `data/raw/*.csv`, `data/fx_daily.csv`, `data/prices_gbp_daily.csv`,
`data/prices_local_daily.csv`, `data/dividends.csv`, `data/fetch_log.json`, `data/fundamentals.csv`, the
universe JSON files, and public web sources. `scripts/fetch_data.py` was **not** read — all checks below
were done with independently written Python against the cached CSV/JSON outputs only.

Date of this review: 2026-09-14. Prices as at 2026-09-11 (Friday).

---

## 1. Rebuild GBP total-return index (RR.L, VWRP.L, SGLN.L, PLTR, IHYU.L, ASML.AS, DRO.AX, 1833.HK)

Method: loaded each raw CSV, built my own split-adjustment (reverse-cumulative product of `Stock Splits`
events), built `TR_t = TR_{t-1} * (adj_close_t + adj_div_t) / adj_close_{t-1}` in local currency, then
converted USD/EUR/AUD/HKD tickers to GBP by **dividing** the local TR index by the corresponding
`GBPxxx=X` rate from `data/fx_daily.csv` (GBp tickers left as pence — the /100 constant cancels in a
return calculation). Computed annualised 1y/3y/5y returns from the rebuilt series and compared with the
same-window annualised returns read directly off `data/prices_gbp_daily.csv`.

| Ticker | 1y (mine) | 1y (file) | 3y (mine) | 3y (file) | 5y (mine) | 5y (file) | Max abs diff |
|---|---|---|---|---|---|---|---|
| RR.L | 30.56% | 30.56% | 87.94% | 87.94% | 67.83% | 67.83% | 0.00pp |
| VWRP.L | 19.82% | 19.82% | 17.55% | 17.55% | 11.46% | 11.46% | 0.00pp |
| SGLN.L | 20.54% | 20.54% | 28.04% | 28.04% | 19.99% | 19.99% | 0.00pp |
| PLTR | 1.94% | 1.94% | 113.90% | 113.90% | 46.07% | 46.07% | 0.00pp |
| IHYU.L | 3.05% | 3.05% | 5.02% | 5.02% | 4.13% | 4.13% | 0.00pp |
| ASML.AS | 115.71% | 115.71% | 38.00% | 38.00% | 16.27% | 16.27% | 0.00pp |
| DRO.AX | -41.65% | -41.65% | 81.92% | 81.92% | 52.63% | 52.63% | 0.00pp |
| 1833.HK | -73.22% | -73.22% | -8.31% | -8.31% | -21.76% | -21.76% | 0.00pp |

**Result: PASS.** All 24 annualised figures across the 8 instruments and 3 windows match `prices_gbp_daily.csv`
to within 0.00pp — well inside the 0.3pp/year tolerance. The split-adjustment, dividend-unit handling, GBp
pence conversion, and FX conversion direction are all correctly and consistently implemented in the shipped
data for every one of these 8 names (spanning GBp, GBP, USD, EUR, AUD and HKD quote currencies).

---

## 2. FX direction check

`data/fx_daily.csv` columns are `GBPxxx=X` (convention: 1 GBP = X units of the quote currency). On 2026-09-11:
GBPUSD=1.35093, GBPEUR=1.16353, GBPCAD=1.86877, GBPAUD=1.88766, GBPHKD=10.59236.

Explicit check — converting a non-GBP raw close to GBP requires **dividing** by the rate (GBP = local / GBPxxx),
not multiplying:

| Ticker | Local close (raw, 2026-09-11) | local / FX (→ GBP) | local × FX (wrong direction) | Plausible? |
|---|---|---|---|---|
| PLTR (USD) | $167.23 | £123.79 | £225.92 | £123.79 is right — PLTR trades ~$167, cable ~1.35, so ~£124 is sane; £226 would imply PLTR is worth more in GBP than USD, which is wrong. |
| MSFT (USD) | $495.63 | £366.88 | £669.56 | £366.88 is right (MSFT ~$496 at ~1.35 cable ≈ £367). |
| ASML.AS (EUR) | €1478.40 | £1270.62 | £1720.16 | £1270.62 is right (EUR is weaker than GBP; dividing is correct). |
| DRO.AX (AUD) | A$1.660 | £0.879 | £3.13 | £0.879 is right. |
| 1833.HK (HKD) | HK$6.125 | £0.578 | £64.88 | £0.578 is right. |

**Result: PASS.** Division is the correct convention given the `GBPxxx=X` column semantics, and it is what
produces the economically sane GBP-equivalent price in every case tested. This is also confirmed indirectly
by Check 1: the pipeline's actual `prices_gbp_daily.csv` return calculations for PLTR/IHYU.L (USD),
ASML.AS (EUR), DRO.AX (AUD) and 1833.HK (HKD) matched my from-scratch rebuild (which used division) to
0.00pp across all three windows — if the pipeline used the wrong direction, my rebuild and the file would
have diverged sharply, especially for DRO.AX and 1833.HK where the underlying local moves are large
(-41.65%/-73.22% 1y).

---

## 3. Dividend units — median(dividend / close) for every `.L` ticker with dividends

| Ticker | n divs | median(div/close) | Flag? |
|---|---|---|---|
| AZN.L | 67 | 0.013311 | |
| BKS.L | 6 | 0.001847 | |
| FTC.L | 27 | 0.004478 | |
| GHYS.L | 28 | **NaN** (one ex-div date has a NaN raw Close — see §5) | see note below |
| GLTL.L | 28 | 0.011640 | |
| GNS.L | 40 | 0.007480 | |
| HSBA.L | 106 | 0.011971 | |
| IBTM.L | 25 | 0.011404 | |
| IEMB.L | 163 | 0.003853 | |
| IGLT.L | 28 | 0.009916 | |
| IHYG.L | 28 | 0.021704 | |
| IHYU.L | 29 | 0.028009 | |
| ISF.L | 54 | 0.008485 | |
| NET.L | 17 | 0.015789 | |
| RR.L | 55 | 0.012670 | |
| SHEL.L | 85 | 0.011943 | |
| ULVR.L | 103 | 0.009562 | |
| VMID.L | 47 | 0.007702 | |

**Result: PASS** (with one minor data hole). Every ticker's median dividend/close ratio falls inside the
plausible 0.0005–0.10 band — no pence/pounds unit errors detected. GHYS.L's raw `Dividends` column itself is
fine; the NaN is purely because one particular ex-dividend row (2026-01-15) has a missing `Close` in the raw
Yahoo download — see the calendar-gap finding in §5, which is the same underlying data hole.

---

## 4. External cross-checks

| Metric | Our data | External source | Source | Assessment |
|---|---|---|---|---|
| VWRP 1y total return (GBP) | 19.82% | ~18.91% ("past year, total return incl. dividends") | justETF/aggregator search result | Close (≈0.9pp gap); consistent with normal cross-provider timing/date-window noise. No red flag. |
| Gold (SGLN.L) 1y change (GBP) | +20.54% | Gold spot moved ~$3,650/oz (9 Sep 2025) → ~$4,284/oz (14 Sep 2026), i.e. ≈ +17–20% in USD; GBPUSD barely moved (1.3535→1.3509 over the year), so the GBP move should track the USD move closely | Search-aggregated spot-price figures (Kitco/TradingView-style reporting) | Consistent. One AI-search summary of a BullionByPost page separately claimed gold-in-GBP was "flat" over the year — that claim contradicts the actual spot-price levels found from other sources and is judged unreliable; our figure and the two independent spot-price data points line up. |
| RR.L 1y share-price change | +29.47% price-only (+30.56% total return incl. ~11p dividends) | Yahoo Finance's own historical-prices page confirms Close = 1123.50p on 2025-09-11 (matches `data/raw/RR.L.csv` exactly) and current price ≈1,417–1,455p | finance.yahoo.com/quote/RR.L/history (fetched directly) | **Confirmed against the primary source** (Yahoo, which is the brief's designated data source). Note: a third-party aggregator (digrin.com) separately showed ~1,180p→~1,424p (+20.6%) for "September 2025→September 2026" — likely a different exact date/monthly-average convention on that site, not a Yahoo data error, since Yahoo's own page matches our raw CSV to the exact penny. |

**Result: PASS**, with the gold "flat" claim flagged as an unreliable secondary source rather than a
problem with our data — do not use it to second-guess SGLN.L.

---

## 5. Calendar checks

- **Row count / start date**: `prices_gbp_daily.csv` and `prices_local_daily.csv` both run 2016-09-12 →
  2026-09-11, 2,525 rows, zero rows before 2016-09-12. **PASS.**
- **One row per VWRP.L trading day, gaps ≤3 days**: checked all consecutive-row calendar gaps >3 days
  (57 instances over 10 years) — every one lines up exactly with a genuine UK bank holiday cluster
  (Christmas/New Year, Easter, early/late May bank holiday, August bank holiday). These are real market
  closures, not missing data. **PASS** — the calendar itself is sound.
- **NaN counts per column / gaps forward-filled silently**: scanned every column in `prices_gbp_daily.csv`
  for internal NaN runs (i.e. NaN gaps strictly between a ticker's own first and last valid date — excludes
  the normal "not yet listed" leading NaNs). Two tickers have real internal gaps:
  - **SMEA.L** (iShares Core MSCI Europe UCITS ETF, GBp): **77 consecutive trading days NaN, 2024-01-02 →
    2024-04-19** (confirmed at the raw-data level: `data/raw/SMEA.L.csv` has no rows at all between
    2023-12-22 and 2024-04-22). This is almost certainly a Yahoo download artefact — a large, liquid,
    continuously-listed European equity ETF should not have a genuine 4-month trading halt. **Major** — this
    falls squarely inside the 5-year core statistics window (2021-09-13 → 2026-09-11) and covers a volatile
    stretch of the market (Dec 2023–Apr 2024); it will bias SMEA.L's own mean/vol/skew/drawdown and any
    pairwise covariance/beta involving it unless `analysis.py` explicitly does pairwise-complete handling.
  - **GHYS.L** (iShares Global High Yield Corp Bond GBP-Hedged UCITS ETF): **16 consecutive trading days
    NaN, 2026-01-02 → 2026-01-23** (raw data has one row with a NaN Close on 2026-01-15 and is missing
    entirely for the following ~9 calendar days). Smaller name, smaller window, but same underlying issue.
  - In both cases the gap correctly was **not** silently forward-filled (good — that's compliant with the
    "≤3 days" rule), but neither gap is recorded in `data/fetch_log.json`'s per-ticker `issues[]` array
    (both show `"issues": []"`), so nothing currently surfaces this to a downstream reader of the log.
    **Recommendation: re-fetch SMEA.L and GHYS.L from Yahoo (a fresh `.history()` call, not the cache) to
    confirm whether the gap is genuinely absent from Yahoo's API or is a caching/pagination bug in the
    fetch script, and record the finding in fetch_log regardless.**
  - No other column (of 84 checked) has an internal NaN run longer than 0 days.
- **Month-end file dates**: 120 of 121 rows in `data/prices_gbp_monthly.csv` are genuine month-end trading
  dates. **The last row is mislabelled**: it is dated **2026-09-30**, a date **19 days after "today"
  (2026-09-14) and beyond the stated as-of/data cutoff (2026-09-11)** — September 2026 was not over when
  this file was built. Checking the value: the 2026-09-30 row's figures are numerically identical to the
  2026-09-11 daily row (e.g. ASML.AS = 1787.584985 in both), confirming this is simply the last available
  (partial-month) data point mis-stamped with the calendar month-end label, most likely from an unguarded
  `resample('M').last()` that labels an incomplete final bucket with the theoretical month-end date rather
  than the actual last observation date. **Major** — any consumer treating this row as "the September 2026
  month-end price" (e.g. a monthly-return or backtest calculation, or an Excel formula keyed on this date)
  would be comparing an 11-trading-day stub month to a full prior month, and the date itself is simply
  wrong/impossible. The weekly file (`prices_gbp_weekly.csv`) does **not** have the equivalent problem —
  its last row is correctly dated 2026-09-11 (the real last Friday of data). **Fix: either drop the
  trailing partial-month row from the monthly file, or re-label it with the true last-observation date
  and flag it as a partial month.**

---

## 6. Proxies

| Instrument | Column | Proxy per `fetch_log.json` | Verified in data |
|---|---|---|---|
| DBMG.L | `DBMG.L` | DBMF (USD→GBP) chained before 2025-04-22 | `prices_gbp_daily.csv` column starts 2019-05-08 (= DBMF's own raw start), matching the splice description; DBMG.L's own raw history genuinely starts 2025-04-22 (351 raw rows) — consistent with "own history chained on from that date." **PASS.** |
| T36N (10y gilt) | `T36N` | IGLT.L (label only — no live Yahoo symbol for the gilt itself) | Column starts at the full common-calendar start, 2016-09-12, and IGLT.L's own raw history goes back to 2008, well before that — proxy covers the whole window as stated. **PASS.** `fetch_log.json`'s `gilt_ticker_discrepancy_note` correctly documents that SPEC_ANALYSIS.md's "T4Q" and core_universe.json's "T36N" are the same instrument, and core_universe.json (binding) is the source of truth. |
| T56 (30y gilt) | `T56` | GLTL.L | Column starts 2016-09-12; GLTL.L raw history starts 2012-05-17, well before the window. **PASS.** |
| IMSR (Terrestrial Energy) | `IMSR` | n/a — de-SPAC cutoff | Raw `data/raw/IMSR.csv` has data from 2024-10-10 (pre-de-SPAC shell), but `prices_gbp_daily.csv`'s IMSR column correctly has its first valid value on **2025-11-03** (first trading day on/after the stated 2025-11-01 cutoff, since 2025-11-01 was a Saturday). **PASS.** |
| SPCX | `SPCX` | n/a — recent IPO | Raw data and the `prices_gbp_daily.csv` column both start exactly **2026-06-12**, with 63 raw daily bars through 2026-09-11 — matches the brief's "63 daily bars" and the fixed 2.5%-policy-weight treatment description exactly. **PASS.** |

**Result: PASS across all 5 proxy/splice checks.**

---

## 7. Fundamentals cross-check (RR.L, PLTR, ONT.L, BKS.L)

- **marketCap units**: sanity-checked `marketCap / sharesOutstanding` against the raw closing price for
  each name (converting GBp→GBP where needed): BKS.L £2.25 vs raw £2.225; ONT.L £1.57 vs raw £1.569; RR.L
  £14.55 vs raw £14.546; PLTR all-USD, consistent. All four match to within ~2%, which is explained by the
  `.info` snapshot being pulled on a slightly different date/share count than the 2026-09-11 raw close.
  **No pence/pounds mix-up found in `marketCap` for these four names** — consistent with the Section-5 policy
  note that GBp tickers' `info['marketCap']` is already GBP, not pence.
- **52-week high/low, local currency (`52w_high_local`/`52w_low_local`)**: recomputed independently from
  `data/raw/<ticker>.csv` High/Low columns over the trailing 252 calendar-day (~52-week) window, excluding
  the stub incomplete bars that have `High=Low=0` (e.g. the 2026-09-14 partial row). Result: **exact match**
  for all four names, e.g. BKS.L 272.0p/145.5p (raw) vs 2.72/1.455 (file, in pounds) — correct to the
  penny; PLTR $207.52/$106.37 (raw) vs 207.52/106.37 (file) — exact. **PASS.**
- **52-week high/low, GBP (`52w_high_gbp`/`52w_low_gbp`) — BUG FOUND.** These columns are **not** a
  52-week high/low of the actual GBP share price. They are the 52-week max/min of the **rebased
  total-return index** from `prices_gbp_daily.csv` (base=100 at that instrument's own history-start date),
  confirmed by direct comparison:

  | Ticker | `52w_high_gbp` (file) | TR-index 52w max (from `prices_gbp_daily.csv`) | Match? |
  |---|---|---|---|
  | RR.L | 2700.914588 | 2700.914588 | exact |
  | BKS.L | 578.158818 | 578.158818 | exact |
  | ONT.L | 29.872675 | 29.872675 | exact |
  | PLTR | 2136.311005 | 2136.311005 | exact |

  Because the TR index is rebased to 100 independently for every instrument at its own inception date, these
  numbers bear no relationship to an actual GBP share price and are wildly inconsistent in scale across
  names (e.g. "£2,700" for a stock whose actual current GBP price is ~£14.55). The CSV does carry a `note`
  field flagging this ("TR-index based (base-100 series), not a raw price level"), so this is a
  *documented* limitation rather than a silent one — **but the field names (`52w_high_gbp`/`52w_low_gbp`)
  and the SPEC_ANALYSIS.md requirement ("52-week high/low local + GBP", "% below 52w high", per-stock table
  identity block, PDF section 7 "price/52w/mcap") both call for an actual GBP price level, comparable to the
  actual current GBP share price**. As shipped, anyone computing "% below 52-week high" as
  `1 − current_price_gbp / 52w_high_gbp` (mixing an actual price against this TR-index figure) would get a
  meaningless result for every single instrument in the fundamentals table, not just these four. (A "%
  below 52-week high" computed instead as `1 − TR_now / TR_52w_high`, i.e. staying consistently within the
  TR-index basis, is fine and does actually cancel out to the right percentage — the danger is only in
  cross-unit use, e.g. next to `marketCap`/price columns which *are* real GBP.)

  **Severity: major.** Confined to two specific fields, but those two fields are populated (and wrong, in
  the "actual price level" sense the spec asked for) for **every** instrument in `fundamentals.csv`/`.json`,
  and they are exactly the fields the PDF/Excel per-stock tables are specified to display. **Fix: replace
  `52w_high_gbp`/`52w_low_gbp` with an actual GBP price-level 52-week high/low** — e.g. `52w_high_local`
  (or the raw High/Low) converted through the same FX-division logic verified correct in §2, rather than
  read off the TR index.
- **Debt figures / other fields**: totalDebt (RR.L £4.373bn, BKS.L £8.6m, ONT.L £41.8m) and totalCash are
  all plausible in scale for GBP once the GBp policy note is applied; no pence/pounds inflation (100×) or
  deflation errors detected for these four names specifically. (Full-universe fundamentals were not
  individually re-verified beyond these four named tickers, per the task scope.)

---

## Summary of findings by severity

**Major**
1. `data/fundamentals.csv` / `.json`: `52w_high_gbp` and `52w_low_gbp` for every instrument are actually
   the 52-week max/min of the rebased TR index (base 100 at each instrument's own start date), not an
   actual GBP price level — inconsistent in scale across instruments and unusable next to any real GBP
   price/market-cap figure. `52w_high_local`/`52w_low_local` are correct. (§7)
2. `data/prices_gbp_daily.csv` (and `prices_local_daily.csv`): **SMEA.L** has a 77-trading-day NaN gap
   (2024-01-02 → 2024-04-19) inside the 5-year core-statistics window, sourced from a genuine hole in the
   raw Yahoo download for a name that should not have a real 4-month trading halt. Not flagged in
   `fetch_log.json`'s per-ticker `issues[]`. Recommend re-fetching. (§5)
3. `data/prices_gbp_monthly.csv`: the final row is dated **2026-09-30** (a date beyond both "today"
   2026-09-14 and the 2026-09-11 data cutoff) but actually just carries the 2026-09-11 partial-month value
   — a real, impossible/mislabelled date that would corrupt any monthly-return or backtest calculation
   keyed on that row. (§5)

**Minor**
4. **GHYS.L** has a 16-trading-day NaN gap (2026-01-02 → 2026-01-23), same root cause pattern as #2 but
   smaller and outside most of the core 5y window's most-recent-and-heavily-weighted stretch; also
   unflagged in `fetch_log.json`. (§5, §3)

**Passed / no issue found**
- GBP total-return index rebuild for all 8 named instruments across 1y/3y/5y — exact match, well inside
  0.3pp/year tolerance. (§1)
- FX direction (division, `GBPxxx=X` convention) — correct for USD, EUR, AUD, HKD conversions, checked
  explicitly plus cross-validated via §1. (§2)
- Dividend units for all 18 `.L` tickers with dividend history — all plausible, no 100× errors. (§3)
- External cross-checks (VWRP, gold, RR.L) against public sources — all consistent; one third-party
  "gold flat" claim and one "digrin" RR.L price series were investigated and judged unreliable/methodology
  mismatches rather than problems with our data. (§4)
- Trading calendar (start date, gap pattern, holiday alignment) — sound. (§5)
- All five proxy/splice arrangements (DBMG.L, T36N, T56, IMSR, SPCX) — match `fetch_log.json`'s stated
  method exactly. (§6)
- `marketCap`, 52w-high/low **local**, and debt figures for RR.L/PLTR/ONT.L/BKS.L — correctly unit-scaled,
  no pence/pounds mix-ups found. (§7)
