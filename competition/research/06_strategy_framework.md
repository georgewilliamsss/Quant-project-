# 06 — Strategy Framework: Maximising P(1st) in the Bloomberg Global Trading Challenge 2026

*Prepared 2026-09-29 for the portfolio-construction agent. Status: framework only. It selects no tickers; screening is a separate step.*
*Inputs: the manager brief, the rules-research update of 29 Sep, a few web checks (the search budget ran out, so some base rates below are rules of thumb and are flagged), and an EV-neutral Monte Carlo written for this memo (assumptions in Appendix A).*

---

## 0. Bottom line (read this if nothing else)

1. **The objective is P(R_us > W), where W is the best return among ~3,000 other teams.** It is not E[R], Sharpe or log-growth. Our payoff is a step function, so everything in the middle of our return distribution is worthless. Only the probability mass above W counts.
2. **Winning needs a multiple of capital.** 2023: HKU made +67.7%. 2024: RIT made about +168 points relative. 2025: CUHK's headline was ">400%", with the book going from $1M to $4.1M. **The planning prior for the 2026 winning bar is a median of about +200%, with a 10th–90th percentile range of about +65% to +440%.** A +20–40% result lands in the top 0.2–1% and wins nothing.
3. **The cap is 20% of NOTIONAL ($200k), not 20% of the current book.** A single ticket therefore adds at most 0.2 × r to the book. Growth compounds only by re-rolling into ⌈V/$200k⌉ tickets. Only two engines can plausibly reach +200–300%:
   - **(A) Whole-book correlated beta.** One theme in its highest-beta names. This is the only single-roll route to +300%.
   - **(B) Sequential compounding of convex binaries** over 3–4 rolls. This is the best route to +100–200%.
   - Earnings roulette, daily top-mover rotation, consensus ("priced-in") PDUFAs, index-like cores and the "safe" leg of a barbell all have **P(win) ≈ 0**.
4. **Correlation.** Above a bar of about +50%, five correlated bets beat five independent ones by an order of magnitude. In a toy example, P(book > +100%) is 25% for correlated bets against 1.6% for independent ones. **But avoid correlation with the field.** A crowded theme wins exactly when the bar is also highest, which cost about 25% of P(win) in the model. The rule: be correlated *within* a roll (bold play), and independent *across* rolls, across engines and from other teams.
5. **Recommendation: a hybrid "bold-play barbell of two lottery types".**
   - 3 slots in one high-beta theme, 2 slots in sequential convex binaries, plus a small buffer slot.
   - At the Oct 27 midpoint, move the whole book into whichever engine is working (state-dependent consolidation).
   - Model P(win) is about 6%, against 0.03% for a random team. Discounted for the limited supply of convex tickets and for other max-variance teams, a **realistic 2–5%**.
6. **A leaderboard exists.** The captain sees our own rank on TMSG, and a full ranking is published weekly. So the game is state-dependent. **Lock in only when our level exceeds the *projected pack maximum*, not merely #2.** With 10 days left that projection is about (1 + #2's return) × 1.55; with 5 days left, × 1.35; with 2 days left, × 1.2. Being 20–40% ahead of #2 with two weeks left is *not* safe.
7. **Must be settled before Oct 12:**
   - How the cap is enforced (at entry only, or continuously).
   - WLS membership of every candidate. INO, at about $130M market cap, is at risk of not being a member.
   - The simulator's fill model.
   - Whether there is a minimum number of positions.
   - Until the cap question is answered, **behave as if the cap is continuous.** The model says this costs about 1 percentage point of P(win); disqualification would cost all of it.

---

## 1. Facts that drive the design

| Fact | Value | Source / confidence | Design consequence |
|---|---|---|---|
| Notional | US$1,000,000. The brief's $100k was wrong. | 2026 T&C (via search); manager | All analysis is in % of notional |
| Position cap | "No single position held… greater than 20% of the **notional amount**" = **$200k** | T&C | The cap does not grow with the book. Book growth needs more names. |
| Cap enforcement | Unknown: checked at entry only, or continuously? | — | Two policies are given below (§3.3) |
| Window | Mon 12 Oct 09:00 NY → Fri 13 Nov 17:00 NY. **25 weekdays**, not 23: US equities are open on Columbus Day (12 Oct) and Veterans Day (11 Nov). | T&C; calendar | Plan roughly 4 binary rolls per slot at most |
| Initial deployment | Positions due by Fri 16 Oct 23:59 NY. The 2025 T&C required the **full $1M invested within the first business week**. | Manager | No early cash; enter on Day 1 |
| Universe | Members of the WLS index (Bloomberg World Large/Mid/Small Cap), about 10,000 names including non-US. No ETFs, long-only, no leverage. | T&C | Microcaps below the WLS small-cap cutoff are **not eligible**. Check MEMB for every name. |
| Scoring | Highest **time-weighted relative return vs WLS**, reported as relative $ profit | T&C; HKU 2023 (+67.7% return ⇒ +$637k relative ⇒ index ≈ +4%) | Relative ≈ R_p − R_idx; the index is common to all teams |
| Leaderboard | The captain sees own performance and **rank on TMSG**. A **full ranking is published weekly** on the portal. | T&C / Info PDF | The state-dependent play in §4 can be operated |
| Field size | 948 teams (2022) → 2,007 (2023) → ~2,450 (2024) → ~2,650 (2025). Expect ~3,000. | Bloomberg press / university releases | — |
| Winners | 2022 Southampton +$306k rel (~+31%). 2023 HKU +67.7%. 2024 RIT +$1.68M rel (~+168 pts), "betting on volatility", mostly foreign stocks, led 5 of 6 weeks. 2025 CUHK ">400%", $1M → $4.1M. | Releases | The bar is a multiple of capital |
| **Depth of the field** | 2025: #9 (Drexel, US biotech) ≈ **+23%**; #69 (USF) +5.3% rel. 2024: #81 (Iona, small-cap earnings) ≈ +20%. | Releases | Only a handful of teams run truly max-variance books. **The bar is set by 1–3 outliers.** |
| Activity | Teams averaged ~28 trades. No known trade limit. | Manager | 60–100 trades is acceptable; check for commissions |

**Regime (manager facts):**
- US 10-year yield at 5.24%, the highest since 2007. The Fed hiked on Sep 16 and more hikes are priced.
- Hormuz has been effectively closed since March. Brent is about $105.
- Bitcoin is about $83k, 35% below its high.
- There is a memory-chip supercycle: SanDisk +695% YTD, Micron about $1T market cap.
- Moderna is +550% YTD, with Phase 3 melanoma data at ESMO on **Sat Oct 24**, so the market reacts **Mon Oct 26**.
- FOMC meets Oct 27–28. Midterms are on Nov 3.
- **INO PDUFA on Fri Oct 30** (INO-3107). An FDA note questions its accelerated-approval eligibility, which makes it close to a genuine coin-flip.

---

## 2. Tournament maths

### 2.1 Why maximising E[R] is wrong

