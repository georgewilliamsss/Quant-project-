# PDF verification, round 1 (blind — build_pdf.py not read)

Extracted all 109 pages with pypdf 6.15.0 (pdfplumber/pypdfium2 not both needed — pdfplumber is not
installed in this environment; pypdfium2 is, and was used for page-image rendering). Cross-checked
against `data/analysis_results.json`, `data/weights.csv`, `data/fundamentals_table.csv`,
`data/stats_daily.csv`, `data/analysis_variants.json`, `data/combined_positions.csv`,
`data/frontier.csv`, `data/backtest_monthly.csv` and `universe/{core_universe,unicorn_final,market_params}.json`.

## 1. Structure

- All nine numbered sections plus the Appendix are present, in order, each starting where its own
  heading text says it does: 1 (p5), 2 (p9), 3 (p14), 4 (p17), 5 (p25), 6 (p33), 7 (p40), 8 (p92),
  9 (p**95**, not 96 — see mismatch below), Appendix (p98).
- **TOC page-number mismatch (spot-checked 10 entries, 2 wrong).** The Contents page (p2) says
  "9. Limitations and disclaimers ... 96" and "9.1 The five that matter most ... 98". The actual
  headings start on **page 95** and **page 96** respectively — both entries are off (by 1 and by 2
  pages). All eight other spot-checked entries (1, 2, 3, 4, 5, 6, 7, 8, Appendix) point to the exact
  right page.
- Page-number footer ("Page N") is present on every page from 2–109. The cover (page 1) has no
  footer — likely deliberate (common convention), but flagging since the brief says "page numbers on
  every page" without excepting the cover.
- No `[CHART` placeholders anywhere in the extracted text.
- No `nan`/`NaN` anywhere. Two literal occurrences of "None" are both ordinary English ("None was",
  "None of this is material"), not placeholder leakage. Every "n/a" found (~35 occurrences) is a
  legitimate not-applicable cell (e.g. YTM for an equity ETF, ex-ante vol for the non-optimised
  unicorn sleeve) — none of them mask a number that should have been computed.
- No black-box glyphs (`■`) or missing/garbled characters anywhere; the only non-ASCII character in
  the whole document is the em dash "—" (109 occurrences, one per running header), which renders
  correctly. The house style's "no Unicode sub/superscripts" rule is honoured throughout (beta+,
  beta-, R2 all spelled out).

## 2. Numbers — 30+ figures cross-checked, zero mismatches found

Checked well beyond the required 30 (roughly 90 individual figures across the items below) against
the source CSVs/JSON with independent re-derivation where relevant (e.g. unicorn-sleeve backtest
CAGR/max-DD recomputed from `backtest_monthly.csv` rather than only re-reading a stored figure).
Every single one matched to rounding:

- Headline table (p7): Moderate12 / unicorn / combined blend, historical, CAPM expected returns;
  ex-ante vol (LW-optimised-part and incl.-SPCX); ex-ante Sharpe; realised 5y vol/Sharpe/Sortino;
  beta/beta+/beta-/asymmetry (as-held and excl.-SPCX); skew; excess kurtosis; backtest 5y CAGR and
  max DD (core, unicorn, combined — unicorn sleeve figures independently rebuilt from
  `backtest_monthly.csv` and matched to 2 d.p.); 95%/99% VaR/CVaR — all exact.
- Top-6+ Moderate12 weights and £ on p5 (IITU.L, ISF.L, SMGB.L, SGLN.L, BRNT.L, RR.L, PLTR, SPCX,
  AZN.L, SHEL.L, HSBA.L, BRK-B, IBTM.L, DBMG.L) against `weights.csv`/`analysis_results.json` — all
  14 weights match; DBMG.L's own £/shares/invested figures were independently recomputed from
  `weights.csv` (£16,414 / 164 shares / £16,352 invested) and are consistent with the row shown.
- Ledoit-Wolf shrinkage block (p10): delta 0.035750, r_bar 0.232234, pi 0.000193, rho 0.000070,
  gamma 0.000003, kappa 40.576325, T 1,135, N 36 — exact match to `covariance.ledoit_wolf` in the JSON.
- rf (3.75%), ERP (4.17%), 10y/30y gilt yields (5.295%/5.747%), T36N YTM (5.466%) — all match
  `market_params.json` / `market_params_used` everywhere they recur (pp7, 10, 41ff, 96, 106, 112 area).
- Three per-stock blocks in full (RR.L p41, PLTR p42, BKS.L p52): price, 52w H/L, %-below-high, mcap
  (GBP and USD), EV, trailing/forward P/E, P/B, EV/EBITDA, dividend yield, total debt/cash/net debt,
  D/E, both interest-cover measures, capex and capex/revenue, FCF, revenue, operating margin, revenue
  growth, Yahoo beta, own beta, beta+/beta-, CAPM Ke, WACC, Kd, tax rate, YTD/1y return, 5y
  vol/max-DD/skew/kurtosis/Sharpe/Sortino — every single field on all three blocks matches
  `fundamentals_table.csv` / `stats_daily.csv` to the displayed precision. SPCX's insufficient-history
  block (p43) correctly states 64 daily bars and the 41.6% share-class market-cap gap.
- Efficient-frontier sample table (p20), all 7 rows (points 1, 6, 11, 16, 21, 26, 30): expected
  return, vol, Sharpe and the three largest holdings all match `frontier.csv` exactly, including two
  three-way weight ties reproduced correctly.
