# Monte Carlo: which strategy archetype maximises P(1st place)?

Prepared 2026-09-29 by the team quant. Code: `competition/sim/tournament_mc.py` (numpy + matplotlib, runs in about 95 s with `python3 tournament_mc.py`). Every number below comes from that run: 200,000 paths per strategy and seed 20261012. The full generated tables are in `competition/sim/tournament_mc_output.md`.

Objective: **P(win) = P(our benchmark-relative return is at least the maximum of the N other teams)**. Expected return is not the objective. Fair share if every team were identical is 1/(N+1), which is **0.033% at N = 3,000**.

## Read this first: two model choices drive everything

1. **Which field?** The field model given in the brief (80% N(0,8%), 15% N(0,20%), 5% static-PDUFA lottery teams; called **F-briefed**) does not match history. Its median winning score at N = 3,000 is +85%. It **never** produces the 2024 (+168%) or 2025 (+310%) winners, since P < 0.001%. It also puts 804 teams above +5.3%, where 2025 had 69. I refit the field to history (**F-recal**, the base case, Section 1). F-recal has a median winning score of **+142%** and a 90th percentile of **+275%**.
2. **Which world?** The briefed PDUFA block has an expected return of **+27% per event** (80% approval, and half of approvals pop +40% to +120%). Phase 3 is +15% per event and the theme basket +10% per month. That is an *edge* assumption, and it compounds: S3 with k = 3 has a mean of +105%. I therefore also run an **EV-neutral world**, where every block keeps its payoff shape but is priced fair: P(approve) falls to 0.52, P(Phase 3 success) to 0.45, theme drift to -2%. Treat briefed-world P(win) as an upper bound that applies only if we really can pick underpriced events. The EV-neutral figures are the robust guide. Sibling note 01_biotech_catalysts.md supports this: events with ~85% approval odds pop 0% to +30%, and +50% to +200% pops come with ~50% odds. That is roughly EV-neutral, and it is not the briefed combination.

## 0. Headline P(win) (N = 3,000, cap policy (a): winners allowed to run past 20%)

| Strategy (5 slots x 20%) | Briefed world, **F-recal (base)** | Briefed world, F-briefed | **EV-neutral world, F-recal** | EV-neutral, F-briefed |
|---|---|---|---|---|
| S1 5 static PDUFA binaries, one event each | 0.62% | 0.65% | 0.11% | 0.52% |
| S2 5-name single-theme basket (rho = 0.7) | 1.7% | 4.9% | 1.1% | 5.9% |
| S2i control: same names, 5 unrelated themes | 0.10% | 0.037% | 0.035% | 0.090% |
| S3 sequential PDUFA, k = 3 per slot | **29.2%** | **57.3%** | 2.8% | 9.7% |
| S4 earnings roulette, 4 rounds per slot | 1.7% | 4.3% | 0.95% | 3.9% |
| S5 2 theme + 3 sequential PDUFA (k = 3) | 14.5% | 33.7% | 1.8% | 7.1% |
| S6 3 theme + 2 sequential PDUFA (k = 3) | 8.6% | 21.6% | 1.4% | 6.0% |
| S7 sequential Phase 3 readouts, k = 3 | 17.9% | 31.9% | **7.3%** | **17.8%** |
| S8 weekly momentum rotation, t(2.5), E\|move\| 15%, 5 rounds | 0.27% | 0.59% | 0.27% | 1.3% |
| S9 5 short-squeeze candidates (extra) | 0.44% | 0.95% | 0.12% | 0.65% |

P(win) by field size N (briefed world, F-recal, policy (a)):

