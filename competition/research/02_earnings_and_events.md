# 02 - Q3 2026 Earnings Season and Scheduled-Event Map (Oct 12 - Nov 13, 2026)

Prepared 2026-09-29 for the Bloomberg Global Trading Challenge 2026 team.
Objective: maximum upside tail, risk ignored. Holding window Oct 12 - Nov 13, 2026 (5PM New York).

> ## STATUS: PARTIAL REPORT - RESEARCH CHANNELS EXHAUSTED
> - This session's shared **WebSearch budget hit its cap (200/200)** after roughly 30 queries from this thread. Every later search returned "web search budget used".
> - **WebFetch is blocked (EGRESS_BLOCKED) on every domain tried**: stocktitan, benzinga, chartmill, tipranks, earningswhispers, sec.gov, marketbeat, fool.com(.au), wallstreethorizon, businesswire, cnbc, wikipedia, investors.coreweave.com, marketchameleon, nasdaq.com, 247wallst, finance.yahoo, stockanalysis, investing.com, thestreet. I did not try to route around the proxy.
> - **I never read a page directly.** All facts below come from search-engine result summaries. These can be wrong or internally inconsistent (several conflicts are flagged below).
> - **Not retrieved at all** (so blank or "n/r" in tables): options-implied moves for every name; last-4 earnings-day moves for nearly every name; short interest for nearly every name; prices for most names; anything on robotics, memes (GME/AMC/OPEN/KSS), most nuclear/eVTOL/drone names, BMNR/SBET, BLSH/KLAR/FIG, and essentially all non-US names.
> - To finish: raise `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` and re-run using the playbook in Section 8, or have a human pull the blocked pages (earningswhispers, marketchameleon, highshortinterest) in a browser.
> - Conflict-of-interest note: the analyst that wrote this is an Anthropic model. The Anthropic-IPO items below come only from third-party web sources; verify them independently.

**Date-basis legend (used in every table)**

| Code | Meaning |
|---|---|
| C | Company-issued announcement (seen as a press-release headline in search results) |
| L | Third-party calendar listing (TipRanks, Nasdaq, MarketBeat, FXEmpire, etc.). Often labelled "confirmed" but frequently algorithmic. Treat as UNVERIFIED (expected). |
| E | Third-party estimate range "based on historical dates" (company has not announced). UNVERIFIED (expected). |
| M | My own recollection of the 2025 pattern or general calendar knowledge. NOT verified in this session. UNVERIFIED (expected). |
| D | Derived by me with arithmetic from a sourced number |
| n/r | Not retrieved (budget/egress block). Not "zero" or "unknown to the market" - just missing from this report. |

Calendar facts used: Oct 12, 2026 is a Monday; Nov 13 is a Friday. A name reporting after the close (AMC) on Nov 12 or earlier has its reaction inside the window; AMC on Nov 13 reacts Nov 16 (outside). Before-the-open (BMO) on Nov 13 is inside. Anything reporting before Oct 12 (e.g. APLD Oct 7) reacts outside the window.

---

## 1. Market backdrop (verified from search summaries, Sept 25-29, 2026)

- Sept 28 close: S&P 500 7,683.69 (-0.77%), Nasdaq Comp 26,820.38 (-0.92%), Dow 51,481.51 (-0.67%). Selling driven by rising Treasury yields and Trump reportedly rebuffing an Iran peace deal; Brent bounced toward ~$110 (a weekly recap the prior week said oil had fallen below $98). A TradingKey weekly recap cites Treasury yields "near 5.2% high" (maturity not specified) and says AI chip stocks led the prior week.
- Bitcoin about $84,062 on Sept 28-29; it was ~$86,625 on Sept 22 (+6.5% that day). Spot BTC ETFs saw +$433M net inflow on Sept 18. Commentary: Q4 is historically the strongest crypto quarter.
- FactSet (via FXStreet): S&P 500 Q3 2026 EPS growth expected +28.9%, the third straight quarter above +25%. Season "gets going in earnest" mid-October with the big banks.
- Macro dates that touch the window: Sept NFP Oct 2 (just before), US midterm elections **Nov 3 (M, calendar fact)**, FOMC **Oct 27-28 (M)**, monthly options expiry **Oct 16 (D: third Friday)**, which is also the deadline for entering initial positions.
- Also flagged for the week of Sept 28: OpenAI Developer Day (Sept 29) and release of the US-China tariff-reduction agreement details.

