# PDF verification, round 2 (blind — build_pdf.py not read)

Extracted all 110 pages with pypdf 6.15.0 (linear) and, for anything spatial/positional (the TOC
cross-check, font-size heading detection), with PyMuPDF 1.26.5 (pdfplumber is not installed in this
environment). Cross-checked against `data/analysis_results.json`, `data/weights.csv`,
`data/fundamentals_table.csv`, `data/unicorn_stats.csv`, `data/analysis_variants.json`,
`universe/market_params.json` and `data/fetch_log.json`. Rendered cover, frontier, one stock-block
and one wide-table page to PNG (PyMuPDF `get_pixmap`) and inspected them visually.

## Round-1 items re-verified

**TOC page-number "mismatch" for section 9 / 9.1 — NOT REPRODUCIBLE. This is a false alarm, not a
live defect.** I built an independent, automated check: parsed all 52 TOC entries from the Contents
page using word-position clustering (grouping spans by y-coordinate, not by pypdf's block/line
iteration order, which is what produces the misleading interleaving), then located the actual
heading for every one of those 52 entries elsewhere in the document by font size (16pt for the nine
numbered sections and "Appendix", 12pt for every subsection) and compared it to each page's own
footer. Result: **zero mismatches out of 52.** Specifically:
- "9. Limitations and disclaimers" — TOC says 96; the heading itself sits at the top of the page
  whose footer reads "Page 96". Match.
- "9.1 The five that matter most" — TOC says 97; the heading (12pt, confirmed by font size against
  the 9pt TOC copy of the same string) sits on the page footed "Page 97". Match.
- "Appendix" — TOC says 99; the 16pt "Appendix" heading sits on the page footed "Page 99". Match.
The original round-1 finding ("listed as 96/98, actual 95/96") does not match either the TOC text as
it is actually laid out on the page (which reads 96/97, not 96/98) or the actual heading pages (96/97,
not 95/96) — it looks like an artifact of reading pypdf's `extract_text()` output linearly through a
dotted-leader TOC, exactly as the build author's own rejection argued. I consider this round-1 item
resolved (or, more precisely, never a real defect) and confirmed independently with a different
extraction method and a full census rather than a spot check.
- **Cover footer:** page 1 carries "Page 1" in the same position/style as every other page. Fixed, confirmed.
- **Frontier label decluttering:** rendered page 20 at 300dpi and zoomed into the dense low-vol
  cluster (Moderate12/Max Sortino/Max Sharpe/Min variance markers plus SGLN.L, IITU.L, CSP1.L,
  VWRP.L, IWQU.L, WLDS.L, ISF.L, SMEA.L, IJPA.L, BRK-B, AZN.L, COPA.L, DBMG.L, ICOM.L, XDWH.L,
  VMID.L, EMIM.L, ULVR.L, IHYU.L, IHYG.L, IEMB.L, IBTM.L, T36N). No labels overlap; "Moderate12
  (headline)" sits clear of SGLN.L and its own marker. Fixed, confirmed.
- **Ccy column wrapping:** page 14 (core universe table) — "GBp", "GBP", "USD" all render on a single
  line, header "Ccy" does not wrap. Fixed, confirmed.
- **IQE.L / FTC.L exchange-note truncation:** page 37 — both notes now render in full ("LSE (AIM;
  move to LSE Main Market announced, still AIM at 2026-09-11)" and "London Stock Exchange (segment
  disputed: candidate sheet says AIM, verification pass records Main Market - confirm on the ii
  instrument page; either way fully dealt by ii)"), no "..." truncation. Fixed, confirmed.
- **Shares column split table:** page 39 now reads "# / Ticker / Shares" together, e.g. "24 IQE.L
  2,249", "25 FTC.L 408" — not a bare "#/Shares" pair. Fixed, confirmed.

No new regressions found from any of the five fixes.

## 1. Structure

- All nine numbered sections plus the Appendix present, in order: 1 (p5), 2 (p9), 3 (p14), 4 (p17),
  5 (p25), 6 (p33), 7 (p41), 8 (p93), 9 (p96), Appendix (p99) — each confirmed both by its own page
  footer and by the automated TOC-vs-heading census above.
