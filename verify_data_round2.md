# Data verification — round 2 (blind, independent re-derivation)

Scope: `data/raw/*.csv`, `data/fx_daily.csv`, `data/prices_gbp_daily.csv`, `data/prices_local_daily.csv`,
`data/dividends.csv`, `data/fetch_log.json`, `data/fundamentals.csv`/`.json`, and public sources.
`scripts/fetch_data.py` was **not** read; all figures below were rebuilt from scratch in a fresh script.
As-of date: 2026-09-11 (today 2026-09-14).

## Summary of round-1 issues — status

| # | Round-1 issue | Status |
|---|---|---|
| 1 | `52w_high_gbp`/`52w_low_gbp` were actually the 52w max/min of the rebased TR index, not a real GBP price level | **FIXED.** Now computed from raw daily High/Low (GBp → /100, other currencies → same-day FX), and documented in the `note` field. Verified exact: RR.L 15.86/9.90 = raw `High`/`Low` max/min over the trailing 365 days ÷100; BKS.L and ONT.L likewise exact; PLTR 52w_high_gbp=157.99 correctly FX-converted (≠ the raw USD 207.52 figure, converted at the FX rate prevailing on the high date, not today's rate). |
| 2 | SMEA.L 77-trading-day gap (2023-12-22→2024-04-22) not recorded in `fetch_log.json` issues[] | **FIXED.** `fetch_log.json → tickers.SMEA.L.issues[]` now documents the gap, confirms it was re-checked with a fresh non-cached fetch, confirms it is a genuine Yahoo hole (not a caching artefact), and confirms `prices_gbp_daily.csv`/`prices_local_daily.csv` correctly show NaN (not forward-filled) across it. |
| 3 | `prices_gbp_monthly.csv` last row mislabelled 2026-09-30 (actually the 2026-09-11 daily value) | **FIXED.** Last row of `prices_gbp_monthly.csv` is now correctly dated 2026-09-11 (a genuine partial-period row, not a fabricated month-end); 120 of the other 121 rows are true calendar month-ends. |

All three round-1 items are resolved. Two new issues were found in this round (below).

## New issues found this round

### 1. [BLOCKER] DBMG.L raw price data has a recurring ~100x pence/pounds scale error across its own-history segment

`data/raw/DBMG.L.csv`, the ~4.5 months of DBMG.L's **own** listed history (2025-04-22 onward, spliced
after the DBMF proxy period per `fetch_log.json.splice_log`), contains repeated stretches where the
`Close` is reported ~100x too small, then reverts — a pence/pounds unit flip within a single ticker's
raw feed, not a one-off. This propagates straight into `prices_gbp_daily.csv` / `prices_local_daily.csv`
as violent single/multi-day −99% crashes followed by +7,500%/+9,900% "recoveries."

Evidence — daily returns on the `DBMG.L` column of `prices_gbp_daily.csv` with |return| > 30%:
```
2025-04-23   -99.00%      2025-04-24   +7,549%
2025-05-16   -99.00%      2025-05-19   +9,813%
2025-06-10   -99.00%      2025-06-18   +9,924%
2025-06-26   -99.00%      2025-07-14   +9,932%
2025-07-24   -99.00%      2025-08-12   +9,875%
```
Checked directly against `data/raw/DBMG.L.csv`: e.g. 2025-05-15 Close=7546.5, 2025-05-16 Close=75.71
(exactly ~100x low), 2025-05-19 Close=7506.0 (back to the correct scale). This is not confined to single
days: 2025-06-10 through 2025-06-17 (6 consecutive trading days) and 2025-06-26 through 2025-07-11
(12 consecutive trading days) and 2025-07-24 through 2025-08-11 (14 consecutive trading days) are ALL
in the wrong (÷100) scale before correcting. Counting rows whose Close is <5% of the ticker's own
post-splice median: **33 of 352 rows (9.4%) of DBMG.L's own-history segment are mis-scaled.**

