# Portfolio_Report.pdf — round-2 blind verification (2026-09-17)

Verifier did not read `scripts/build_pdf.py`. Extraction via `pypdf`; page renders via `pypdfium2`. Report is 169 pages.

## Headline verdict on the two round-1 findings

| # | Round-1 finding | Status now |
|---|---|---|
| 1 | TOC page numbers systematically wrong from 1.1 onward; page-6 spot-check fails | **NOT RESOLVED** — still wrong, same pattern |
| 2 | Two per-holding news claims (7.2/1.4) cite stories absent from the structured JSON news DB, present only in the narrative `.md` | **PARTIALLY RESOLVED** — the two examples originally suspected (CEZ/Temelín early-works contract, "Italian Eurofighters" detail) are in fact present, embedded in JSON item `summary` fields, so they check out. But a **new/different instance of the same class of problem** was found: the "AI executives publicly called for slower frontier-model development" claim (section 1.4 and repeated in the 5.1/7.2 semiconductor commentary) has **no corresponding item anywhere in the three structured news JSON files** — it exists only in `universe/NEWS_AND_IMPACT_2026-09-16.md`. So the underlying defect class is not fixed, only the two originally-cited examples.

## 1. Structural checks

- Sections 1–9 + Appendix all present, in order, with 1.4 "Recent developments" and the required moonshot-rebuild framing on the cover page. ✓
- No blank pages found; no placeholder/lorem-ipsum text found in any extracted page. ✓
- Footer consistently reads "Educational analysis, not advice — data as at 2026-09-16" with correct "Page N", and N matches the physical page index throughout (checked pages 1, 6, 45, 169 by render). ✓
- **TOC page numbers**: built a full actual-vs-TOC page map for every top-level and sub-section by locating each heading's real page in the extracted text. Result: **every top-level section (1., 2., …, 9., Appendix) lands on the TOC-printed page**, but starting from 1.1 the TOC number is wrong, and the error is **cumulative/compounding** through the document:
  - 1.1: TOC says page 6, actually on page 4 (off by 2)
  - 1.2: TOC says 7, actually 6 (off by 1)
  - 1.4: TOC says 10, actually 7 (off by 3)
  - 4.1–4.6: each off by 1
  - 6.2–6.8: off by 1 to 4 (6.4 "The profile of the 40": TOC says 43, actually 39 — off by 4)
  - 7.1: TOC says 61, actually 50 (off by 11)
  - 7.2: TOC says 142, actually 61 (off by 81 — the entire 7.2 block, pp. 61–141, is misattributed to start at p.142)
  - A1–A7 (appendix): all off by 2–6
  - Full page-by-page mismatch table (54 headings checked, 15 exactly correct, 39 wrong) is reproducible from `data/analysis_results.json`-independent text search; see method note below.
- **Spot-check of page 6 (as the task requested)**: page 6's actual content is section **1.2 Headline statistics** (confirmed both by text extraction and by a rendered PNG of the page). The TOC lists 1.2 as page 7 and 1.1 as page 6. The spot-check therefore **still fails**, identically to round 1.

