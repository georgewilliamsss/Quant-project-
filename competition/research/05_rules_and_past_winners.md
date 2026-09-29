# Bloomberg Global Trading Challenge 2026: exact rules and what it takes to win

Prepared 2026-09-29 by the research analyst. Scope: Part A (rules of the 2026 edition) and Part B (past winners and return spread, 2021-2025).

## Evidence quality: read this first

- Every direct page fetch was blocked by the network egress policy (WebFetch returned EGRESS_BLOCKED for portal.bloombergforeducation.com, bloomberg.com, assets.bbhub.io, data.bloomberglp.com, TUM, HKU, Baruch, quantchallenges.com, Yahoo Finance, PRNewswire, Barchart, CUHK, Lehman, Essex, UT Dallas and others). I did not try to route around the block.
- All findings below therefore come from WebSearch result summaries that cite those pages, not from my own reading of the primary pages. Text in "quotes" is as relayed by the search tool. It is probably verbatim for short legal phrases, but I could not confirm it against the original page.
- The shared WebSearch budget (200 per session) ran out after roughly 35 of my searches. The last three planned searches were not performed. See "Open items" for exactly what is still missing and how to close it.
- Confidence tags used below: **[Confirmed]** = same fact returned by 2 or more independent sources or by the official page itself; **[Single]** = one source only; **[Inferred]** = my deduction, not published; **[Not found]** = searched, nothing returned.

---

## 1. Rules that change our strategy (top section)

### 1.0 Corrections to our team's working assumptions

| Team assumption | What the sources say | Status |
|---|---|---|
| $100,000 notional | **US$1,000,000 virtual USD.** 2025 T&C: "The starting notional amount to be invested by each team is US$1,000,000". Also in the 2022 FAQ, 2024 HKU intro PDF, TUM page and the Jan 2026 press release. Only the scale changes: the 20% cap is $200,000 per name. Returns are scale-free. | [Confirmed] |
| Starts Oct 14, one month | **Starts Mon 12 Oct 2026, 09:00 NY. Ends Fri 13 Nov 2026, 17:00 NY.** That is 5 calendar weeks (25 weekdays), not one month. | [Confirmed] (portal listing, TUM listing, search summaries agree) |
| Min 5 stocks | No explicit minimum count found in any source. 5 is arithmetic: with a 20% cap and a full-investment requirement you need at least 5 names. | [Not found] as a stated rule, [Inferred] |
| Long-only, no leverage, no shorting, 20% cap | Long only, no leverage, single-name equities only (no ETFs), 20% cap: stated in the 2024 HKU intro PDF and the FAQ as relayed. | [Confirmed for 2024; probable for 2026, not read on the 2026 page] |
| Anyone can enter | **Teams of 3-5 students led by a faculty advisor**, executing trades in the Bloomberg Terminal. Faculty advisor or team captain registers the team. We must confirm we are eligible (student status, advisor, Terminal access). | [Confirmed] |

### 1.1 Registration deadline is in 5 days

- "Faculty Advisors or Team Captains must register their teams by October 4, 2026, 11:59 PM (New York Time)." Oct 4 is a **Sunday**. Today is Tuesday 29 Sep. One search result showed the registration window as Aug 31 - Oct 5, 2026; treat the earlier date (Oct 4, 11:59 PM NY) as binding.

### 1.2 Cap: "20% of the notional amount", and the measurement question is unresolved

- Rule text (as relayed, appears in T&C, FAQ and 2024 intro): **"No single position held by a Team may be greater than twenty percent (20%) of the notional amount."**
- Wording is "of the notional amount" (the $1M starting amount), not "of portfolio value". Whether it is tested only when an order is placed, or continuously on marked value, and what happens when a winner drifts above the cap (forced sale, order rejection, disqualification, nothing) is **[Not found]** in anything I could see.
- Circumstantial evidence [Inferred]: the 2025 winner reportedly grew $1M to $4.1M. If a strict continuous cap of $200k per name applied, that portfolio would need 21 or more names all at the cap. That seems unlikely for a 5-week concentrated run, which weakly suggests the cap is enforced at order entry only. This is a guess, not a rule.
- Strategy implication: this is the single most valuable fact to nail down before Oct 12 because it determines whether we can "let winners run" beyond $200k. Until confirmed, plan for the worst case (trim to the cap) and price that in.