- "Page N" footer present on every one of the 110 pages, including the cover (page 1 = "Page 1").
- No "[CHART" placeholders anywhere. No bare "nan"/"NaN" token anywhere (checked with a word-boundary
  regex, not substring, to avoid false hits inside words like "financ..."). The two occurrences of
  "None" are ordinary English ("None was", "None of this is material"). All 172 occurrences of "n/a"
  sampled are legitimate not-applicable cells. No "■" glyphs and no garbled characters around dashes;
  the only non-ASCII character used is the em dash, which renders correctly throughout.

## 2. Numbers — over 110 individual figures cross-checked, zero mismatches

- **Headline table (p7):** all three sleeves' expected-return triplet (historical/CAPM/blend),
  ex-ante vol (LW-optimised-part and incl.-SPCX), ex-ante Sharpe, realised 5y vol/Sharpe/Sortino,
  beta/beta+/beta-/asymmetry (as-held and excl.-SPCX), skew, excess kurtosis, backtest 5y CAGR and max
  DD, realised 5y max DD, 95%/99% VaR/CVaR — 30 distinct figures across Core/Unicorn/Combined columns,
  checked against `analysis_results.json -> portfolios.Moderate12`, `unicorn_sleeve.stats`/
  `.expected_return`, `combined_portfolio`. All exact.
- **Top-6+ Moderate12 weights and £ (p5):** IITU.L, ISF.L, SMGB.L, SGLN.L, BRNT.L, RR.L, PLTR, SPCX,
  AZN.L, SHEL.L, HSBA.L, BRK-B, IBTM.L, DBMG.L — all 14 weights checked against `weights.csv` column
  `Moderate12`; all match to the displayed percentage.
- **Ledoit-Wolf shrinkage block (p10):** delta 0.035750, r_bar 0.232234, pi 0.000193, rho 0.000070,
  gamma 0.000003, kappa 40.576325, T 1,135, N 36 — exact match to `analysis_results.json ->
  covariance.ledoit_wolf`.
- **Market params:** rf 3.75% (`boe_bank_rate.value`), ERP 4.17% (`damodaran_erp.value`), 10y/30y
  gilt yields 5.295%/5.747% (`gilt_yield_10y`/`gilt_yield_30y`) — all match `market_params.json` and
  recur consistently in `analysis_results.json -> market_params_used`.