| Strategy | N = 1,000 | N = 3,000 | N = 5,000 |
|---|---|---|---|
| S1 static PDUFA x5 | 10.1% | 0.62% | 0.079% |
| S2 one-theme basket | 9.2% | 1.7% | 0.55% |
| S2i 5 unrelated themes | 3.7% | 0.10% | 0.008% |
| S3 seq PDUFA k=3 | 52.5% | 29.2% | 20.0% |
| S4 earnings x4 | 8.3% | 1.7% | 0.78% |
| S5 2 theme + 3 seq PDUFA | 34.7% | 14.5% | 8.4% |
| S6 3 theme + 2 seq PDUFA | 25.1% | 8.6% | 4.5% |
| S7 seq Phase 3 k=3 | 30.6% | 17.9% | 13.2% |
| S8 weekly rotation x5 | 2.9% | 0.27% | 0.089% |
| S9 squeeze x5 | 5.1% | 0.44% | 0.099% |
| *Fair share 1/(N+1)* | *0.100%* | *0.033%* | *0.020%* |

The same table for the EV-neutral world and for F-briefed is T6/T8 in the generated output. S7 leads the EV-neutral world at every N: 14.8% / 7.3% / 4.9% on F-recal.

**Conclusion.** The winning score in the last two editions was a multiple of capital, and our recalibrated field puts the median winner at +142% for N = 3,000. The only thing that matters is therefore the right tail of one slot's *compounded* return. Under the 20% cap, a single winning ticket is diluted to one fifth of the book: with four flat slots, one slot must return about **+610%** to lift the book to +142%. That is why 5 independent static lottery tickets are close to worthless (S1: 0.6%, or 0.1% EV-neutral). One correlated theme basket beats independent names with identical per-name odds by 17x to 30x (S2 1.7% vs S2i 0.10%; EV-neutral 1.1% vs 0.035%). But it tops out around +110%, and it collapses if other teams hold the same theme: 30 crowding teams cut it to 0.10%. **Sequential re-rolling of binaries dominates both.** P(win) climbs steeply with the number of events per slot k (S3 at k = 1/2/3/4: 0.65 / 10 / 29 / 48%; EV-neutral: 0.11 / 1.0 / 2.8 / 4.7%). The highest-variance version, rolling Phase-3-style binaries (S7), is the most robust leader. It scores 17.9% in the briefed world and **7.3% EV-neutral**, which is about 220x fair share, while S3 falls to 2.8% EV-neutral. Two refinements help while we are the underdog: let winners run rather than trimming to 20%, and deliberately *correlate* our binaries (same sector). The manager's weekly-rotation S8 is 25x to 100x weaker than sequential binaries, because an E|move| of 15% a week is too little variance per round. At 30% a week it reaches 3.0%. That is exactly what one of the ~30 calibrated "lottery" teams in the field gets, so it confers no advantage.

## 1. What return do we need? (field models and calibration)

Distribution of the field maximum (the winning benchmark-relative return):

| Field | N | p10 | p25 | p50 | p75 | p90 | p99 |
|---|---|---|---|---|---|---|---|
| F-recal | 1,000 | +34% | +56% | +87% | +130% | +191% | +410% |
| **F-recal** | **3,000** | **+82%** | **+106%** | **+142%** | **+197%** | **+275%** | **+561%** |
| F-recal | 5,000 | +106% | +132% | +172% | +235% | +326% | +662% |
| F-briefed | 1,000 | +66% | +71% | +77% | +84% | +90% | +101% |
| F-briefed | 3,000 | +76% | +80% | +85% | +91% | +96% | +107% |
| F-briefed | 5,000 | +80% | +84% | +88% | +93% | +98% | +108% |
| F-briefed, EV-neutral world | 3,000 | +60% | +64% | +70% | +77% | +83% | +99% |

**P(field max is below X)**, which is roughly our chance of winning if we finish at +X:

| Field | N | < +50% | < +100% | < +200% | < +300% |
|---|---|---|---|---|---|
| F-recal | 1,000 | 20.4% | 59.3% | 91.2% | 97.3% |
| **F-recal** | **3,000** | **0.85%** | **20.9%** | **75.9%** | **92.2%** |
| F-recal | 5,000 | 0.035% | 7.4% | 63.2% | 87.3% |
| F-briefed | 1,000 | 0.011% | 98.6% | 100.0% | 100.0% |
| F-briefed | 3,000 | <0.001% | 95.8% | 100.0% | 100.0% |
| F-briefed | 5,000 | <0.001% | 93.2% | 100.0% | 100.0% |

