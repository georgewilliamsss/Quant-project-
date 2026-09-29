# Binary Biotech / Pharma Catalysts, Oct 12 - Nov 13, 2026 (Bloomberg Global Trading Challenge)

Prepared 2026-09-29. **STATUS: PARTIAL / INCOMPLETE. Read the limitations block first.**

## 0. Limitations of this pass (important)

1. **WebFetch was blocked for every domain I tried** (MarketBeat, pdufa.bio, BiopharmaWatch, CatalystAlert, FDATracker, RTTNews, BioPharmCatalyst, Benzinga, TipRanks, TheraRadar, CheckRare, Assyro, fda.gov, sec.gov, federalregister.gov, globenewswire, biospace, nasdaq.com, finance.yahoo.com, stockanalysis.com and others): `EGRESS_BLOCKED`. `curl` to the same hosts also failed. So I could **not open any calendar page**. I only saw search-engine summaries of them.
2. **The session-wide WebSearch budget (200 calls) ran out after about 28 of my searches.** The remaining searches I planned (individual price/market-cap checks, Q4 readout verification, ESMO/AHA/ASH/SITC/AASLD abstract dates, the full October/November calendar rows) were refused. The list below is therefore **not the "definitive" list**. It is the verified core plus flagged leads.
3. **Prices and market caps are mostly UNVERIFIED.** The only price/market-cap figure I obtained is for Inovio (INO), from an undated search snippet. Nothing was fabricated. Where I did not see a number I say UNVERIFIED.
4. Upside, downside and probability figures are **my own estimates** from base rates and general biotech reaction patterns. They are not sourced facts. Items tagged `[model memory]` come from my training knowledge (cutoff around June 2026) and were not re-verified this session.
5. To finish the job, raise `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` and run the queries in Section 6.

Weekday check (computed): Oct 17 = Saturday, Oct 24 = Saturday, Oct 30 = Friday, Nov 1 = Sunday, Nov 13 = Friday, Nov 14 = Saturday, Nov 22 = Sunday, Nov 27 = Friday (day after US Thanksgiving), Nov 28 = Saturday. **FDA usually acts on or before the goal date and, when it lands on a weekend, usually on the preceding Friday.** So the Nov 14 (Saturday) goal dates below can resolve on Friday Nov 13, the last day of the competition. Early actions are also happening: Welireg + Lenvima was approved Sept 24, 10 days before its Oct 4 PDUFA.

---

## 1. Summary table (sorted by rough upside x probability; estimates are mine)

Mkt cap / price are UNVERIFIED unless stated. "In window?" = falls inside Oct 12 - Nov 13.

