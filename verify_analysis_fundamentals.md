# Adversarial verification — Fundamentals, CAPM, WACC, position sizing

Lens: fundamentals / CAPM / WACC / position sizing. `scripts/analysis.py` was **not** read; all numbers below were
independently recomputed from `data/info/*.json`, `data/fin/*.csv`, `data/raw/*.csv`, `data/fx_daily.csv`,
`universe/market_params.json` and `data/prices_gbp_daily.csv`, using `/usr/bin/python3` (pandas/numpy), and compared
against `data/fundamentals_table.csv`. Tickers checked: **RR.L, PLTR, ASML.AS, ONT.L, NVTS, 1833.HK, SLX.AX**.
rf = Bank Rate 3.75% (`market_params.boe_bank_rate`), ERP = 4.17% (`market_params.damodaran_erp`).

All working code is inlined in each section so every number can be reproduced.

---

## Summary of findings

| # | Severity | Finding |
|---|----------|---------|
| 1 | **major** | `trailing_pe` / `forward_pe` in `fundamentals_table.csv` are computed by Yahoo off the **live price at fetch time (2026‑09‑14)**, not the "price as at 2026‑09‑11" the brief mandates elsewhere in the same row. Confirmed for all 7 names; multiples are overstated/understated by ~2–8%. |
| 2 | **major** | `market_cap` column is **not uniformly GBP** — it is a straight copy of Yahoo's `info['marketCap']`, which is in the instrument's **own reporting currency** (USD for PLTR/NVTS, EUR for ASML.AS, HKD for 1833.HK, AUD for SLX.AX). Only the two GBp names (RR.L, ONT.L) are correctly GBP. `market_cap_usd_m` is also **missing (NaN)** for RR.L, PLTR and ASML.AS — the three largest names in the sample. |
| 3 | **major** | `pct_below_52w_high` is computed against a **close‑price‑only** 52‑week high, while the adjacent `high_52w_local`/`high_52w_gbp` columns in the *same row* report a **different, higher** 52‑week high computed from the intraday **High** column. Two different "52‑week high" numbers appear side‑by‑side for every one of the 7 rows checked. |
| 4 | minor | `capex_to_revenue` mixes a **FY (statement) capex** numerator with a **TTM (info) revenue** denominator — confirmed exactly for all 7 names (`|capex_fy| / info.totalRevenue`, not FY revenue). It also silently flips the sign (capex_fy is negative, capex_to_revenue is reported positive) without a documented convention. |
| 5 | minor | `total_debt` (and hence `net_debt`, `debt_to_equity_book`) comes from `info['totalDebt']`, which for 6 of 7 names equals the **latest quarterly** balance-sheet figure (acceptable under the spec's "latest FY and latest 4 quarters"), but for **RR.L it matches neither the FY2025 (£4.272bn) nor the latest-quarter (£4.311bn) figure in the shipped `data/fin/RR.L_balance_*.csv`** — it is unreconciled against the primary source files provided. |
| 6 | minor | `cost_of_debt` (Kd) for **PLTR (1.64%)** and **NVTS (2.92%)** cannot be reproduced from any shipped source: `Interest Expense` is `NaN` in both FY and quarterly income statements for both tickers, and neither `info` json has an interest-expense field. The documented fallback (rf+2% = 5.75%) was not applied either. Financially immaterial here (debt is <0.2% of enterprise value for both), but the number is untraceable. |
| 7 | none (checked, correct) | CAPM chain (β_own → Ke = rf+β·ERP), the WACC formula itself (E/(D+E)·Ke + D/(D+E)·Kd·(1−t), using market-cap E and the table's own D), β_own vs VWRP.L (5y daily, GBP), YTD (GBP), and `combined_positions.csv` (shares=floor(£/price), £200,000 total, 40×£1,000 unicorns, core=£160,000, SPCX=£4,000) **all reconcile exactly**. No WACC value falls outside 3–20%. |

Net effect on the **portfolio itself** (£ position sizes in `combined_positions.csv`): **none** — that file uses `price_gbp` values that match my independent Sept‑11 close-based GBP prices exactly for every ticker checked, and every arithmetic identity (shares, £200k, £40k unicorns, £160k core, SPCX £4,000) holds to the penny. The issues above sit in the **fundamentals/valuation table** that would feed the PDF's "Individual holdings" and "Core universe" sections, not in the position-sizing pipeline.

---

## 1. Price in GBP (as at 2026‑09‑11)

```python
import pandas as pd, json
fx = pd.read_csv("data/fx_daily.csv", index_col=0, parse_dates=True)
asof = pd.Timestamp("2026-09-11")
ccy = {"RR.L":"GBp","PLTR":"USD","ASML.AS":"EUR","ONT.L":"GBp","NVTS":"USD","1833.HK":"HKD","SLX.AX":"AUD"}
fx_col = {"USD":"GBPUSD=X","EUR":"GBPEUR=X","HKD":"GBPHKD=X","AUD":"GBPAUD=X"}
for t in ccy:
    raw = pd.read_csv(f"data/raw/{t}.csv", index_col=0, parse_dates=True)
    px_local = raw.loc[asof, "Close"]
    px_gbp = px_local/100.0 if ccy[t]=="GBp" else px_local/fx.loc[asof, fx_col[ccy[t]]]
    print(t, px_local, px_gbp)
```

| Ticker | Local close (raw) | Ccy | Own price_gbp | Table price_gbp | Match |
|---|---|---|---|---|---|
| RR.L | 1454.60p | GBp | 14.546000 | 14.546000 | Yes |
| PLTR | 167.2300 | USD | 123.788665 | 123.788665 | Yes |
| ASML.AS | 1478.4000 | EUR | 1270.616172 | 1270.616172 | Yes |
| ONT.L | 156.90p | GBp | 1.569000 | 1.569000 | Yes |
| NVTS | 11.6300 | USD | 8.608875 | 8.608875 | Yes |
| 1833.HK | 6.1250 | HKD | 0.578247 | 0.578247 | Yes |
| SLX.AX | 4.6500 | AUD | 2.463367 | 2.463367 | Yes |

All 7 match to 6 d.p. — the Sept‑11 close and GBp/FX conversion are correct.

---

## 2. 52‑week high/low, % below high — Finding #3 (major)

Two different methodologies coexist for "52‑week high" within one row:

```python
win = raw[t].loc[asof - pd.Timedelta(days=365):asof]
close_hi, close_lo = win["Close"].max(), win["Close"].min()   # matches pct_below_52w_high
hilo_hi, hilo_lo   = win["High"].max(),  win["Low"].min()      # matches high_52w_local / high_52w_gbp
```

| Ticker | Close-based 52wH (local) | High/Low-col 52wH (local) | Table `high_52w_local` | Table `pct_below_52w_high` | Implied high from that % |
|---|---|---|---|---|---|
| RR.L | 15.7040 | 15.8600 | 15.86 | -7.374% | 15.7040 |
| PLTR | 207.1800 | 207.5200 | 207.52 | -19.283% | 207.1800 |
| ASML.AS | 1721.4000 | 1741.0000 | 1741.0 | -14.116% | 1721.4000 |
| ONT.L | 1.8300 | 1.9140 | 1.9140 | -14.262% | 1.8300 |
| NVTS | 31.7900 | 34.1700 | 34.17 | -63.416% | 31.7900 |
| 1833.HK | 22.7400 | 23.4000 | 23.40 | -73.065% | 22.7400 |
| SLX.AX | 10.4900 | 10.8500 | 10.85 | -55.672% | 10.4900 |

`high_52w_local`/`high_52w_gbp` = **High/Low column**-based extremes; `pct_below_52w_high` = derived from the
**Close-only** extreme. For every single row the "implied high" backed out of `pct_below_52w_high` (right-hand
column) is the *lower* Close-based number, not the `high_52w_local` figure printed two columns to its left. Neither
methodology is wrong per se (intraday High/Low is the more conventional "52-week range"; the brief's own instruction
to "compute 52-week high/low from the price history yourself" doesn't specify Close vs. High/Low) — but the two
figures are inconsistent with each other in the same row, which will read as an error to anyone cross-checking "X%
below the 52w high of Y" against Y itself. Recommend picking one convention (High/Low column is standard) and
recomputing `pct_below_52w_high` from it.

---

## 3. Market capitalisation — Finding #2 (major)

```python
info = {t: json.load(open(f"data/info/{t}.json")) for t in ccy}
for t in ccy:
    shares = info[t]["sharesOutstanding"]
    live_price_local = info[t]["regularMarketPrice"]
    mcap_native = shares * live_price_local / (100.0 if ccy[t]=="GBp" else 1.0)
    print(t, mcap_native, info[t]["marketCap"])   # identical -> info['marketCap'] is in NATIVE currency
```

| Ticker | Ccy of instrument | Table `market_cap` | Actually denominated in | Own mcap GBP (shares × Sept‑11 price_gbp) | Own mcap USD | Table `market_cap_usd_m` |
|---|---|---|---|---|---|---|
| RR.L | GBp | 117,339,889,664 | **GBP** (correct, GBp special-cased) | 119,878,217,485 | 161,947,248,899 | **NaN — missing** |
| PLTR | USD | 416,474,038,272 | **USD**, not GBP | 284,802,232,344 | 384,748,280,179 | **NaN — missing** |
| ASML.AS | EUR | 533,053,997,056 | **EUR**, not GBP | 488,043,671,612 | 659,313,523,491 | **NaN — missing** |
| ONT.L | GBp | 1,505,357,952 | **GBP** (correct) | 1,533,705,605 | 2,071,931,070 | 2,033.9 |
| NVTS | USD | 2,843,308,288 | **USD**, not GBP | 2,247,721,299 | 3,036,517,295 | 2,843.3 (= USD figure again, consistent with itself) |
| 1833.HK | HKD | 13,100,015,616 | **HKD**, not GBP — ~19× too large if read as GBP | 1,229,715,057 | 1,661,260,691 | 1,671.0 |
| SLX.AX | AUD | 1,205,637,888 | **AUD**, not GBP — ~1.9× too large if read as GBP | 685,895,798 | 926,598,174 | 855.2 |

`market_cap` is `info['marketCap']` verbatim (also built off the **live** Sept‑14 price for the non-GBp names, not
the Sept‑11 "as at" price — same vintage issue as the P/E finding below). For a model whose brief states "All
returns, risk and £ sizing in GBP terms," a column literally named `market_cap` holding EUR for ASML.AS and HKD for
1833.HK (with no currency suffix or footnote) is a real currency-labelling error, and it is missing the USD figure
(needed for the brief's own $100m–$5bn/‑$10bn unicorn screen) for 3 of the 7 names, including the largest ones. Own
GBP and USD market caps (right-hand columns, computed at the Sept‑11 close, per the brief's "as at" date) are given
above for use instead.

---

## 4. Balance sheet: total debt, cash, net debt, D/E — Finding #5 (minor)

```python
bal = pd.read_csv(f"data/fin/{t}_balance_annual.csv", index_col=0)   # latest column = latest FY
bal_q = pd.read_csv(f"data/fin/{t}_balance_quarterly.csv", index_col=0)  # latest column = latest quarter
```

| Ticker | Table `total_debt` | = `info.totalDebt`? | Balance-sheet FY (latest annual col) | Balance-sheet latest quarter | Reconciles to any shipped statement? |
|---|---|---|---|---|---|
| RR.L | 4,373,000,192 | Yes | 4,272,000,000 (FY2025) | 4,311,000,000 (2026‑06‑30) | **No — matches neither** |
| PLTR | 211,400,000 | Yes | 229,338,000 (FY2025) | 211,400,000 (2026‑06‑30) | Yes, latest quarter |
| ASML.AS | 1,984,400,000 | Yes | 4,390,900,000 (FY2025) | 1,984,400,000 (2026‑06‑30) | Yes, latest quarter |
| ONT.L | 41,800,000 | Yes | 41,500,000 (FY2025) | 41,800,000 (2026‑06‑30) | Yes, latest quarter |
| NVTS | 5,136,000 | Yes | 6,472,000 (FY2025) | 5,136,000 (2026‑06‑30) | Yes, latest quarter |
| 1833.HK | 29,060,000 | Yes | 39,790,000 (FY2025) | 29,060,000 (2026‑06‑30) | Yes, latest quarter |
| SLX.AX | 642,197 | Yes | 642,197 (FY2026‑06‑30) | 642,197 (2026‑06‑30) | Yes |

6 of 7 tie exactly to the **latest quarterly** balance sheet (acceptable under the spec's "latest FY **and latest 4
quarters**" wording, though it means D/E and net debt are on a more current basis than the "FY" label on adjacent
columns like `capex_fy`/`total_stockholders_equity_fy` implies — a labelling inconsistency, not a wrong number).
**RR.L is the exception**: 4,373,000,192 does not equal the FY2025 figure, the latest-quarter figure, or any other
column in `data/fin/RR.L_balance_annual.csv` / `..._quarterly.csv` — it can only be traced to `info['totalDebt']`,
whose as-of date isn't stated in the JSON. Net debt (own calc using FY2025 statement figures: debt 4.272bn − cash
6.034bn = **‑1.762bn**) vs table's net_debt (‑2.111bn, using info debt 4.373bn − info cash 6.484bn) differ by ~£0.35bn
— not enough to move D/E out of a sane range (own D/E off FY statement = 1.567 vs table 1.604, a 2.4% difference)
but it means RR.L's leverage inputs are not reproducible from the shipped `data/fin/` CSVs alone.

D/E, Kd, tax rate and the resulting WACC are otherwise **internally self-consistent**: given the table's own
`market_cap` (E), `total_debt` (D), `cost_of_equity_capm`, `cost_of_debt` and `tax_rate`, plugging into
`WACC = E/(D+E)·Ke + D/(D+E)·Kd·(1−t)` reproduces the table's `wacc` to 6 decimal places for all 7 names (code
below) — and because E and D are each expressed in the *same* native currency per row, the currency-mislabelling in
Finding #2 does **not** propagate into the WACC ratio itself.

```python
wacc_check = E/(D+E)*Ke + D/(D+E)*Kd*(1-tax)   # E=market_cap, D=total_debt, all from fundamentals_table.csv row
# RR.L: 0.091001 vs table 0.091001 (match); same exact match for all other 6 names
```

All 7 WACCs land in **6.5%–12.2%**, well inside the 3–20% sanity band — no explanation required.

---

## 5. Interest cover, tax rate, Kd — Finding #6 (minor)

```python
inc = pd.read_csv(f"data/fin/{t}_income_annual.csv", index_col=0)
interest_exp = inc.loc["Interest Expense", inc.columns[0]]   # latest FY
tax_rate = min(max(inc.loc["Tax Provision", col]/inc.loc["Pretax Income", col], 0.0), 0.35)
```

| Ticker | FY interest expense | FY pretax | FY tax provision | Tax rate (own, bounded) | Table `tax_rate` | Table `cost_of_debt` | Reproducible from `data/fin`? |
|---|---|---|---|---|---|---|---|
| RR.L | 302,000,000 | 6,935,000,000 | 1,099,000,000 | 0.158472 | 0.158472 | 0.069060 (=302m/4,373,000,192) | Yes (mixes FY interest-expense with the non‑FY total_debt from §4) |
| PLTR | **NaN in both FY and quarterly** | 1,657,368,000 | 22,724,000 | 0.013711 | 0.013711 | **0.016414 — no source found** | **No** |
| ASML.AS | 118,300,000 | 11,406,100,000 | 2,013,400,000 | 0.176520 | 0.176520 | 0.059615 (≈118.3m/1,984,400,000) | Yes |
| ONT.L | 2,800,000 | ‑139,900,000 (loss) | 5,300,000 | fallback 0.25 (raw ratio negative) | 0.25 | 0.066986 | Yes |
| NVTS | **NaN in both FY and quarterly** | ‑115,782,000 (loss) | 50,000 | fallback 0.25 | 0.25 | **0.029206 — no source found** | **No** |
| 1833.HK | 2,678,000 | 380,773,000 | 2,822,000 | 0.007411 | 0.007411 | 0.092154 | Yes |
| SLX.AX | 67,597 | ‑38,620,683 (loss) | 0 | fallback 0.25 | 0.25 | 0.105259 | Yes |

Tax-rate bounding/fallback logic (0–35%, else 25%) works exactly as specified in all 7 cases — no issue there.

`Interest Expense` is `NaN` for **both** PLTR and NVTS across every column of both the annual and quarterly income
statements shipped in `data/fin/`, and neither `data/info/PLTR.json` nor `data/info/NVTS.json` carries any
interest-expense-like field. Yet `cost_of_debt` is a specific non-fallback, non-zero number for both (1.64% and
2.92%) that I cannot reconstruct from any file in this repo. The documented fallback (`rf + 2% = 5.75%`) was not
used either. **Financially immaterial** here — debt is under 0.2% of enterprise value for both names, so plugging
in 5.75% instead changes WACC by <0.01 percentage points for either — but flagged per the "default to reporting a
mismatch when uncertain" instruction, since the number's provenance is untraceable from the shipped data.

---

## 6. Capex (latest FY) and capex/revenue — Finding #4 (minor)

```python
cf = pd.read_csv(f"data/fin/{t}_cashflow_annual.csv", index_col=0)
capex_fy = cf.loc["Capital Expenditure", cf.columns[0]]     # Yahoo convention: negative = cash outflow
info_rev = json.load(open(f"data/info/{t}.json"))["totalRevenue"]   # TTM, not FY
```

| Ticker | `capex_fy` (table, FY, Yahoo sign) | FY revenue (from `data/fin` income stmt) | `info.totalRevenue` (TTM) | `|capex_fy|` / FY revenue | Table `capex_to_revenue` | Matches which denominator |
|---|---|---|---|---|---|---|
| RR.L | ‑985,000,000 | 21,207,000,000 | 23,164,999,680 | 0.04645 | **0.04252** | TTM |
| PLTR | ‑33,882,000 | 4,475,446,000 | 6,155,940,864 | 0.00757 | **0.00550** | TTM |
| ASML.AS | ‑1,631,200,000 | 32,667,300,000 | 35,327,500,288 | 0.04993 | **0.04617** | TTM |
| ONT.L | ‑45,700,000 | 223,900,000 | 235,000,000 | 0.20411 | **0.19447** | TTM |
| NVTS | ‑1,478,000 | 45,916,000 | 36,535,000 | 0.03219 | **0.04045** | TTM |
| 1833.HK | ‑39,923,000 | 5,468,174,000 | 5,449,814,016 | 0.00730 | **0.00733** | TTM (close to FY here) |
| SLX.AX | ‑107,663 | 13,283,319 | 18,865,644 | 0.00811 | **0.00571** | TTM |

`capex_to_revenue` = `|capex_fy (statement, FY)| / info.totalRevenue (TTM)` — confirmed to match exactly for all 7 (the
one place FY and TTM happen to be close is 1833.HK). This mixes two different accounting periods and is up to ~25%
off the FY/FY ratio (e.g. NVTS: 4.05% reported vs 3.22% on an FY/FY basis). It also silently drops the sign
(`capex_fy` is negative in every row; `capex_to_revenue` is positive) — worth a one-line note in
`Sources_Assumptions` so a reader doesn't read the sign flip as an error. Not large enough to move any name across a
materiality threshold, hence minor.

---

## 7. P/E trailing & forward — Finding #1 (major)

```python
info = json.load(open(f"data/info/{t}.json"))
tpe, eps = info["trailingPE"], info["trailingEps"]
live_price = info["regularMarketPrice"]      # as fetched 2026-09-14
sept11_close = info["previousClose"]          # = raw Close on 2026-09-11 exactly, confirmed
implied_live   = live_price/(100 if ccy=="GBp" else 1)/eps
implied_sept11 = sept11_close/(100 if ccy=="GBp" else 1)/eps
```

| Ticker | trailingEps | Live price (fetched 2026‑09‑14) | Sept‑11 close | Table `trailing_pe` | = price/EPS using **live** price | = price/EPS using **Sept‑11** close |
|---|---|---|---|---|---|---|
| RR.L | 0.36 | £14.238 | £14.546 | 39.55 | **39.55 (matches)** | 40.41 |
| PLTR | 1.17 | $173.31 | $167.23 | 148.13 | **148.13 (matches)** | 142.93 |
| ASML.AS | 25.43 | €1387.80 | €1478.40 | 54.57 | **54.57 (matches)** | 58.14 |
| 1833.HK | 0.25 | HK$6.16 | HK$6.125 | 24.64 | **24.64 (matches)** | 24.50 |
| ONT.L, NVTS, SLX.AX | negative EPS | — | — | `NaN` (correctly blank, loss-making) | — | — |

`info['previousClose']` equals the raw Sept‑11 `Close` exactly for every name checked, confirming the fetch date was
2026‑09‑14 and Yahoo's `trailingPE`/`forwardPE` fields are computed off `regularMarketPrice` as of that live fetch,
**not** the Sept‑11 "price as at" date used everywhere else in the row (`price_gbp`, the 52‑week stats, YTD). The
gap is 2–8% on the multiple across the 4 profitable names in this sample — not large, but a genuine as-of-date
mismatch inside a single row of the fundamentals table, present in every row with a computable P/E. Recommend
recomputing trailing/forward P/E as `price_gbp (Sept‑11) / EPS` rather than taking Yahoo's live-computed field.

---

## 8. β_own (5y daily vs VWRP.L, GBP), CAPM Ke — no issue found (checked, correct)

```python
px = pd.read_csv("data/prices_gbp_daily.csv", index_col=0, parse_dates=True)
start, end = pd.Timestamp("2021-09-13"), pd.Timestamp("2026-09-11")
r = px[[t, "VWRP.L"]].loc[start:end].dropna().pct_change().dropna()
beta = np.cov(r[t], r["VWRP.L"])[0,1] / np.var(r["VWRP.L"], ddof=1)
Ke = 0.0375 + beta * 0.0417
```

| Ticker | n (daily obs, overlap with VWRP.L) | Own β | Table `beta_own_vs_vwrp` | Own Ke = rf+β·ERP | Table `cost_of_equity_capm` |
|---|---|---|---|---|---|
| RR.L | 1,259 | 1.3124 | 1.3124 | 0.092227 | 0.092227 |
| PLTR | 1,259 | 1.4468 | 1.4468 | 0.097830 | 0.097830 |
| ASML.AS | 1,259 | 1.9236 | 1.9236 | 0.117715 | 0.117715 |
| ONT.L | 1,246 | 1.3534 | 1.3534 | 0.093936 | 0.093935 |
| NVTS | 1,232 | 2.0258 | 2.0258 | 0.121977 | 0.121976 |
| 1833.HK | 1,259 | 0.6661 | 0.6661 | 0.065277 | 0.065278 |
| SLX.AX | 1,259 | 1.1167 | 1.1167 | 0.084067 | 0.084068 |

Exact match on β_own for all 7 names, and Ke reproduces `rf + β·ERP` to 5–6 d.p. using rf=3.75% and Damodaran
ERP=4.17% from `market_params.json`. (β+/β− were spot-checked too — within ~3% of the table, consistent with the
brief's stated methodology of splitting on **benchmark excess return** rather than raw benchmark return as I did
for this quick check; not flagged, as this was outside the requested check list and doesn't affect Ke.)

---

## 9. YTD (GBP) — no issue found (checked, correct)

```python
px = pd.read_csv("data/prices_gbp_daily.csv", index_col=0, parse_dates=True)
v0 = px[t].loc[:"2025-12-31"].dropna().iloc[-1]
v1 = px[t].loc[:"2026-09-11"].dropna().iloc[-1]
ytd = v1/v0 - 1
```

| Ticker | Own YTD (GBP) | Table `ret_ytd` | Table `ytd_return_gbp` |
|---|---|---|---|
| RR.L | 27.5291% | 27.5291% | 27.5291% |
| PLTR | ‑6.2117% | ‑6.2117% | ‑6.2117% |
| ASML.AS | 58.8263% | 58.8263% | 58.8263% |
| ONT.L | 22.1963% | 22.1963% | 22.1963% |
| NVTS | 62.3773% | 62.3773% | 62.3773% |
| 1833.HK | ‑57.0626% | ‑57.0626% | ‑57.0626% |
| SLX.AX | ‑42.6027% | ‑42.6027% | ‑42.6027% |

Exact match for all 7.

---

## 10. `data/combined_positions.csv` — no issue found (checked, correct)

```python
df = pd.read_csv("data/combined_positions.csv")
assert (np.floor(df.gbp/df.price_gbp) == df.shares).all()
```

- **shares = floor(£/price_gbp)**: exact match, 0 mismatches across all 54 rows (14 core + 40 unicorn).
- **Total £ target (`gbp` column) sums to £199,999.99999999994** ≈ £200,000 (floating-point rounding only).
  Actual invested capital (`shares × price_gbp`) sums to **£199,004.17**, leaving **£995.83 residual cash** from
  share-count flooring — consistent with "£200,000 ± residual cash."
- **40 unicorn rows**, each with `gbp == 1000.0` exactly → **£40,000** unicorn sleeve, matches the 20%/£40,000 spec.
- **14 core rows**, `gbp` sums to **£159,999.99999999994** ≈ £160,000; `weight_of_sleeve` sums to 1.0 and
  `weight_of_sleeve × 160,000` reproduces the `gbp` column exactly for every core row.
- **SPCX**: `gbp = £4,000.00`, `weight_of_sleeve = 0.025` (2.5% of the £160,000 core) — matches
  `SPEC_ANALYSIS.md` §5's binding policy weight exactly. 35 shares at £111.930188 = £3,917.56 invested, £82.44 residual
  from flooring.
- **ASML.AS is absent from `combined_positions.csv`** — checked against `data/weights.csv`: ASML.AS received
  **0.0% weight in Moderate12** (the headline optimised portfolio: `MinVariance=0.0, MaxSharpe≈3.2e‑16, Moderate12=0.0,
  MaxSortino=0.0`; only `EqualWeight=2.71%` and `NaiveReference=0.75%` are non-zero), so `floor(£0/price)=0` shares —
  correctly and legitimately excluded from the headline position list, not a data error. Its `weights.csv` price_gbp
  (1270.616171862681) matches my independent Sept‑11 price_gbp for ASML.AS exactly.

---

## Reproducing this check

All code above ran against `/usr/bin/python3` with pandas 2.3 / numpy 2.0, reading only the files listed in the task
brief. No file under `scripts/` was opened. Working script saved at
`/private/tmp/claude-501/-Users-georgewilliams-Desktop-Claude-Projects-Investing-101/0a2ff4be-227a-46ed-8c9b-f9d54feff8e2/scratchpad/verify_fundamentals.py`
if the parent session wants to re-run or extend it.