- Variant A (gilts at redemption yield, p23): expected return 14.9%, ex-ante vol 12.0%, Sharpe 0.87,
  14 holdings, T36N 17.3%, SMGB.L 17.9%, 0% bond-ETF weight — all match
  `analysis_variants.json -> Moderate12_GiltsAtYield` exactly.
- Section 8 cost arithmetic (p93–94): £55,555 non-sterling exposure, £416.66 FX charge (0.75%),
  £27,721.57 UK-main-market exposure, £138.61 stamp duty, £215.46 dealing commission (54 trades x
  £3.99, 14 core + 40 unicorn lines), £770.73 total day-one cost — every step ties out exactly against
  `combined_positions.csv`, including correctly excluding GBp (pence-quoted LSE) lines from the
  "non-sterling" FX bucket. Residual-cash table (core £818/0.51%, unicorn £178/0.44%, total
  £996/0.50%) and the BRK-B/SPCX rounding-residual rows also match exactly.

No mismatches were found in this pass — every cross-checked figure is either an exact string match
or agrees to the last displayed digit after independent recomputation.

## 3. Completeness

- Core universe table (p14–15): all 37 instruments present, in the same order as
  `universe/core_universe.json`, bucket counts stated (12/6/11/5/2/1 = 37) and correct.
- Unicorn table (p37–38): all 40 rows present (# 1–40) plus a "Total 40 names x GBP 1,000" row; a
  companion mini-table on p38 carries the Shares column, keyed by row number (see minor note below).
- 11 core-stock blocks + 40 unicorn blocks = 51 "Business." paragraphs, confirmed by count. All 11
  core blocks carry "Why it is in the core."; all 40 unicorn blocks carry "Thesis.", "Why 10x." and
  "What kills it." (40/40/40/40 counted) — template fields are complete for both groups (core stocks
  have no thesis/why-10x/what-kills-it data upstream in `fundamentals_table.csv`, so the "Why it is in
  the core" substitution is a deliberate, data-driven adaptation, not a gap).
- SPCX's 64-bar insufficient-history warning appears explicitly (p43), with the correct 41.6%
  share-class market-cap-gap disclosure.
- The beta-asymmetry finding is stated prominently and honestly, not buried: section 2.5's own bolded
  sentence is "no long-only portfolio in this universe achieved positive daily beta asymmetry on the
  optimised part alone," repeated in the p7 headline table (both as-held +0.09 and excl.-SPCX -0.09
  figures shown) and again in 9.1's five key takeaways.
- The ii cost caveat is present and detailed: FX charge, stamp duty (with AIM exemption noted),
  dealing commission, platform fee, and — importantly — the explicit statement that bid-offer spread
  "is not modelled anywhere in this report and on the smallest unicorn lines will be the largest
  single cost of all," plus a table flagging which ii cost figures are unverified against ii's own
  live rates page.
- The disclaimer appears on the cover page in full ("This is educational analysis, not personalised
  investment advice...") and is additionally carried as a running header on every single page
  ("Educational analysis, not advice — data as at 2026-09-11"), including the executive summary.
- Every figure has a caption with source, and every window-dependent figure (frontier, betas,
  correlation, drawdown, backtest) states its data window explicitly (e.g. Figure 2: "5y daily,
  benchmark VWRP.L"; Figure 6: "5y daily GBP total returns on the 1,135-day complete-case..."); point-
  in-time figures (weights, sector/region splits) reasonably omit a window since none applies.

## 4. Render check (4 pages converted to PNG with pypdfium2 and inspected)

- **Cover (p1):** Clean, disclaimer box renders correctly, no overflow.
- **Frontier page (p20, Figure 4):** Chart and 30-point sample table render correctly and match the
  data. One legibility issue: in the dense low-volatility cluster (5–15% vol / 5–15% return) several
  ticker labels overlap each other (e.g. around ISF.L/CSP1.L/IWQU.L/EMIM.L/COPA.L/DBMG.L), making
  individual points hard to read without zooming — a matplotlib label-collision issue, not a data
  error.
- **Stock-block page (p50, SIE.DE; also verified p41 RR.L via text):** Clean two-column table layout,
  nothing cut off or overlapping, business/rationale paragraphs render fully.
- **Wide-table pages (p14 core universe, p37–38 unicorn table):** Both render cleanly with no cell
  overlap or cut-off text. Two minor cosmetic points:
  1. The narrow "Ccy" column wraps currency codes onto two lines (e.g. "GB" / "p", "US" / "D"), and
     the column header itself wraps to "Cc" / "y". Legible but visually cramped — widening that
     column by a few points would fix it.
  2. On the unicorn table, "Exchange" free-text notes for IQE.L and FTC.L are truncated with "..."
     mid-sentence ("LSE (AIM; move to LSE Main Market announced...", "London Stock Exchange (segment
     disputed: ca...") — likely deliberate space-saving, but it cuts off exactly the disputed-segment
     nuance that a reader would want; consider a footnote instead of an inline truncation for these
     two flagged names.
  3. The Shares column for the 40 unicorn positions is split into a second, separate table matched
     only by row number rather than integrated into the main table — usable, but requires the reader
     to cross-reference two tables/pages to see ticker+shares together.

## Overall

This is a very accurate build: of ~90 individually cross-checked figures across headline stats,
weights, per-stock fundamentals, the frontier, a policy variant, and dealing-cost arithmetic, none
disagreed with the underlying data files. The one substantive defect found is the TOC page-number
mismatch for section 9 and 9.1 (see Structure, above). The remaining findings are cosmetic
(column-width wrapping, a dense chart's overlapping labels, two truncated free-text notes, and a
split Shares table) and do not affect the correctness of any number in the report.