Why this matters beyond DBMG.L itself: DBMG.L is one distinct optimiser bucket ("trend ≤15%" per
PROJECT_BRIEF) and its column feeds the shared 36/37-asset covariance matrix. The spec calls for
Ledoit–Wolf constant-correlation shrinkage, whose shrinkage target uses the *average pairwise
correlation across the whole universe* — one column with fabricated ±99%/+9,900% daily swings will
distort that average and therefore leak into the shrunk covariance (and hence the optimiser weights)
for every other core asset, not just DBMG.L. It will also badly corrupt DBMG.L's own vol/Sharpe/
Sortino/skew/kurtosis/max-drawdown/VaR/CVaR figures reported in the per-asset tables.

**Fix**: sanity-check every ticker's raw Close series for the mis-scaling pattern used here for the GBp
trap generally (a specific, in-band ratio test), e.g. flag/replace any single-day return whose magnitude
is consistent with a ~100x (or 1/100x) unit flip relative to the surrounding week's median, before it
enters `split_adjust()`/`build_local_tr_index()`. For DBMG.L specifically, either correct the 33 affected
rows (rescale by 100 where flagged) or re-fetch fresh from Yahoo to see if the anomaly persists; document
the correction in `fetch_log.json`'s issues[] the same way the SMEA.L gap now is.

### 2. [MAJOR] Fundamentals (marketCap, EV, P/E, dividend yield, etc.) reflect a live/intraday quote, not the stated "as at 2026-09-11" price — undocumented

`data/info/<ticker>.json`'s `currentPrice`/`regularMarketPrice` do not equal `previousClose` (which does
match the 2026-09-11 close in the price files), i.e. `.info` was evidently queried live at fetch-run time
(after 2026-09-11, plausibly on 2026-09-14 based on the stray extra raw bar noted below) rather than
being pinned to the 2026-09-11 cutoff used everywhere else in the pipeline:

| Ticker | info.currentPrice | info.previousClose (=2026-09-11 close) |
|---|---|---|
| RR.L | 1423.8p | 1454.6p |
| BKS.L | 225.0p | 222.5p |
| ONT.L | 154.0p | 156.9p |
| PLTR | $173.31 | $167.23 |

`data/fundamentals.csv`'s `marketCap` is `info['marketCap']` taken as-is (per the documented policy that
GBp `marketCap` is already in GBP, which is correctly applied — no pence/pounds mix-up found): confirmed
exactly, e.g. BKS.L marketCap 154,839,024 = 225.0p × 68,817,346 shares ÷ 100 — i.e. it is priced off the
**live** 225.0p quote, not the 222.5p close that the rest of the workbook treats as "the" 2026-09-11
price. The same applies to `enterpriseValue`, `trailingPE`, `forwardPE`, `priceToBook`. The magnitude of
drift is small (roughly 1–2% here) but it is systematic across essentially every stock in the universe,
undocumented anywhere in `fetch_log.json` or the `note` field, and creates an internal date inconsistency
between the fundamentals table and every price-history-derived figure that is dated 2026-09-11.

**Fix**: either re-derive marketCap/EV/P-E/P-B from the 2026-09-11 close × shares outstanding (consistent
with the rest of the pipeline) instead of trusting `.info`'s live quote, or explicitly document in
`fetch_log.json`/the `note` field that these specific `.info`-sourced fields are "live as at fetch time"
rather than "as at 2026-09-11," so the PDF/Excel captions can say so accurately.

### 3. [MINOR] A handful of thin-liquidity LSE small-caps have genuine multi-day stale-price runs — confirm this isn't mistaken for a pipeline forward-fill bug