We win if R_us > W, where W = max over the other ~3,000 teams. For any plausible strategy, W sits far in the right tail. Two comparisons:
- A book with E[R] = +10% and σ = 10% has P(R > +100%) ≈ 0.
- A book with E[R] = −5%, 60% volatility and right skew has P(R > +100%) of about 5–10%.

For a fixed mean, the distribution that maximises P(R > W) has two points: finish just above W, or lose everything. That gives P = (1 + E[R]) / (1 + W). With W = +200% and E[R] = 0, the theoretical ceiling is 33%. The cap and the instruments available keep us far below that ceiling, but the direction is clear: **give up everything in the middle of the distribution to buy probability above W.**

This is Dubins–Savage *bold play*. In a sub-fair game with a target far above current wealth, stake the maximum on the fewest, most convex bets. Kelly sizing, Sharpe, beta and drawdown are all irrelevant here.

Two facts from tournament theory also shape the plan:
- If K teams run max-variance books with similar skill, our symmetric P(win) is about **1/K**. Our edge has to come from three things:
  1. Engineering the payoff shape: rolls, bold play, consolidation.
  2. Not wasting variance on negatively skewed tickets.
  3. Using the leaderboard to choose variance by state.
- Mutual-fund tournament evidence (Brown, Harlow & Starks, 1996; Chevalier & Ellison, 1997) shows that participants who are behind at mid-period *raise* their risk. **Expect the field's variance, and so the bar, to rise in the final two weeks.**

### 2.2 What return wins?

| Year | Teams | Winner (relative) | Notes |
|---|---|---|---|
| 2022 | 948 | ~+31% | Bear market |
| 2023 | 2,007 | ~+64% (+67.7% absolute) | HKU |
| 2024 | ~2,450 | ~+168% | RIT: "betting on volatility", mostly foreign stocks |
| 2025 | ~2,650 | ≥ +310% (headline ">400%") | CUHK. #9 was only about +23%, so the winner was a far outlier. |

**Prior used for 2026:** ln(1+W) ~ N(ln 3, 0.46), with a floor at +40%. That gives a 10th / 50th / 90th percentile of **+66% / +199% / +440%**. W is correlated (ρ = 0.4) with speculative risk appetite during the window: hot markets raise the bar.

**Sanity check.** Suppose about 40 teams run max-variance books, each with P(> +100%) ≈ 10% and P(> +200%) ≈ 3%. Then:
- P(max < +100%) = 0.9^40 ≈ 1.5%.
- P(max < +200%) = 0.97^40 ≈ 30%.

So the bar is almost certainly above +100%, and more likely than not above +200%. That matches 2024–25.

**Sensitivity.** Results are shown for bar medians of +100%, +200% and +300% (§5).
- In a quiet year, with a bar of about +100%, independent binaries gain relative value.
- In a mania year, with a bar of +300% or more, only correlated beta can compete.

### 2.3 The 20%-of-notional cap: how is a +200–300% book even reachable?

Let V be the book value in units of the $1M notional and m_i the price multiple of name i.

| Route | Arithmetic | What +200–300% requires | Verdict |
|---|---|---|---|
| **Static hold, cap checked at entry only** | V_T = 0.2 · Σ m_i | +300% ⇔ Σ m_i = 20. That means all five names 4×, or one 10× plus four 2.5×. A lone +200% winner adds only +40%. | Possible only if a whole theme melts up, or runners are allowed to run |
| **Static hold, cap enforced continuously** (trim to $200k, redeploy) | V ≈ e^F · (1 + 0.2 Σ ln-legs). The factor F compounds fully if trimmed cash goes into *other names in the same theme*. Idiosyncratic runners are only "log-harvested". | A 10× runner is worth about 0.2 · ln 10 = **+46%**, against **+180%** under entry-only. A 5× runner: +32% vs +80%. A 3× runner: +22% vs +40%. | Only a factor-wide melt-up gets there. It needs ≥ V/$200k liquid names in the theme (15 names at V = $3M). |
| **Sequential independent binaries** | V_{k+1} = V_k · (1 + mean return of the n_k = max(5, ⌈V_k/0.2⌉) tickets) | +200% = three rounds of +44% each. With convex tickets (+110% on a hit, −55% on a miss), a +44% round needs 3 of 5 to hit: P = 16%. Three such rounds in a row: **0.4%**. | This is the engine for +100–200%. It rarely reaches +300%. |
| **Sequential *correlated* rolls** (the whole book on one driver, twice) | (1.82)² = 3.3 | Two hits at p ≈ 0.3 each gives a **9% chance of +230%** | The arithmetic of bold play. The hard part is finding real clusters with p ≈ 0.3 of +80%. |
| **Daily rotation into the biggest movers** | 25 rolls × 5 names of ≈ zero-edge ±10% tickets, costing about 1% a day | Book σ ≈ 25–30% with negative drift. P(+200%) ≈ 0; the simulation gives **0.03%**. | Dominated. The only exception is a simulator fill edge (§7). |

**Ranking of routes to +200–300%:**
1. A theme melt-up with runners, if the cap is entry-only.
2. A theme burst followed by a correlated event cluster.
3. Three to four rolls of convex binaries.
4. Nothing else matters.

We cannot tell where CUHK's 4.1× came from. It fits an Asian small-cap melt-up plus entry-only runners plus rotation. Simulator artefacts, such as corporate actions that were not adjusted, cannot be ruled out. **We do not plan on artefacts or exploit them** because of disqualification risk, but they may inflate the bar. Avoid holding names with pending reverse splits or rights issues (check CACS).

### 2.4 Five independent lottery tickets, or five correlated bets on one theme?

Toy model: five slots at 20% each. Each ticket hits with probability p for +U and otherwise loses D. Book return = 0.2 · Σ r_i. Exact binomial results:

| Ticket (EV) | Threshold | P, independent | P, perfectly correlated |
|---|---|---|---|
| p = 0.25, +150% / −40% (EV +7.5%) | book > +20% | **36.7%** | 25.0% |
| | book > +50% | 10.4% | **25.0%** |
| | book > +100% | 1.6% | **25.0%** |
| p = 0.30, +120% / −55% (EV −2.5%) | book > +20% | 16.3% | **30.0%** |
| | book > +50% | 3.1% | **30.0%** |
| | book > +100% | 0.24% | **30.0%** |

With independent tickets, one winner is diluted to 20% of the book, so clearing +100% needs four or more hits out of five. A correlated book hits all at once. The crossover sits at a bar of roughly +30–40%. **The bar is about +200%, so correlation *within* a roll dominates.**

**The crowding correction is the subtle part.** P(win) = E_state[ P(R > W | state) ]. If our correlated bet is the field's favourite theme (in 2026, memory), its good state is also the state where the bar is highest. In the model, the same theme held as a crowded position (loading 0.6 on the risk-appetite factor that drives W) wins **3.05%**, against **3.92%** when uncrowded, at a +200% bar. That is a relative penalty of about 25%. Idiosyncratic binaries do not move with the bar at all; they win in quiet or risk-off months when the bar is lower.

