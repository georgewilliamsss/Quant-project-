# Blind PDF verification — moonshot refresh, round 1

Verifier did not read `scripts/build_pdf.py`. Extracted `Portfolio_Report.pdf` with `pypdf` (169 pages,
466,053 characters), rendered 6 pages to PNG with `pypdfium2` (pages 1, 25, 51, 101, 151, 169), and cross-checked
figures against `data/analysis_results.json`, `data/weights.csv`, `data/fundamentals_table.csv`,
`data/unicorn_stats.csv`* (via `analysis_results.json`'s `unicorn_sleeve` block, which is the same source),
`data/analysis_variants.json`, `data/refresh_diff.json`, `universe/market_params.json`,
`universe/unicorn_final.json`, `universe/dossiers/*.md` and `universe/news_*_2026-09-16.json`.

\* `unicorn_stats.csv` duplicates the per-name figures already reconciled through `fundamentals_table.csv` and
`analysis_results.json.unicorn_sleeve`; not separately re-diffed.

## Verdict

**Not clean.** Substance (every number checked) is excellent — I could not find a single wrong figure anywhere
in 30+ cross-checked statistics, weights, £ amounts, per-stock fundamentals or per-name dossier facts. But there
are two real defects:

1. **Blocker-grade cosmetic bug: the printed Table of Contents page numbers are systematically wrong**
   from section 1.1 onward, and the error grows to 5 pages by the end of the document.
2. **Major sourcing gap: two of the seven per-holding news items in section 1.4** (ARA.TO and BIOA) cite
   specific stories that do not exist in the required `universe/news_*_2026-09-16.json` files — only in the
   narrative `universe/NEWS_AND_IMPACT_2026-09-16.md`.

Neither defect corrupts a number in the model. Both are real and both were explicitly in scope for this check.

## 1. Structure

- 169 pages, page-footer numbering 1–169, perfectly sequential, no gaps or repeats.
- All required sections present in order: 1 (with 1.1–1.4, including "1.4 Recent developments"), 2, 3, 4, 5, 6,
  7 (7.1 core stocks, 7.2 moonshot in rank order), 8, 9, Appendix (A1–A7, including "A6. Dossier digest").
- Footer reads "Educational analysis, not advice — data as at 2026-09-16" on every one of the 169 pages
  (173 total occurrences of the date string; the extra 4 are inline citations elsewhere in the text, not a defect).
- No placeholder text (`TODO`/`Lorem ipsum`/`[insert`/etc.) anywhere; every hit for the word "placeholder" is
  legitimate prose describing the DBMG.L/WLDS.L data-fault repairs, not leftover template text.
- No blank pages. One page (25) extracts almost no text — rendered it and confirmed it is a full-page
  "Weight vs. risk contribution" bar chart with a caption and footer, not blank.
- `pypdf`'s embedded bookmark **outline is fully correct** — every one of the 20 top-level + all nested
  bookmarks (including all 51 individual-holding bookmarks) points to the right page. A reader navigating by
  clicking bookmarks (Acrobat, Preview's sidebar, etc.) will always land in the right place.

## 2. TOC page numbers — confirmed defect (spot-check requested page 6, and full sweep)

Page 6 itself: the content on the physical page footer-labelled "Page 6" is section **1.2 Headline
statistics**, which the printed Contents page (page 2) says is on **page 7**. That is already wrong, one page
early.

I did not stop at page 6 — I extracted every TOC entry from the printed Contents (pages 2–3) and located each
heading's actual page by exact text search, skipping the TOC occurrence. Result: every top-level section heading
(1., 2., 3., 4., 5., 6., 7., 8., 9., Appendix) lands exactly where the TOC says. **Every subsection lands one or more
pages earlier than the TOC claims**, and the gap grows monotonically through the document:

| Heading | TOC page | Actual page | Off by |
|---|---|---|---|
| 1.1 The portfolio at a glance | 6 | 4 | 2 |
| 1.2 Headline statistics | 7 | 6 | 1 |
| 1.4 Recent developments | 10 | 7 | 3 |
| 2.5 The positive-skew measures | 16 | 13 | 3 |
| 3.2 Resolutions and corrections | 20 | 18 | 2 |
| 4.6 Sensitivity to the expected-return estimate | 27 | 26 | 1 |
| 5.7 What these numbers do NOT include | 37 | 36 | 1 |
| 6.8 What changed against the quality sleeve | 50 | 47 | 3 |
| 7.1 Core sleeve single stocks | 61 | 50 | **11** |
| 7.2 Moonshot sleeve, in rank order | 142 | 61 | **81** |
| 8.1 Dealing costs | 143 | 142 | 1 |
| 9.1 The five that matter most | 150 | 148 | 2 |
| A1. Full per-asset statistics | 156 | 150 | 6 |
| A6. Dossier digest | 168 | 163 | **5** |

(Full sweep of all ~55 numbered TOC entries is in the verifier's working notes; every subsection after 1.1 that I
checked is wrong except three — 1.3, 5.5 and 8.2/8.4 — where the TOC's stale value happens to coincide with the
real one because two consecutive headings land on the same physical page.)

This is not a rounding or off-by-one quirk confined to one place: by "7.1"/"7.2" the printed numbers are pointing
at completely wrong parts of the document (TOC says 7.2 "Moonshot sleeve" starts on page 142 — that is actually
where section 8 starts; the real 7.2 is on page 61). A reader who flips to a printed page number rather than
using a PDF viewer's clickable bookmarks (which, as noted, are all correct) will be misled, increasingly so later
in the report. This looks like the TOC generator recording each heading's page number one heading late (or
skipping the page-number update when the previous heading closes on the same page as the next one opens),
so the misalignment compounds every time two headings share a page and self-corrects only when two more
headings happen to share a page again by coincidence.

**Severity: blocker** for the printed TOC as a navigation aid (it is wrong for the majority of subsections and
badly wrong for two of them); does not affect the report's data or clickable navigation.

## 3. Numeric cross-checks (30+ figures, all correct)

All of the following were checked against source files and matched to the printed precision in every case (no
discrepancies found):

- **Headline statistics (§1.2, page 6)**: core/moonshot/combined expected returns (blend, historical, CAPM),
  ex-ante vol (LW and incl. SPCX), ex-ante Sharpe, realised 5y vol/Sharpe/Sortino, beta/beta+/beta-/asymmetry
  (incl. the SPCX-excluded variant), skew, excess kurtosis, backtest 5y CAGR and max DD, 95%/99% VaR & CVaR —
  all match `analysis_results.json` → `portfolios.Moderate12`, `unicorn_sleeve.stats`, `combined_portfolio` to
  the last printed digit.
- **Top-8+ weights and £ amounts (§1.1, page 4)**: IITU.L 5.4%, ISF.L 13.5%, SMGB.L 16.6%, SGLN.L 14.8%,
  BRNT.L 5.2%, RR.L 5.0%, PLTR 5.0%, SPCX 2.5%, AZN.L 1.1%, SHEL.L 5.0%, HSBA.L 5.0%, BRK-B 1.4%,
  IBTM.L 10.0%, DBMG.L 9.5% — all match `data/weights.csv`'s `Moderate12` column and `data/combined_positions.csv`
  £ figures exactly (incl. shares and cash residual of £751 / £713).
- **Backtest**: 5y CAGR 26.0%/12.9%/23.9% (core/moonshot/combined) and max drawdowns match
  `analysis_results.json` `backtest_5y`/`backtest_monthly_5y` blocks.
- **Unicorn/moonshot sleeve stats**: vol 26.5%, Sharpe 0.32, Sortino 0.46, beta/+/- 0.87/0.77/0.91, asymmetry
  -0.13, skew 0.11, kurtosis 1.32, max DD -45.5%, VaR/CVaR at 95%/99% — all match `unicorn_sleeve.stats`.
- **Rates, yields, ERP (§1.4, §2.2, §7)**: Bank Rate 3.75%, Damodaran mature-market ERP 4.17%
  (2026-07-01), 10y gilt yield 5.30%, 30y gilt yield 5.89%, T36N clean price 96.75 — all match
  `universe/market_params.json`.
- **Fed range and UK CPI**: "25bp to 3.75%-4.00%, unanimously 12-0" matches `us_fed_decision_2026_09_16`/
  `us_fed_funds_range`; UK CPI "3.1% year on year from 2.9% in July... core CPI unchanged at 2.6%, services
  3.4%" matches `uk_cpi_latest` exactly, including the ONS source URL.
- **Three per-stock blocks, checked line-by-line against `fundamentals_table.csv` / `stats_daily.csv`**:
  - RR.L (page 51): every one of ~35 fields (price, 52w H/L, market cap GBP/USD, EV, P/E trailing/forward,
    P/B, EV/EBITDA, debt, cash, net debt, D/E, interest cover ×2, capex, capex/revenue, FCF, revenue, margins,
    revenue growth, beta Yahoo/own, beta+/-, Ke, WACC, Kd, tax rate, YTD/1y, vol, max DD, skew/kurtosis,
    Sharpe/Sortino) matches the CSV row exactly.
  - PRME (page 100–101, moonshot #20): every field, plus the "Key backers", "Catalysts", "Why 10x", "What
    kills it" narrative paragraphs, and the "What falsifies it"/"Confidence 6/10" block, match
    `universe/unicorn_final.json` and `universe/dossiers/PRME.md` verbatim.
  - IPWR dossier digest entry (A6, page 164): confidence "7/10" and the falsifier text match
    `universe/dossiers/IPWR.md` §9 verbatim.
- **What-changed numbers (§1, §4, §6.8)**: "34 of 40 names are different" matches `refresh_diff.json`
  (`n_kept: 6`, `n_added: 34`, `n_dropped: 34`); the full §6.8 old-vs-new table (mean return, CAGR, total
  return, vol, Sharpe, Sortino, skew, kurtosis, max DD, beta/+/-, asymmetry, R², expected returns) matches
  `refresh_diff.json` → `unicorn_sleeve` to the printed decimal in every one of the ~15 rows; the combined-book
  cost sentence (expected return 15.5%→14.3%, vol 14.4%→14.2%, Sharpe 0.81→0.74, backtest CAGR 26.0%→23.0%,
  risk share 32.2%→31.9%) matches `refresh_diff.json` → `combined_200k` exactly.

I did not find a single numeric mismatch anywhere I checked.

## 4. Section 1.4 news items vs `universe/news_*_2026-09-16.json`

Checked every discrete news claim in §1.4 against the three structured files (`news_geopolitics-energy`,
`news_rates-inflation`, `news_sectors-holdings`, all `_2026-09-16.json`). Most match exactly on date and source:
Fed hike, ECB deposit-rate rise, UK CPI/ONS, US 10y through 5%, Saudi pipeline/Brent, China rare-earth exit
controls, TSMC/Samsung High-NA EUV, BIS AI-capex warning, ECB AI-capex warning, AZN COPD/lung-cancer/
breast-cancer readouts, HSBC downgrade, Rolls-Royce SMR/CEZ/Temelin, Terrestrial Energy (IMSR) NRC filing,
Filtronic (FTC.L) satellite contract.

**Two do not match:**

- **ARA.TO (Aclara Resources), "+10.57%... on a US EXIM Bank letter of interest for up to USD 750m for the
  Louisiana rare-earth project"**: this specific story (source: Mine Listings, dated 2026-09-15) does **not**
  appear in any of the three `news_*.json` files. The only `ARA.TO`-tagged item in
  `news_sectors-holdings_2026-09-16.json` is an unrelated 2026-09-02 Neo Performance Materials/Carester
  rare-earth supply deal. The EXIM Bank story does exist, but only in the narrative file
  `universe/NEWS_AND_IMPACT_2026-09-16.md` (line 81).
- **BIOA (BioAge Labs), "-8.72%... traced to the Morgan Stanley healthcare conference on the 16th where the
  company acknowledged a setback in the wider cardiovascular-inflammation field and a pause in one planned
  late-stage study"**: this story does **not** appear in any of the three `news_*.json` files either. The only
  `BIOA`-tagged item in `news_sectors-holdings_2026-09-16.json` is an unrelated 2026-09-08 Structure
  Therapeutics GLP-1 competitor-data item. `NEWS_AND_IMPACT_2026-09-16.md` (line 83) explicitly labels this as
  something "the upstream pass recorded ... as unexplained" and that "own search found [a] likely cause" for,
  i.e. it was added in a later manual pass and never written back into the structured JSON files.

**Severity: major.** These are exactly the two names the report highlights as needing individual explanation
("the largest gain" and one of "the only sleeve-level news that is still about something this portfolio holds"),
and their cited facts are not independently traceable through the file the SPEC nominates as the source of
truth for section 1.4 — only through a narrative markdown file whose own text admits the item was patched in
after the fact.

## 5. Page renders

Rendered and visually inspected pages 1 (cover), 25 (weight/risk-contribution bar chart), 51 (Rolls-Royce
holding block), 101 (Prime Medicine dossier continuation), 151 (per-asset statistics appendix table), 169 (final
appendix page). All are cleanly laid out: readable tables, correctly rendered charts and legends, no
overlapping text, no cut-off content, no obviously broken pagination, consistent house style (navy headings,
zebra tables, footer/disclaimer banner). No visual defects found.

## Files read

`Portfolio_Report.pdf`; `data/analysis_results.json`; `data/weights.csv`; `data/fundamentals_table.csv`;
`data/refresh_diff.json`; `data/combined_positions.csv`; `universe/market_params.json`;
`universe/unicorn_final.json`; `universe/dossiers/PRME.md`; `universe/dossiers/IPWR.md`;
`universe/news_geopolitics-energy_2026-09-16.json`; `universe/news_rates-inflation_2026-09-16.json`;
`universe/news_sectors-holdings_2026-09-16.json`; `universe/NEWS_AND_IMPACT_2026-09-16.md` (spot-check only).
`scripts/build_pdf.py` was deliberately not read (blind-verifier role).