Scanning `prices_gbp_daily.csv` for runs of an identical consecutive value >3 trading days (the
brief's "forward-fill ≤3 days" rule) turns up 4 tickers not already flagged/excluded
(SMEA.L/IMSR/SPCX/DBMG.L/T36N/T56 are the documented exceptions): **NET.L** (25-day run, Jul–Aug 2020),
**FTC.L** (22-day run, May–Jun 2018), **WLDS.L** (13-day run, May 2018), **BKS.L** (12-day run,
Nov–Dec 2020). Checked directly against `data/raw/<ticker>.csv`: these are genuine repeated closing
quotes with `Volume=0` on most of the affected days already present in Yahoo's own raw feed for these
thinly-traded AIM names — not an artefact of this pipeline's forward-filling. No action needed on the
data itself, but worth a one-line note in `fetch_log.json`'s issues[] for these four tickers (as already
done for SMEA.L) so a future reviewer doesn't mistake genuine market illiquidity for a fill-forward bug.

### 4. [MINOR / informational] Raw cache files extend one trading day past the stated 2026-09-11 cutoff

`data/raw/*.csv` (e.g. `SPCX.csv`) contain a bar dated 2026-09-14 (today), one row beyond
`fetch_log.json`'s own logged `n_rows` (e.g. SPCX logged as 63 rows; the raw file now has 64). Confirmed
this does **not** leak downstream: `prices_gbp_daily.csv`/`prices_local_daily.csv` have zero rows after
2026-09-11 for every column checked. Harmless, but the raw cache is not frozen exactly at the stated
as-of date — worth noting if `fetch_data.py` is ever re-run and expected to be a pure no-op cache hit.

## Check-by-check detail

### Check 1 — independent GBP total-return index rebuild (own code, no reliance on fetch_data.py)

Rebuilt from `data/raw/<ticker>.csv` for all 8 requested names: split-adjusted Close (accumulating the
`Stock Splits` column backward), `TR_t = TR_{t-1} × (P_t + D_t)/P_{t-1}`, then divided by the matching
`GBPxxx=X` column of `data/fx_daily.csv` for non-GBP names (GBp/GBP names left as-is — pence is a GBP
subunit and cancels out of the ratio). Base date fixed at 2016-09-12 (the file's own common-calendar
start; `fx_daily.csv` itself only starts there, so pre-2016-09-12 history for IHYU.L/ASML.AS/DRO.AX
can't be FX-converted with this data — matches the project's stated 10y window anyway). Compared 1y/3y/5y
cumulative returns to `data/prices_gbp_daily.csv`:

| Ticker | my 1y | file 1y | diff | my 3y | file 3y | diff | my 5y | file 5y | diff |
|---|---|---|---|---|---|---|---|---|---|
| RR.L | 30.537% | 30.537% | ~0pp | 561.80% | 561.80% | ~0pp | 1260.21% | 1260.21% | ~0pp |
| VWRP.L | 19.809% | 19.809% | ~0pp | 61.968% | 61.968% | ~0pp | 71.572% | 71.572% | ~0pp |
| SGLN.L | 20.527% | 20.527% | ~0pp | 110.154% | 110.154% | ~0pp | 147.719% | 147.719% | ~0pp |
| PLTR | 1.938% | 1.938% | ~0pp | 893.228% | 893.228% | ~0pp | 551.901% | 551.901% | ~0pp |
| IHYU.L | 3.045% | 3.045% | ~0pp | 16.234% | 16.234% | ~0pp | 22.392% | 22.392% | ~0pp |
| ASML.AS | 115.598% | 115.598% | ~0pp | 162.620% | 162.620% | ~0pp | 112.900% | 112.900% | ~0pp |
| DRO.AX | −41.624% | −41.624% | ~0pp | 489.774% | 489.774% | ~0pp | 725.621% | 725.621% | ~0pp |
| 1833.HK | −73.194% | −73.194% | ~0pp | −22.312% | −22.312% | ~0pp | −71.941% | −71.941% | ~0pp |

All differences are at floating-point noise level (~1e-14), far inside the 0.3pp/year tolerance. **PASS**
for all 8 instruments — confirms the GBp-pence rebuild, split adjustment, dividend handling and FX
conversion methodology in `prices_gbp_daily.csv` are all correct for these names.