**Resolution:**
- Correlated *within* each roll.
- Independent *across* rolls and across the two engines.
- Always take the **less-crowded, higher-beta expression** of a theme: foreign small caps and second-derivative suppliers, not the mega-caps every student owns.

### 2.5 Concentration: exactly five names at 20%, or six to seven?

- **Always hold the minimum: n = ⌈V/$200k⌉** (five at the start), plus at most one small buffer slot.
- Six or seven equal weights dilute the only lever we have, which is the weight per ticket.
  - For a single theme it barely matters, because the factor dominates. Five and seven names gave 3.05% and ≈3.0%.
  - For independent tickets, extra names are pure loss at high bars.
- **If V < $1M and there is no minimum-count rule, drop to ⌈V/$200k⌉ names**, for example four names at $0.8M. The gain is small (+0.1 pp) but it costs nothing and raises variance exactly when we are behind.
- **Under a continuous cap, buy about $190k per name (5% headroom) plus a sixth ticket of about $50k.** That keeps the book "fully invested" without breaching the cap on the first uptick or FX move.

### 2.6 Barbell or all-lottery?

A classic barbell (safe core plus lottery sleeve) is **dominated**. With 60% index-like and 40% lottery, the sleeve must return +500% for the book to reach +200%. The safe leg adds essentially no probability above the bar. **All capital should be in lottery tickets.**

The only barbell worth holding is **between two lottery types** whose payoffs are imperfectly correlated with each other *and with the bar*: theme beta on one side, idiosyncratic binaries on the other. Its purpose is to keep us in contention across regimes, so that the midpoint consolidation (§4) has a working engine to move into.

---

## 3. The 20% cap and sequential re-rolling

### 3.1 How many rolls are possible?

- There are 25 trading days.
- A binary roll takes 2–5 days: enter between T−3 and T−1 to capture the pre-event run-up, exit at T+1.
- In theory that allows 4–5 rolls per slot. **In practice, 3–4**, because of ticket supply, weekends and events that resolve after hours.
- Theme slots get one or two "bursts".

P(win) by number of rolls, five slots, bar median +200%, all tickets EV-neutral:

| Rolls | Skeptically priced binaries (p 0.40, +60% / −50%) | **Convex binaries** (p 0.30, +110% / −55%) | Convex: P(> +100%) | Convex: P(> +200%) |
|---|---|---|---|---|
| 1 (static) | 0.95% | 2.25% | 2.9% | 0.05% |
| 2 | 2.00% | 3.95% | 7.5% | 0.75% |
| 3 | 2.82% | **5.49%** | 10.7% | 2.1% |
| 4 | 3.52% | 6.64% | 13.0% | 3.5% |
| 5 | 4.17% | 7.91% | 14.9% | 5.0% |

- Rolling roughly doubles to triples P(win) compared with a static hold. Each extra roll still helps, but by less, and each costs 1–3% in spread and sell-the-news drift.
- **Roll only into convex tickets.** A filler roll into a low-convexity ticket is worse than leaving the money in the theme.
- Compounding with the notional cap: after a winning round the book holds more $200k tickets. Each ticket is still capped, but the round multiplier applies to the whole book. The same machinery forces diversification as V grows, which is why a correlated driver is needed for the final multiple.

### 3.2 Ticket quality: supply is the binding constraint

| Ticket type | Shape | P(win), 5 slots × 4 rolls, bar +200% |
|---|---|---|
| Consensus / "priced-in" PDUFA: 88% approval → +5%; CRL → −45% to −60% | **Negative skew** | **0.03%** (poison) |
| Skeptically priced binary: 40% → +60%; 60% → −50% | Moderate | 3.5% |
| **Convex binary:** 30% → +110%; 70% → −55% (INO type) | Strong right skew | 5.5% at 3 rolls |

**Rule-of-thumb base rates** (not re-verified this session):
- Overall FDA approval at the PDUFA date is roughly 85–90%, lower for small sponsors and first-cycle applications.
- Small-cap approval-day reactions are often muted or "sell the news". CRLs typically cost −30% to −60%.
- Small-cap Phase 3 success runs at roughly 50–60%, with +30% to +200% on success and −50% to −80% on failure.
- Small caps commonly run up into the event and fade afterwards.

So **Phase 3 readouts and *contested* PDUFAs are the tickets; consensus PDUFAs are not.**

**Qualification test for a binary slot (all must pass):**
1. The stock is a WLS member (check MEMB).
2. The event is dated inside the window and resolves before Nov 13 16:00 NY.
3. Options, or the stock's history, imply a move of at least ±35–40%.
4. The upside-state move is at least 1.5–2× the downside-state move. Signs of this: the market prices low success odds after a prior CRL, eligibility questions, a controversial AdCom, high short interest, or a price deep below the approval-case valuation.
5. ADV of at least $2M.

Expect only about **6–10 qualifying events** in the window. That supports **2 binary slots × 3–4 rolls**, not 5. This supply limit is why the recommendation is a hybrid rather than all-binaries.