| # | Ticker | Company | Mkt cap | Price | Catalyst | Date | In window? | Est. upside | Est. downside | P(positive) | Notes |
|---|--------|---------|---------|-------|----------|------|-----------|-------------|---------------|-------------|-------|
| 1 | INO (NASDAQ) | Inovio Pharmaceuticals | ~$130M (undated snippet) | ~$2.44 (undated snippet) | BLA PDUFA, INO-3107 for adult recurrent respiratory papillomatosis (accelerated approval) | **Oct 30, 2026 (Fri)** | YES | +80% to +200% | -55% to -75% | ~55% | Only verified in-window, sub-$500M, single-asset PDUFA. Cash runway only "into Q4 2026", so a financing follows either outcome. |
| 2 | OCGN (NASDAQ) | Ocugen | UNVERIFIED | UNVERIFIED | Ph3 topline, OCU400 gene therapy, retinitis pigmentosa | "Q4 2026" (no exact date verified) | MAYBE (~35% chance it lands by Nov 13) | +80% to +300% | -50% to -70% | ~40% | Retail-favourite lottery ticket. Timing is the main risk. |
| 3 | VIR (NASDAQ) | Vir Biotechnology | UNVERIFIED | UNVERIFIED | Ph3 ECLIPSE 1 topline, tobevibart + elebsiran, hepatitis delta | "Q4 2026" | MAYBE (~25%) | +40% to +100% | -40% to -60% | ~65% | Mirum's brelovitug AZURE-1 (also HDV) reported Sept 28. Check that outcome for read-through. |
| 4 | PYPD (NASDAQ) | PolyPid | UNVERIFIED (micro-cap) | UNVERIFIED | NDA PDUFA, D-PLEX100 (surgical-site infection prevention), priority review | Nov 28, 2026 (Sat) | NO (15 days late) | +40% to +100% | -50% to -70% | ~75% | Run-up trade inside window, exit before Nov 13. Partnered with Azurity ($30M upfront/near-term). |
| 5 | IRD (NASDAQ) | Opus Genetics | UNVERIFIED (small-cap) | UNVERIFIED | sNDA PDUFA, phentolamine 0.75% (Ryzumvi) for presbyopia | **Oct 17, 2026 (Sat)**; action likely by Fri Oct 16 | YES (borderline: may resolve before positions must be entered) | +15% to +60% | -30% to -50% | ~85% | Label expansion on an already-approved drug, two positive Ph3s (VEGA-2, VEGA-3). Mostly priced in. Same date shown for Viatris "MR-141" on TipRanks. |
| 6 | TLSA (NASDAQ) | Tiziana Life Sciences | UNVERIFIED (micro-cap) | UNVERIFIED | Ph2a results, intranasal foralumab, non-active secondary progressive MS | "October 2026" | LIKELY | +50% to +200% | -40% to -60% | ~25-30% | BiopharmaWatch flags low probability. Ph2a, so pure lottery. |
| 7 | CAPR (NASDAQ) | Capricor Therapeutics | UNVERIFIED | UNVERIFIED | BLA PDUFA (extended from Aug 22), deramiocel, DMD | Nov 22, 2026 (Sun) | NO (9 days late) | +30% to +100% | -50% to -70% | ~42% (BiopharmaWatch PoA) | Delayed into Nov 22 via major amendment. Early action unlikely for a CRL-history cell therapy. |
| 8 | SVRA (NASDAQ) | Savara | UNVERIFIED (small/mid) | UNVERIFIED | BLA PDUFA (extended from Aug 22), MOLBREEVI (molgramostim), autoimmune PAP, priority review | Nov 22, 2026 (Sun) | NO (9 days late) | +20% to +50% | -40% to -60% | ~85% | FDA cited no safety/efficacy/manufacturing concerns in the extension letter. |
| 9 | PCVX (NASDAQ) | Vaxcyte | UNVERIFIED (mid/large) | UNVERIFIED | Ph3 OPUS-1 topline (VAX-31 adults: safety, tolerability, immunogenicity) | "Q4 2026" | MAYBE | +15% to +30% | -35% to -55% | ~75% | Big binary but not a doubling candidate. |
| 10 | AGIO (NASDAQ) | Agios | UNVERIFIED (mid) | UNVERIFIED | mitapivat FDA goal date (indication UNVERIFIED) | Nov 1, 2026 (Sun) per MarketBeat snippet | YES | +5% to +15% | -20% to -35% | ~85% | Mid-cap, low tail. |
| 11 | BTAI (NASDAQ) | BioXcel Therapeutics | UNVERIFIED (micro-cap) | UNVERIFIED | IGALMI PDUFA (indication ambiguous, see Section 3) | Nov 14, 2026 (Sat), UNVERIFIED | Borderline (Nov 13 Fri action possible) | +50% to +150% | -50% to -70% | ~30% | UNVERIFIED. Search snippet described a "low probability of approval". |
| 12 | CYTK (NASDAQ) | Cytokinetics | UNVERIFIED (mid/large) | UNVERIFIED | aficamten FDA goal date (indication UNVERIFIED) | Nov 14, 2026 (Sat), per MarketBeat snippet | Borderline | +5% to +10% | -10% to -20% | ~90% | Low value. |
| 13 | PHAR (NASDAQ ADS; PHARM Euronext Amsterdam) | Pharming Group | UNVERIFIED (~small/mid) | UNVERIFIED | Resubmitted sNDA PDUFA, Joenja (leniolisib), pediatric APDS age 4-11 (40/50 mg BID, >=27 kg) | Oct 24, 2026 (Sat) | YES | +5% to +15% | -15% to -30% | ~80% | Revenue-generating company, low tail. |
| 14 | GSK (NYSE/LSE) | GSK | mega-cap | n/a | NDA PDUFA, bepirovirsen, chronic hepatitis B | Oct 26, 2026 (Mon) | YES | ~0 to +2% for GSK | ~0 to -3% | ~80% | Big pharma, negligible move. Possible sympathy moves in small HBV names (see Section 3). |