### 1.3 Must be fully invested early; cash is not a free option

- 2025 T&C as relayed: "the entire starting notional amount must be invested in full within the first business week of the Challenge Period (i.e., no later than 9:00 am ET on October 17, 2025)".
- 2026 listing as relayed: challenge begins Oct 12 09:00 NY, initial positions must be entered by **Oct 16, 11:59 PM NY**. The exact 2026 cut-off wording may differ from 2025 (9:00 am ET vs 11:59 PM), so read the 2026 T&C.
- Whether uninvested cash earns anything, whether cash is scored at 0% or at the benchmark, and whether you can go to cash after the first week are **[Not found]**.
- Strategy implication: you cannot sit in cash waiting for a catalyst at the start. With a 20% cap and full investment you are structurally 5-plus names.

### 1.4 How the score works: relative P&L vs the WLS Index (formula not public in what I saw)

- Ranking rule as relayed: "The winning team will have the highest time weighted relative return, relative to the Bloomberg World Large, Mid & Small Cap Price Return Index (WLS Index)." T&C variant: "The winning team is selected based on trades that generate the highest Relative P&L over the Challenge Period. The definition of 'Relative P&L' can be found on the Bloomberg Terminal under Calculations on the TMSG help menu." Handbook variant: the win criterion is the "Rel P&L" column.
- Handbook (2025 edition per the result) on why relative matters: "Your trades don't just have to make money; they have to make more money than the benchmark index. For this reason, you can have a positive P&L, but a negative Relative P&L."
- The benchmark is a **Price Return** index, so it excludes dividends. Whether team P&L includes dividends is [Not found].
- The winners are published in **dollar relative profit on the $1M** (2021: nearly $470k; 2022: $305,644; 2023: $637,399; 2024: $1,676,618). In 2023 the same team is quoted at +67.7% return and +$637,399 relative profit. 67.7% minus 63.7% implies a benchmark move of about 4.0% over the window, i.e. relative = arithmetic difference in returns applied to $1M [Inferred]. It is not a ratio.
- Strategy implication: because it is relative, in a rising market a cash position hurts and in a falling market it helps [Inferred from the definition, not from a stated cash rule]. The objective is to beat the index, not to make money.

### 1.5 Trading is continuous, executed inside the Terminal