**Worked candidates:**
- **INO, PDUFA Oct 30.** A competing RRP therapy (believed to be Precigen's, approved in 2025) presumably explains the FDA's accelerated-approval eligibility note. The market therefore probably prices low approval odds. Approval could be worth +100% or more; a CRL perhaps −40% to −60%. That is a textbook convex ticket, **if it is a WLS member**. At about $130M market cap it may sit below the WLS small-cap cutoff. If it is not a member, it cannot be traded.
- **Moderna / ESMO (Sat Oct 24).** After +550% YTD, the headline name probably carries *negative* event skew; check the options skew. **Trade the read-through instead:** small-cap mRNA and neoantigen cancer-vaccine peers, where success is less priced in.

### 3.3 Cap-handling policy under both readings

| Situation | **A. Cap checked at entry only** (pre-trade check; appreciation allowed) | **B. Cap enforced continuously** (≤ $200k at all times) | **Default until confirmed** |
|---|---|---|---|
| Opening sizes | 5 × ~$199k | 5 × ~$190k plus a sixth name at ~$50k | Follow B |
| Theme winner, momentum intact | **Let it run.** Never add above $200k. Sell only to fund a better ticket. | Trim at 15:30 NY every day back to ≤ $190k. **Put the excess into other names in the same theme**, which keeps the factor exposure. | Follow B |
| Binary winner after the event | Sell at T+0/T+1 (post-event drift is usually negative). Reroll in tickets of ≤ $200k. | Same | Same |
| Loser | Sell after the event and reroll the full residual. | Same; can also top up to $200k. | Same |
| Book above $1M | Open more tickets: n = ⌈V/$200k⌉ | Same (forced) | Same |
| FX drift on foreign names | Irrelevant | Keep the 5% headroom | Follow B |
| **Cost in P(win)** (crowded theme, bar +200%) | **3.05%** | **2.07%** | — |

**Action:** before Oct 12, get written clarification through the faculty advisor, Bloomberg for Education support or TMSG. Until then, stay B-compliant, because disqualification makes P(win) zero while compliance costs about 1 pp. If Bloomberg confirms entry-only, switch to A immediately. Runners are where entry-only earns its advantage.

---

## 4. State-dependent playbook

### 4.0 State variables and modes

**Inputs:**
- V: book value divided by notional.
- d: trading days left.
- L: the best return on the latest leaderboard, excluding ours (if we are #1, use #2).

**Projected bar:** B̂ = (1 + L) · m(d) − 1. Here m(d) is the median multiple by which the maximum of about 40 max-variance challengers grows over the remaining days, assuming about 7.5% daily volatility each:

| d (days left) | 20 | 15 | 10 | 5 | 2 | 1 |
|---|---|---|---|---|---|---|
| m(d) | 1.9 | 1.75 | 1.55 | 1.35 | 1.2 | 1.15 |

(From simulation: pack volatility 0.25 → 1.42×; 0.30 → 1.55×; 0.40 → 1.83×; 0.15 → 1.21×; 0.10 → 1.12×.)

Until the week-2 leaderboard is out, use the prior of +200%. After that, take B̂ = max((1+L)·m(d), 1.4) − 1.

**Gap:** G = ln(1+V) − ln(1+B̂).

| Mode | Trigger | Behaviour |
|---|---|---|
| **Hail Mary** | G ≤ −0.4 | Maximum variance. The **fewest names allowed.** Put everything on the single most convex *correlated* driver, preferring events that resolve late. |
| **Contention** | −0.4 < G < +0.10 | Maximum variance with bold play: consolidate into whichever engine is working. |
| **Leader** | +0.10 ≤ G < +0.30 | Cut variance **by switching from correlated to independent tickets**, not by going to cash. |
| **Lock** | G ≥ +0.30 | An index-tracking basket (§4c) |

The model supports this. In the two-stage simulation, the optimal stage-2 action was maximum variance (a correlated cluster, or convex binaries) in **every** gap bucket except the top one. Even there, independent binaries (38.6%) beat index-tracking (32.7%).

**Value of playing by state** (opening book, then stage 2, bar +200%):

| Opening book (Oct 12–27) | Stage 2 = lock in (index) | Best fixed stage-2 | Policy on own V | **Policy on gap to leader** |
|---|---|---|---|---|
| Hybrid: 3 theme + 2 convex slots × 2 | 2.3% | 5.9% | 6.1% | **6.4%** |
| 5 names in one theme | 1.3% | 5.4% | 5.6% | 5.7% |
| 5 convex slots × 2 (supply-limited) | 4.0% | 6.8% | 7.2% | **7.75%** |

Locking in unconditionally at midpoint cuts P(win) by 50–75%. Using the leaderboard adds 0.3–1 pp.

### (a) Opening book, Oct 12–16

- **Slots 1–3 (~$570k): the theme sleeve.** One theme, chosen by the score in §5, held in its highest-beta WLS names that have catalysts inside the window.
- **Slots 4–5 (~$380k): convex binaries.** The two best qualifying events resolving between Oct 13 and Oct 30. A name ahead of its event is also acceptable, to capture the run-up.
- **Slot 6 (~$50k, continuous-cap reading): buffer.** The third-best convex ticket, or a high-short-interest name inside the theme.
- **Supply adjustments:**
  - If three or more high-quality binaries resolve in the first two weeks, shift to 2 theme + 3 binary slots.
  - If none qualify, put all 5 slots in the theme.
  - **Never fill a slot with a consensus PDUFA or an index-like name.**
- **Timing:**
  - US and European names at the Oct 12 open.
  - Asian names at their Oct 13 local open, which is the evening of Oct 12 in New York. Tokyo is believed to be closed Oct 12 for Sports Day, and Canada for Thanksgiving; **verify both.**
  - Be fully invested well before Oct 16.

### (b) After each catalyst

- **Binary hit:** sell on the reaction day (T+0 if the news comes during market hours, otherwise the next open). Reroll the proceeds into ≤ $200k tickets for the next qualifying event; any excess funds extra tickets or theme names. **Exception, in Contention mode with an entry-only cap:** if the winner joins a broad momentum move, hold it with a 25% trailing stop.
- **Binary miss:** sell immediately. Do not average down; post-CRL drift is negative. Reroll the *full* residual at full size. Being down is a reason for more variance, never less.
- **Event slips outside the window, or resolves early:** exit and reroll.
- **Theme sleeve:**
  - Hold while the sleeve stays within 25% of its high-water mark and the theme still has catalysts ahead.
  - If the sleeve is up 30% or more within 5 days with broad participation (a mania signature) and we are in Contention, **consolidate:** move binary proceeds into more theme names (bold play).
  - If the stop is hit, kill the theme and reroll into the next-best theme or the binaries.
- **Weekly leaderboard:** recompute B̂, G and the mode.

### (c) Far ahead at mid-window: lock in?

**Not by default. Only when G ≥ +0.3.** The brief's instinct was "no", and the numbers mostly agree, but for a specific reason. Leading #2 is not the test. What matters is where the *maximum of the chasing pack* will finish. That maximum drifts upward (it is the best of about 40 draws), and teams that are behind raise their variance.

Simulation: 10 days left; #2 at +80%; 40 challengers spread up to 40% (in log terms) below #2. Our P(win) by our own remaining volatility σ:

| Pack vol (10 days) | We are at | Median pack maximum at the end | σ = 0.03 | σ = 0.15 | σ = 0.30 | σ = 0.50 |
|---|---|---|---|---|---|---|
| 0.25 | +100% | +156% | 1.0% | 8.0% | 17.7% | **22.8%** |
| 0.25 | +150% | +156% | **41.8%** | 41.3% | 40.2% | 37.8% |
| 0.25 | +200% | +156% | **86.5%** | 75.9% | 62.2% | 51.6% |
| 0.25 | +300% | +156% | **99.6%** | 98.0% | 88.2% | 72.5% |
| 0.40 | +150% | +229% | 5.1% | 10.2% | 17.2% | **21.9%** |
| 0.40 | +200% | +229% | 30.8% | 32.3% | **33.6%** | 33.3% |
| 0.40 | +300% | +229% | **82.1%** | 76.0% | 65.0% | 54.2% |

- **Rule:** reduce variance only when our level is above the projected pack maximum, B̂. At +100% against a #2 at +80%, we must keep *maximum* variance: 23% vs 1%.
- **How to lock:** not cash. Cash has a relative return of −R_idx, which carries the full variance of the index. Instead hold an **index-tracking basket of the largest WLS constituents**, n = ⌈V/$200k⌉ names, weighted towards USD names and spread across regions. Its tracking error is a few percent over two weeks.
- **In Leader mode (+0.1 to +0.3):** the cheap way to cut variance is to move from *correlated* bets to *independent* ones, and to sell binaries *before* their events.
- **Visibility:** the weekly leaderboard shows our position to everyone. Challengers will aim at our number, so expect the pack's variance to be at the high end (0.3–0.4). That argues for keeping variance longer than the 0.25 row suggests.

### (d) Far behind with 10 days left

Example: V = 0.9 against a projected bar of +200%, so G ≈ −1.2. We need 3.3× in 10 days.

- Only **correlated bold play** gets there:
  - The single most convex correlated driver available.
  - Two sequential whole-book cluster rolls (0.3² ≈ 9% of +230% *if* such clusters exist).
  - A theme already in mania, with runners.
- **Hold the fewest names allowed** (four at V = 0.8 if there is no minimum-count rule). **Prefer events that resolve in the last days**, when there is no time for mean reversion.
- Expect P(win) of about 0.5–2% from this state. That is still more than 20× the P(win) of a team that gives up.
- **Never split a Hail Mary into many small independent bets.** That is timid play in a sub-fair game, and it lowers P(reach target).

### (e) Endgame, Nov 9–13

- **The last catalysts are the most valuable.** A jump on Nov 12–13 is locked in, with no time for post-event drift or mean reversion. Events that resolve *after* Nov 13 only offer run-up, so they carry low variance.
- **Candidate end-window resolvers** (placeholders; confirm with EVTS and the FDA calendar):
  - Early-November PDUFAs and late-breaking abstracts at medical meetings (AASLD, AHA, SITC).
  - US small-cap Q3 reports after the close up to **Nov 12**.
  - Japanese small-cap results released after the Tokyo close on **Nov 12 JST**, which trade on Nov 13 JST (the evening of Nov 12 in New York). Stocks can move limit-up.
  - Taiwanese monthly sales, due by **Nov 10**.
  - US CPI for October, around Nov 10–12.
- **Contention or Hail Mary modes:** the whole book should sit in events resolving between Nov 10 and Nov 13 16:00 NY.
- **Lock mode:** be in the index-tracking basket by the Nov 12 close.
- **Final marks:** Asian names mark at the Nov 13 Asian close (around 02:00–04:00 NY), European names around 11:30 NY, and US names at 16:00 NY.

---

## 5. Candidate archetypes and P(win)

Monte Carlo with 200,000 paths. All tickets are EV-neutral (|EV| ≤ ~4%), because **no stock-picking edge is assumed.** The bar is correlated with risk appetite (Appendix A). Treat absolute P(win) values as optimistic upper bounds; halve them for realism. **The ranking is the robust output.**

| Archetype | EV | P > +100% | P > +200% | P > +300% | P(win), bar +100% | **P(win), bar +200%** | P(win), bar +300% | Verdict |
|---|---|---|---|---|---|---|---|---|
| Index-like reference (TE 3%) | 0% | 0 | 0 | 0 | 0 | **0** | 0 | Never |
| Daily top-mover rotation, 5 × 25 | −17% | 0.00% | 0 | 0 | 0.11% | **0.03%** | 0.01% | Dominated |
| (iii) Earnings roulette, 5 slots × 6 rolls (±15–20% implied moves) | −6% | 0.01% | 0 | 0 | 0.44% | **0.13%** | 0.03% | Dominated: moves too small, diluted by the cap |
| Consensus PDUFAs, 5 × 4 | −1% | 0 | 0 | 0 | 0.12% | **0.03%** | 0.01% | Poison (negative skew) |
| (iv) Short-squeeze basket (high SI), hold | +2% | 7.3% | 2.5% | 1.0% | 7.2% | **3.5%** | 1.8% | Runner assumption is generous; realistic ~1%. Use high SI as a *tie-breaker inside the theme* |
| (i) 5 skeptical binaries, static | −0.5% | 0.4% | 0.0% | 0 | 3.4% | **1.0%** | 0.3% | Too diluted when not rolled |
| (i) Skeptical binaries, 5 × 4 rolls | −2% | 6.5% | 0.6% | 0.04% | 9.2% | **3.6%** | 1.4% | Needs 20 events that do not exist |
| (i) **Convex** binaries, 5 × 3 rolls | +3% | 10.7% | 2.1% | 0.3% | 12.3% | **5.5%** | 2.5% | Best per ticket, but **supply-limited** |
| (ii) One crowded theme, entry-only cap | +2% | 6.6% | 3.3% | 1.9% | 5.6% | **3.05%** | 1.8% | The fattest far tail |
| (ii) One crowded theme, continuous cap | −5% | 5.6% | 2.5% | 0.9% | 4.2% | **2.1%** | 1.1% | Runners lose their convexity |
| (ii) One *uncrowded* theme, entry-only | +2% | 6.5% | 3.2% | 1.8% | 6.4% | **3.9%** | 2.4% | Crowding costs about 25% |
| (ii) Two themes, 3 + 2 | +2% | 5.7% | 2.2% | 1.2% | 5.7% | **2.8%** | 1.5% | Do not split the theme sleeve |
| (ii-geo) Hormuz *escalation* basket | −1% | 0.1% | 0 | 0 | 2.1% | **0.6%** | 0.2% | Closure already priced; low convexity |
| (ii-geo) Hormuz *reopening* basket | +2.5% | 2.2% | 0.03% | 0 | 3.3% | **1.1%** | 0.3% | The more convex side, but low probability; use as a trigger (below) |
| (v) Hybrid, static: 3 theme + 2 convex × 3 | +2.6% | 7.5% | 2.1% | 0.9% | 8.4% | **3.6%** | 1.6% | Needs the midpoint consolidation → |
| (v) **Hybrid + state-dependent consolidation** (two-stage model) | — | — | — | — | — | **≈ 6.4%** | — | **Recommended** |
| (x) Bold play: 5 names on one event, rolled twice | +4% | 10.5% | 5.5% | 2.7% | 11.8% | **6.7%** | 3.8% | Theoretical best; real clusters with p ≈ 0.3 of +80% are rare |
| (x) Theme for the first half, then an event cluster | +4% | 10.3% | 2.8% | 1.3% | 11.5% | **5.3%** | 2.5% | This is what the hybrid consolidates towards |

**Assessment of each archetype:**

- **(i) Five independent small-cap biotech binaries.** Static: poor, because of dilution. Rolled 3–4 times with *convex* tickets: the best route to +100–200%. Their independence from the field is valuable in risk-off months. **Constraint:** only about 6–10 qualifying WLS events, so use 2 slots, not 5. Realistic P(win) as a pure strategy: 1.5–3%.
- **(ii) Single-theme momentum concentration.** The only single-roll route to +300%. Industry and theme momentum persists at 1–12 months (Moskowitz & Grinblatt), while single-stock one-month returns tend to reverse (Jegadeesh). So **buy the theme, not last month's single-stock winner.** Risks: momentum crashes in high-rate, risk-off rebounds (Daniel & Moskowitz), and crowding. Realistic P(win): 1.5–3%.
  - **Theme score** (the portfolio agent picks the winner):
    1. 1-month and 3-month industry momentum.
    2. Name-level volatility of 100% or more annualised, with beta to the theme factor of 1.5 or more.
    3. At least one scheduled catalyst in the window.
    4. At least 8 liquid WLS names; 15 or more to scale under a continuous cap.
    5. Minus crowding: penalise mega-caps and names every team owns.
  - **Shortlist for 2026:**
    - **Memory and storage.** The momentum leader but crowded. Express it through **Asian small and mid caps**: DRAM/NAND makers, controllers, modules, HBM equipment and test. Catalysts: SK hynix and Samsung Q3 in late October, Seagate/WDC/SanDisk in late October to early November, TrendForce contract prices at month-end, Taiwan monthly sales by Nov 10, Kioxia (check whether it reports inside the window).
    - **Crypto beta.** BTC is −35% from its high, so this is a reversal bet with convexity: a +30% BTC rebound implies roughly +60–100% for levered treasury companies and miners. Catalysts: FOMC Oct 28, midterms Nov 3. Less crowded after the drawdown.
    - **Whatever the screen shows leading on 1–3-month momentum** among quantum, nuclear/SMR, drones and defence, rare earths and space.
- **(iii) Earnings roulette.** Dominated as a whole-book strategy. The one use is as **end-window resolvers** (Japanese small-cap and US small-cap results on Nov 11–12) inside the binary slots.
- **(iv) Squeeze candidates.** High short interest underperforms on average (Asquith, Pathak & Ritter) but has fat right tails. Use it to choose *between* theme names, not as its own sleeve.
- **(v) Hybrid (recommended).** Two lottery types with different correlation to the bar, followed by state-dependent consolidation.
- **Geopolitical optionality.** Hormuz has been shut since March and Brent is at $105, so escalation is largely priced: tankers and E&Ps might gain +20–40% even if it gets worse. **The more convex side is reopening.** On a credible deal, the most damaged oil importers and transport names could move +40–70%: airlines, Asian refiners and chemicals, and GCC names inside WLS. But the probability inside five weeks is low, perhaps 10–15%, and a single 20% slot adds only about +13%. **Use it only as a trigger-based whole-book cluster:** if talks with a date or a ceasefire framework appear mid-window, it becomes a Contention or Hail Mary option. Do **not** hold energy or tankers as a "safe" leg; they carry negative skew to reopening.

---

## 6. Benchmark-relative subtleties

- **Relative return ≈ R_p − R_idx** (HKU 2023: 67.7% − ~4% = +$637k). The index is common to every team. What separates teams is the difference in beta times the index move: a few percent at most, which is noise against a +200% bar. **Do not time the market.**
- **Cash is never right, except in Lock mode, and even then the index-tracking basket is better.** Cash returns −R_idx, which carries the index's variance and has no upside tail. It gains only if the index falls, and even then by far less than the bar.
- **A risk-off month changes the mix, not the aim.** Speculative themes crash more often in risk-off, and the bar falls because other aggressive teams get hurt. Both effects favour the **idiosyncratic binary engine**, which does not move with risk appetite. In a risk-on melt-up, themes win but the bar rises with them. This is the hedge the hybrid gives us.
- **Currency.** Scoring is in USD. A 2–4% FX move over a month is irrelevant to a lottery ticket. It matters only (1) under a continuous cap (keep headroom) and (2) in Lock mode (use USD names). JPY can rally 5–8% in a risk-off carry unwind, which would lift Japanese small caps in USD terms. HKD is pegged.
- **International names are independent catalysts.** Their news flow is uncorrelated with the US names most teams hold, which also lowers correlation with the bar. RIT (2024) won "mostly with foreign stocks".
- **Price-limit regimes.** Korea ±30%, Taiwan ±10%, mainland China ±10% or ±20%, and Japan's price bands all *cap* single-day moves but produce multi-day continuation. **Hong Kong has no limit**, so small caps can do +100% in a day. For endgame bursts, prefer markets without limits or with wide ones.

---

## 7. Execution details that matter

1. **Enter on Day 1.** Returns are time-weighted from the start, and every day of exposure is extra variance, which is what we are buying. There is no reason to wait for Oct 16. Binaries with later events should also be entered early, to catch the run-up.
2. **Check WLS membership for every name** (MEMB on `WLS Index`). Membership is also why microcaps are excluded. Trade the **local line that is the index member**, not an ADR, unless the ADR is itself confirmed tradable. Ask whether a name dropped from WLS mid-challenge can still be held.
3. **Liquidity.** Require ADV of at least $2M, so that $200k is no more than 10% of ADV, and a tight spread. The simulator uses real prices, but a thin name may fill at stale or off-market prices. Avoid names with wide spreads, where the simulator might buy at the ask and mark at the bid.
4. **Learn the fill model in Week 1 with a small test order.** Questions to answer:
   - Market or limit fills? Last price or bid/ask?
   - Is after-hours trading allowed? FDA decisions often land after the close.
   - Are there commissions?
   - **Can a stock locked limit-up in Asia be bought at the limit price?** If so, that is a structural continuation edge for Asian momentum names. It is allowed under the rules, but note in writing that we checked it.
   - What happens with price below $1 or board lots in Hong Kong?
5. **Pending corporate actions** (CACS): avoid names with reverse splits or rights issues in the window. The pricing risk and the compliance-review risk are not worth it.
6. **Asian session.** Have someone covering it: place orders around 19:00–21:00 NY for the Tokyo, Seoul and Taipei opens. Asian results released after the local close trade the next local session. The last Asian session inside the window is Nov 13 local.
7. **Daily Terminal workflow** (check exact function names on the Terminal):

   | Purpose | Functions |
   |---|---|
   | Screening | EQS: WLS members, market cap, ADV, 1M/3M momentum, volatility, short interest |
   | Catalysts | EVTS / ERN for earnings dates; the Bloomberg Intelligence FDA/PDUFA calendar; ECO for macro dates |
   | Implied moves | OMON / OV |
   | Short interest | SI |
   | Movers | MOST |
   | News | TOP, CN, NI |
   | Corporate actions | CACS |
   | Index membership | MEMB |
   | Rank and messages | TMSG |

8. **Compliance log.** Keep a timestamped record of each position's value against the $200k cap at entry, and at 15:30 NY every day while the continuous reading might apply.

---

## 8. STRATEGY SPEC (for the portfolio-construction agent)

**Objective:** maximise P(1st) against a projected bar of +200% (use the leaderboard to update it). Only the probability above the bar counts. There is no risk budget.

**Slots:**
- Five core slots of $190–199k each (entry-only: $199k; continuous or unknown: $190k).
- One optional buffer slot of about $50k (continuous or unknown reading).
- Once V > $1M: n = ⌈V/$200k⌉ slots.
- If V < $1M and there is no minimum-count rule: ⌈V/$200k⌉ slots.

**Allocation across engines (opening):**

| Engine | Slots | Content |
|---|---|---|
| **Theme (correlated beta)** | 3 (~57%) | One theme with the highest score. Its highest-beta, least-crowded WLS names (foreign small or mid caps preferred), each with at least one catalyst in the window. Break ties towards higher short interest. |
| **Convex binaries (independent, sequential)** | 2 (~38%) | Only tickets passing the §3.2 test. A ladder of 3–4 rolls per slot. |
| Buffer | 1 (~5%) | The third-best convex ticket, or a high-SI theme name |

Supply adjustment: 2 theme + 3 binary if three or more strong binaries resolve before Oct 30; 5 theme if none qualify. **Never** use consensus PDUFAs, index-like names or cash as filler.

**Rotation rules:**
1. Binaries: enter T−5 to T−1, exit at the T+0/T+1 reaction, win or lose. Reroll the **full** proceeds, capped at $200k per ticket, into the next qualifying event within 1–2 days.
2. Theme: hold while the sleeve is within 25% of its high-water mark and catalysts remain. Mania signal (sleeve +30% in 5 days with broad participation) in Contention → consolidate into the theme. Stop → kill it and reroll into the next theme or binaries.
3. **Midpoint, Tue Oct 27** (after the weekly leaderboard, before the FOMC): compute G and set the mode (§4.0). In Contention, move the **whole book into the engine that is working**:
   - Theme sleeve up 30% or more with momentum intact → 5 or more theme names, plus keep the INO slot if it is eligible.
   - Theme flat or down while binaries are working → binary ladder plus the best event cluster (FOMC, election or Hormuz-deal cluster, ESMO read-through).
   - Both down (G ≤ −0.4) → Hail Mary.
4. Re-check the mode after each weekly leaderboard (around Oct 16, 23 and 30, and Nov 6) and on TMSG rank changes.
5. Endgame (from Nov 9): Contention or Hail Mary → the whole book in events resolving between Nov 10 and Nov 13 16:00 NY. Lock → index-tracking basket by the Nov 12 close.

**Cap policy:** A (entry-only) or B (continuous) exactly as in §3.3. **Default to B until Bloomberg confirms in writing.**

**Monitoring cadence:**

| When (NY time) | What |
|---|---|
| 07:30 daily | News and FDA actions overnight; Asian closes; TMSG rank; update the catalyst calendar (EVTS, FDA calendar, ECO) |
| 09:30–10:00 | Execute US/EU rolls |
| 15:30 | Cap check and trims (B); plan the Asian orders |
| 19:00–21:00 | Asian session orders |
| Weekly | Recompute B̂ and G from the leaderboard; re-screen themes (EQS) |
| Before every ticket | Run the §3.2 qualification test |

**Kill criteria:**
- Theme: sleeve −25% from its high-water mark, or the theme factor −20% over 10 days → exit.
- A ticket whose event date moves outside the window → exit.
- G ≥ +0.3 → kill maximum variance and go to the index-tracking basket.
- G between +0.1 and +0.3 → kill correlated bets and switch to independent ones.
- Any compliance flag → fix the same day.
- **A falling book is NOT a kill criterion.** Behind means more variance.

**Worked schedule over 25 trading days.** [P] marks placeholders to confirm on the Terminal.

| Day | Date | Catalysts | Actions |
|---|---|---|---|
| D1 | Mon Oct 12 | Start 09:00. US open (Columbus Day); Tokyo and Canada believed closed [verify] | Enter US/EU theme names and binaries S4 (PDUFA-A name), S5 (PDUFA-B name) at the open. Queue Asian theme orders. Send a test order. Chase the cap ruling. |
| D2 | Tue Oct 13 | Asian theme fills (evening of D1 in NY). US banks report [P] | Complete the theme sleeve; confirm fully invested |
| D3 | Wed Oct 14 | US CPI (September) [P] | — |
| D4 | Thu Oct 15 | **Mid-October PDUFA-A** [P] | S4 exits at T+1 |
| D5 | Fri Oct 16 | Initial-position deadline 23:59. Weekly leaderboard [P] | S4 rerolls into the ESMO read-through or PDUFA-C. Theme stop check. |
| D6–D8 | Oct 19–21 | Seagate / TSLA [P]; **mid-October PDUFA-B** [P] | S5 exits at T+1 and rerolls. Hong Kong may be closed ~Oct 19 [verify]. |
| D9 | Thu Oct 22 | **SK hynix Q3** [P] (theme catalyst) | Hold the theme; add names if a mania signal appears |
| D10 | Fri Oct 23 | Weekly leaderboard [P] | Hold ESMO read-through names over the weekend |
| — | **Sat Oct 24** | **ESMO: Moderna Phase 3 melanoma** | — |
| D11 | Mon Oct 26 | ESMO reaction | Exit ESMO names; reroll into INO (if in WLS) or an FOMC/earnings cluster |
| **D12** | **Tue Oct 27** | **MIDPOINT.** FOMC day 1. MSFT/GOOGL/META earnings ~Oct 27–29 [P] | **Compute G, set the mode, consolidate** |
| D13 | Wed Oct 28 | **FOMC decision 14:00** | FOMC high-beta cluster, if chosen |
| D14 | Thu Oct 29 | Samsung Q3 [P]; AAPL/AMZN [P]; ECB/BOJ [P] | — |
| D15 | Fri Oct 30 | **INO PDUFA** (INO-3107); TrendForce contract prices [P]; weekly leaderboard [P] | INO resolves (same day, or Nov 2 if after the close) |
| D16 | Mon Nov 2 | INO reaction if after-hours | Reroll into the Nov 3–6 events |
| D17 | Tue Nov 3 | **US midterms** (results overnight) | Election or policy cluster, if chosen |
| D18 | Wed Nov 4 | Election reaction | Exit the election cluster |
| D19–D20 | Nov 5–6 | Small-cap Q3 peak; AASLD/AHA/SITC [P]; US payrolls Nov 6 [P]; **weekly leaderboard → endgame mode** | Build the endgame book |
| D21 | Mon Nov 9 | Early-November PDUFA-C/D [P]; Japanese results season | Endgame book in place |
| D22 | Tue Nov 10 | **Taiwan October monthly sales deadline**; PDUFA-C [P] | — |
| D23 | Wed Nov 11 | Veterans Day (equities open) | — |
| D24 | Thu Nov 12 | US CPI (October) [P]; **last US after-close reports and last Japanese results that resolve inside the window** | Lock mode → index basket by the close. Otherwise: maximum variance into Nov 13. |
| D25 | Fri Nov 13 | Asian closes 02:00–04:00, EU ~11:30, **US close 16:00 = final marks**, end 17:00 | No new positions after the Asian closes except US names |

**Rolls implied:** each binary slot runs about 4 rolls (D1–5, D6–11, D11–16, D16–25). The theme sleeve gets one burst, which may be extended at the midpoint.

---

## 9. Recommendation

**Adopt archetype (v): the bold-play hybrid.** Three slots in one high-beta theme (the far-tail engine) plus two slots in a ladder of convex binaries (the engine for +100–200%, independent of the field). At the Oct 27 midpoint, consolidate by state, using the leaderboard. End the window on maximum variance unless G ≥ +0.3.

Why this beats the alternatives:
1. **Pure binaries** score best per ticket, but the supply of qualifying WLS events (about 6–10) cannot fill 5 slots × 3–4 rolls. The filler would be negatively skewed, and consensus PDUFAs have P(win) ≈ 0.
2. **A pure theme** is the only single-roll route to +300%, but it is exposed to crowding and momentum crashes in a regime of 5.2% yields and Fed hikes. It also loses much of its convexity under a continuous cap.
3. **The hybrid** keeps a way to win in both kinds of market: a melt-up (theme) and a quiet or risk-off month with a lower bar (binaries). The midpoint rule then turns whichever engine is working into a whole-book bold play. The model puts it at about 6% (realistically 2–5%), roughly 100 times a random team's 1/3,000 = 0.03%. It never holds index-like names or cash while we are in contention.

**Open items, in priority order:**
1. Cap enforcement ruling.
2. WLS membership for INO and for every candidate.
3. Simulator fill model, including limit-up behaviour, after-hours trading and commissions.
4. Minimum position count.
5. Leaderboard publication day and time.
6. Theme screen and scoring (EQS).
7. The full in-window catalyst calendar (PDUFAs, Phase 3 readouts, conference late-breakers, earnings dates for theme names).

---

## Appendix A: Monte Carlo assumptions

200,000 paths. All returns are relative to WLS. V is in units of the $1M notional, and the cap is 0.2 applied at entry unless stated otherwise.

**Winning bar W:** ln(1+W) = ln(1 + median) + 0.46·z, floored at +40%. z has correlation 0.4 with a risk-appetite factor S ~ N(0,1). The two-stage model splits the bar into the level visible at midpoint (A, 55% of the log-mean) plus later growth (B), each with half the variance.

**Tickets** (all calibrated so |EV| ≤ ~4%; no picking edge):
- **Skeptical binary:** 40% chance of a log-normal with median +60% (σ 0.35); otherwise median −50% (σ 0.30). EV −0.5%.
- **Convex binary:** 30% chance of median +110% (σ 0.40); otherwise median −55% (σ 0.30). EV ≈ +1%.
- **Consensus PDUFA:** 88% chance of +5% (σ 0.10); otherwise −45% (σ 0.25).
- **Theme factor over 23–25 days:** a mixture driven by the latent 0.6·S + 0.8·ε.
  - 8% mania: log return N(0.90, 0.35), i.e. a median of +146%.
  - 22% crash: N(−0.45, 0.15).
  - Otherwise: N(−0.06, 0.18).
  - Each name adds idiosyncratic noise N(0, 0.25). Each name also has a "runner" chance of 1% (8% in mania) of an extra 2.5–10× leg.
  - Per-name EV is normalised to +2%.
  - "Uncrowded" sets the S-loading to 0.
  - Continuous cap: the factor compounds fully, but a positive idiosyncratic leg x is harvested as x rather than e^x − 1.
- **Earnings ticket:** Student-t with 3 degrees of freedom, scaled to σ 0.17, minus 2.3% for costs and IV crush.
- **Daily mover:** t3, σ 0.10, minus 1.2% per day.
- **Squeeze:** the theme model with loading 0.3, idiosyncratic σ 0.35 and a 3% runner probability.
- **Event cluster:** 5 names on one event. 30% chance of a common log return N(0.60, 0.25); otherwise N(−0.45, 0.20). Idiosyncratic noise 0.15.
- **Hormuz baskets:**
  - Escalation: 15% chance of +35%, 25% chance of −22%, otherwise −2%.
  - Reopening: 12% chance of +65%, otherwise −7%.

**Rolls:** each round holds n = max(5, ⌈V/0.2⌉) equal tickets; the book multiplier is 1 + the mean ticket return.

**Leader's dilemma:** 40 challengers spread evenly up to 0.4 in log terms below #2. Each has remaining volatility σ_c with drift −σ_c²/2. We have volatility σ with the same drift.

**Limitations:**
- Ticket shapes are stylised.
- The bar is modelled as independent of *our* choices.
- Supply constraints are handled qualitatively.
- The two-stage policy is chosen in-sample (buckets), so it is slightly optimistic.
- Absolute P(win) values are upper bounds; the **ranking** and the qualitative rules are the robust outputs.

## Appendix B: Sources (web checks, 29 Sep 2026)

- Bloomberg for Education, *Trading Challenge Terms & Conditions*: https://portal.bloombergforeducation.com/trading_challenges/terms
- Bloomberg, *Trading Challenge info* (20% of notional; TMSG own rank; weekly full ranking; no ETFs): https://assets.bbhub.io/professional/sites/10/Trading-Challenge_Info.pdf
- 2026 challenge page (dates, $1M notional, WLS universe): https://portal.bloombergforeducation.com/trading_challenges/13 ; https://quantchallenges.com/challenges/2026-bloomberg-global-trading-challenge-qc-2899
- Bloomberg press, 2025 record participation (CUHK >400%, $4.1M, 2,600+ teams): https://www.bloomberg.com/company/press/bloombergs-global-trading-challenge-sets-participation-record/
- CUHK: https://ug.bschool.cuhk.edu.hk/cuhk-business-school-team-wins-2025-bloomberg-global-trading-challenge-as-global-champions/
- RIT 2024 (+$1,676,618 relative, "betting on volatility", mostly foreign stocks, led 5 of 6 weeks): https://www.rit.edu/news/rit-trio-triumphs-global-trading-challenge
- RIT 2023 (2,007 teams): https://www.rit.edu/news/rit-secures-top-spot-north-america-third-globally-bloomberg-2023-global-trading-challenge
- HKU 2023 (+67.7%, +$637,399): https://www.hkubs.hku.hk/media/school-news/2023-bloomberg-global-trading-challenge/
- Bloomberg press 2022 (Southampton +$305,644; 948 teams): https://www.bloomberg.com/company/press/bloomberg-trading-challenge-attracts-4500-students-globally/
- Drexel (#9 globally, +23%, US biotech): https://www.lebow.drexel.edu/news/drexel-finance-students-place-first-north-america-bloomberg-global-trading-challenge
- Iona (#81 of 2,424, +$204,564, small-cap earnings): https://www.iona.edu/news/iona-university-students-place-top-3-percent-bloomberg-global-trading-challenge
- USF (#69, +$53,194 relative): https://www.usf.edu/business/news/2025/12-10-bloomberg-trading-challenge-usf.aspx
- Waterloo (#2 in 2025): https://uwaterloo.ca/math/news/math-team-gwnb-wins-second-place-bloomberg-global-trading
- Literature (from memory, not re-checked):
  - Dubins & Savage (1965), *How to Gamble If You Must*.
  - Brown, Harlow & Starks (1996), *J. Finance*.
  - Chevalier & Ellison (1997), *JPE*.
  - Moskowitz & Grinblatt (1999).
  - Jegadeesh (1990).
  - Daniel & Moskowitz (2016), *Momentum Crashes*.
  - Asquith, Pathak & Ritter (2005).