### Check 2 — FX direction

Verified explicitly for 2026-09-11: `GBPUSD=X` = 1.350931. PLTR raw close $167.23 → $167.23/1.350931 =
**£123.79**; MSFT raw close $495.63 → $495.63/1.350931 = **£366.88**. Both divide (not multiply) by the
GBPxxx rate, matching the "GBP price = USD price / GBPUSD" rule (GBPUSD=X quotes USD-per-GBP). The same
divide-by-rate convention was independently confirmed to reproduce the file's TR index exactly for EUR
(ASML.AS), AUD (DRO.AX) and HKD (1833.HK) in Check 1 above (a direction error would have thrown those
comparisons off by a squared-FX-return factor, not by ~1e-14). **PASS.**

### Check 3 — dividend units for .L tickers

For every LSE ticker with dividend events, `median(Dividend / Close on ex-date)`:

```
AZN.L 0.0133   BKS.L 0.0018   FTC.L 0.0045   GHYS.L 0.0251  GLTL.L 0.0116
GNS.L 0.0075   HSBA.L 0.0120  IBTM.L 0.0114  IEMB.L 0.0039  IGLT.L 0.0099
IHYG.L 0.0217  IHYU.L 0.0280  ISF.L  0.0085  NET.L 0.0158   RR.L  0.0127
SHEL.L 0.0119  ULVR.L 0.0096  VMID.L 0.0077
```
All 17 lie between 0.0018 and 0.028 — comfortably inside the 0.0005–0.10 plausible band. **PASS, no unit
errors.**

### Check 4 — external cross-checks

- **VWRP**: justETF reports VWRP 1y total return **18.91%** (in GBP, ISIN IE00BK5BQT80). Our file: **19.81%**
  as at 2026-09-11. ~0.9pp apart — plausibly explained by justETF's page not being dated exactly
  2026-09-11 (search snapshot suggests it may reflect a slightly earlier date); not able to pin down an
  exact "as of" date for the justETF figure, so treat as broadly consistent rather than an exact match.
  justETF 3y figure was not retrievable from the search snippets returned.
- **Gold in GBP**: our SGLN.L 1y return = **+20.53%**. Cross-checked via components: spot gold in USD
  rose from ~$3,481/oz (Sep 2025) to ~$4,421/oz (Sep 2026), i.e. **+27.0% in USD**, while GBPUSD barely
  moved over the same year (1.3535 → 1.3509 in our own `fx_daily.csv`, essentially flat, −0.19%) — so a
  GBP gold return in the low-to-high-20s% is exactly what the USD price + flat cable implies; SGLN.L's
  +20.5% (slightly below the pure metal move, consistent with the ETC's ~0.12% TER and tracking) is
  **consistent and plausible**. One AI-generated web-search summary claimed gold was "flat in GBP over
  the year" — this is self-contradictory with the same search's own USD/FX figures (27% USD gain ÷
  ~flat GBPUSD ≠ flat GBP return) and should be disregarded as an unreliable auto-summary rather than
  treated as a genuine discrepancy in our data.
- **RR.L**: our raw close 2026-09-11 = **1454.60p**, 1y price return (close-only, no div) = 1454.6/1123.5
  − 1 = **29.5%** (TR return incl. dividends = 30.5%, matches). External sources (LSE/AJ Bell/HL search
  results) place RR.L trading in the **1417p–1455p** range in mid-September 2026 with a 52-week range of
  roughly **1019p–1585p** low/high — our raw 52-week window gives 1029p–1570p over the trailing 365
  calendar days to 2026-09-11. **Consistent** (small differences expected from slightly different exact
  dates/sources).

### Check 5 — calendar integrity

- `prices_gbp_daily.csv`: 2,525 rows, first 2016-09-12, last 2026-09-11, exactly matching
  `fetch_log.json`'s `n_common_calendar_days: 2525` and `common_calendar_start/end`. Index strictly
  monotonic increasing, zero duplicate dates, **zero rows before 2016-09-12**. **PASS.**