- Trades are sent through the Terminal (TMSG) to the challenge network: "Teams of 3-5 students, led by a faculty advisor, will use the Terminal to define market assumptions, develop a return-generating strategy, and execute trades over the Bloomberg network." "For each stock the team picks, the team captain will designate the dollar amount for trade from available funds." TMSG monitors cash balances, trade status and P&L in real time.
- No trade-count limit found [Not found]. Actual behaviour: press releases report about 48,000 trades in 2023 (1,727 teams) and 72,000+ in 2025 (about 2,600 teams), i.e. **about 28 trades per team on average in both years** [derived by me]. Winners describe "daily portfolio monitoring" (2025) and led "five of the six weeks" (2024). So rebalancing during the window is allowed and used.
- Need: at least one Bloomberg Terminal login on the team (typically the university's Bloomberg lab). Confirm we have this.

### 1.6 Universe

- "Any stock in the WLS Index", "Single name equities - no ETFs", "Long only - no short positions", "No leverage" (2024 HKU intro PDF, [Confirmed for 2024]). FAQ as relayed also says ETFs are not permitted.
- The WLS Index is the allowed list. RIT reported about 10,000 stocks in the Bloomberg World index; in 2022, 948 teams collectively held 4,469 distinct stocks. So non-US listings are allowed. Foreign stocks were a deliberate part of the 2024 winner's edge.
- Options, futures, FX, crypto directly, ETFs: excluded by construction (single-name index constituents only) [Inferred]. Crypto exposure is only possible through listed equities that are index members.
- ADR treatment, minimum price, penny stocks, minimum market cap or liquidity, currency/settlement treatment for non-USD names, corporate-action handling: **[Not found]**. Since the index covers large, mid and small caps, micro-caps are presumably out [Inferred]. Trade sizing is in USD amounts, so FX handling is probably done by the platform; unknown.

### 1.7 Payoff structure: it is a tournament, so risk-seeking is rewarded

- One global ranking among about 2,600-2,700 teams (2025) with the Grand Prize going to the top team and one regional winner per region (see Section 3). Winners have said so explicitly (RIT 2024): the strategy was to "make as much money as possible without being concerned about the risks of losing", and "while it's not necessarily a great strategy in real life, it worked for this competition".
- The score is unbounded upside and (relatively) bounded downside for ranking purposes, so maximizing P(rank 1) is not the same as maximizing Sharpe. See Section 4 for the return levels involved.

---

## 2. Part A detail: timeline, prizes, participation

### 2.1 Timeline (2026 edition)

| Milestone | Date/time | Source status |
|---|---|---|
| Registration opens | Aug 31, 2026 (window listed as Aug 31 - Oct 5) | [Single] search summary of portal/quantchallenges listing |
| Team registration deadline | **Sun Oct 4, 2026, 11:59 PM NY** (window page says Oct 5) | [Confirmed] by 2 result summaries (portal, TUM-related) |
| Challenge begins | **Mon Oct 12, 2026, 09:00 AM NY** | [Confirmed] |
| Initial positions deadline | **Fri Oct 16, 2026, 11:59 PM NY** | [Confirmed]; 2025 T&C said fully invested "no later than 9:00 am ET" on the Friday, so check whether 2026 is different |
| Performance measured through | **Fri Nov 13, 2026, 5:00 PM NY** | [Confirmed] |
| Winners announced | Fri Nov 20, 2026 | [Single], from a search summary. Past editions announced results weeks later (2025 press release was dated Jan 27, 2026) |

Weekdays: Oct 12-16, 19-23, 26-30, Nov 2-6, 9-13 = 25 trading weekdays.

Older editions used different dates (an older info sheet gave an "October 8, 09:00 am NY" initial-positions cut-off). Do not reuse.

### 2.2 Prizes and rounds

- Structure [Confirmed]: a single global leaderboard, no separate school-level qualifying round found. Bloomberg recognizes a **Grand Prize winner plus one winner per region**. 2025 regional winners were Europe, Latin America, Middle East and Africa, and North America; the Grand Prize team (CUHK, Hong Kong) fills Asia and Oceania. In 2023, HKU was listed as "Grand Prize Winner, Regional Prize Winner: Asia and Oceania", so one team can fill both.
- Prize content: no cash prize found [Not found]. Reported rewards are institutional: e.g. Bloomberg for Education gave all Bilkent University students 6 months of free Bloomberg.com access for its regional win. Another result mentioned a one-year Bloomberg.com trial for a winning campus [Single, vague]. Certificates exist on the portal. quantchallenges.com lists a "reward" field but I could not read it.
- Percentile bragging rights are used by universities (top 1%, 3%, 5%) but the official ranked list is on the portal leaderboard (2025 challenge appears to be portal ID 8: portal.bloombergforeducation.com/trading_challenges/8/leaderboard; 2026 is ID 13).

### 2.3 Participation by year

| Year | Teams | Students / countries | Trades | Source status |
|---|---|---|---|---|
| 2021 | "nearly 500" | n/a | n/a | [Single] UConn Today headline ("Topped Nearly 500 Teams to Win Bloomberg's First Global Trading Challenge") |
| 2022 | 948 | ~4,500 students; 35 countries; 948 teams invested $785,061,647 across 4,469 individual stocks | n/a | [Confirmed] Bloomberg release "Bloomberg Trading Challenge Attracts 4,500 Students Globally" |
| 2023 | 1,727 | ~8,400 students | 48,000+ | [Confirmed] FDU note (41st of 1,727) plus release "8400 Students Compete..."; AI stocks most popular |
| 2024 | 2,453 | ~10,000 students (release headline); 46 countries; RIT says 396 universities | n/a | [Confirmed] RIT article; a Waterloo article cites 13,029 people in 2,520 teams (probably registrations, year not confirmed) |
| 2025 | 2,600+ (Bloomberg release, Jan 27, 2026); 2,700 in USF and ARU write-ups | 11,000+ students, 50 countries (release); ARU says 57 countries; USF says 400 universities; CUHK says 396 universities | 72,000+ | [Confirmed] "Bloomberg's Global Trading Challenge Sets Participation Record" |

Field growth: roughly 500 to 948 to 1,727 to 2,453 to 2,600-2,700. Extrapolating, expect 2,800-3,200 teams in 2026 [Inferred].

2022 side note [derived]: $785.1M invested / 948 teams = $828k per team, i.e. on average about 17% of the $1M notional was not invested in that edition.

### 2.4 FAQ nuances: what I could and could not find

| Question | Finding |
|---|---|
| Corporate actions | [Not found]. Bloomberg publishes an index corporate-action methodology (assets.bbhub.io), but no challenge-specific rule surfaced |
| Options, futures, FX | Not allowed by construction: single-name equities in WLS only [Inferred] |
| Penny stocks, minimum price, minimum market cap, liquidity | [Not found] |
| ADRs | [Not found]. They are single-name equities but only allowed if in the WLS Index |
| Non-US exchanges | Allowed: RIT winner held mostly foreign stocks; ~10,000-name universe [Confirmed] |
| Currency/settlement | [Not found] |
| Cap breach handling | [Not found] |
| Trade limits | [Not found] |
| Cash return | [Not found] |
| Benchmark formula | Defined in TMSG help under Calculations (Terminal only); not public in what I saw |

---

## 3. Historical winning returns table (Part B)

Return basis differs across sources (relative dollar profit on $1M, absolute return, or "return"). Treat as order-of-magnitude.

| Year | Teams | Winner | Winner result | Other ranks published | Status |
|---|---|---|---|---|---|
| 2021 (first global edition) | ~500 | UConn Stamford, 5 graduate students (financial risk management) | Portfolio beat the Bloomberg benchmark by "nearly $470,000" (about +47 pts on $1M) | 2nd: a team from a Saudi Arabian university, more than $100k behind, so 2nd is at most about $370k relative [Inferred from "more than $100,000"] | [Single] UConn Today and Hartford Business Journal |
| 2022 | 948 | University of Southampton (UK) | Relative profit **$305,644** (about +30.6 pts) | n/a | [Confirmed] Bloomberg release |
| 2023 | 1,727 | University of Hong Kong (HKU), Asia-Oceania regional winner as well | **+67.7% return over six weeks; relative profit +$637,399** (about +63.7 pts, implying about +4% benchmark) | A Waterloo team placed 10th in the year before GWNB's 2nd (so 2023 if GWNB is 2024); FDU 41st of 1,727 | [Confirmed] HKU page and Bloomberg release |
| 2024 | 2,453 | RIT "Tigers Trading" (Macko, Ptak, Kauffman) | Relative profit **$1,676,618** (about +167.7 pts) | 2nd: Waterloo GWNB, most likely (result surfaced in a 2024 query; year not confirmed). Newcastle "Wall St Warriors" 1st in UK and 20th globally (year not confirmed). Return of 2nd not found | [Confirmed] RIT release for winner |
| 2025 | 2,600-2,700 | CUHK "Bear Bull" (Sayogo, Perdana, Tjen, Nicolaus; advisor Prof. Haynes Yung) | Headline "return of more than 400%, growing its virtual portfolio to US$4.1 million" (internally inconsistent: $1M to $4.1M is +310%, not +400%; unresolved whether relative or absolute) | 6th: Anglia Ruskin "Team Alpha", profit $438,846 (Europe winner). 9th: Drexel LeBow "Daring Dragon Sharks", 23% return (North America winner, 1st of 907 NA teams). 12th: Bilkent ECON team (MEA winner). 19th: Essex County College (5th in NA). 69th: USF Bulls, relative return $53,194 (+5.3 pts), "top 3%". 2nd-5th not published in anything I saw | [Confirmed] winner headline; [Single] each other rank |

Waterloo GWNB note: Waterloo's story says the team finished second worldwide by "highest time weighted relative return" and that Gao's team the previous year (as a first-year) placed tenth. Because the page also cites "13,029 people in 2,520 teams", which does not match the 2025 release (2,600+) or the 2024 RIT count (2,453), the edition is not certain. Weight it as 2024 but unconfirmed. Return not found.

### 3.1 Regional winners found (2025)

| Region | Winner | Detail |
|---|---|---|
| Asia and Oceania | (Grand Prize) CUHK | >400% headline |
| Europe | Anglia Ruskin University, Cambridge, UK ("Team Alpha") | 6th worldwide; profit $438,846 on $1M; five-week challenge |
| North America | Drexel University LeBow ("Daring Dragon Sharks": Vu, Ali, Cao, Zheng; advisor Prof. Daniel Dorn) | 1st of 907 NA teams, 9th worldwide, 23% return over a six-week description |
| Latin America | Universidad de Lima ("Profitable Values": Alarcon, Forlong, Chevarria, Delgado) | return not published in what I saw |
| Middle East and Africa | Bilkent University, Ankara ("Bilkent ECON": Gokcen, Cula, Donmez; advisor Prof. Hakan Kara) | 12th worldwide; return not found |

Earlier regionals: 2022 Southampton (UK) won overall. 2023: HKU took Grand Prize plus Asia-Oceania. UK note: Newcastle placed 1st in UK, 20th globally in a year that is not confirmed.

---

## 4. What it takes to win (calibration)

### 4.1 Return needed

| Percentile in 2025 (about 2,700 teams) | Rank | Reported result | Basis |
|---|---|---|---|
| Top 0.04% (winner) | 1 | >400% headline, $4.1M final (about +310% by the dollars) | as published, unclear whether relative |
| Top 0.22% | 6 | +$438,846 (about +44%) | profit on $1M |
| Top 0.33% | 9 | +23% | return |
| Top 2.6% | 69 | +$53,194 (+5.3%) | relative return |

- Winner needed, by year: about +30 to +47 pts relative (2021, 2022, fields of 500-950); about +64 pts (2023); about +168 pts (2024); about +310 pts or more (2025). The winning number has risen every year while the field grew about 5x; the last two winners were multiple-of-capital outcomes.
- The 2025 distribution is extremely fat-tailed at the top: the winner's reported profit is roughly 7x or more that of the 6th place team (+310% to +400% vs +44%). Rank 6 to 9 to 69 falls from about +44% to +23% to +5%. So a diversified, risk-managed "+10-25% over the index" outcome lands roughly in the top 0.3%-2% but is nowhere near the win.
- Order-statistics reading [Inferred]: for a field of about 3,000 teams, the winner is the roughly 99.97th percentile. The two most recent winners posted about +168 pts (2024) and +310 pts or more (2025). If 2026 resembles those editions, a winning run is a triple-digit relative return in five weeks. With a 20% cap that requires cap-sized holdings that multiply (or repeated compounding through rotation), which only comes from concentrated, extremely high-volatility positions. This is my reading of the pattern, not a published requirement; P(rank 1) is low even for the best strategy, and rank 1 appears reachable only through extreme variance.
- Comparison: the +23% Drexel run (9th of about 2,700) and the +5.3% USF run (69th) show that a modest strategy earns a top-1% to top-3% finish and no more. If "top 1-3%" is the acceptable goal, volatility-lean strategies work; if the goal is winning, they do not.

### 4.2 Strategies reported by winners and placers

| Team/year | Reported approach | Status |
|---|---|---|
| RIT, 2024 winner | "Betting on volatility", mostly foreign stocks; led the standings in five of six weeks; they learned from the previous year that the aim is to "make as much money as possible without being concerned about the risks of losing" | [Confirmed] RIT news pages |
| CUHK "Bear Bull", 2025 winner | "Active, disciplined strategy with daily portfolio monitoring and risk management across global equity markets over five weeks", executed via the Terminal. **No holdings or catalysts published** | [Confirmed] CUHK Business School and GLEF pages |
| HKU, 2023 winner | React to macro news and events; "If you get complacent, you'll miss out on opportunities". AI stocks were the most popular investment across the field that year (48,000+ trades) | [Confirmed] HKU page and release |
| Drexel, 2025 NA winner and 9th worldwide | Data science and business analytics; seriously considered liquidating to preserve profits during large market moves, which "turned out well" | [Single] Drexel and Triangle articles |
| USF Bulls, 2025 (69th) | Earnings-volatility strategy: stocks with appropriate volatility on earnings day across technology, healthcare, energy and rare earth materials | [Single] USF release |
| ARU Team Alpha, 2025 (6th) | Adjusted portfolios as markets moved; no specifics found | [Single] |

Themes: high volatility, foreign and non-US stocks, daily monitoring, event and earnings catalysts, momentum in hot themes (AI in 2023; rare earths noted in 2025). No source I saw names crypto proxies, biotech catalysts or leveraged-style plays as winners' holdings. Do not assume those from this report. (A separate research note, 01_biotech_catalysts.md, covers biotech catalysts.)

### 4.3 What the spread tells us

- Ranked dollar profits fall very steeply from first place. Ranks 6, 9, 69 in 2025 are separated by +44%, +23%, +5% while the winner is at +310% or more.
- RIT (2024) said explicitly that it ignored downside risk; CUHK (2025) describes daily risk management, so risk-seeking is not universal among winners. The contest formula (relative to a broad world index, ranked ordinally) still pays for variance [Inferred].

---

## 5. Open items and how to close them

Ordered by value to our strategy:

1. **Cap enforcement** (Section 1.2): read the live FAQ on the portal (portal.bloombergforeducation.com/trading_challenges/faqs) and the 2026 T&C (.../trading_challenges/terms) for the exact "20%" text, and email or ask Bloomberg for Education whether a position that appreciates above $200k (or above 20% of portfolio value) is auto-sold, blocked or allowed.
2. **Relative P&L formula and cash treatment**: Terminal function TMSG then help menu then Calculations then "Relative P&L". Confirm: is the benchmark measured from Oct 12 09:00 or from each team's entry time? Does cash earn 0%? Is P&L price-only or total return?
3. **2025 full leaderboard**: open portal.bloombergforeducation.com/trading_challenges/8/leaderboard (a browser with Bloomberg for Education login may be needed). It should give the entire ranked relative-return distribution and settle whether CUHK's number is relative or absolute and what ranks 2-5 achieved. Do the same for the 2026 leaderboard (ID 13) during the event to track live ranking.
4. **Eligibility**: confirm that the team meets the "3-5 students with faculty advisor" requirement and has Terminal access; registration closes Sun Oct 4, 11:59 PM NY.
5. **Full-investment deadline in 2026**: 2025 wording was "invested in full within the first business week (no later than 9:00 am ET on October 17, 2025)"; 2026 landing page says initial positions by Oct 16 11:59 PM NY. Confirm which governs.
6. **CUHK 2025 holdings**: check the CUHK Business School news page (bschool.cuhk.edu.hk/school-news/cuhk-business-school-students-crowned-world-champions-in-bloomberg-global-trading-challenge/) and ug.bschool.cuhk.edu.hk for any strategy detail; also the Waterloo (uwaterloo.ca/math/news/math-team-gwnb-wins-second-place-bloomberg-global-trading) page for the year and the return of the 2nd-place team.
7. **Remaining unrun searches** (budget exhausted): Waterloo GWNB year and return; Newcastle year and return; 2021/2022 runner-up returns; 2025 "top 1%" cut-off return from FSU/other universities; Asia-Pacific and UK regional stories with returns (Southampton 2022, City St George's "Bayes" 2022, Newcastle, Edge Hill 2024, NMIMS 2025, Kean, Iona, LSU top 1% 2024, Zicklin/Baruch). To continue, raise CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION.

---

## 6. Sources (all reached via search summaries; primary pages were egress-blocked)

Official Bloomberg and portal:
- 2026 challenge page: https://portal.bloombergforeducation.com/trading_challenges/13 and https://portal.bloombergforeducation.com/trading_challenges
- FAQs: https://portal.bloombergforeducation.com/trading_challenges/faqs
- Terms: https://portal.bloombergforeducation.com/trading_challenges/terms
- 2025 leaderboard: https://portal.bloombergforeducation.com/trading_challenges/8/leaderboard
- 2022 FAQ PDF: https://assets.bbhub.io/professional/sites/10/2022-Bloomberg-Global-Trading-Challenge-FAQ.pdf
- 2021 T&C PDF: https://assets.bbhub.io/professional/sites/10/Trading-Challenge-Terms-and-Conditions.pdf
- Older info sheet: https://assets.bbhub.io/professional/sites/10/Trading-Challenge_Info.pdf
- 2025 Trader's Handbook (mirror): https://studylib.net/doc/27984002/2025-bloomberg-traders-handbook-
- Press releases: "Bloomberg's Global Trading Challenge Sets Participation Record" (https://www.bloomberg.com/company/press/bloombergs-global-trading-challenge-sets-participation-record/ and https://www.prnewswire.com/news-releases/bloombergs-global-trading-challenge-sets-participation-record-302670176.html); "Bloomberg Enriches Financial Education for 10,000 Students through Global Trading Challenge" (https://www.prnewswire.com/news-releases/bloomberg-enriches-financial-education-for-10-000-students-through-global-trading-challenge-302369506.html); "8400 Students Compete in Bloomberg Global Trading Challenge..." (https://www.prnewswire.com/news-releases/8400-students-compete-in-bloomberg-global-trading-challenge-building-real-world-investing-skills-302046417.html); "Bloomberg Trading Challenge Attracts 4,500 Students Globally" (https://www.prnewswire.com/news-releases/bloomberg-trading-challenge-attracts-4-500-students-globally-301752535.html)
- HKU 2024 intro PDF (rules slide): https://ug.hkubs.hku.hk/f/competition/254985/262466/2024_GTC_Introduction.pdf
- TUM 2026 page: https://www.fa.mgt.tum.de/en/fm/teaching/project-studies/list-of-open-project-studies/bloomberg-global-trading-challenge-2026/
- HKU 2026 page: https://ug.hkubs.hku.hk/competition/bloomberg-global-trading-challenge-2026
- Baruch 2026 PDF: https://zicklin.baruch.cuny.edu/wp-content/uploads/sites/10/2026/09/2026-Bloomberg-Global-Trading-Challenge.pdf (surfaced in results, content not readable)
- quantchallenges.com listing: https://quantchallenges.com/challenges/2026-bloomberg-global-trading-challenge-qc-2899 (content not readable)

Winners and placers:
- CUHK: https://www.bschool.cuhk.edu.hk/school-news/cuhk-business-school-students-crowned-world-champions-in-bloomberg-global-trading-challenge/ ; https://www.glef.cuhk.edu.hk/news-events/grand-prize-winner-bloomberg-global-trading-challenge-2025/
- RIT 2024: https://www.rit.edu/news/rit-trio-triumphs-global-trading-challenge ; https://www.rit.edu/spotlights/rit-students-win-international-bloomberg-trading-competition
- HKU 2023: https://ug.hkubs.hku.hk/student-sharing/2023-bloomberg-global-trading-challenge-grand-prize-winner-regional-prize-winner-asia-and-oceania ; https://financefeeds.com/hong-kong-university-wins-bloombergs-trading-challenge/
- Southampton 2022 (via release) and City St George's: https://www.citystgeorges.ac.uk/news-and-events/news/2022/12/bayes-students-trade-their-way-to-the-top-in-bloomberg-global-trading-challenge
- UConn 2021: https://today.uconn.edu/2021/12/business-graduate-students-turned-on-the-jets-topped-nearly-500-teams-to-win-bloombergs-first-global-trading-challenge/ ; https://hartfordbusiness.com/article/uconn-students-take-top-prize-in-prestigious-2021-bloomberg-global-trading-challenge/
- ARU: https://www.businessweekly.co.uk/posts/anglia-ruskin-wolves-devour-european-crown-in-bloomberg-global-trading-challenge
- Drexel: https://www.lebow.drexel.edu/news/drexel-finance-students-place-first-north-america-bloomberg-global-trading-challenge ; https://www.thetriangle.org/article/lebow-team-wins-bloomberg-global-trading-challenge
- Bilkent: https://library.bilkent.edu.tr/congratulations-to-bilkent-econ-team-6-months-free-acess-to-bloomberg-com/
- Universidad de Lima: https://www.bloomberg.com/latam/blog/equipo-de-la-universidad-de-lima-obtiene-el-primer-puesto-a-nivel-latinoamericano-en-competencia-de-inversiones-de-bloomberg/
- USF 2025: https://www.usf.edu/business/news/2025/12-10-bloomberg-trading-challenge-usf.aspx
- Waterloo GWNB: https://uwaterloo.ca/math/news/math-team-gwnb-wins-second-place-bloomberg-global-trading ; https://uwaterloo.ca/math-business-accounting-programs/news/team-math-faculty-students-placed-1st-among-canadian-teams
- FDU 2023 (41st of 1,727): https://medium.com/@fdusilberman/silberman-students-place-41st-out-of-1-727-teams-for-the-2023-bloomberg-global-trading-challange-4ad343e0a8ea
- Essex County College 2025: https://www.essex.edu/news/ecc-students-achieve-strong-results-in-2025-bloomberg-global-trading-challenge/
- Newcastle: https://www.ncl.ac.uk/business/news/bloomberg-global-trading-challenge-2024/