Also seen but low value or outside the window: Tecentriq colon cancer (Roche, Oct 9, before window), ifinatamab deruxtecan ES-SCLC (Merck/Daiichi, October, exact date UNVERIFIED), satralizumab thyroid eye disease (Roche, October, exact date UNVERIFIED), BBP-418 (BridgeBio, Nov 27), Praxis relutrigine (Dec 27) and ulixacaltamide (Jan 29, 2027).

---

## 2. FDA Advisory Committee meetings found in the window

| Date | Committee | Topic | Tradable? | Source |
|------|-----------|-------|-----------|--------|
| Oct 1, 2026 | VRBPAC | 2027 Southern Hemisphere influenza strain selection | No (before window, routine) | https://www.fda.gov/advisory-committees/advisory-committee-calendar/vaccines-and-related-biological-products-advisory-committee-october-1-2026-meeting-announcement |
| **Oct 30, 2026**, 8:30am-3pm ET, White Oak, hybrid | Dermatologic and Ophthalmic Drugs AdComm | NDA 219694, **atropine sulfate ophthalmic solution 0.01% (SYD-101), Sydnexis**, slowing myopia progression in children >=3 | Sponsor Sydnexis appears to be privately held `[model memory, UNVERIFIED]`, so no direct ticker. Possible sympathy in other myopia/atropine names. | https://www.fda.gov/advisory-committees/advisory-committee-calendar/october-30-2026-dermatologic-and-ophthalmic-drugs-advisory-committee-meeting-announcement-10302026 ; https://www.federalregister.gov/documents/2026/09/25/2026-19700/dermatologic-and-ophthalmic-drugs-advisory-committee-notice-of-meeting-establishment-of-a-public ; https://reviewofmm.com/fda-review-for-sydnexis-syd-101-scheduled-for-oct-30/ |

I found no other FDA AdComm for Oct/Nov 2026 in the searches I could run. The FDA calendar page itself was blocked, so **this is not confirmed to be exhaustive**. Re-check https://www.fda.gov/advisory-committees/advisory-committee-calendar.

---

## 3. Detailed sections