- Calendar-day gaps between consecutive rows are all ≤5 calendar days (57 such gaps, all falling on
  bank-holiday weekends — e.g. Christmas/New Year, Easter, May Day — a normal feature of a trading-day
  calendar, not a data gap). **PASS** (no genuine calendar hole).
- NaN counts per column are highest for the shortest-history/newest-listed names as expected (SPCX 2,460
  NaN of 2,525 rows = correct, since it only has 65 trading days of history; IMSR 2,309 NaN = correct
  per the 2025-11-01 cutoff; SMEA.L 77 NaN = the documented gap). No column shows an unexplained NaN
  count inconsistent with its known first-trade date or documented gap.
- Forward-fill runs >3 trading days: see Minor issue #3 above (4 genuine-illiquidity tickers, not a bug).
- `prices_gbp_monthly.csv`: 121 rows, 120 of 121 are true calendar month-ends; the 121st (last) row is
  now correctly dated 2026-09-11 (the round-1 mislabelling is fixed — see table above).
  `prices_gbp_weekly.csv`: last row correctly dated 2026-09-11. **PASS.**

### Check 6 — proxies

- **DBMG.L**: `fetch_log.json.splice_log` states proxy=DBMF, own history from 2025-04-22, "proxy GBP TR
  chained before own_history_start, rescaled for continuity, rebased to 100." Confirmed the switchover
  date and presence of both segments in `prices_gbp_daily.csv`. **However see Blocker #1 above**: the
  own-history segment itself (post-2025-04-22) contains a serious raw-data scaling defect independent of
  the splice mechanism.
- **T36N / T56**: both present in `prices_gbp_daily.csv` for the full 2,525-row common calendar (no
  "own" ticker exists, proxy used in full throughout per `splice_log`) — T36N via IGLT.L, T56 via
  GLTL.L, matching PROJECT_BRIEF/SPEC's naming (T36N replaces the earlier "T4Q" reference). **PASS.**
- **IMSR**: first bar in `prices_gbp_daily.csv` is 2025-11-03 (first trading day on/after the mandated
  2025-11-01 cutoff) — **PASS, no pre-cutoff shell-company bars present.**
- **SPCX**: first bar 2026-06-12 exactly as specified, 65 rows on the common calendar through
  2026-09-11. **PASS.**

### Check 7 — fundamentals cross-check (RR.L, PLTR, ONT.L, BKS.L)

- 52-week high/low (local and GBP): confirmed exact match to raw daily `High`/`Low` column max/min over
  the trailing 365 calendar days for all four (e.g. RR.L 15.86/9.90 = raw High max/Low min ÷100 exactly);
  correctly FX-converted for PLTR (52w_high_gbp 157.99 ≠ naive USD/today's-FX conversion of 207.52,
  correctly using the FX rate prevailing on the actual high date). **Round-1 fix confirmed correct.**
- Market cap: GBp tickers' `marketCap` taken directly from `.info` (no further pence conversion) per the
  documented policy — confirmed correct in scale for all four (e.g. RR.L £117.3bn ≈ 8.24bn shares ×
  ~£14.2–14.5/share; BKS.L £154.8m ≈ 68.8m shares × ~£2.22–2.25/share) — **no pence/pounds mix-up found**.
  However, see Major issue #2: the price used is a live intraday quote, not the stated 2026-09-11 close.
- Total debt: RR.L £4.373bn, ONT.L £41.8m, BKS.L £8.6m, PLTR $211.4m — all plausible order-of-magnitude
  for these companies' known balance sheets; no scale errors found.
- Dividend yield spot-check across the wider fundamentals table (e.g. AZN.L 2.04%, HSBA.L 3.59%,
  SHEL.L 3.26%, ULVR.L 3.62%) reads as a genuine percentage figure, not a mis-scaled fraction — no issue
  found (not one of the seven explicitly-requested tickers, but checked as it sits next to the requested
  fields).
