# Bloomberg Global Trading Challenge 2026: Master Playbook

Written 29 Sep 2026 from research notes 01-07 in `competition/research/`. Anything tagged **Verify:** must be checked on the Terminal before money goes into it.

---

## 1. Read this first

### 1.1 What we had wrong

| We thought | Correct fact | Consequence |
|---|---|---|
| $100,000 notional | **US$1,000,000.** The 20% cap is **$200,000 per name.** | Returns are scale-free; order sizes are 10x bigger. |
| Starts Oct 14, runs a month | **Opens Mon Oct 12, 09:00 NY. Measured to Fri Nov 13, 17:00 NY.** 25 weekdays. | Two extra days at the start. |
| Register when ready | **Registration closes Sun Oct 4, 23:59 NY.** Advisor or captain registers a team of 3-5 students. | Register this week. Confirm eligibility and Terminal access. |
| Score = our return | **Time-weighted return relative to the WLS Price Return Index**, published as dollar relative P&L. | Cash loses whatever the index gains. |
| Build the book gradually | **Fully invested in week 1.** Initial positions due **Fri Oct 16, 23:59 NY** (2025 rules said 09:00 that Friday). | Enter on Day 1. |
| Minimum 5 stocks | No stated minimum. Five comes from the 20% cap plus full investment. | Hold ⌈book value / $200k⌉ names. |
| Anything goes | Long only, no leverage, no ETFs, WLS members only (~10,000 global names). | Micro-caps below the WLS cut-off are out. |

### 1.2 Five things to confirm on the Terminal before Oct 12

1. **Cap enforcement.** Is the 20% cap checked only at order entry, or continuously? What happens on a breach? Read the TMSG help menu and the challenge FAQ, then get a written answer from Bloomberg for Education through the faculty advisor. This decides whether winners can run.
2. **WLS membership of every candidate.** `WLS Index MEMB <GO>`, or index membership on `DES`. Trade the local line that is in the index. INO (~$130M) is at real risk of being below the cut-off.
3. **Simulator fill rules.** Market or limit fills, last price or bid/ask, after-hours trading (FDA news often lands after the close), whether a Taipei or Tokyo stock locked limit-up can be bought at the limit, commissions. Answer with one small test order.
4. **Minimum price and liquidity rules.** Minimum price, market cap or volume, Hong Kong board lots, any minimum number of positions.
5. **How relative P&L treats cash and FX.** TMSG help → Calculations → Relative P&L. Benchmark measured from Oct 12 09:00 or from our entry? Cash at 0%? Price or total return? How are non-USD positions converted, and do FX moves count against the cap?

---

## 2. The bar and the logic