### 3.1 INO - Inovio Pharmaceuticals (NASDAQ): INO-3107, recurrent respiratory papillomatosis (RRP)  [TOP PICK, verified date]
- **Catalyst and date:** BLA under accelerated approval, PDUFA goal date **Oct 30, 2026 (Friday)**. BLA accepted Dec 2025. Per company commentary relayed in the Q2 2026 earnings summary, the FDA has completed the **late-cycle review meeting and all pre-licensure inspections**, and an "informal clinical meeting" was held where Inovio presented the totality of the data.
- **Price / market cap:** ~$2.44 and ~$129.66M per a search-engine snippet (the aggregator pages returned were Investing.com, TipRanks, TradingView, CNBC, WallStreetZen, Morningstar). **Undated. Re-check before trading.**
- **Why binary:** INO-3107 is the company's lead and effectively only near-term value driver. Cash runway was guided only **"into Q4 2026"** (Seeking Alpha headline), so approval would unlock financing and a CRL could be existential. Expect an equity raise in either case, so any pop can be partly diluted.
- **Competitive context** `[model memory, UNVERIFIED]`: a competing RRP therapy (Precigen's PRGN-2012, Papzimeos) received FDA approval in 2025, which raises the bar for INO-3107's evidence package. The "informal clinical meeting" suggests the FDA had clinical questions. Both cut P(approval) below the usual 85-90% base rate.
- **Historic reaction range (judgment):** micro-cap single-asset approval that the market prices at 40-60%: +50% to +200%. CRL: -55% to -80%.
- **Estimate:** upside +80% to +200%, downside -55% to -75%, P(approval) ~55%.
- **Sources:** https://seekingalpha.com/news/4564118-inovio-targets-october-30-pdufa-date-for-inominus-3107-approval-while-extending-cash-runway ; https://finance.yahoo.com/healthcare/articles/inovio-pharmaceuticals-inc-ino-q2-050345655.html ; https://ir.inovio.com/news/news-details/2025/FDA-Accepts-for-Review-INOVIOs-BLA-for-INO-3107-for-the-Treatment-of-Adults-with-Recurrent-Respiratory-Papillomatosis-RRP/default.aspx ; https://www.rrpf.org/news/fda-accepts-inovio-bla-ino-3107-adult-rrp
- **Cross-check status:** PDUFA date confirmed in 3 sources (Seeking Alpha, Yahoo Finance summary, RTTNews/Pulmonology Advisor October lists). Price NOT cross-checked.

### 3.2 OCGN - Ocugen (NASDAQ): OCU400, Ph3 liMeliGhT, retinitis pigmentosa
- **Catalyst:** Ph3 topline "expected in Q4 2026". This came from a search summary for "Phase 3 topline data expected fourth quarter 2026". The individual source page was not opened. Exact date UNVERIFIED. Probability it lands by Nov 13: ~35% (guess).
- **Why binary:** OCU400 is the lead asset. A clean Ph3 win would likely support a BLA and a re-rating. Failure or an ambiguous "trend" outcome typically produces -50% or worse.
- **Estimate:** upside +80% to +300%, downside -50% to -70%, P(positive) ~40%. Price and market cap UNVERIFIED.
- **Sources:** query results included https://curvedtrading.com/articles/en/investing/best-small-cap-biotech-stocks-2026-readouts/ and https://www.redchip.com/education/4-biotech-stocks-with-near-term-clinical-catalysts . Confirm against the company's Q2 2026 release.

### 3.3 VIR - Vir Biotechnology (NASDAQ): ECLIPSE 1 Ph3, hepatitis delta
- **Catalyst:** Ph3 ECLIPSE 1 topline (tobevibart + elebsiran combination) "expected in the fourth quarter of 2026" per the Q1 2026 corporate update. Exact date UNVERIFIED.
- **Read-through:** Mirum's brelovitug Ph3 AZURE-1 (HDV) topline call was scheduled **Sept 28, 2026**. The outcome was not visible to me. Check it, as it can move VIR either way.
- **Estimate:** upside +40% to +100%, downside -40% to -60%, P(positive) ~65% `[model memory: encouraging Ph2 data, not re-verified]`. Price and market cap UNVERIFIED.
- **Source:** https://investors.vir.bio/news/news-details/2026/Vir-Biotechnology-Provides-Corporate-Update-and-Reports-First-Quarter-2026-Financial-Results/default.aspx and https://www.biopharmawatch.com/blog/biotech-catalysts-to-watch-week-of-2026-09-28

### 3.4 IRD - Opus Genetics (NASDAQ): phentolamine ophthalmic solution 0.75% (Ryzumvi), presbyopia sNDA
- **Catalyst and date:** sNDA accepted Feb 2026, **PDUFA Oct 17, 2026 (Saturday)**. Approval or CRL could arrive Fri Oct 16 or earlier, i.e. possibly before positions must be entered. Supported by Ph3 VEGA-2 and VEGA-3 (met primary and all key secondary endpoints, no treatment-related SAEs).
- **Why less binary:** the drug is already approved for another indication (reversal of mydriasis), and presbyopia drops are a crowded category (competitors approved). Approval is largely expected. Sub-$300M-cap upside limited to the "sell-the-news vs. relief" range.
- **Same-date entry:** TipRanks calendar snippet lists Oct 17 for both "Mr-141 by VTRS" (Viatris) and phentolamine 0.75 by IRD. Likely the same molecule under a licensing arrangement `[model memory, UNVERIFIED]`.
- **Estimate:** upside +15% to +60%, downside -30% to -50%, P(approval) ~85%.
- **Sources:** https://ir.opusgtx.com/press-releases/detail/519/opus-genetics-announces-fda-acceptance-of-supplemental-new-drug-application-for-phentolamine-ophthalmic-solution-0-75-for-the-treatment-of-presbyopia ; https://www.globenewswire.com/news-release/2026/02/25/3244435/0/en/Opus-Genetics-Announces-FDA-Acceptance-of-Supplemental-New-Drug-Application-for-Phentolamine-Ophthalmic-Solution-0-75-for-the-Treatment-of-Presbyopia.html ; https://www.tipranks.com/calendars/fda

### 3.5 TLSA - Tiziana Life Sciences (NASDAQ): intranasal foralumab, na-SPMS, Ph2a
- **Catalyst:** results "expected in October 2026" per BiopharmaWatch's weekly catalyst blog. BiopharmaWatch rated probability of approval/success low. Exact date UNVERIFIED.
- **Estimate:** upside +50% to +200%, downside -40% to -60%, P(positive) ~25-30%. Price and market cap UNVERIFIED.
- **Source:** https://www.biopharmawatch.com/blog/biotech-catalysts-to-watch-week-of-2026-09-28

### 3.6 CAPR - Capricor (NASDAQ): deramiocel, Duchenne muscular dystrophy  [delayed INTO Nov 22, just outside window]
- **Catalyst and date:** BLA goal date **extended from Aug 22 to Nov 22, 2026 (Sunday)** after FDA classified submission of 24-month HOPE-3 open-label extension data and a refined indication (upper-limb function focus) as a **major amendment** (standard 3-month extension). BiopharmaWatch PoA: 42%.
- **Why binary:** deramiocel is the lead asset. The company previously received a CRL `[model memory: July 2025]`, and the FDA has been CRL-prone on cell/gene therapies with single-trial or CMC-heavy packages.
- **Window angle:** the decision falls 9 days after Nov 13. A run-up inside the window is plausible. Early action (before Nov 13) is possible but unlikely for a case that has already had a delay.
- **Estimate:** upside +30% to +100% (depends heavily on where the stock sits, UNVERIFIED), downside -50% to -70%, P(approval) ~42% (cited).
- **Sources:** https://www.capricor.com/investors/news-events/press-releases/detail/354/capricor-therapeutics-announces-extension-of-pdufa-target ; https://www.globenewswire.com/news-release/2026/08/24/3349793/0/en/capricor-therapeutics-announces-extension-of-pdufa-target-action-date-as-fda-continues-review-of-deramiocel-bla.html ; https://www.biopharminternational.com/view/fda-extends-deramiocel-pdufa-date-to-november-2026-after-capricor-submits-refined-dmd-indication ; https://cureduchenne.org/research/capricors-pdufa-date-for-fda-to-review-deramiocel-has-been-extended-to-november-22-2026/

### 3.7 SVRA - Savara (NASDAQ): MOLBREEVI (molgramostim), autoimmune PAP  [delayed INTO Nov 22, just outside window]
- **Catalyst and date:** BLA under **Priority Review**, goal date extended to **Nov 22, 2026 (Sunday)** in April 2026 after FDA judged responses to information requests a major amendment. Company says FDA cited no safety, efficacy or manufacturing concerns.
- **Estimate:** upside +20% to +50%, downside -40% to -60%, P(approval) ~85%. Market cap UNVERIFIED (I do not want to guess).
- **Sources:** https://investors.savarapharma.com/news/news-details/2026/Savara-Announces-the-U-S--Food--Drug-Administration-FDA-Has-Extended-the-Review-Period-for-the-Molgramostim-Inhalation-Solution-Molgramostim-Biologics-License-Application-BLA-in-Autoimmune-Pulmonary-Alveolar-Proteinosis-Autoimmune-PAP/default.aspx ; https://www.biopharminternational.com/view/fda-extends-review-of-savara-s-molgramostim-bla-for-pap

### 3.8 PYPD - PolyPid (NASDAQ; ticker from model memory, not seen in sources): D-PLEX100, prevention of surgical-site infection in colorectal surgery
- **Catalyst and date:** NDA accepted with **Priority Review**, **PDUFA Nov 28, 2026 (Saturday)**, about a quarter earlier than the company had guided. FDA identified no filing review issues. Post-acceptance, an exclusive US/Canada deal with **Azurity** delivered $30M upfront/near-term milestones, plus >$290M additional milestones and tiered royalties up to mid-20s %. Azurity targets an early-2027 launch.
- **Why interesting:** a micro-cap with a partner and priority review has better approval odds than a typical solo micro-cap. A run-up into the date is plausible, but the decision is after Nov 13.
- **Estimate:** upside +40% to +100%, downside -50% to -70%, P(approval) ~75%. Price and market cap UNVERIFIED.
- **Source:** https://www.globenewswire.com/news-release/2026/07/29/3335209/0/en/polypid-announces-fda-acceptance-of-nda-with-priority-review-for-d-plex.html ; https://www.sec.gov/Archives/edgar/data/0001611842/000121390026088040/ea030152801ex99-1.htm

### 3.9 PHAR - Pharming Group: Joenja (leniolisib), pediatric APDS
- **Catalyst and date:** resubmission seeking approval of 40 mg and 50 mg BID for children 4-11 weighing >=27 kg: **PDUFA Oct 24, 2026 (Saturday)**. A separate priority-review sNDA for lower doses (13-27 kg) has a **PDUFA of Jan 30, 2027**.
- Low tail (marketed product, ~$1B-scale company `[model memory, UNVERIFIED]`).
- **Sources:** https://www.sec.gov/Archives/edgar/data/0001828316/000182831626000041/pharmingannouncesusfdaacce.htm ; https://www.pharming.com/news/pharming-group-announces-us-fda-acceptance-priority-review-supplemental-new-drug-application-leniolisib-pediatric-APDS

### 3.10 GSK - bepirovirsen, chronic hepatitis B (big pharma, listed for completeness)
- **PDUFA Oct 26, 2026 (Monday).** NDA under FDA review for an antisense oligonucleotide targeting HBV RNA. Negligible move for GSK. Possible **sympathy candidates** in small-cap HBV names (e.g. Arbutus ABUS, Aligos ALGS, Assembly Bio ASMB) and Ionis (originator, royalty) `[model memory, UNVERIFIED; check before use]`.
- **Sources:** https://www.pulmonologyadvisor.com/news/october-2026-fda-pdufa-dates/ ; https://www.marketbeat.com/fda-calendar/upcoming/

### 3.11 PCVX - Vaxcyte: VAX-31 adult Ph3 OPUS-1
- Topline safety/tolerability/immunogenicity in **Q4 2026**, with further Ph3 trials in 1H 2027 (Aug 5, 2026 8-K). A big binary but a mid/large cap where a win adds tens of percent, not multiples.
- **Source:** https://www.sec.gov/Archives/edgar/data/0001649094/000164909426000041/pcvx-20260805xexx991.htm

### 3.12 AGIO (mitapivat, Nov 1) and CYTK (aficamten, Nov 14)
- Both dates come only from a MarketBeat-derived search summary ("Mitapivat (AGIO, Nov 1), Aficamten (CYTK, Nov 14), BBP-418 (BBIO, Nov 27), Deramiocel (CAPR, Nov 22), MOLBREEVI (SVRA, Nov 22)"). Indications for the AGIO and CYTK events were **not** shown. They look like supplemental indications on drugs already approved `[model memory: mitapivat and aficamten were approved Dec 2025, UNVERIFIED]`. Mid/large caps. Low tail.
- **Source:** https://www.marketbeat.com/fda-calendar/upcoming/

### 3.13 BTAI - BioXcel Therapeutics (ticker from model memory, not seen in sources): IGALMI
- A BiopharmaWatch summary gave "IGALMI PDUFA date **Nov 14, 2026**" with "low probability of approval for its Alzheimer's indication", while another BiopharmaWatch blog title references "IGALMI PDUFA for Agitation in Bipolar Disorder". **Indication and date are inconsistent across snippets: UNVERIFIED.** If real and if the FDA acts on Fri Nov 13, this would be an in-window micro-cap binary with low P(approval).
- **Sources:** https://www.biopharmawatch.com/blog/biotech-catalysts-to-watch-week-of-2026-09-28 ; https://www.biopharmawatch.com/fda-calendar

### 3.14 ALDX - Aldeyra Therapeutics: reproxalap (dry eye)
- CRL issued **Mar 16, 2026** (after PDUFA had been pushed from Dec 16, 2025). Aldeyra plans a **Formal Dispute Resolution Request** with a meeting with FDA's Office of New Drugs **in Q4 2026**. Not a clean binary in the window (FDRR outcomes are slow and rarely granted), but headline-driven volatility is possible. Low P(positive) for a reversal.
- **Sources:** https://ir.aldeyra.com/news-releases/news-release-details/aldeyra-therapeutics-announces-pdufa-extension-new-drug ; https://www.sec.gov/Archives/edgar/data/1341235/000119312526109511/aldx-20260317.htm

### 3.15 Events already past or just before the window (do not trade as catalysts)
- Belzutifan + lenvatinib (Merck/Eisai, RCC): approved Sept 24, 10 days before its Oct 4 goal date. https://www.morningglorysciences.com/en/belzutifan-lenvatinib-welireg-ccrcc-post-io-fda-2026-en/
- Tecentriq stage III dMMR colon cancer (Roche): Oct 9 (before window).
- Ameluz PDT (Biofrontera, BFRI): PDUFA Sept 28, BiopharmaWatch PoA 89%. Outcome unknown to me.
- Mirum (MIRM) brelovitug AZURE-1 HDV Ph3 topline: Sept 28 call. Outcome unknown to me.

---

## 4. Fall 2026 watchlist leads (UNVERIFIED events, tickers only)

BioPharmCatalyst's "Key Catalysts due in Fall 2026" watchlist names these tickers: **GALT, CNTB, BIVI, TENX, ACET, ONCY, GSK, SCYX, MPLT, MNOV**. I could not open the article, so I do not know the specific event or date for each. I also saw BiopharmaWatch mention **Connect Biopharma (CNTB) rademikibart Ph2/asthma exacerbations topline "expected soon"**. From memory only `[model memory, UNVERIFIED]`, plausible identities are:

| Ticker | Company | Possible event (model memory, UNVERIFIED) |
|--------|---------|------------------------------------------|
| GALT | Galectin Therapeutics | belapectin, NASH cirrhosis, follow-up/FDA path |
| CNTB | Connect Biopharma | rademikibart, acute asthma exacerbation Ph2 topline (per BiopharmaWatch) |
| BIVI | BioVie | NE3107 / bezisterim, Ph2 data |
| TENX | Tenax Therapeutics | oral levosimendan, Ph3 LEVEL in PH-HFpEF |
| ACET | Adicet Bio | CAR-gd T cells in autoimmune disease, early data |
| ONCY | Oncolytics | pelareorep, registrational planning/data |
| SCYX | SCYNEXIS | ibrexafungerp (GSK-partnered), Ph3 MARIO |
| MPLT | MapLight Therapeutics | ML-007C-MA, Ph2 ZEPHYR, schizophrenia |
| MNOV | MediciNova | MN-166 (ibudilast), Ph3 COMBAT-ALS |

The September 25, 2026 BioPharmCatalyst article "Key Phase 3 catalysts for the next 6 months" is likely the best single list to mine next: https://www.biopharmcatalyst.com/news/2026/september-25-2026-biopharmcatalyst-weekly-watchlist-key-phase-3-catalysts-for-the-next-6-months . Fall list: https://www.biopharmcatalyst.com/news/2026/biopharmcatalyst-weekly-watchlist-key-catalysts-due-in-fall-2026-and-other-near-term-events . Also seen but unread: https://maandhunter.substack.com/p/biotech-catalyst-watchlist-active .

Conferences (**all dates UNVERIFIED, from memory, confirm before use**): ESMO 2026 (late Oct), ACR Convergence (late Oct), ASN Kidney Week (late Oct/early Nov), AASLD The Liver Meeting (early Nov), AHA Scientific Sessions (early-mid Nov), ObesityWeek (Nov), SITC (Nov), ASH abstract publication (early Nov). Late-breaking abstracts are typically what create the +50% type moves. I could not verify any of these this session.

---

## 5. Top lottery tickets (provisional, ranked; low-confidence because coverage is partial)

1. **INO (Oct 30 PDUFA).** The single best verified fit: in window, ~$130M market cap (undated), single asset, accelerated-approval BLA with late-cycle and inspections done, cash runway short. Approval could plausibly double or triple the stock from a ~$2-3 base. CRL is likely -60% or worse. P(approve) ~55%. Highest expected tail of anything I could fully verify. Check price and any pre-decision run-up before sizing.
2. **OCGN (Ph3 OCU400, Q4 2026).** Largest possible upside (+80% to +300%) but timing is the risk, roughly one-in-three chance of reading out by Nov 13. Only worth holding if a fresh company update pins the date before Nov 13.
3. **TLSA (Ph2a foralumab, October).** Pure Ph2a lottery, likely in window, low probability but genuine multi-bagger potential if positive.
4. **VIR (ECLIPSE 1 Ph3, Q4).** Higher probability of success and mid-single-digit-billion-or-lower scale (UNVERIFIED), so +40% to +100% is the realistic range. Check the AZURE-1 outcome from Sept 28 first.
5. **IRD (Oct 17 PDUFA).** High P(approval) but mostly priced in. Moves are likely a smaller-percentage relief/sell-the-news. May resolve before the Oct 16 entry deadline. Low tail, lower priority.
6. **PYPD (Nov 28 PDUFA).** Outside the window but a partnered, priority-review micro-cap. Best used as a run-up trade, not a hold-through.
7. **CAPR (Nov 22 PDUFA, delayed into it).** Outside the window; 42% PoA per BiopharmaWatch. A run-up candidate only if it is still cheap. Early action before Nov 13 is unlikely.
8. **BTAI (IGALMI, Nov 14 per one snippet).** UNVERIFIED lead only. If verified and if FDA acts Fri Nov 13, this would be a true in-window micro-cap binary with low P(approval).

Honourable mentions (not tails): SVRA (Nov 22, ~85% approval, modest upside), PCVX (Q4, mid/large cap), PHAR (Oct 24, low tail), AGIO (Nov 1), GSK (Oct 26).

---

## 6. Dates just outside the window (Nov 14-30) and other leads

| Date | Ticker | Catalyst | Confidence |
|------|--------|----------|-----------|
| Nov 14 (Sat) | CYTK | aficamten FDA goal date (indication UNVERIFIED) | dated from MarketBeat snippet only |
| Nov 14 (Sat) | BTAI | IGALMI PDUFA (indication ambiguous) | BiopharmaWatch snippet only, UNVERIFIED |
| Nov 22 (Sun) | CAPR | deramiocel BLA, DMD (delayed from Aug 22) | 5+ sources |
| Nov 22 (Sun) | SVRA | MOLBREEVI BLA, aPAP (delayed from Aug 22) | 4+ sources |
| Nov 27 (Fri) | BBIO | BBP-418, LGMD (large-cap, low tail) | MarketBeat snippet only |
| Nov 28 (Sat) | PYPD | D-PLEX100 NDA | company press release, SEC 6-K |
| Q4 2026 | ALDX | Formal dispute resolution meeting/decision | company 8-K and summary |
| Dec 27, 2026 | PRAX | relutrigine (extended from Sept 27) | company Q2 2026 release |
| Jan 29, 2027 | PRAX | ulixacaltamide, essential tremor | company Q2 2026 release |
| Jan 30, 2027 | PHAR | leniolisib low-dose pediatric sNDA (priority) | company release |
| Q1 2027 | Takeda | zasocitinib (TAK-279) | 6-K |

---

## 7. To finish this research (queries and pages I could not run)

When search budget/fetch access is restored, prioritise these:
1. Full October and November PDUFA lists: pdufa.bio/calendar, marketbeat.com/fda-calendar/upcoming/, assyro.com/tools/pdufa-calendar/2026/november, tipranks.com/calendars/fda, biopharmcatalyst.com/calendars/pdufa-calendar. My searches surfaced only ~10 unique small/mid-cap dates, while the calendars quote 7 October and 11-13 November goal dates.
2. Current price and market cap for INO, IRD, TLSA, OCGN, VIR, CAPR, SVRA, PYPD, BTAI (company IR, StockAnalysis, MarketBeat).
3. BioPharmCatalyst Sept 25 and Fall 2026 watchlist articles (specific events for GALT, CNTB, BIVI, TENX, ACET, ONCY, SCYX, MPLT, MNOV).
4. Company guidance for Q4 2026 / "second half 2026" Ph3 and pivotal Ph2 readouts, especially any micro/small caps with guidance of "October" or "November".
5. Outcome of Mirum AZURE-1 (Sept 28) and Ameluz PDUFA (Sept 28).
6. Confirm ESMO / AHA / ASH / SITC / AASLD / ObesityWeek dates and abstract-embargo dates for Oct 12 - Nov 13.
7. Confirm exact Oct dates for ifinatamab deruxtecan (ES-SCLC) and satralizumab (TED), and the indications behind AGIO Nov 1 and CYTK Nov 14.
8. FDA advisory calendar for any meeting added after Sept 29.

---

## 8. Methodology notes and general reaction heuristics (my judgment, not sourced)

- FDA approval base rate ~85-90% for standard NDAs/BLAs with no AdComm and no disclosed issues. I lowered this for: accelerated approval on single-arm data (INO), prior CRL and a review extension (CAPR), and cell/gene therapy CMC risk.
- Phase 3 success base rate ~50-60% overall; higher when Ph2 data used the same endpoint and population, lower for repurposed or subgroup-rescued programs.
- Typical reactions for sub-$500M single-asset names: approval that was ~50% priced = +50% to +200%; approval already ~85% priced = 0% to +30% and occasional sell-the-news; CRL or Ph3 failure = -50% to -90%; positive surprise Ph3 in a micro-cap = +100% to +400%.
- FDA has recently been acting **ahead of** goal dates in some cases (Welireg, 10 days early), and weekend goal dates usually resolve the prior Friday. This makes Nov 14 (Sat) dates potentially in-window and Nov 22 (Sun) dates plausibly resolve Fri Nov 20, still outside.
- Most search snippets came from calendar aggregators (MarketBeat, BiopharmaWatch, TipRanks, RTTNews). I treated single-snippet items as leads, not facts, and labelled them.