Method note: headings were located by normalising whitespace and substring-searching each TOC entry's text against every extracted page from page 4 onward, taking the first page a heading's text appears on (verified this does not false-match against the TOC's own listing since the TOC itself is confined to pages 2–3).

## 2. Number cross-checks (30 spot-checked against source files)

All of the following matched their source file exactly (to the displayed rounding):

- **Headline statistics table (1.2, page 6)** vs `data/analysis_results.json` (`portfolios.Moderate12`, `unicorn_sleeve.stats`, `combined_portfolio`): expected-return blend 15.4/10.0/14.3%, historical-5y 23.6/12.1%, CAPM/yield 7.2/7.9%, ex-ante vol 12.0%/12.8%, ex-ante Sharpe 0.91, realised vol/Sharpe/Sortino 12.1%/1.67/2.45, betas 0.79/0.85/0.77, asymmetry 0.08 (ex-SPCX −0.09), skew −0.49, kurtosis 2.71, backtest CAGR 26.0%, backtest max DD −3.8%, realised max DD −13.4%, VaR/CVaR 95% 1.13%/1.68%, 99% 1.96%/2.82% — **all match** `analysis_results.json` to the displayed precision.
- Benchmark VWRP.L 5y figures (71.2% return, 13.0% vol, −17.6% max DD) — consistent with the "combined GBP 200,000" column context; not independently re-derived here but internally consistent with the combined-portfolio beta/vol figures shown.
- **Weights table (4.2, page 22)**: DBMG.L row (MinVariance 12.9%, MaxSharpe 8.7%, Moderate12 9.5%, MaxSortino 8.8%, EqualWeight 2.7%, Naive 5.0%) matches `data/weights.csv` row DBMG.L exactly.
- **Frontier sample (4.3, page 23)**: points 1/6/11/16/21/26/30 (return/vol/Sharpe/top-3 holdings) — spot-checked structure and internal consistency (monotonic vol/return); format and top holdings consistent with `data/weights.csv` composition patterns (SGLN.L, ISF.L, IBTM.L, SMGB.L, IITU.L, BRNT.L all appear as core universe tickers).
- **Macro/rate inputs**: Fed funds range "3.75%-4.00%" (matches `universe/market_params.json` → `us_fed_funds_range.value`), UK CPI "3.1%" y/y with core 2.6% and services 3.4% unchanged (matches `uk_cpi_latest`), Damodaran mature-market ERP 4.17% as at 2026-07-01 (matches `damodaran_erp`, including the report's own note distinguishing it from the US-specific 4.09% monthly-implied series — this note is also reproduced correctly in the PDF at line ~798), Bank Rate 3.75% (matches `boe_bank_rate.value`), UK 10y/30y gilt yields 5.30%/5.89% (matches `gilt_yield_10y`/`gilt_yield_30y` to the reported precision — PDF's "10-year *fell* about 8bp to 5.30%" language is consistent with the JSON's own as-of note).
- **Payoff arithmetic block (6.6, page 45)**: cost = 40 × £1,000 = £40,000 = 20% of £200,000 — arithmetically correct; scenario table (0x/~1x/3x/10x/30x counts summing to 40 in each row: 28+10+2+0+0=40; 30+6+2+1+1=40; 30+5+2+2+1=40; 25+8+4+2+1=40) all sum correctly; sleeve values (£16,000/£52,000/£67,000/£70,000) consistent with the stated position counts and multiples.
- **Per-name dossier blocks (7.2)**: two names fully spot-checked verbatim against `universe/unicorn_final.json` and (for IPWR) implicitly against the dossier file referenced — **IPWR** (thesis, key backers, catalysts, why-10x, what-kills-it, 10x end cap $0.639bn, confidence 7/10, judge scores 8.4/7.8/8.5, weighted 8.24) and **BIOA** (key backers incl. the Novartis/Lilly caveat language, catalysts) both match `unicorn_final.json` **word-for-word**.
- Position sizing table (6.5, page 45): shares = floor(£1,000/GBP price) verified for spot-checked rows (e.g. BIOA: £1,000/£5.752 = 173.8 → 173 shares, matches); total invested £39,962 is plausible for 40 lines each ≤£1,000 with rounding-down.

No numeric discrepancy was found in any of the 30-plus values checked above.

## 3. News cross-check against structured JSON (section 1.4 and holding-level mentions)

Checked every distinct factual news claim named in 1.4 against `universe/news_geopolitics-energy_2026-09-16.json`, `news_rates-inflation_2026-09-16.json`, `news_sectors-holdings_2026-09-16.json`:

**Confirmed present in structured JSON** (date + source match): Fed 25bp hike to 3.75–4.00%, 12-0, "remaining elevated" language; ECB 25bp to 2.50%; UK CPI 3.1%/core 2.6%/services 3.4%; US 10y Treasury >5%; UK 30y gilt ~5.89%; Aramco/Saudi East-West pipeline drone strike and shutdown; Brent $108.75→$105.83; US SPR 285.0m barrels; Houthi capture of Hanish islands; NATO/Italian-Eurofighters drone shoot-down over Lithuania (the "Italian Eurofighters" and "carrying explosives" detail is in the JSON item's `summary` field, sourced to Al Jazeera, 2026-09-15) — **round-1's flagged item is in fact sourced correctly, just embedded in a summary rather than the headline**; SMGB.L −3.41%/ASML.AS −5.56%; China rare-earth licensing extension to samarium/gadolinium/lutetium; TSMC/Samsung High-NA EUV commitment; BIS and ECB AI-capex warnings; gold flat in GBP despite dollar fall; AZN.L COPD/lung-cancer/breast-cancer readouts; PLTR +4.25%; HSBA.L downgrade; **RR.L SMR early-works contract with CEZ for Temelín** (present in the JSON item's `summary` field, dated 2026-09-10, source nuclear-news.net — round-1's other flagged item is also, in fact, correctly sourced); SPCX lock-up; IMSR Graphite Topical Report (2026-09-10, Terrestrial Energy IR); ARA.TO EXIM Bank letter of interest (2026-09-15, Mine Listings); BIOA Morgan Stanley conference remarks (2026-09-16, Investing.com); FTC.L $8m mmWave contract (2026-09-16, ADVFN).

**Not found in any structured JSON item** (present only in the narrative file `universe/NEWS_AND_IMPACT_2026-09-16.md`, with no headline/source/URL of its own):
- "AI executives publicly called for slower frontier-model development on the 14th" — appears in the PDF at section 1.4 (page 7/8) and is echoed in the narrative MD's section-5 sector table and per-stock ASML note. No item in `news_sectors-holdings_2026-09-16.json`, `news_geopolitics-energy_2026-09-16.json` or `news_rates-inflation_2026-09-16.json` reports this event; the only semiconductor-adjacent items in the JSON are the TSMC/Samsung EUV commitment and the rare-earth control items. This is the same category of defect round 1 flagged (a specific news claim sourced only from the narrative synthesis file, not from the structured DB the SPEC designates as source of truth for section 1.4/7.2), even though the two specific examples round 1 cited turned out to be correctly sourced on closer inspection.

## Conclusion

- Round-1 issue 1 (TOC page numbers, page-6 spot-check) — **confirmed still broken**, same severity and pattern as before.
- Round-1 issue 2 (news sourcing) — the two originally-cited examples are false positives on re-inspection (they are sourced, just inside JSON `summary` text rather than a `headline` field), but a genuine instance of the same underlying problem remains: the AI-executives/frontier-model-slowdown claim in section 1.4 has no structured-JSON backing.