At N = 3,000 on F-recal: +50% almost never wins (0.85%). +100% wins about 1 time in 5. +140% is a coin flip. +200% wins about 3 times in 4, and +275% wins 9 times in 10.

**Calibration against history** (facts from 05_rules_and_past_winners.md: winners +64 pts in 2023 (N = 1,727), +168 pts in 2024 (N = 2,453), about +310% in 2025 (N ≈ 2,650); 2025 rank facts #6 +44%, #9 +23%, #69 +5.3%):

| Field | median max N=3k | p90 max | teams > +5.3% (2025: 69) | > +23% (2025: 9) | > +44% (2025: 6) | P(max >= +64%), N=1,727 | P(max >= +168%), N=2,453 | P(max >= +310%), N=2,650 |
|---|---|---|---|---|---|---|---|---|
| **F-recal** | +142% | +275% | 80 | 7.8 | 4.8 | 86.5% | 30.7% | 6.4% |
| F-briefed | +85% | +96% | 804 | 129 | 37 | 99.4% | <0.001% | <0.001% |

- **The brief's +40 / +60 / +100% alternatives.** F-briefed's median winner is +77 / +85 / +88% at N = 1k / 3k / 5k, so it sits between the +60% and +100% alternatives, nearer +100%. In the EV-neutral world it is +61 / +70 / +74%, which matches the **+60%** alternative and the 2023 winner. **None of the three alternatives matches 2024 or 2025.** F-recal matches the 2024 winner at N = 3,000 (+142%) and N = 5,000 (+172%). It puts the 2025 result (+310%) at roughly its 93rd percentile, i.e. a 1-in-15 year.
- **How F-recal was fitted** (grid of 600 settings; reproduce with `--calibrate`). The bulk is the briefed shape with sds x 0.25, i.e. 80% N(0,2%) and 15% N(0,5%), needed to match only 69 teams above +5.3%. Only **1% of teams (≈30 at N = 3,000) are lottery teams**, but they run a very fat process: 5 slots, each compounding 5 weekly t(2.5) moves with E|move| = 30% (moves capped at +900% a week), no trimming. The coordinator suggested a *larger* lottery share. The fit rejects it: 3-5% lottery teams overshoot the 2025 counts. For example, 5% lottery teams at E|move| 20% put 29 teams above +23% (actual 9) and 13 above +44% (actual 6), with a p90 of only +252%. Adding 5-10x microcap moonshots did not improve the fit either, so that parameter is 0 (it stays in PARAMS). A brute-force simulation of 4,000 whole fields confirms the closed form: median +142% vs +140%, p90 +275% vs +269%.
- **If winners keep rising** (+68 → +168 → +310 over three years), use T9 in the output. It rescales the field max so its median equals T. At T = +310% the leaders are S3 at 4.5% and S7 at 4.1% in the briefed world, and S7 at 1.3% vs S3 at 0.21% EV-neutral.

## 2. The key question: independent tickets vs one correlated theme vs sequential re-rolling

N = 3,000, cap policy (a) unless marked (b):

| Book | mean | p99 | Briefed, F-recal (a) | Briefed, F-recal (b) | Briefed, F-briefed (a) | EV-neutral, F-recal (a) | EV-neutral, F-recal (b) | EV-neutral, F-briefed (a) |
|---|---|---|---|---|---|---|---|---|
| S1 5 independent PDUFA tickets | +27% | +79% | 0.62% | 1.7% | 0.65% | 0.11% | 0.26% | 0.52% |
| S1 same, biotech rho = 0.3 | +27% | +100% | 1.7% | 4.6% | 4.4% | 0.60% | 1.6% | 3.9% |
| S2i 5 momentum names, unrelated themes | +10% | +60% | 0.10% | 0.10% | 0.037% | 0.035% | 0.035% | 0.090% |
| S2 5 names, one theme (rho = 0.7) | +10% | +114% | 1.7% | 1.7% | 4.9% | 1.1% | 1.1% | 5.9% |
| S3 sequential PDUFA k = 2 | +61% | +170% | 10.1% | 14.1% | 28.0% | 1.0% | 1.1% | 5.0% |
| S3 sequential PDUFA k = 3 | +105% | +294% | 29.2% | 33.9% | 57.3% | 2.8% | 2.2% | 9.7% |
| S3 sequential k = 3, biotech rho = 0.3 | +105% | +392% | 30.2% | 37.4% | 51.6% | 5.2% | 6.6% | 13.3% |
| S7 sequential Phase 3 k = 3 | +51% | +351% | 17.9% | 15.8% | 31.9% | **7.3%** | 4.7% | 17.8% |
| S4 earnings roulette x4 | +12% | +130% | 1.7% | 1.7% | 4.3% | 0.95% | 0.81% | 3.9% |
| S8 weekly rotation x5 | +1% | +74% | 0.27% | 0.24% | 0.59% | 0.27% | 0.24% | 1.3% |

**Answer.**

1. **Independent vs correlated, same per-name odds.** One correlated theme beats five independent names by **17x** in the briefed world on F-recal (1.7% vs 0.10%), **31x** EV-neutral (1.1% vs 0.035%) and **130x** on F-briefed (4.9% vs 0.037%). Versus independent *biotech* tickets (S1) the theme is 2.7x better in the briefed world (1.7% vs 0.62%) and 10x better EV-neutral (1.1% vs 0.11%). Mechanism: with a 20% cap, five independent tickets average each other out. Book sd is roughly the per-name sd divided by sqrt(5), and one hit adds only 0.2 x its return. A single correct theme call moves all five slots together. Adding biotech-sector correlation of 0.3 to our "independent" tickets lifts S1 from 0.11% to 0.60% EV-neutral, for the same reason.
2. **The theme's limits.** Even with its +60% melt-up regime, S2's p99 is only +114%, below the +142% median winner. It needs a bigger mania (melt-up +150%: 8.8%; +200%: 11.8%) or a smaller field. It is also the most crowding-sensitive book: if 10 / 30 / 100 other teams hold the same theme, S2 falls from 1.7% to **0.25% / 0.10% / 0.035%**. Hybrids S5/S6 hardly care (14.5% → 14.0%), because their tail comes from the binaries.
3. **Sequential re-rolling dominates both**, in every world and field tested. EV-neutral on F-recal it gets **2.8% (S3) and 7.3% (S7) vs 1.1% for the theme and 0.11% for static tickets**. Compounding within a slot is what beats the cap. Three consecutive +80% Phase 3 wins turn a 20% slot into 5.8x, a book of about +100% from one slot alone. The best variant is the one with the **largest per-event variance** (Phase-3-like, sd ≈ 79% per event), not the most events. Earnings roulette (sd 35% per event, 4 rounds) gets only 0.95% EV-neutral, and weekly rotation at 15% E|move| gets 0.27%.
4. **Correlating the binaries helps us as underdogs.** With rho = 0.3 among our binaries, S3 rises from 2.8% to 5.2% and S7 from 7.3% to 9.4% (EV-neutral). It hurts only when the book is already the favourite (briefed S3 on F-briefed: 57% → 52%). This is the standard tournament result: add correlation and variance when the target sits far above your mean.

## 3. Sequential re-rolling: P(win) vs events per slot k (N = 3,000)

| Strategy | k | mean (briefed) | Briefed F-recal (a) | Briefed F-recal (b) | Briefed F-briefed (a) | EV-neutral F-recal (a) | EV-neutral F-recal (b) | EV-neutral F-briefed (a) |
|---|---|---|---|---|---|---|---|---|
| S3 PDUFA | 1 | +27% | 0.65% | 1.7% | 0.73% | 0.11% | 0.26% | 0.57% |
| S3 PDUFA | 2 | +61% | 10.1% | 14.1% | 28.0% | 1.0% | 1.1% | 5.0% |
| S3 PDUFA | 3 | +105% | 29.2% | 33.9% | 57.3% | 2.8% | 2.2% | 9.7% |
| S3 PDUFA | 4 | +160% | 48.0% | 53.1% | 73.7% | 4.7% | 3.2% | 12.5% |
| S7 Phase 3 | 1 | +15% | 1.1% | 2.5% | 2.7% | 0.48% | 1.1% | 3.0% |
| S7 Phase 3 | 2 | +32% | 8.4% | 9.0% | 19.8% | 3.3% | 3.1% | 12.0% |
| S7 Phase 3 | 3 | +51% | 17.9% | 15.8% | 31.9% | 7.3% | 4.7% | 17.8% |
| S7 Phase 3 | 4 | +74% | 24.3% | 22.1% | 34.8% | 9.8% | 5.9% | 16.8% |
| S5 2 theme + 3 seq | 2 | +41% | 4.4% | 4.9% | 12.7% | 0.66% | 0.64% | 3.6% |
| S5 2 theme + 3 seq | 3 | +67% | 14.5% | 13.0% | 33.7% | 1.8% | 1.2% | 7.1% |
| S6 3 theme + 2 seq | 2 | +30% | 2.8% | 2.9% | 8.1% | 0.64% | 0.60% | 3.6% |
| S6 3 theme + 2 seq | 3 | +48% | 8.6% | 6.7% | 21.6% | 1.4% | 0.99% | 6.0% |

The step from k = 1 to k = 2 is worth 10x to 15x. After that, returns diminish but stay positive up to k = 4 on F-recal. **Feasibility warning:** k = 3 across 5 slots needs 15 resolved binaries in 25 trading days. 01_biotech_catalysts.md found **one** verified in-window sub-$500M PDUFA (INO, Oct 30; P ~55%, +80% to +200% / -55% to -75%, which is a Phase-3-like payoff) plus a handful of unverified ones. In practice each "chain" must mix event types: PDUFAs, Phase 3 toplines, conference late-breakers (ESMO, AASLD, AHA) and only the highest-implied-move earnings. Assume k ≈ 2 is realistic; that is 3.3% for S7 and 1.0% for S3 EV-neutral.

## 4. The 20% cap: (a) let winners run vs (b) trim to 20% after each event

With exactly 5 slots and full investment, "trim the winner to 20% and spread the proceeds" equals re-equalising all 5 slots after every event. The book then compounds event by event: gross = Π(1 + 0.2 r_e).

| Strategy | Briefed F-recal (a) → (b) | EV-neutral F-recal (a) → (b) |
|---|---|---|
| S1 static PDUFA | 0.62% → 1.7% | 0.11% → 0.26% |
| S3 seq PDUFA k=3 | 29.2% → 33.9% | 2.8% → 2.2% |
| S7 seq Phase 3 k=3 | 17.9% → 15.8% | **7.3% → 4.7%** |
| S5 / S6 hybrids | 14.5% → 13.0% / 8.6% → 6.7% | 1.8% → 1.2% / 1.4% → 0.99% |
| S8 weekly rotation | 0.27% → 0.24% | 0.27% → 0.24% |
| S4 earnings | 1.7% → 1.7% | 0.95% → 0.81% |

- Trimming *helps* static one-shot tickets (S1, S9). The trimmed proceeds become fresh stakes in the later binaries, so winnings compound across the book.
- Trimming *hurts* the sequential strategies in the EV-neutral world (S7 loses a third of its P(win)), because it kills the "one slot goes 5-8x" tail that wins tournaments.
- It helps S3 only in the briefed world, where every PDUFA carries +27% EV and spreading money across more positive-EV events adds mean.
- Recommendation: plan for (a), and confirm how Bloomberg enforces the cap before Oct 12 (open item 1 in 05_rules_and_past_winners.md). If the cap is enforced continuously, sequential books lose 20% to 35% of their P(win) but still lead.

## 5. Sensitivities (N = 3,000, F-recal, policy (a))

| Parameter | Values | Result |
|---|---|---|
| P(approve), briefed world | 0.70 / 0.75 / 0.80 / 0.85 / 0.90 | S3: 14.7 / 21.1 / 29.2 / 38.9 / 49.9%. S5: 7.8 / 10.7 / 14.5 / 19.2 / 24.9%. S6: 5.1 / 6.7 / 8.6 / 10.9 / 13.7%. S1: 0.36 → 1.0% |
| Approval pop scale (0.27 = EV 0 at P = 0.8) | 0.27 / 0.5 / 0.75 / 1.0 / 1.25 / 1.5 | S3: 0.04 / 1.8 / 12.0 / 29.2 / 46.5 / 60.5%. S5: 0.12 → 37%. S1: 0.001 → 3.8%. **Everything hinges on the size of the approval pop.** |
| Approval model N(+25%, 20%) instead of two-regime | two-regime → normal | S3 29.2% → 2.8%; S5 14.5% → 1.4%; S1 0.62% → 0.022% |
| Events per slot k | 1 → 4 | See Section 3 |
| Theme rho | 0.3 / 0.5 / 0.7 / 0.9 | S2: 1.2 / 1.4 / 1.7 / 1.9% (EV-neutral 0.74 → 1.2%). S5/S6 flat (14.4-14.5%, 8.3-8.7%) |
| Correlation among our binaries | 0 / 0.3 / 0.6 | S1: 0.62 / 1.7 / 2.9% (EV-neutral 0.11 / 0.60 / 1.5%). S3: 29.2 / 30.2 / 30.3% (EV-neutral 2.8 / 5.2 / 7.0%). S7: 17.9 / 19.9 / 21.0% (EV-neutral 7.3 / 9.4 / 10.8%). S5: 14.5 / 16.3 / 17.6% |
| Theme melt-up size | +30 / +60 / +100 / +150 / +200% | S2: 0.64 / 1.7 / 4.5 / 8.8 / 11.8%. S6: 7.7 → 14.6%. S5: 13.9 → 18.2% |
| Theme melt-up probability | 0.05 / 0.10 / 0.15 / 0.25 | S2: 0.77 / 1.2 / 1.7 / 2.5% |
| Rotation weekly E\|move\| (S8) | 10 / 15 / 20 / 25 / 30% | 0.054 / 0.27 / 0.80 / 1.7 / 3.0% |
| Earnings E\|move\| (S4) | 15 / 20 / 25 / 30% | 0.23 / 0.76 / 1.7 / 3.1% |
| Crowding: M extra teams in our theme | 0 / 10 / 30 / 100 | S2: 1.7 / 0.25 / 0.10 / 0.035%. S5: 14.5 / 14.0 / 14.0 / 13.9% |

What to spend research time on, in order:

1. The **payoff size** of the events we pick. Pop scale and the approval model move P(win) by 10x to 100x.
2. The **per-event variance** of each chain.
3. **k**, the number of events we can realistically chain.
4. Probability estimates, which move P(win) by about 2x across 0.7-0.9.

Theme rho barely matters once correlation is high.

## 6. Distribution statistics (benchmark-relative, briefed world)

| Strategy | cap | mean | median | p90 | p99 | P(>+50%) | P(>+100%) | P(>+200%) |
|---|---|---|---|---|---|---|---|---|
| S1 static PDUFA x5 | a | +27% | +27% | +57% | +79% | 16.4% | 0.033% | <0.001% |
| S1 static PDUFA x5 | b | +30% | +28% | +69% | +107% | 23.3% | 1.6% | <0.001% |
| S2 one-theme basket | a=b | +10% | +8% | +66% | +114% | 16.7% | 2.4% | 0.001% |
| S2i 5 unrelated themes | a=b | +10% | +10% | +37% | +60% | 2.9% | 0.001% | <0.001% |
| S3 seq PDUFA k=3 | a | +105% | +98% | +198% | +294% | 77.4% | 48.9% | 9.7% |
| S3 seq PDUFA k=3 | b | +120% | +105% | +233% | +387% | 79.2% | 52.8% | 15.9% |
| S4 earnings x4 | a | +12% | +7% | +60% | +130% | 14.0% | 2.6% | 0.14% |
| S5 2 theme + 3 seq PDUFA | a | +67% | +61% | +143% | +225% | 57.6% | 25.7% | 2.1% |
| S6 3 theme + 2 seq PDUFA | a | +48% | +42% | +116% | +190% | 44.0% | 15.1% | 0.67% |
| S7 seq Phase 3 k=3 | a | +51% | +33% | +190% | +351% | 43.9% | 27.5% | 8.8% |
| S7 seq Phase 3 k=3 | b | +55% | +30% | +179% | +414% | 40.7% | 23.7% | 8.0% |
| S8 weekly rotation x5 | a | +1% | -1% | +32% | +74% | 3.5% | 0.30% | 0.011% |
| S9 squeeze x5 | a | +10% | +5% | +45% | +83% | 7.7% | 0.29% | <0.001% |

EV-neutral world (policy a): every mean ≈ 0. p99 / P(>+100%): S7 +258% / 11.9%; S3 +157% / 4.7%; S5 +134% / 3.0%; S4 +110% / 1.4%; S2 +104% / 1.3%; S1 +61% / 0.002%. S7 has the *lowest* median of all (-27%) and the best P(win). That is the tournament trade-off in one line.

## 7. Charts

- `../sim/fig_return_distributions.png`: log-scale histograms of relative return per strategy, (a) vs (b), with the median winning score of each field marked.
- `../sim/fig_pwin_by_strategy.png`: P(win) by strategy and N (log scale) for three settings: briefed/F-recal, briefed/F-briefed, EV-neutral/F-recal. Fair share is marked.
- `../sim/fig_sensitivity.png`: P(win) vs P(approve), pop scale, k, binary rho, theme rho and melt-up size. Solid lines are the briefed world and dashed lines EV-neutral.

## 8. Implications for the book (quant view, to be reconciled with 06_strategy_framework.md)

1. Build **5 chains, not 5 positions.** Each slot holds the highest-variance binary catalyst available. When it resolves, win or lose, the slot rolls into the next catalyst. Prefer Phase-3-like payoffs (+80% to +200% / -60% to -75%, odds near 50%) over "priced-in" PDUFAs (80-90% approval, 0% to +30% pop). The latter are low-variance and add almost nothing (S1-like).
2. **Do not diversify across sectors.** Clustering in biotech (rho ≈ 0.3) roughly doubles P(win) for an underdog book.
3. **Let winners run** unless the cap rule forces trimming.
4. Use a **theme basket only as filler** when no binary is available for a slot, and only in a theme we believe is *not* already crowded by other student teams. A hot theme everyone holds (e.g. the 2026 memory/AI-hardware trade in 03_momentum_and_themes.md) is the worst case for S2.
5. Weekly "top mover" rotation and 25%-implied-move earnings roulette are not enough variance per round to win at N = 3,000. Use them only to keep a slot busy between catalysts.

## 9. Assumptions (all parameters live in `PARAMS` at the top of the script)

**Simulation:** 200,000 paths per strategy. The field lottery CDF is built from 400,000 samples. P(win) = E[(1 - S_team(X))^N] is exact given i.i.d. teams and is validated by brute-force simulation of 4,000 whole fields. Common random numbers are used across sensitivity values.

**Constraints:**
- 5 slots x 20%, fully invested, long only, no leverage, 25 trading days.
- A single stock return is floored at -95% per event.
- Cap policy (a) lets slots compound freely. Policy (b) re-equalises to 20% after every event, with events staggered one at a time. In hybrids, theme slots spread their monthly return geometrically over the rounds.

**Benchmark:**
- Index return over the window ~ N(0, 5%).
- Relative = our return minus the index (arithmetic, as Bloomberg's Rel P&L appears to be).
- Block returns are drawn independently of the index (`beta_stock = 0`, the brief's literal spec). S1 slots sit in index-like stocks after their event.

**PDUFA (briefed):** P(approve) = 0.80. Approval is two-regime: 50% of approvals "priced in" U(+5%, +20%), 50% "big pop" U(+40%, +120%). Alternative approval model N(+25%, 20%). CRL N(-50%, 15%). EV +27% per event.

**Phase 3 (briefed):** P(success) = 0.55. Success N(+80%, 40%), failure N(-65%, 15%). EV +15%.

**Earnings roulette:** Student-t(3) scaled to E|move| = 25%. Up-moves x1.1, down-moves x0.9 (mean +2.5%). Capped at +300%. 4 sequential rounds per slot.

**Weekly rotation (S8):** Student-t(2.5) scaled to E|move| = 15%, symmetric, capped at +300% per week, 5 rounds.

**Theme basket:**
- Per name N(+8%, 35%), within-theme correlation rho = 0.7.
- Regimes are shared by the theme: melt-up p = 0.15 adds +60%; crash p = 0.20 adds -35%.
- EV +10% per month.

**Short squeeze (S9):** P = 0.15 of N(+120%, 60%), else N(-10%, 25%).

**Sequential k:** 3 events per slot by default (S3, S5, S6, S7). Our binaries are independent by default; the rho option uses a one-factor Gaussian copula per event round.

**EV-neutral world:** the same payoffs at market-fair odds. P(approve) 0.519, P(Phase 3 success) 0.448, P(squeeze) 0.077, theme drift -2%, earnings mean removed. The rotation block is unchanged because it is already mean-zero.

**Fields:**
- **F-briefed**, as specified: 80% N(0,8%), 15% N(0,20%), 5% lottery teams holding 5 static PDUFA binaries. In the EV-neutral world its lottery teams use EV-neutral binaries.
- **F-recal** (base): 79.2% N(0,2%), 14.8% N(0,5%), plus 1% lottery teams. Each lottery team compounds, per slot, 5 weekly t(2.5) moves with E|move| 30% (capped at +900% per week) and does not trim.
- Teams are i.i.d. and independent of us. The one exception is the crowding test, where crowd teams share our theme regime, theme factor and index draw.

**Limitations (what the model leaves out):**
- No transaction costs, spreads, halts, liquidity limits or capacity (20% of $1M = $200k per name).
- No pre-event run-up or post-event drift.
- No financing or dilution after a catalyst, which 01_biotech_catalysts.md flags for INO.
- Proceeds are assumed to roll instantly into the next event at fair prices.
- The field is modelled as independent of us. In reality lottery teams chase the same few catalysts, so our biotech chains could be crowded in the same way as S2 (not modelled).
- WLS index membership of micro-caps (e.g. a ~$130M name) is not checked and must be verified per name.
- F-recal rests on one year of rank facts plus three winners.
- The EV-neutral world has no edge. Any genuine event-selection edge moves results toward the briefed-world column.

## 10. Reproduce / modify

```
cd competition/sim
python3 tournament_mc.py              # full run, ~95 s, writes the 3 PNGs + tournament_mc_output.md + tournament_mc_results.json
python3 tournament_mc.py --quick      # 50k paths, ~30 s
python3 tournament_mc.py --calibrate  # refit the recalibrated field (grid search), ~15 s
```

To change an assumption, edit `PARAMS` (for example `PARAMS['pdufa']['p_approve']`, `PARAMS['k_seq']`, `PARAMS['fields']['recal']['w_lottery']`) and rerun. Strategy slot layouts are in `strategy_spec()`.