### What is actually hot in September 2026 (not 2025's list)
- **Quantum**: strong September rally. Sept 17: IONQ +9%, QBTS +8%, RGTI +7%. Sept 23: IONQ +11% (NVIDIA research-center deal + real-time error-correction decoder on an off-the-shelf CPU), QBTS +5% (~$18.38), RGTI +4% (~$17.15). Sept 24: IONQ +4%, QBTS +3%, RGTI +2%. US Commerce (CHIPS) awarded $100M each to D-Wave, Rigetti and Quantinuum. IonQ lifted its 2026 revenue outlook to $450-460M from $280-290M. Trailing-two-year gains cited: IONQ ~+400%, RGTI ~+1,820%, QBTS ~+1,670%, QUBT ~+1,200%. A Motley Fool piece (Sept 22) is headlined about an "$895 million warning" for the group (content not read; likely dilution/financing - UNVERIFIED).
- **Neoclouds**: choppy. Strong summer ("CoreWeave & Nebius are soaring", Aug 12), a sharp drop July 16 (NBIS -13%, "neocloud trade unravels"), and another selloff into Sept 25 after Redburn initiated the group (Sept 23, IREN Neutral) and SemiAnalysis published ClusterMAX ratings (CRWV and NBIS top-tier). YTD: NBIS +163%, WULF +94%, APLD +74%, WYFI +53%, CRWV +50%, IREN +40%, CIFR +38%.
- **Crypto proxies**: rebounding with BTC > $84K. MSTR, ASST (Strive) and COIN are named as heavily shorted / squeeze candidates because investors short them to hedge BTC upside. Clear Street raised COIN's target to $224 from $204. CRCL surged >15% to above $102 in a recent session (date not confirmed).
- **Mega-IPO wave**: SpaceX (SPCX) listed June 12, 2026; Cerebras (CBRS) listed May 14, 2026; Anthropic and OpenAI have filed confidentially. See Section 4.
- **Micro-cap mania** (StockTitan Sept 2026 monthly): GLND +299%, INDP +241%, GRML +215%, TJGC +162%, SECZ +155%. YTD 2026: MGRT +1,590%, ANL +1,025%, XHLD +936%. These are micro-caps; liquidity and eligibility under the competition's rules are unchecked.
- **High short interest screens (Sept 2026)**: Venture Global (NYSE: VG) 80.47% of float (mkt cap $32.19B; the screen's top), Minimed Group (NASDAQ: MMED) 47.64% ($5.61B), plus a Benzinga list of 10 names with >33% SI that includes SoundHound (SOUN). 44 mid-to-mega caps had SI >20% of shares outstanding in early September. ASX's most-shorted: Lotus Resources (ASX: LOT) 14.8%. Float-based SI on VG looks like a screen artefact - verify before relying on it.

---

## 2. Structural findings that change the plan

1. **NVDA is OUTSIDE the window.** Q3 FY27 report: TipRanks lists Nov 25, Wall Street Horizon lists Nov 17 (both L). Either way after Nov 13. Guidance: Q3 FY27 revenue $108.0B +/-2% (from the Q2 FY27 8-K CFO commentary). No NVDA earnings catalyst is available in the window.
2. **APLD reports Oct 7 AMC (C)**, reaction Oct 8: five days BEFORE the window opens. Not capturable as an earnings event.
3. **Several marquee names sit on the window's right edge or beyond**: CRWV (L Nov 16, but see #4), RKLB (L Nov 16, E Nov 9-13), NBIS (E Nov 20-30), HUT (L Nov 18), CRDO (L Nov 30/Dec 2), IREN (conflict: FXEmpire Nov 4 vs TipRanks Dec 1). The team must confirm dates in the first days of Oct/Nov.
4. **"Confirmed" on TipRanks is unreliable.** Its Nov 16 dates for both RKLB and CRWV equal roughly Q2 report date + 98 days (RKLB reported Aug 10; CoreWeave reported ~Aug 11), which looks algorithmic. By 2025 analogy (M: RKLB Nov 10, CRWV Nov 10, NBIS Nov 11), the true dates may well be Nov 9-12, i.e. inside the window. Treat CRWV/RKLB/NBIS as "likely inside, must verify".
5. **SpaceX is now a public $1.9-2T stock** with its first Q3 report unconfirmed (~Nov 3) and a lock-up release keyed to that report (Section 4). It is the single biggest scheduled event in the window.
6. **Anthropic IPO is reported for October** (pricing forecast ~Oct 26 by one source). OpenAI has filed confidentially but may wait until 2027. An AI-lab mega-IPO could move AI-infrastructure comps (sympathy/re-rating) - a thematic catalyst, not a tradable date we can confirm.
7. **Cerebras 180-day lock-up expiry falls about Nov 9-10 (D)**, inside the window (see Section 4).
8. Q2 pattern shows many of these names reported the week of Aug 4-13, 2026, so Q3 reports cluster Nov 3-12. Practical implication for a time-weighted score: to capture reactions from Nov 3 onward the book must be fully invested by then; a name reporting Nov 11-12 gives only 1-2 days after the event inside the window.

---

## 3. Master table (sorted by expected event date)

Prices are the last figure found in search summaries and are dated where known. "Implied move" and "Last-4 moves" are n/r unless stated. Market caps are as quoted by sources.

| Date (basis) | Ticker (Exch) | Event | Price (date) | Mkt cap | Short int. | Implied move | Last-4 earnings-day moves | Notes / confidence |
|---|---|---|---|---|---|---|---|---|
| Oct 7 AMC (C) - OUTSIDE window | APLD (NASDAQ) | FQ1 FY27 results, call 5:00pm ET; qtr ended Aug 31 | n/r | ~$8.37B (9/25 article) | n/r | n/r | n/r | Reaction Oct 8, before window. YTD +74%. 600 MW contracted / ~$16B prospective lease revenue (per source). |
| Wk of Sep 28 (L) | OURA (NASDAQ) | IPO: roadshow from Sept 21, 50M sh at $40-44 | IPO range | n/r | n/a | n/a | n/a | Debut lands just before window; no lock-up in window. |
| ~Oct 21-22 (M) | TSLA (NASDAQ) | Q3 results (2025: Oct 22) | n/r | n/r | n/r | n/r | n/r | NOT searched. Verify. |
| ~Oct 26 (E, third-party forecast) | Anthropic (Nasdaq, ticker unconfirmed) | IPO pricing/listing | private | $965B post-money (May Series H); talk of up to $2T IPO | n/a | n/a | n/a | Confidential S-1 filed Jun 1, 2026; GS/JPM/MS lead; raise >$60B reported. No public S-1/price range confirmed in my results. Ticker "ANTP" appeared on a private-market page - UNVERIFIED. |
| Oct 27-28 (M) | FOMC | Rate decision | - | - | - | - | - | Macro. |
| Oct 28 BMO (L) | VRT (NYSE) | Q3 results | n/r | n/r | n/r | n/r | n/r | One listing says "confirmed" Oct 28; another estimates Oct 21-26. Verify. |
| Oct 29 AMC (L) | COIN (NASDAQ) | Q3 results (Q2 was Thu Jul 30) | n/r (+0.43% on 9/29) | n/r | Flagged heavily shorted | n/r | n/r | Clear Street PT $224 (from $204). Some listings show "unconfirmed". |
| Oct 29-Nov 2 (E) | RIOT (NASDAQ) | Q3 results | n/r | n/r | n/r | n/r | n/r | Another listing: Nov 10. |
| Oct 30-Nov 2 (E) | CBRS (NASDAQ) | Q3 results (Q2 was Aug 12) | n/r (IPO $185) | ~$95B at day-1 close | n/r | n/r | Day-1 IPO +68%, day-2 about -10% (not earnings) | Last-4 earnings moves n/r (only 1-2 reports as public co.). |
| Nov 3 AMC (L, "confirmed") | SMCI (NASDAQ) | FQ1 FY27 results | n/r | n/r | n/r | n/r | n/r | Company release not seen. Historically a habitual +/-10-20% mover (M) - verify. |
| Nov 3 AMC (L, unconfirmed) | AMD (NASDAQ) | Q3 results | n/r | n/r | n/r | n/r | n/r | AMD IR page showed no upcoming events at time of listing. |
| Nov 3 AMC (L, unconfirmed) | SPCX (NASDAQ) | First Q3 report; triggers ~28% lock-up tranche | $147.28 (9/28) | ~$1.9T (D: $2.1T at $161 close, scaled) | n/r | n/r | Q2 (Aug 4): +9.4% regular session, then -8.6% after hours (to $114.6) | 52-wk range $104.83-$225.64. See Section 6 #1. |
| Nov 3 | US midterm elections | Election day | - | - | - | - | - | Macro/regime event (M, calendar fact). |
| Nov 4 AMC (L) | MSTR (NASDAQ) | Q3 results | ~$158.61 (Sept, undated) | n/r (~4% of BTC supply, ~$70B BTC) | Flagged heavily shorted | n/r | n/r | Another source estimates Oct 29-Nov 2. |
| Nov 4 (L) | HOOD (NASDAQ) | Q3 results | n/r | n/r | n/r | n/r | n/r | Analysts raised PTs with BTC > $84K (Stocktwits headline). |
| Nov 4 (L, conflict) | IREN (NASDAQ) | FQ1 FY27 results | $44.09 (9/25) | n/r | n/r | n/r | n/r | FXEmpire Nov 4 vs TipRanks Dec 1 (both L). YTD +40%. |
| Nov 4-9 (E) / Nov 11 (L) | IONQ (NYSE) | Q3 results | n/r (+9% 9/17, +11% 9/23, +4% 9/24) | n/r | n/r | n/r | n/r | Guidance raised to $450-460M (from $280-290M). Exchange listed as NYSE from memory (M). |
| Nov 6-12 (E) | QBTS (NYSE) | Q3 results (Q2 call was Aug 6, 8:00am ET) | ~$18.38 (9/23 intraday) | n/r | n/r | n/r | n/r | CHIPS $100M. |
| Nov 9-13 (E) | RGTI (NASDAQ) | Q3 results (Q2 was Aug 6 AMC) | ~$17.15 (9/23 intraday) | n/r | n/r | n/r | Aug 6 report: +8.5% next day; others n/r | CHIPS $100M. Right edge of window. |
| Nov 9 AMC projected (E) | ASTS (NASDAQ) | Q3 results | n/r | n/r | n/r | n/r | n/r | Range Nov 9-13. |
| Nov 9-13 (E) / Nov 16 (L) | RKLB (NASDAQ) | Q3 results | n/r | n/r | n/r | n/r | n/r | Q2 (Aug 10 AMC): record revenue, record backlog, guided another record Q3. |
| ~Nov 9-10 (D) | CBRS (NASDAQ) | 180-day IPO lock-up expiry (May 14 + 180d = Nov 10) | n/r | - | - | - | - | Standard-term assumption; check 424B4/S-1 for staggered or earnings-based early release (as SpaceX has). UNVERIFIED. |
| Nov 10 (L, conflict with E Nov 2-5) | ALAB (NASDAQ) | Q3 results | n/r | n/r | n/r | n/r | n/r | Listing calls Nov 10 "official"; another estimate is Nov 2-5. |
| Nov 10 (L) | RIOT | Q3 results | n/r | n/r | n/r | n/r | n/r | See above. |
| Nov 11 (L) | CRCL (NYSE) | Q3 results | >$102 after +15% surge (date n/r) | n/r | n/r | n/r | n/r | 2025 IPO at $31, peaked ~$299 in June 2025 (M). |
| ~Nov 10-12 (M) | CRWV (NASDAQ) | Q3 results | $87.72 (9/25) | $58.8B (source) | n/r | n/r | n/r | TipRanks L says Nov 16 = OUTSIDE (likely algorithmic). $104B backlog; +50% YTD. |
| Nov 13 5PM NY | - | Competition window ends | - | - | - | - | - | - |
| AFTER WINDOW | NVDA | Q3 FY27: Nov 17 (L) or Nov 25 (L) | - | - | - | - | - | Outside. |
| AFTER WINDOW | NBIS | Q3: E Nov 20-30 | $237.61 (9/25) | n/r | n/r | n/r | n/r | Q2 6-K dated Aug 12. 2025 report was ~Nov 11 (M), so date may be earlier - verify. |
| AFTER WINDOW | HUT | Q3: L Nov 18 | n/r | n/r | n/r | n/r | n/r | |
| AFTER WINDOW | CRDO | FQ2 FY27: L Nov 30 / Dec 2 | n/r | n/r | n/r | n/r | n/r | |
| AFTER WINDOW | SPCX | Full 180-day lock-up expiry Dec 8 | - | - | - | - | - | Musk ~6.4B shares locked until Jun 12, 2027. |

Names for which I found Q2 reporting already done and no reliable Q3 date: MARA (Q2 8-K Aug 6), CLSK (FQ3 reported Aug 6; FQ4 likely late Nov/Dec, so probably outside - M), CIFR (renamed Cipher Digital Inc. in Feb 2026; Q3 date n/r), OKLO (Q2 10-Q filed; Q3 n/r; 2025 pattern ~Nov 11 (M)).

### Names NOT researched (no searches left) - starting-point priors only (all M / UNVERIFIED)
These are 2025-pattern recollections. Use only to decide what to verify first.

| Group | Tickers | Prior for Q3 2026 timing (M, UNVERIFIED) |
|---|---|---|
| eVTOL / space / drones | JOBY, ACHR, LUNR, ONDS, RCAT | JOBY/LUNR ~Nov 5-6; ACHR ~Nov 12; ONDS ~Nov 12-13 (edge); RCAT fiscal year ends Apr 30 so its next report may be outside the window |
| Nuclear / SMR | OKLO, SMR, NNE, LEU, CCJ | OKLO ~Nov 11; SMR ~Nov 6; NNE ~Nov 12-13 (edge); LEU ~Nov 5; CCJ ~late Oct |
| Memes | AMC, OPEN, GME, KSS | AMC ~Nov 5; OPEN ~Nov 5-6; GME reports early/mid Dec (outside); KSS late Nov (outside) |
| Crypto treasuries / new IPOs | BMNR, SBET, FIG, KLAR, BLSH | FIG ~Nov 5; KLAR ~Nov 18 (outside); BLSH mid-Nov (edge/outside); BMNR fiscal year ends Aug 31; SBET unclear |
| Other retail/high-beta to check | PLTR (~Nov 2-3), APP, HIMS, UPST, SOFI, SOUN (SI>33%), RDDT, CVNA | Not searched |

Data points I did get on 2025 IPO names: Klarna (KLAR) traded ~$17.66 on Jun 18, 2026, about -56% vs its $40 IPO price. Figma (FIG) was reported to be below its $33 IPO price in one source (conflicting with an older "-13% since IPO" piece; treat as UNVERIFIED). Discord's IPO base case slipped to 2027; Databricks is still private.

---

## 4. Non-earnings scheduled corporate/market events

### 4a. IPOs and lock-ups
| Date | Event | Detail | Basis |
|---|---|---|---|
| Aug-Oct 2026 (ongoing) | SPCX staggered lock-up releases | 20% of the ~4.6B-share 180-day block after Q2 earnings (first release Aug 6, ~911.5M shares eligible); then ~7% tranches every 2-4 weeks through October | L (multiple web sources agree) |
| Around Q3 report (~Nov 3-4) | SPCX earnings-triggered release | Largest single supply event: ~28% (~1.3B shares) of the 180-day block | L |
| Dec 8 | SPCX full 180-day expiry | Outside window | L |
| Jun 12, 2027 | Musk shares (~6.4B) unlock | 366-day lock, no early release | L |
| ~Nov 9-10 | CBRS 180-day lock-up | May 14 IPO + 180 days = Nov 10 (D). Verify actual terms | D / UNVERIFIED |
| ~Oct (unconfirmed) | Anthropic IPO | Nasdaq target; one forecast puts pricing ~Oct 26. Confidential S-1 Jun 1, 2026. | E |
| 2027? | OpenAI IPO | Confidential draft S-1 reported (May 22 or Jun 8, 2026); Reuters (late June) says it may wait until 2027 | L |
| Sept 2026 (India) | NSE IPO (Rs 22,568.94 crore) and ESDS (up >290% from issue) listed in September | Global-equities angle: Indian IPO gainers ran hard in Sept; ESDS is cloud-GPU/AI datacentre | L |

Other IPO lock-ups in the window correspond to IPOs priced roughly Apr 15 - May 17, 2026 (180-day rule). I could not retrieve the 2026 IPO list (stockanalysis.com/ipos/2026, Renaissance Capital, IPOScoop are all in the blocked/unsearched set). This is a gap.

### 4b. Index events (all UNVERIFIED; not searched)
- **S&P 500 quarterly rebalance**: announcement typically early December (M), so outside. But check whether SPCX (listed June) has already been added to S&P 500 / Nasdaq-100 or has a pending fast-entry decision - I could not verify either way.
- **Nasdaq-100 annual reconstitution**: announced early December (M); outside.
- **MSCI November 2026 Index Review**: in 2025 the announcement was ~Nov 5 with implementation at the Nov 24 close (M). By analogy the 2026 announcement should land in the first week of Nov (inside the window), with implementation late Nov (outside). Verify on msci.com. Global-equities angle: additions of fast-growing Asian/EM names can pop on announcement.
- **FTSE Russell**: US Russell reconstitution was announced to move to semi-annual (June and November) beginning 2026 (M - my recollection, verify). If true, November preliminary lists and rank-day flows could fall in or just after the window; check FTSE Russell's 2026 schedule.
- **FTSE All-World / Hang Seng reviews**: September FTSE review already done; Hang Seng Q3 review historically announced in the third week of Nov (M), likely just outside.

### 4c. Corporate/product events (n/r - not searched)
- Tesla Q3 earnings ~Oct 21-22 (M). Any Tesla/xAI/robotaxi/Optimus events unverified.
- Apple (Q3 earnings ~Oct 29-30 (M); any October product event unverified), Nvidia GTC-type events (2025's DC event was late Oct (M)), AMD analyst day (2025's was Nov 11 (M)), Meta/Microsoft/Alphabet/Amazon earnings ~Oct 28-30 (M) - these set AI-capex tone for the whole AI complex and fall inside the window.
- Big banks ~Oct 13-16 (search: "mid-October"), TSMC ~Oct 15-16 and ASML ~Oct 14-15 (M).
- FDA PDUFA dates, court rulings, SPAC votes: not searched. Biotech binary events are a major +100% source and are an important gap.

---

## 5. Non-US names (high beta) - ALL UNVERIFIED (M), none searched

Included only as a checklist. The competition covers global equities, so these need real verification.

| Region | Names / events to check | Prior timing (M, UNVERIFIED) |
|---|---|---|
| Korea | SK Hynix Q3 (HBM), Samsung Electronics final Q3, Hanwha Aerospace | SK Hynix ~Oct 22-23; Samsung prelim ~Oct 7-8 (before window), final ~Oct 29-30 |
| Japan | SoftBank Group (large OpenAI exposure), Kioxia, Advantest, Tokyo Electron, Sakura Internet | SoftBank ~Nov 11-12; chip-equipment names late Oct |
| Taiwan | TSMC (ADR: TSM), Foxconn | TSMC ~Oct 15-16 |
| Europe | ASML, Rheinmetall, Nebius-style AI infra plays | ASML ~Oct 14-15; Rheinmetall ~Nov 6 |
| Hong Kong / China ADRs | Tencent (~Nov 12-13), JD (~Nov 13), Alibaba (Sept-qtr report was Nov 25 in 2025, likely outside), Xiaomi / XPeng / NIO / Li Auto (mostly mid-to-late Nov, likely outside), Pop Mart (Q3 update mid-Oct), BYD (late Oct) | Verify each; several fall right after Nov 13 |
| Canada | Shopify (~Nov 4-5), Celestica (~late Oct), Cameco (~late Oct), Denison/uranium names | Verify |
| Australia | ASX names screened for short interest: Lotus Resources (LOT) 14.8% SI (uranium). ASX earnings season is mostly Feb/Aug, so October events are AGMs and quarterly activity reports (late Oct) | Verify |
| India | September IPO class (ESDS +290% from issue) | Not researched further |

---

## 6. Provisional Top 10 "most explosive scheduled-event names"

**Read this first:** the ranking is provisional. It is built only from (a) a date that plausibly falls inside the window, (b) verified catalysts/momentum in September, and (c) a high-beta profile. I could not retrieve implied moves, short interest, or earnings-day histories, so no name has been screened on "habitually moves 20-50%". Everything labelled UNVERIFIED still needs the Section 8 checks. "Bull case" below is a scenario argument, not a forecast; I am not asserting any of these will rise.

### 1. SpaceX (SPCX, NASDAQ) - the biggest single scheduled event
- Timing: first Q3 report unconfirmed, forecast ~Nov 3 AMC (reaction Nov 4). A ~28% lock-up tranche (~1.3B shares) is tied to that report; 7% tranches drip through October.
- Verified facts: IPO Jun 12 at $135 (~$75B raised, ~$1.77T implied); opened $150, closed day one $161 (~$2.1T). Price $147.28 on Sept 28; 52-week range $104.83-$225.64. Q2 (Aug 4): revenue $7.8B (+92% y/y) vs ~$6.8-6.9B consensus, adjusted EBITDA $3.54B, net loss $541M, capex $18.4B of which $15.83B AI. Stock rose 9.4% in the session, then fell 8.6% after hours on capex worries - i.e. it swings ~9% on the print in both directions. Analyst average target $222.42 (high $450, low $140); 28 buy / 2 sell.
- Bull case: a second big revenue beat with capex now understood by investors, plus the market looking through the supply overhang, could take the stock back to the $225 high (+53% from $147). The Street high ($450) is +205%. A mega-cap AI-adjacent IPO wave (Anthropic in October) could re-rate anything AI-linked.
- Reality check: at ~$1.9T, +100% inside five weeks is very unlikely; realistic tail is +30-50%. It is the most liquid, least-capacity-constrained name on the list, which matters for a 20% position.

### 2. Cerebras (CBRS, NASDAQ) - earnings plus lock-up expiry
- Timing: Q3 estimated Oct 30-Nov 2 (unconfirmed); 180-day lock-up computed at ~Nov 9-10 (UNVERIFIED terms).
- Verified facts: priced at $185 on May 14, 2026, raising $5.55B (30M shares), the largest US tech IPO since Uber (2019) at the time; +68% on day one (~$95B market cap; close ~$311, D), about -10% the next day. Q2 reported Aug 12. Current price n/r.
- Bull case: pure-play AI-inference silicon with a limited float, reporting into an AI-capex-friendly tape, possibly re-rated by the Anthropic/OpenAI IPO wave. Lock-ups often cause weakness into expiry and relief after; the two events give two shots inside the window.
- Gaps: price, short interest, options implied move, analyst targets, exact lock-up terms.

### 3. IonQ (IONQ) - guidance already lifted 60%, sector momentum
- Timing: estimated Nov 4-9 (E), one listing Nov 11 (L). Likely inside the window.
- Verified facts: 2026 revenue outlook raised to $450-460M from $280-290M (midpoint +60%); NVIDIA research-center deal and real-time QEC decoder news on Sept 22-23; +9% (Sept 17), +11% (Sept 23), +4% (Sept 24); ~+400% over two years. Price n/r.
- Bull case: a further raise/large bookings, an NVIDIA tie-in and government funding flow in a basket already ripping in September. Quantum names historically overshoot (RGTI/QBTS ~+1,700-1,800% in two years).
- Risk to thesis: financing/dilution ("$895M warning" headline, unread).

### 4. Rigetti (RGTI) - highest beta of the quantum trio
- Timing: E Nov 9-13. Sits on the right edge: only a report AMC on or before Nov 12 reacts inside the window.
- Verified: ~$17.15 (Sept 23 intraday); ~+1,820% over two years; $100M CHIPS award; last report (Aug 6 AMC) +8.5% next day.
- Bull case: small-cap, retail-loved, high short-interest quantum name with new federal money; sector squeeze if IONQ/QBTS print well earlier in the week.

### 5. D-Wave Quantum (QBTS) - earlier in the window than RGTI
- Timing: E Nov 6-12. Q2 was pre-market Aug 6 (8:00am ET call), so the reaction may come the same day.
- Verified: ~$18.38 (Sept 23 intraday); ~+1,670% over two years; $100M CHIPS award.
- Bull case: commercial annealing revenue + government money + basket momentum; the earlier date leaves room to add or rotate after IONQ/RGTI results.

### 6. Strategy (MSTR) - levered Bitcoin with squeeze fuel
- Timing: Nov 4 AMC (L) or Oct 29-Nov 2 (E).
- Verified: ~$158.61 (Sept, undated); holds ~4% of the 21M BTC supply (~$70B); Benzinga flags MSTR, COIN and ASST as heavily shorted (shorted as BTC hedge). BTC ~$84K, with Q4 historically the strongest crypto quarter.
- Bull case: BTC moves to $100K+ (+19% from $84K), and MSTR's premium plus a squeeze on shorts produces a 2-3x beta move. Earnings are largely a mark-to-market print; the tradeable catalyst is BTC itself.
- Gaps: earnings-day history, exact SI %, mNAV.

### 7. CoreWeave (CRWV) - date is the swing factor
- Timing: L says Nov 16 (outside); 2025-analogy says ~Nov 10 (inside). Verify.
- Verified: $87.72 (Sept 25); $58.8B market cap vs $104B backlog; +50% YTD; fell into Sept 25 on Redburn/SemiAnalysis notes (though SemiAnalysis rated CRWV top-tier). Q2 reported ~Aug 11.
- Bull case: backlog conversion plus financing relief after a September derating; a neocloud that has swung -13% (NBIS on Jul 16) and "soared" (Aug 12) within weeks. Only worth a slot if the date is confirmed inside the window.

### 8. Rocket Lab (RKLB) - space halo from SpaceX
- Timing: E Nov 9-13; L Nov 16 (likely algorithmic).
- Verified: Q2 (Aug 10 AMC) record revenue, record backlog, guided another record Q3. Price/cap/SI/implied move n/r.
- Bull case: SpaceX now trades as a public comp and space names can re-rate together around SPCX's Nov 3 print; a Neutron milestone (UNVERIFIED) would be a separate catalyst.

### 9. Circle (CRCL, NYSE) - stablecoin/crypto beta with a history of huge swings
- Timing: Nov 11 (L) - two days before the window closes.
- Verified: surged >15% to above $102 in a recent crypto rebound. 2025 IPO at $31, peak ~$299 (M).
- Bull case: crypto Q4 seasonality + stablecoin narrative + a high-beta chart that has already traded 3x its current level. Gaps: earnings history, SI.

### 10. AST SpaceMobile (ASTS) - retail-favourite, event-heavy
- Timing: E Nov 9-13 (projected Nov 9 AMC).
- Verified: date estimate only. Price, market cap, SI, and launch schedule n/r.
- Bull case: same space-halo logic as RKLB, plus satellite-launch news flow (UNVERIFIED). Included as a placeholder pending data; it should be replaced if the Section 8 checks turn up a better name.

**Next in line (data-thin):** COIN (Oct 29, heavily shorted), IREN ($44.09; Nov 4 vs Dec 1 date conflict), NBIS ($237.61; +163% YTD; date likely late), HOOD (Nov 4), ALAB (Nov 10), SMCI/AMD (Nov 3), OKLO/SMR/NNE/JOBY/ACHR/LUNR (dates M only).

---

## 7. Key caveats
1. Dates: only APLD's (Oct 7) is company-issued in my evidence. Every other date is a listing, estimate or memory. Names near Nov 9-13 can slip outside the window.
2. Implied moves and earnings-day histories are missing for everything - the "habitual 20-50% mover" screen has NOT been done.
3. Search summaries conflict in several places (NVDA Nov 17 vs 25, IREN Nov 4 vs Dec 1, ALAB Nov 10 vs Nov 2-5, VRT Oct 28 vs Oct 21-26, RKLB/CRWV Nov 16 vs Nov 9-13). All are flagged.
4. A large-cap like SPCX gives a wide range but not +100%; the true +100%-tail candidates are small caps and binary events (biotech PDUFAs, micro-caps), which I did not cover.
5. Macro is fragile: yields near multi-year highs, oil ~$98-110 with Iran headlines, Nov 3 midterms, FOMC Oct 27-28. Earnings growth (+28.9%) is strong.

---

## 8. Playbook to finish (priority order; needs a raised search budget or browser access)

1. Confirm exact Q3 dates and BMO/AMC for: CRWV, NBIS, IREN, RKLB, ASTS, RGTI, QBTS, IONQ, ALAB, CIFR, MARA, RIOT, CLSK, OKLO, SMR, NNE, JOBY, ACHR, LUNR, ONDS, AMC, OPEN, FIG, CRCL, HOOD, COIN, MSTR, SMCI, AMD, PLTR (company IR "to announce third quarter 2026 results" press releases appear ~2-4 weeks ahead).
2. For each: options-implied earnings move (marketchameleon / optionslam / barchart), last 4 earnings-day moves (marketchameleon earnings-dates pages), short interest % float (fintel / highshortinterest / ortex), price and market cap.
3. IPO/lock-up: full 2026 IPO list from stockanalysis.com/ipos/2026 and Renaissance Capital; filter IPOs priced Apr 15 - May 17 for 180-day expiries falling Oct 12 - Nov 13; read CBRS's prospectus lock-up section.
4. Anthropic: check for a public S-1, price range and roadshow dates (pricing usually 2+ weeks after the public filing; a public S-1 in late Sept/early Oct would confirm an Oct/Nov listing).
5. Index events: MSCI Nov 2026 review dates; FTSE Russell 2026 semi-annual recon schedule; SPCX fast-entry status for Nasdaq-100/S&P 500.
6. Biotech PDUFA / adcom calendar for Oct 12 - Nov 13 (biopharm catalyst calendars) and any court rulings/SPAC votes.
7. International: SoftBank, SK Hynix, Samsung, TSMC, ASML, Tencent, JD, Alibaba, Xiaomi, XPeng, NIO, Li Auto, Pop Mart, Cameco, Shopify, Celestica, Rheinmetall, Hanwha - confirm dates and 2026 YTD performance.
8. "What is hot" cross-check: 2026 YTD top gainers among >$1B caps (StockTitan YTD page and Finviz-type screens are blocked here), plus retail-sentiment trackers (Stocktwits trending, Reddit).

---

## 9. Sources (search-result summaries; pages were not opened directly)

**Season / market context**
- [US earnings season Q3 2026 - ii](https://www.ii.co.uk/investing-with-ii/international-investing/us-earnings-season)
- [What will the Q3 earnings season show? - FXStreet](https://www.fxstreet.com/news/what-will-the-q3-earnings-season-show-202609280620)
- [When is earnings season? Q3 2026 - earnings-watcher](https://earnings-watcher.com/wiki/when-is-earnings-season)
- [Stock market news Sept 28, 2026 - CNBC](https://www.cnbc.com/2026/09/27/stock-market-today-live-updates.html)
- [Stock market next week Sept 28-Oct 2 - CNBC](https://www.cnbc.com/2026/09/25/stock-market-next-week-outlook-for-sept-28-oct-2-2026.html)
- [Stock Market Today Sept 28, 2026 - TheStreet](https://www.thestreet.com/stock-market-today/stock-market-today-dow-jones-sp-500-nasdaq-updates-sept-28-2026)
- [Market Week Sept 28, 2026 - First Financial Trust](https://www.firstfinancialtrust.com/2026/09/28/marketing-week-september-28-2026/)
- [TradingKey Wall Street weekly report](https://www.tradingkey.com/analysis/stocks/us-stocks/262188606-nasdaq-mu-oil-usd-btc-weekly-tradingkey)

**Hot names / short interest**
- [StockTitan - September 2026 top monthly momentum](https://www.stocktitan.net/rankings/stock-gains-monthly/2026/september)
- [StockTitan - 2026 YTD best performers](https://www.stocktitan.net/rankings/stock-gains-ytd/2026)
- [AltIndex - best small caps Sept 2026](https://altindex.com/best-stocks/small-cap-stocks)
- [Motley Fool AU - 10 most shorted ASX shares, Sept 28, 2026](https://www.fool.com.au/2026/09/28/these-are-the-10-most-shorted-asx-shares-28-september-2026/)
- [Benzinga - Squeeze watch: 10 stocks with over 33% short interest](https://www.benzinga.com/trading-ideas/movers/26/09/62004722/squeeze-watch-10-stocks-with-over-33-short-interest)
- [Benzinga - Crypto stock short squeeze](https://www.benzinga.com/trading-ideas/long-ideas/26/09/62035123/crypto-stock-short-squeeze-investors-are-shorting-these-3-stocks-to-hedge-bitcoins-rise)
- [ChartMill - most shorted US stocks](https://www.chartmill.com/stock/markets/usa/screener/most-shorted-stocks)
- [IBKR hottest shorts 09-21-2026](https://www.interactivebrokers.com/campus/traders-insight/securities/short-selling/ibkrs-hottest-shorts-as-of-09-21-2026/)

**AI / neoclouds / semis**
- [NVDA earnings - TipRanks](https://www.tipranks.com/stocks/nvda/earnings)
- [NVDA earnings calendar - Wall Street Horizon](https://www.wallstreethorizon.com/nvidia-earnings-calendar)
- [NVIDIA Q2 FY27 CFO commentary - SEC 8-K](https://www.sec.gov/Archives/edgar/data/0001045810/000104581026000073/q2fy27cfocommentary.htm)
- [Neocloud stocks fall - 24/7 Wall St, Sept 25](https://247wallst.com/investing/2026/09/25/neocloud-stocks-fall-as-selling-extends-after-a-week-of-research-notes-iren-drops-4-coreweave-slides-3-nebius-eases/)
- [Nebius sinks 13% - 24/7 Wall St, Jul 16](https://247wallst.com/investing/2026/07/16/nebius-sinks-13-as-the-neocloud-trade-unravels-how-coreweave-iren-and-the-ai-data-center-stocks-stack-up/)
- [CoreWeave & Nebius soaring - 24/7 Wall St, Aug 12](https://247wallst.com/investing/2026/08/12/coreweave-nebius-are-soaring-this-brand-new-etf-gives-exposure-across-top-neocloud-stocks/)
- [Neocloud stocks - Macroplane](https://macroplane.com/blog/neocloud-stocks) / [TECHi](https://www.techi.com/neocloud-stocks/)
- [CoreWeave Q2 2026 results - IR](https://investors.coreweave.com/news/news-details/2026/CoreWeave-Reports-Strong-Second-Quarter-2026-Results/default.aspx) / [CNBC](https://www.cnbc.com/2026/08/11/coreweave-crwv-q2-earnings-report-2026.html) / [Investing.com date](https://www.investing.com/equities/coreweave-earnings)
- [NBIS earnings dates - Market Chameleon](https://marketchameleon.com/Overview/NBIS/Earnings/Earnings-Dates/)
- [IREN - FXEmpire](https://www.fxempire.com/stocks/iren/earnings) / [IREN - TipRanks](https://www.tipranks.com/stocks/iren/earnings)
- [Applied Digital sets Q1 FY27 call for Oct 7 - StockTitan](https://www.stocktitan.net/news/APLD/applied-digital-sets-fiscal-first-quarter-2027-conference-call-for-66oeqzfsi05b.html) / [Rallies](https://rallies.ai/news/applied-digital-schedules-fiscal-q1-2027-results-conference-call-ac0dc6cb3c9d6bc6)
- [SMCI - TipRanks](https://www.tipranks.com/stocks/smci/earnings)
- [AMD earnings Q3 2026 - Dividend Calculator](https://dividendcalculator.co/2026/09/24/amd-earnings/) / [AMD - TipRanks](https://www.tipranks.com/stocks/amd/earnings)
- [VRT - TipRanks](https://www.tipranks.com/stocks/vrt/earnings)
- [ALAB - Market Chameleon](https://marketchameleon.com/Overview/ALAB/Earnings/Earnings-Dates/) / [Investing.com](https://www.investing.com/equities/astera-labs-earnings)
- [CRDO next earnings date](https://www.nextearningsdate.com/crdo.html)

**Quantum**
- [D-Wave, Rigetti and IonQ rally on $100M boost - Yahoo Finance](https://finance.yahoo.com/markets/stocks/articles/d-wave-rigetti-ionq-stocks-125904784.html)
- [Motley Fool Sept 22, 2026 - quantum "$895 million warning"](https://www.fool.com/investing/2026/09/22/ionq-rigetti-dwave-quantum-computing-send-shockwaves-through-wall-street-with-895-million-warning/)
- [24/7 Wall St - IonQ +11% Sept 23](https://247wallst.com/investing/2026/09/23/ionq-surges-11-as-nvidia-research-center-deal-follows-error-decoder-breakthrough-d-wave-climbs-5-rigetti-rises-4/) / [Sept 17](https://247wallst.com/investing/2026/09/17/ionq-climbs-9-on-quantum-optimization-work-with-nvidia-d-wave-rises-8-rigetti-gains-7/) / [Sept 24](https://247wallst.com/investing/2026/09/24/ionq-rises-4-as-post-breakthrough-buying-continues-d-wave-quantum-gains-3-rigetti-adds-2/)
- [IONQ earnings dates - Market Chameleon](https://marketchameleon.com/Overview/IONQ/Earnings/Earnings-Dates/) / [Nasdaq](https://www.nasdaq.com/market-activity/stocks/ionq/earnings)
- [RGTI earnings dates - Market Chameleon](https://marketchameleon.com/Overview/RGTI/Earnings/Earnings-Dates/)
- [QBTS earnings dates - Market Chameleon](https://marketchameleon.com/Overview/QBTS/Earnings/Earnings-Dates/) / [D-Wave Q2 8-K](https://www.sec.gov/Archives/edgar/data/0001907982/000190798226000127/qbts-20260806xexx991.htm)

**Crypto**
- [MSTR earnings - TipRanks](https://www.tipranks.com/stocks/mstr/earnings) / [Market Chameleon](https://marketchameleon.com/Overview/MSTR/Earnings/Earnings-Dates/)
- [COIN earnings - Market Chameleon](https://marketchameleon.com/Overview/COIN/Earnings/Earnings-Dates/) / [TipRanks](https://www.tipranks.com/stocks/coin/earnings) / [Coinbase Q2 8-K](https://www.sec.gov/Archives/edgar/data/0001679788/000167978826000087/coin-20260730.htm)
- [HOOD earnings - Investing.com](https://www.investing.com/equities/robinhood-markets-earnings)
- [CRCL - Nasdaq](https://www.nasdaq.com/market-activity/stocks/crcl/earnings) / [Quartr](https://quartr.com/companies/circle-internet-group-inc_20576)
- [Coinbase, Circle, MicroStrategy surge - Yahoo Finance](https://finance.yahoo.com/markets/crypto/articles/coinbase-circle-microstrategy-stocks-surge-210600203.html)
- [Crypto stocks rise with BTC above $84K - Stocktwits](https://stocktwits.com/news-articles/markets/cryptocurrency/crypto-stocks-rise-with-bitcoin-above-84-k-analysts-raise-riot-robinhood-price-targets/cZMZ29DRBgF)
- [Bitcoin news - CoinStats](https://coinstats.app/ai/a/latest-news-for-bitcoin)
- [RIOT - TipRanks](https://www.tipranks.com/stocks/riot/earnings) / [CleanSpark FQ3 2026 - Nasdaq](https://www.nasdaq.com/press-release/cleanspark-reports-third-fiscal-quarter-2026-results-2026-08-06) / [Hut 8 - TipRanks](https://www.tipranks.com/stocks/tse:hut/earnings) / [MARA Q2 8-K](https://www.sec.gov/Archives/edgar/data/0001507605/000150760526000020/q22026earningsannouncement.htm)

**Space / IPOs / lock-ups**
- [SpaceX - Investing.com quote](https://www.investing.com/equities/spacex) / [earnings](https://www.investing.com/equities/spacex-earnings)
- [SpaceX Q2 earnings - CNBC](https://www.cnbc.com/2026/08/04/spacex-spcx-earnings-live-updates-q2-2026.html) / [CNN](https://www.cnn.com/2026/08/04/business/spacex-earnings-q2-2026) / [Quartz](https://qz.com/spacex-earnings-revenue-q2-2026-080426) / [INDmoney](https://www.indmoney.com/blog/us-stocks/spacex-q2-earnings-why-spcx-stock-fell)
- [SpaceX lock-up - Investing.com](https://www.investing.com/news/stock-market-news/spacex-ipo-lockup-expiry-123b-in-shares-set-to-unlock-in-early-august-2026-93CH-4796311) / [Motley Fool](https://www.fool.com/investing/2026/08/05/spacexs-lockup-expires-on-aug-6-heres-why-9115-mil/) / [StockAlarm](https://pro.stockalarm.io/blog/spacex-ipo-lockup-financials) / [TradingKey](https://www.tradingkey.com/analysis/stocks/us-stocks/262164335-spacex-stock-spcx-lockup-expiration-key-information-tradingkey)
- [Initial public offering of SpaceX - Wikipedia](https://en.wikipedia.org/wiki/Initial_public_offering_of_SpaceX)
- [Rocket Lab Q2 2026 results - IR](https://investors.rocketlabcorp.com/news-releases/news-release-details/rocket-lab-announces-second-quarter-2026-financial-results-posts) / [RKLB - TipRanks](https://www.tipranks.com/stocks/rklb/earnings) / [Market Chameleon](https://marketchameleon.com/Overview/RKLB/Earnings/Earnings-Dates/)
- [ASTS - Market Chameleon](https://marketchameleon.com/Overview/ASTS/Earnings/Earnings-Dates/) / [nextearningsdate](https://www.nextearningsdate.com/asts.html)
- [Cerebras IPO - CNBC](https://www.cnbc.com/2026/05/14/cerebras-cbrs-stock-trade-nasdaq-ipo.html) / [day-2 drop - CNBC](https://www.cnbc.com/2026/05/15/cerebras-stock-ipo-debut-ai.html) / [Q2 - CNBC](https://www.cnbc.com/2026/08/12/cerebras-cbrs-q2-earnings-report-2026.html) / [CBRS dates - Market Chameleon](https://marketchameleon.com/Overview/CBRS/Earnings/Earnings-Dates/)
- [Anthropic IPO - Gradually](https://www.gradually.ai/en/anthropic-ipo/) / [StartupHub](https://www.startuphub.ai/ai-news/ipo-watch/2026/anthropic-ipo-roadshow-investor-meetings-2026-07-21) / [GraniteShares](https://graniteshares.com/research/anthropic-ipo-2026-explained-from-965-billion-to-a-possible-2-trillion-listing/) / [Forge](https://forgeglobal.com/insights/anthropic-upcoming-ipo-news/) / [Anthropic - confidential draft S-1](https://www.anthropic.com/news/confidential-draft-s1-sec)
- [OpenAI confidentially files - CNBC](https://www.cnbc.com/2026/06/08/openai-confidentially-files-for-ipo-prepping-wall-street-for-ai-debut.html) / [SmartAsset](https://smartasset.com/investing/openai-stock-ipo)
- [Best recent and upcoming IPOs 2026 - U.S. News](https://money.usnews.com/investing/articles/new-and-upcoming-ipos-in-2026)
- [September 2026 IPO gainers (India) - Kotak Neo](https://www.kotakneo.com/news/market-news/september-2026-ipo-gainers-esds-ss-retail-hero-motors/)
- [Klarna IPO breakdown - ValueAdd VC](https://valueaddvc.com/blog/klarna-ipo-the-complete-breakdown-of-europes-most-anticipated-tech-listing) / [Capital.com](https://capital.com/en-int/learn/ipo/klarna-ipo)
- [Discord IPO slips to 2027 - Curved](https://curvedtrading.com/articles/en/investing/discord-ipo/)
- [Figma since IPO - TIKR](https://www.tikr.com/blog/figma-stock-is-down-13-since-ipo-heres-what-could-drive-a-21-annual-return)