**Target: +140% relative in 25 trading days.** Winners made +64 points (2023), about +168 (2024) and at least +310% (2025). The Monte Carlo in note 07, fitted to those winners and to 2025 rank data (#6 +44%, #9 +23%, #69 +5.3%), puts the median winning score for a 3,000-team field at **+142%**. +100% wins about 1 time in 5, +140% is a coin flip, +200% wins 3 times in 4. A +20-40% result is top 1% and wins nothing.

**Why five static picks cannot win.** A position is capped at $200k at entry, so a stock that doubles adds only +20% to the book. With four flat positions, the fifth must return about **+610%** to lift the book to +142%. Five independent tickets held to the end won **0.6%** of simulations (0.11% with fairly priced events).

**What wins: a chain of correlated binary bets, winners left to run.**
- **Chain, don't hold.** Each slot owns one catalyst. When it resolves, win or lose, the slot sells and rolls everything into the next catalyst. Going from 1 to 3 events per slot lifted P(win) about tenfold: 7-29% under the notes' assumptions, 2.8-7.3% with fairly priced events.
- **Correlate our bets.** One correlated theme beat five unrelated names 17-31x. Modest correlation among our binaries nearly doubled P(win) (2.8% → 5.2%).
- **Buy variance.** Contested FDA decisions and Phase 3 readouts (+80% to +200% / -55% to -75%) are the tickets. Consensus approvals (+5% / -50%) are poison. Earnings roulette (0.95%) and weekly momentum rotation (0.27%) are too tame.
- **Let winners run** where the cap allows. Trimming to 20% cut the best chain's P(win) by a third.
- **Avoid the crowd.** Every team will own Micron. A crowded theme pays exactly when the bar is highest, so we take the theme through higher-beta, less-owned names.

**Realistic expectation:** 2-5% to win, about 100 times a random team's 0.033%. Being behind means adding variance, never cutting it.

---

## 3. The opening book (enter Oct 12-13)

**Structure:** 3 slots in one theme (memory and AI hardware, through its highest-beta, least-crowded names) and 2 slots in a biotech binary chain. Slots shift toward events as November supply arrives.

**Sizing.** Five positions at 20% ($200k nominal). Until Bloomberg confirms the cap is checked only at entry (reading A), buy **$190k each** and put the remaining **$50k in SNDK US** as a buffer (reading B), so we stay fully invested without breaching on the first uptick or FX move. Under reading A, buy $199k each. **Under the strict (continuous) reading the cap does not grow with the book: above $1M, re-spread across ⌈book value / $200k⌉ names** (seven at $1.4M, ten at $2M).

| Slot | Ticker | Sleeve | Main catalyst | Bull / bear (estimates) | Exit |
|---|---|---|---|---|---|
| 1 | **AXTI US** | Theme | Q3 results, late Oct / early Nov | +50% to +100% / -35% to -50% | Day after Q3 print |
| 2 | **2408 TT** | Theme | October sales by Nov 10 | +50% to +80% / -30% to -40% | Day after October sales |
| 3 | **285A JP** | Theme | Results ~Nov 12-14 | +50% to +80% / -30% to -40% | Through results if ≤ Nov 12 JST |
| 4 | **MRNA US** | Binary A | ESMO Phase 3 data, Sat Oct 24 | +30% to +60% / -20% to -35% | Mon Oct 26 open |
| 5 | **INO US** | Binary B | PDUFA Fri Oct 30 | +80% to +200% / -55% to -75% | Reaction day |

**Slot 1: AXTI US (AXT Inc).** US small-cap making indium-phosphide and gallium-arsenide substrates for AI-datacentre optics. The highest-beta name in the complex: **+1,529% over 52 weeks**, ranked #2 for a +50% month (10-12%) in note 03, and a small-float supplier rather than a mega-cap every team owns. Catalysts: SK Hynix Q3 read-through (~Oct 22-23), hyperscaler capex (~Oct 27-29), China export-licence headlines, own Q3. Bull +50% to +100%; bear -35% to -50% on a rate spike or supply-glut headline (memory names fell 5-16% in single days on Jul 2, Aug 6, Aug 18). Exit the day after the Q3 print and roll into IONQ US. **Verify:** Q3 date (last year's pattern only), price, float, short interest, ADV ≥ $2M, WLS membership.

**Slot 2: 2408 TT (Nanya Technology).** Taiwan commodity-DRAM maker, historically the highest-beta proxy for DRAM contract prices (up as much as 95% in Q1). Note 06 prefers Asian mid-caps: few student teams hold them and their news flow is independent of US names. The 2024 winners held mostly foreign stocks. Taiwan's ±10% limit turns big news into multi-day runs. Catalysts: SK Hynix Q3, Samsung final Q3 (~Oct 29-30), TrendForce contract prices at month-end, **October sales by Nov 10**. Bull +50% to +80%; bear -30% to -40%. Exit the day after the October sales release, then roll into the endgame. **Verify:** price, YTD move, WLS membership, limit-up fills.

**Slot 3: 285A JP (Kioxia Holdings).** Japanese NAND maker and SanDisk's fab partner. SanDisk is +695% YTD on NAND pricing; Kioxia has the same driver, a listing students rarely touch, and results that may land at the very end of the window. Catalysts: SanDisk fiscal Q1 (~Nov 5-6), NAND contract prices, **own results ~Nov 12-14**. Bull +50% to +80%; bear -30% to -40%. If results come after the Tokyo close on or before Nov 12, hold through the last Tokyo session; if later, sell Nov 11 and roll into the endgame. Tokyo is shut Mon Oct 12, so this fills at the Oct 13 Tokyo open. **Verify:** results date, price, WLS membership.

**Slot 4: MRNA US (Moderna).** +550% YTD after its Aug 19 Phase 3 melanoma win (intismeran plus Keytruda). Full data at the ESMO Presidential Symposium on **Sat Oct 24**: the biggest dated binary in the first half. At ~$70-75B, Merck could bid, which gives a real right tail (note 03: 9% for a +50% month). Certainly a WLS member, liquid, and it correlates our binary sleeve with INO. Bull +30% to +60% on stronger survival data or a bid (Aug 19 was +100% intraday); bear -20% to -35% sell-the-news. **Sell at the Mon Oct 26 open**, win or lose, or on the day of any bid. **Verify:** ESMO slot, and `OMON` implied move and skew by Oct 9. If the implied move is below ±15% or puts are richer than calls, swap to a WLS small-cap mRNA or cancer-vaccine peer showing ±35% into ESMO (find it on `BI` and `EQS`).

**Slot 5: INO US (Inovio).** ~$130M biotech; its BLA for INO-3107 in adult recurrent respiratory papillomatosis is under accelerated-approval review, **PDUFA Fri Oct 30**. The only verified in-window, sub-$500M, single-asset FDA decision in our research, and a genuine coin-flip: a competitor was approved in 2025, and an FDA note reportedly questions accelerated-approval eligibility. That is the contested, convex ticket the simulation rewards. Hold from Day 1 to catch the run-up. Bull +80% to +200%; bear -55% to -75%; approval odds ~50-55%. Sell on the reaction day (Oct 30 in hours, else Mon Nov 2 open). Sell at once if INO announces a raise or the date is extended. **Verify:** WLS membership, price, the FDA-note source (it comes from Inovio's own Dec 2025 BLA-acceptance announcement, as summarised in search results of its 8-K and Seeking Alpha coverage: the FDA's filing letter flagged as a potential review issue a preliminary conclusion that the company had not submitted adequate information to justify accelerated-approval eligibility; note 01 did not find it but did find the late-cycle meeting and inspections completed), and any shelf or at-the-market offering (cash runs only "into Q4 2026"). **If INO is not a WLS member**, slot 5 goes into SNDK US (to $190k) until Oct 26, then COIN US.

---

## 4. The rotation calendar

**The rule.** Sell the day after the event resolves, win or lose. Roll the full proceeds into the slot's next event within 1-2 days, capped at $200k per name; any excess opens a new slot. Never average down.

### 4.1 Slot chains

| Slot | Leg 1 | Leg 2 | Leg 3 | Endgame (Nov 9-13) |
|---|---|---|---|---|
| 1 | AXTI US → Q3 print | IONQ US, Q3 Nov 4-9 | — | Next free endgame name |
| 2 | 2408 TT → Nov 10 sales | — | — | Next free endgame name |
| 3 | 285A JP → results | — | — | Kioxia if results ≤ Nov 12 JST |
| 4 | MRNA US → Oct 26 | MSTR US, Oct 26 → Nov 5 | QBTS US, Q3 Nov 6-12 | Next free endgame name |
| 5 | INO US → Oct 30 / Nov 2 | CBRS US (Q3) or SMCI US (Nov 3) | — | CBRS lock-up or RGTI US |

### 4.2 Dated calendar

(E) = third-party estimate, (L) = calendar listing; neither is company-confirmed. **Verify every date on `EVTS` a week ahead.**

| Date (NY) | Event | Slot | Action | Alternatives if the date slips |
|---|---|---|---|---|
| Mon Oct 12 | Opens 09:00. Tokyo, Toronto closed. | All | Buy AXTI, MRNA, INO, SNDK buffer at the open. Queue Nanya (Taipei open 21:00 NY) and Kioxia (Tokyo, Oct 13). Small test order. | 000660 KS or SNDK US if a foreign fill fails |
| Wed Oct 14 | US Sept CPI. ASML (~Oct 14), TSMC (~Oct 15). | Theme | Hold. | — |
| Fri Oct 16 | Entry deadline 23:59. Options expiry. IRD PDUFA Sat Oct 17. | All | Confirm 100% invested. Skip IRD (consensus). | — |
| Oct 22-23 | SK Hynix Q3 (~). Leaderboard. | Theme | If the sleeve gains 30% in 5 days, add theme names. | — |
| Sat Oct 24 | ESMO: Moderna. PHAR PDUFA (consensus, skip). | 4 | Hold over the weekend. | — |
| Mon Oct 26 | ESMO reaction. GSK PDUFA (skip). | 4 | Sell MRNA at the open; buy MSTR US (FOMC, earnings, election). | COIN US (Oct 29 AMC, L); CBRS US (Oct 30-Nov 2, E); HOOD US (Nov 4, L) |
| ~Oct 26 | Anthropic IPO pricing: **unverified rumour, conflict of interest noted.** | None | Not traded. Verify independently. | — |
| Tue Oct 27 | **Midpoint.** FOMC day 1. MSFT, GOOGL, META (~Oct 27-29). | All | Compute the gap, set the mode, consolidate (section 6). | — |
| Wed Oct 28 | **FOMC 14:00** (hike ~70% priced). | 4, theme | Hold through. | — |
| Thu Oct 29 | ECB. US GDP and PCE. COIN Q3 AMC (L). Samsung final Q3 (~). | 4 | If chain 4 holds COIN, sell Oct 30. | — |
| Fri Oct 30 | **INO PDUFA.** BoJ. CBRS Q3 window opens. Leaderboard. | 5 | Sell INO on the reaction. | If extended: sell, roll early. |
| Late Oct / early Nov | AXTI Q3. Seagate, WDC fiscal Q1. | 1 | Sell AXTI day after print; buy IONQ US. | QBTS US; ASTS US |
| Mon Nov 2 | INO reaction if after hours. | 5 | Buy CBRS US if its Q3 is still ahead, else SMCI US (Nov 3 AMC, L). | SPCX US (Nov 3, low convexity); DJT US |
| Tue Nov 3 | **Midterms.** SPCX Q3 plus ~28% lock-up tranche (L). SMCI, AMD. | 4, 5 | Hold MSTR. | — |
| Wed Nov 4 | Election reaction. MSTR Q3 AMC (L). HOOD. Refunding. | 4 | Hold MSTR into its print. | — |
| Thu Nov 5 | BoE. MSCI review (~Nov 5-12). SanDisk FQ1 (~). | 4 | Sell MSTR; buy QBTS US. | RGTI US; ASTS US |
| Fri Nov 6 | US payrolls. Leaderboard. | All | Set endgame mode; draft the endgame book. | — |
| Mon Nov 9 | ASTS Q3 AMC (E). CBRS lock-up (~Nov 9-10). | All | **Endgame book in place.** | — |
| Tue Nov 10 | US Oct CPI. Taiwan sales deadline. ALAB (L). US-China truce expiry (~). | 2 | Sell Nanya day after its release; roll into the endgame. | — |
| Wed Nov 11 | CRCL Q3 (L). IONQ (L date). Veterans Day, stocks open. | — | — | — |
| Thu Nov 12 | Last US after-close reports reacting in window. Last Japanese results. | All | Lock mode only: index basket by the close. | — |
| Fri Nov 13 | Asian closes 02:00-04:00 NY. **US close 16:00 = final marks.** Possible FDA action on Sat Nov 14 goal dates. | All | No new Asian trades after their close. | — |

### 4.3 The endgame: every slot in an event resolving Nov 10-13

Fill slots in this order, skipping names already held. Use only names whose event `EVTS` confirms will land by the Nov 12 US close or the Nov 13 Asian session.

| # | Name | Event | Date |
|---|---|---|---|
| 1 | RGTI US | Q3 results | E Nov 9-13; only if after the close on or before Nov 12 |
| 2 | QBTS US | Q3 results | E Nov 6-12 |
| 3 | IONQ US | Q3 results | E Nov 4-9, L Nov 11 |
| 4 | CBRS US | 180-day IPO lock-up | ~Nov 9-10, derived. **Verify:** prospectus terms |
| 5 | 285A JP | Results | ~Nov 12-14. **Verify** |
| 6 | ASTS US | Q3 results | E Nov 9 AMC |
| 7 | CRWV US | Q3 results | ~Nov 10-12 by 2025 pattern; L says Nov 16 |
| 8 | FRO / DHT / STNG US | Post-midterm Iran strike risk | Nov 4-13 (section 5) |
| 9 | BTAI US | IGALMI goal date Sat Nov 14, possible Fri action | **Verify:** date and indication conflict |
| 10 | CYTK US | Aficamten goal date Sat Nov 14 | Consensus (~90%, +5-10%). Only if shown to be contested. |

The quantum names make a correlated earnings cluster at the very end, when there is no time for moves to fade: the bold-play finish.

---

## 5. Scenario overlays

**Hormuz (note 04: grind 50-55%, escalation 25-30%, reopening 15-20%).**
- *Grind (default):* no tanker or airline position. Tankers sit near records, so escalation is largely priced. They are not a safe leg.
- *Escalation signals* (talks formally end, US strikes before the midterms, attacks on Gulf infrastructure, Brent above $115): roll the next free slot into **FRO US**, then DHT US or STNG US, two slots at most. Oil lifts yields, which hits memory, quantum and crypto, so watch the theme kill rule.
- *Reopening signals* (a deal with a date, blockade lifted, Brent below $95): roll one or two slots into **AAL US, UAL US or CCL US** and hold the theme, which gains from lower yields. June's deal erased Brent's wartime gains and collapsed within ~3 weeks, so take profits within days. If a dated framework appears while we are in Contention or Hail Mary mode, reopening can take the whole book.

**FOMC, Oct 28 (hike 65-72% priced).** Every memory sell-off in July-September came with a yield spike. A hawkish hike hits the theme and the crypto chain; a hold (~30%) sparks a long-duration rally. Do not de-risk into the meeting. Apply the kill rule after the decision. PCE (Oct 29) and the BoJ (Oct 30) complete the bond-rout risk week.

**Midterms, Nov 3.** A Democratic sweep (~62%) is priced. The tradable surprise is a **Republican Senate hold (~31%)**: MSTR, COIN, HOOD and DJT rally. Chain 4 holds MSTR through the vote for this reason. Skip solar on a sweep; it is crushed by rates. Senate control may not be called until Nov 4 or later.

**A post-midterm Iran strike (reported as expected after Nov 3, inside our window).** Brent heads to $120-150; tankers and defence rise; airlines, cruise lines and long-duration names fall as yields climb. Our quantum-heavy endgame is exposed. If strike signals are strong by the Nov 6 leaderboard, move 1-2 endgame slots into FRO / DHT / STNG and hold to the close on Nov 13. In Hail Mary mode with strong signals, the whole book goes into FRO, DHT, STNG, INSW and TNK.

---

## 6. Mid-competition decision rules

**Oct 27 midpoint check (before the FOMC).**
1. R = our relative return; L = the best other return on the leaderboard (#2 if we lead); d = trading days left (14 at the Oct 27 open).
2. Projected bar **B̂ = max((1 + L) × m(d), 1.4) − 1**, with m(d) = 1.9 / 1.75 / 1.55 / 1.35 / 1.2 / 1.15 at 20 / 15 / 10 / 5 / 2 / 1 days left: how far the best of ~40 max-variance teams typically climbs. Before the first leaderboard, B̂ = +140%.
3. Gap **G = ln(1 + R) − ln(1 + B̂).**

| Mode | Gap | Behaviour |
|---|---|---|
| Hail Mary | G ≤ −0.4 | Fewest names allowed; everything on the most convex correlated driver, preferring the latest events (the quantum cluster). |
| Contention | −0.4 < G < +0.10 | Maximum variance; whole book into the engine that is working. |
| Leader | +0.10 ≤ G < +0.30 | Swap correlated bets for independent ones; sell binaries before their events. Never cash. |
| Lock | G ≥ +0.30 | Index-tracking basket. |

*Example:* we are +30%, the leader +60%. B̂ = 1.6 × 1.7 − 1 = +172%; G = ln 1.3 − ln 2.72 = −0.74: Hail Mary. Even +80% against a leader at +60% gives G = −0.41. Beating #2 is not the test.

**Midpoint consolidation (Contention).** Theme up 30%+ with momentum: whole book into the theme, 5+ names (add SNDK US, 000660 KS, WDC US), keeping INO through Oct 30. Theme flat or down while binaries work: move theme slots into the crypto-election and quantum clusters. Both down: Hail Mary.

**Leaderboard.** Note 06 reports that TMSG shows our rank and a full ranking is published weekly (~Oct 16, 23, 30, Nov 6). **Verify** the cadence and whether portal challenge 13 is live. Recompute B̂ and G after each release.

**Locking in (almost never).** Only at G ≥ +0.30; with a leader at +60% at midpoint, that means we are at +267% or more. Lock into an index-tracking basket of the largest WLS constituents (⌈book value / $200k⌉ names, USD-weighted, spread across regions), never cash: cash scores minus the index with no upside. A falling book is never a reason to de-risk.

**Theme kill rule.** Sell the whole sleeve if it falls 25% from its high-water mark, or the memory factor falls 20% in 10 days; roll early into the quantum cluster or binaries.

**Cap handling.**

| Situation | A: checked at entry only | B: continuous (default until confirmed in writing) |
|---|---|---|
| Opening sizes | 5 × $199k | 5 × $190k plus $50k SNDK buffer |
| Theme winner, momentum intact | Let it run; never add above $200k | Trim to ≤ $190k at 15:30 NY daily; move excess into other theme names |
| Binary winner | Sell at T+0 / T+1 and roll | Same |
| Book above $1M | ⌈book value / $200k⌉ slots | Same (forced) |
| Foreign names | FX irrelevant | Keep 5% FX headroom |

Keep a timestamped log of every position against $200k at entry and at 15:30 NY daily. Disqualification costs everything; reading B costs about 1 point of P(win). Switch to A the day Bloomberg confirms it.

---

## 7. Daily routine on the Terminal

**07:30 NY, ten minutes:**
1. `TMSG`: positions, cash (~0), rank, anything above $190k.
2. `NI FDA`, `NI BIO`, `TOP`, `CN` on holdings: overnight FDA actions, readouts, deals, offerings.
3. `EVTS` / `ERN` on holdings and next-in-chain names: date, time, before-open or after-close. Anything that slipped outside the window is sold today.
4. `CACS` on holdings: reverse splits, rights issues, offerings.
5. `GP` / `GIP` on holdings and the theme sleeve: the −25% high-water-mark rule.
6. `ECO` for macro releases; `CO1 Comdty GP` and Iran headlines for Hormuz signals.
7. `OMON` on the next roll candidates: implied move ±35-40% or more.

**Also:** 09:30-10:00 US and European rolls. 15:30 cap check (reading B). 19:00-21:00 Taipei and Tokyo orders. Weekly: recompute the gap, rerun the screens, check `SI` / `HDS` short interest, and read `BI` dashboards (memory pricing, FDA calendar). **Verify** function names and screen fields with `HELP HELP` on day one.

**EQS screens (every Monday and before every roll):**

| Screen | Criteria |
|---|---|
| **Binary chain** | Member of WLS Index · market cap $100M-$5B · price > $1 · 20-day average value traded > $2M · 30-day realised volatility > 80% · then keep names with an FDA date, readout or earnings within 10 trading days (`EVTS`, `BI` FDA calendar) and an `OMON` implied move of ±35%+ |
| **Theme momentum** | Member of WLS Index · market cap $500M-$50B · 1-month return > +25% and 3-month > +50% · 30-day realised volatility > 70% · 20-day value traded > $10M · next earnings before Nov 12 · tie-break on short interest > 10% of float |
| **Squeeze tie-breaker** | Short interest > 25% of float · days to cover > 5 · value traded > $20M · price > $3 · market cap $500M-$50B · 1-month > +30% · within 5% of 52-week high · no convertible or at-the-market issuance in 30 days |

---

## 8. Bench

| Sleeve | Ticker | Catalyst and date | Note |
|---|---|---|---|
| Theme | SNDK US | Fiscal Q1 ~Nov 5-6 | $1,713, +695% YTD, 6-11% daily swings. Crowded: buffer only. |
| Theme | 000660 KS | SK Hynix Q3 ~Oct 22-23 | ±30% limit. Mega-cap fallback. |
| Theme | WDC US | Fiscal Q1 late Oct / early Nov | Moves like levered memory |
| Theme | STX US | Fiscal Q1 late Oct | Lower beta than WDC |
| Theme | 2344 TT | October sales by Nov 10 | Winbond. Unverified. |
| Biotech | OCGN US | OCU400 Phase 3 "Q4 2026" | ~35% chance by Nov 13. Hold only once dated. |
| Biotech | VIR US | ECLIPSE 1 Phase 3 "Q4 2026" | ~25% in window. Check Mirum's Sept 28 read-through. |
| Biotech | TLSA US | Foralumab Phase 2a, "October" | Long odds, multi-bagger payoff. WLS risk. |
| Biotech | BTAI US | IGALMI goal date Nov 14 | Conflicting sources. Low approval odds = convex. |
| Crypto / election | COIN US | Q3 Oct 29 AMC (L) | Heavily shorted; Republican-hold winner |
| Crypto / election | DJT US | Election Nov 3 | $9.12, $2.54B. Purest Republican-hold ticket. |
| Endgame | ASTS US | Q3 Nov 9 AMC (E) | Space retail favourite |
| Endgame | CRWV US | Q3 ~Nov 10-12 or Nov 16 | Only if confirmed inside the window |
| Hormuz up | STNG US | Strike risk Nov 4-13 | Record close $87.85 on Sep 17 |
| Hormuz down | AAL US | Any reopening deal | Best de-escalation trade (note 04) |

---

## 9. Honest limitations

- **Every fact comes from search-engine summaries.** The research environment's network policy blocked every finance and company website tried (Bloomberg, SEC, FDA, exchanges, Yahoo, Nasdaq and dozens more), so no primary page was read, and the session's search allowance ran out early. Much planned research never ran.
- **Most prices and market caps are unverified.** Verified: SNDK $1,713, MU $1,053, SPCX $147, DJT $9.12, INO ~$2.44 / ~$130M (undated), a few quantum prices. AXTI, Nanya, Kioxia, the tankers and most biotechs have none.
- **Most dates are not company-confirmed.** Earnings dates are third-party listings (TipRanks dates look algorithmic) or last-year patterns. Well supported: the INO PDUFA (three sources), ESMO, FOMC, CPI, BoJ, BoE, ECB, the election.
- **Open conflicts:** INO's FDA eligibility note (sourced from Inovio's Dec 2025 acceptance announcement via search summaries; not independently read); MSTR on Nov 4 or Oct 29-Nov 2; CRWV and RKLB on Nov 16 or Nov 9-12; BTAI's indication; the 10-year yield (5.25% or "nearly 5%"); CUHK's 2025 ">400%" against $1M → $4.1M (+310%).
- **The Monte Carlo is a model.** Stylised payoffs; a field fitted to three winners and one year of ranks; no costs, spreads, run-ups, post-event drift or post-financing dilution; other teams assumed not to chase our events. Trust the ranking of strategies, not the absolute P(win).
- **The Anthropic IPO item is an unverified rumour, and a conflict of interest is noted:** this plan was prepared with Anthropic-built software. It is excluded from the book. Verify it independently.
- **Re-verify everything on the Terminal before Oct 12**, starting with section 1.2, then each ticker's WLS membership, price and event date.