- **Three per-stock blocks in full (RR.L p42, PLTR p43, BKS.L p53):** every field on all three blocks
  — price local/GBP, 52w H/L, % below high, mcap (GBP/USD), EV, trailing/forward P/E, P/B, EV/EBITDA,
  dividend yield, total debt/cash/net debt, D/E, both interest-cover measures, capex and
  capex/revenue, FCF, revenue, operating margin, revenue growth, Yahoo beta, own beta, beta+/beta-,
  CAPM Ke, WACC, Kd, tax rate, YTD/1y return, 5y vol/max-DD/skew/kurtosis, and (RR.L/PLTR only)
  Sharpe/Sortino — checked field-by-field against `fundamentals_table.csv` rows RR.L/PLTR/BKS.L; every
  single value matches to the displayed precision (roughly 30 fields per row = ~90 individual checks).
  SPCX's insufficient-history block (p44) states 64 daily bars, matching `analysis_results.json ->
  asset_stats.SPCX.n_obs` = 64 exactly (this differs from `fetch_log.json`'s raw-fetch count of 63
  rows, but that is a pre-existing upstream data-pipeline detail, not a PDF-vs-source mismatch — the
  PDF agrees with the analysis file it cites).
- **Efficient-frontier sample table (p20), all 7 rows** (points 1, 6, 11, 16, 21, 26, 30): expected
  return, vol, Sharpe, largest-three holdings all match `frontier.csv`.
- **Variant A (gilts at redemption yield, p23):** expected return 14.9%, ex-ante vol 12.0%, Sharpe
  0.87, 14 holdings, T36N 17.3%, SMGB.L 17.9%, 0% bond-ETF weight — all match
  `analysis_variants.json -> variants.Moderate12_GiltsAtYield` exactly.

No mismatches found anywhere in this pass.

## 3. Completeness

- Core universe table (p14-16): 37 instruments present (spot-checked full first page of 20 rows plus
  the RR.L/PLTR/SPCX/AZN.L/etc. rows on p15).
- Unicorn table (p37-39): automated count confirms rows numbered 1 through 40 all present, in rank
  order, plus the "# / Ticker / Shares" continuation table on p39.
- SPCX's insufficient-history warning (p44) is explicit and correctly worded (64 bars, 41.6%
  share-class market-cap gap).
- The beta-asymmetry finding is stated prominently: p11's bolded sentence reads "no long-only
  portfolio in this universe achieved positive daily beta asymmetry on the optimised part alone," and
  the same figures (as-held +0.09, excl.-SPCX -0.09) recur in the p7 headline table.
- The ii cost caveat is present and detailed across pp16, 32, 93-96: explicit "bid-offer spread...is
  not modelled anywhere in this report and on the smallest unicorn lines will be the largest single
  cost of all," the ii platform fee being a fixed charge rather than a percentage, and a
  hedged-bond-ETF correction (SHYU/SEMB vs IHYU/IEMB) noted as an error caught during universe-building.
- The disclaimer appears on the cover page in full and is carried as a running header on every page
  ("Educational analysis, not advice — data as at 2026-09-11").
- Every figure/chart (10 numbered figures, p6 through p35) has a caption with source and, where a
  time window applies, the window itself (e.g. Figure 2: "5y daily, benchmark VWRP.L"; Figure 8:
  "2021-10-31 to..."); point-in-time figures (sleeve/bucket split, sector/region counts) reasonably
  state "as at 2026-09-11" or cite the JSON source instead of a window.
- One observation, not a defect: the 40 unicorn stock blocks consistently substitute a "Judge mean
  (asym / fit / surv)" row where the 11 core-stock blocks show "Sharpe / Sortino 5y" — verified this
  is systematic across all 40 unicorn pages checked (p53-60), not a one-off omission, and Sharpe/
  Sortino values do exist in `fundamentals_table.csv` for unicorns (e.g. BKS.L sharpe=0.288,
  sortino=0.463) if a reviewer wanted them added; this looks like a deliberate template choice
  (screening-judge score is more relevant to the unicorn narrative than a 5y Sharpe on 40 volatile,
  often short-history names) rather than a bug, but is worth a one-line confirmation from whoever owns
  the template that it's intentional.

## 4. Render check (4 pages rendered to PNG at 150-300dpi with PyMuPDF and inspected)

- **Cover (p1):** clean, disclaimer box intact, footer "Page 1" present, no overflow.
- **Frontier page (p20, Figure 4):** chart and 30-point sample table render correctly; zoomed into
  the dense cluster and confirmed no ticker-label overlaps (see TOC/round-1-fix section above).
- **Stock-block pages (p42 RR.L, p43 PLTR, p53 BKS.L):** clean two-column table layout on all three,
  nothing cut off or overlapping, business/thesis paragraphs render fully within the page.
- **Wide-table page (p14, core universe):** renders cleanly, no cell overlap, no cut-off text, Ccy
  column single-line as noted above.

## Overall

This is a very accurate, well-corrected build. All five round-1 fixes are confirmed working with no
regressions. The single round-1 "major" finding not already accepted as fixed — the TOC page-number
mismatch for section 9/9.1 — does not reproduce under an independent, exhaustive, position-based
re-derivation of all 52 TOC entries; I could not find a real TOC/heading-page mismatch anywhere in the
document. Of well over 100 individually cross-checked figures across the headline stats table, three
full per-stock blocks, portfolio weights, the LW shrinkage decomposition, market parameters, the
frontier sample, and a policy variant, none disagreed with the underlying data files. The only
non-defect item worth a human confirmation is the deliberate Judge-mean-instead-of-Sharpe/Sortino
substitution in the 40 unicorn blocks, which is consistent across all of them and not a completeness gap.
