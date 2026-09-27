# `data/thesis/` — Portfolio thesis holdings

## Provenance

Transcribed from `Portfolio_Report.pdf` (repo root), the user's own uploaded document
("Two-Sleeve Portfolio: 80% Optimised Core / 20% Moonshot Sleeve — A GBP 200,000 model
portfolio for a UK investor on interactive investor"). Prices and statistics are as at
the close of **2026-09-16**; the report itself is dated 2026-09-17. See
`thesis_extract.md` (session scratchpad) for the full page-by-page extraction this file
was built from. This is a hypothetical/educational model portfolio, not a confirmed live
holding — the source document says so explicitly and repeatedly.

The user has since uploaded the actual build pipeline's output files at the repo root
(`combined_positions.csv`, `weights.csv`, `prices_gbp_daily.csv`, and others). Those are
authoritative for exact weights/positions and were used to reconcile and correct this
file — see "Reconciliation against `combined_positions.csv`" below.

## `thesis_holdings.csv`

54 rows: the 14 held core-sleeve lines ("Moderate12" portfolio) + the 40 equal-weighted
moonshot names. The four zero-weight core-universe names quoted in the report for
comparison only (ULVR.L, MSFT, ASML.AS, SIE.DE — each still had a "why it would be in the
core" rationale but is not part of the money actually allocated) are **excluded**.

| Column | Meaning |
|---|---|
| `ticker` | Yahoo-style ticker exactly as given in the thesis. |
| `name` | Company / fund name. |
| `sleeve` | `core` (80% of book, mean-variance optimised) or `moonshot` (20%, equal-weighted). |
| `exchange` | Listing venue. |
| `currency` | Currency of the listing itself, inferred from the ticker suffix (`.L`→GBP, no suffix→USD, `.AX`→AUD, `.TO`→CAD, `.BR`/`.PA`→EUR, `.ST`→SEK, `.SW`→CHF, `.HK`→HKD). Note the thesis's own price/statistics series is entirely GBP-denominated (rebuilt in GBP from first principles for every line, including non-GBP listings) — `currency` here describes the *listing*, not the currency the thesis reports prices in. Where `price_local` for a non-GBP-listed core line is in fact a GBP-converted figure taken from the thesis table, `notes` says so ("price quoted in GBP in thesis"). |
| `sector` | Sector/bucket label from the thesis. |
| `weight_total` | Decimal fraction of the whole GBP 200,000 book, to full precision (source: `combined_positions.csv`'s `weight_of_total` — the optimiser's own continuous per-line weight, pre-whole-share-rounding). Every moonshot line = 0.005 (each name is exactly 0.5% of the total book). |
| `weight_sleeve` | Decimal fraction within its own sleeve, to full precision (`weight_of_sleeve`). Every moonshot line = 0.025 (each name is exactly 2.5% of the GBP 40,000 moonshot sleeve). |
| `gbp_invested` | GBP actually spent on whole shares/units, to the penny (`invested_gbp`), for all 54 lines including moonshot (previously only available for core; the PDF table omitted per-line moonshot invested amounts). |
| `price_local` | Per-share/unit price (`price_gbp`), for all 54 lines including moonshot (previously blank for moonshot — the PDF's moonshot table omitted prices/shares for space; now filled from `combined_positions.csv`). |
| `shares` | Whole shares/units held (`shares`), for all 54 lines including moonshot (same fill as `price_local`). |
| `notes` | Short flags transcribed from the thesis: data-quality repairs, tradeability/venue risk, unverified claims, name substitutions, fixed/manual weights, etc. |

### Sleeve arithmetic

- **Core sleeve**: target 80% of GBP 200,000 = GBP 160,000. The optimiser's own weights
  ("Wt of core") sum to exactly 100.000% of GBP 160,000 (confirmed in the source to
  1e-06, and reconfirmed here from `combined_positions.csv`'s full-precision
  `weight_of_total`, which also sums to exactly 0.800000 across the 14 core lines).
  Turning those continuous weights into whole shares, the actual amount invested is
  **GBP 159,286.96** (≈ the PDF's rounded "GBP 159,287"; 99.554% of the GBP 160,000
  target), leaving **≈GBP 713** as unallocated rounding cash inside the core sleeve
  (0.446% of core, 0.3565% of the whole book). This file's `weight_total`/`weight_sleeve`
  columns hold the *model* weights (summing to exactly 0.8000 / 1.0000 for the core
  sleeve), not a weight recomputed from `gbp_invested`; the two differ by exactly the
  GBP 713 cash residual (`713 / 200,000 = 0.003565`), which is a pure whole-share-
  rounding artefact, not a data error. Reconciliation, reproduced with pandas:

  ```
  core weight_total sum (combined_positions.csv weight_of_total, full precision) = 0.800000
  core gbp_invested sum (combined_positions.csv invested_gbp)                    = 159,286.96
  implied weight from gbp_invested (÷200,000)                                    = 0.796435
  gap (≈ GBP 713 core rounding cash ÷ 200,000)                                    = 0.003565
  ```

- **Moonshot sleeve**: target 20% of GBP 200,000 = GBP 40,000, split equally across 40
  names at GBP 1,000 cost each (2.5% of the GBP 40,000 sleeve = 0.5% of the GBP 200,000
  total per name — "every position is GBP 1,000 regardless of rank"). 40 × GBP 1,000 =
  GBP 40,000 less GBP 38.29 of whole-share rounding cash (`combined_positions.csv` sums
  to GBP 39,961.71 actually invested, matching the PDF's rounded "GBP 39,962");
  `weight_total`/`weight_sleeve` in this file are the sleeve's flat target weights
  (0.005 / 0.025 each), which is also what the thesis itself reports at the sleeve level.

- **Whole portfolio**: total invested ≈GBP 199,248.67 (159,286.96 core + 39,961.71
  moonshot); total residual cash ≈GBP 751.33 (0.38% of GBP 200,000).

### Reconciliation against `combined_positions.csv`

After this file was first built from `Portfolio_Report.pdf`'s text tables alone, the
user separately uploaded the actual portfolio-construction pipeline's output files to
the repo root (`combined_positions.csv`, `weights.csv`, `prices_gbp_daily.csv`, etc.).
`combined_positions.csv` carries the same 54-ticker universe (ticker set matched
exactly, 54/54, no additions or removals) but at full floating-point precision, and —
critically — includes per-line price/shares/invested-GBP for the 40 moonshot names,
which the PDF's own moonshot table omitted for space. This file was rebuilt to prefer
`combined_positions.csv` wherever the two disagreed:

- **`weight_total` / `weight_sleeve`**: corrected on the 8 core lines whose PDF display
  percentage was rounded to 1 d.p. of core before this file's first build (IITU.L,
  ISF.L, SMGB.L, SGLN.L, BRNT.L, AZN.L, BRK-B, DBMG.L) — e.g. AZN.L's PDF-derived
  `weight_total` was 0.0088 (from "1.1%" of core, itself rounded) vs. the precise
  0.008621 in `combined_positions.csv`. The other 6 core lines (RR.L, PLTR, SPCX,
  SHEL.L, HSBA.L, IBTM.L) were already exact because their rounded core % coincides
  with a binding constraint (e.g. RR.L sits exactly at the 5% single-stock cap). All 40
  moonshot lines were already exact (0.005 / 0.025 flat).
- **`gbp_invested`**: corrected on all 14 core lines (previously rounded to the nearest
  whole GBP from the PDF text, e.g. IITU.L GBP 8,624 → GBP 8,623.73) and on 39 of 40
  moonshot lines (previously a flat GBP 1,000 placeholder; now the precise invested
  amount after whole-share rounding, e.g. IPWR GBP 998.96). One moonshot line
  (HYT.AX) rounds to exactly GBP 1,000.00 either way.
- **`shares` / `price_local`**: unchanged for the 14 core lines (already matched
  `combined_positions.csv` exactly — the PDF's own core table already gave the true
  share counts). Filled in for the first time for all 40 moonshot lines, which the PDF
  table had left blank.
- **Not changed**: `name`, `sleeve`, `exchange`, `currency`, `sector`, `notes` — these
  were outside the requested reconciliation scope (ticker set, `gbp_invested`, `shares`,
  `weight_total`) and were left as transcribed from the PDF. One discrepancy was
  noticed but deliberately **not** applied: `combined_positions.csv` classifies
  `currency` more finely than this file does — it distinguishes pence-quoted LSE lines
  (`GBp`) from pounds-quoted ones (`GBP`), and lists `BRNT.L` (WisdomTree Brent Crude
  Oil) as `USD`-quoted despite its `.L` suffix — whereas this file's `currency` column
  uses the simple suffix-inference rule described above (`.L`→`GBP` uniformly). Flagging
  this here for visibility rather than silently changing the column's semantics.
- 148 individual field values were corrected/filled across all 54 rows in total.
  `core weight_total` still sums to exactly 0.800000 and `moonshot weight_total` to
  exactly 0.200000 after reconciliation — the fixes corrected precision on individual
  rows without changing either sleeve total.

### The thesis's own price panel

The thesis's own GBP total-return daily price panel (the series the 169-page report's
own risk/return statistics, betas, VaR/CVaR, drawdowns and backtests are computed from)
**now lives at the repo root as `prices_gbp_daily.csv`**, uploaded by the user alongside
`combined_positions.csv` / `weights.csv` / `fx_daily.csv` / `prices_local_daily.csv` and
related files. A runner/backtest script built against this thesis should read prices
from `prices_gbp_daily.csv` (repo root) rather than from anywhere under `data/thesis/`.
This is exactly what `quantstack.thesis.run` does: its `DEFAULT_PRICES` points at the
repo-root file, and the CLI's `--prices` flag overrides it for a different panel.

This directory does not duplicate or move that file. (An earlier version of this
project attempted to build a stand-in proxy panel under `data/thesis/proxy/` from
unrelated third-party example datasets, because at the time this sandbox could not
reach any market-data provider and the thesis's own price panel was not yet available;
that stand-in is no longer needed now that the real panel exists at the repo root, and
has been removed.)
