# tournament_mc.py output (generated, do not edit by hand)

### T1. Expected return per event embedded in each building block

| Block | Mean (briefed) | Sd (briefed) | Mean (EV-neutral) | EV-neutral change |
|---|---|---|---|---|
| PDUFA | +27% | 52% | -0% | P(good) 0.80 -> 0.519 |
| Phase 3 | +15% | 79% | +0% | P(good) 0.55 -> 0.448 |
| Earnings | +3% | 35% | -0% |  |
| Rotation (weekly) | +0% | 23% | +0% |  |
| Squeeze | +9% | 57% | -0% | P(good) 0.15 -> 0.077 |
| Theme name (month) | +10% | 45% | +0% | drift +0.08 -> -0.02 |


### T2. Distribution of the field maximum (winning relative return)

| Field | N | p10 | p25 | p50 | p75 | p90 | p99 |
|---|---|---|---|---|---|---|---|
| F-recal | 1,000 | +34% | +56% | +87% | +130% | +191% | +410% |
| F-recal | 3,000 | +82% | +106% | +142% | +197% | +275% | +561% |
| F-recal | 5,000 | +106% | +132% | +172% | +235% | +326% | +662% |
| F-briefed | 1,000 | +66% | +71% | +77% | +84% | +90% | +101% |
| F-briefed | 3,000 | +76% | +80% | +85% | +91% | +96% | +107% |
| F-briefed | 5,000 | +80% | +84% | +88% | +93% | +98% | +108% |
| F-briefed, EV-neutral world | 1,000 | +50% | +55% | +61% | +68% | +76% | +91% |
| F-briefed, EV-neutral world | 3,000 | +60% | +64% | +70% | +77% | +83% | +99% |
| F-briefed, EV-neutral world | 5,000 | +64% | +69% | +74% | +80% | +86% | +101% |


### T2b. Validation: closed-form (1-S)^N vs brute-force simulated fields, N=3,000

| Field | Brute-force fields | p10 closed/brute | p50 closed/brute | p90 closed/brute |
|---|---|---|---|---|
| F-recal | 4000 | +82% / +82% | +142% / +140% | +275% / +269% |
| F-briefed | 4000 | +76% / +76% | +85% / +85% | +96% / +96% |


### T3. Calibration against history: which field model matches?

| Field | median max (N=3k) | p90 max | # teams > +5.3% (2025: 69) | # > +23% (2025: 9) | # > +44% (2025: 6) | P(max >= +64%) N=1,727 (2023) | P(max >= +168%) N=2,453 (2024) | P(max >= +310%) N=2,650 (2025) |
|---|---|---|---|---|---|---|---|---|
| F-recal | +142% | +275% | 80.1 | 7.8 | 4.8 | 86.5% | 30.7% | 6.4% |
| F-briefed | +85% | +96% | 804.2 | 129.3 | 36.8 | 99.4% | <0.001% | <0.001% |

| Field | median field max, N=1,000 | median field max, N=3,000 | median field max, N=5,000 |
|---|---|---|---|
| F-recal | +87% (nearest +100%) | +142% (nearest +168%) | +172% (nearest +168%) |
| F-briefed | +77% (nearest +68%) | +85% (nearest +100%) | +88% (nearest +100%) |
| F-briefed, EV-neutral world | +61% (nearest +60%) | +70% (nearest +68%) | +74% (nearest +68%) |


Candidates: the brief's +40/+60/+100% alternatives and the actual winners +68% (2023), +168% (2024), +310% (2025).


### T4. What return do we need? P(field max below X)

| Field | N | P(max < +50%) | P(max < +100%) | P(max < +200%) | P(max < +300%) |
|---|---|---|---|---|---|
| F-recal | 1,000 | 20.4% | 59.3% | 91.2% | 97.3% |
| F-recal | 3,000 | 0.85% | 20.9% | 75.9% | 92.2% |
| F-recal | 5,000 | 0.035% | 7.4% | 63.2% | 87.3% |
| F-briefed | 1,000 | 0.011% | 98.6% | 100.0% | 100.0% |
| F-briefed | 3,000 | <0.001% | 95.8% | 100.0% | 100.0% |
| F-briefed | 5,000 | <0.001% | 93.2% | 100.0% | 100.0% |


Read: if we finish at +X, P(max < X) is roughly our chance of winning with that score.


### T5. Strategy return distributions (benchmark-relative, briefed world)

| Strategy | cap | mean | median | p90 | p99 | P(>+50%) | P(>+100%) | P(>+200%) |
|---|---|---|---|---|---|---|---|---|
| S1 static PDUFA x5 | a | +27% | +27% | +57% | +79% | 16.4% | 0.033% | <0.001% |
| S1 static PDUFA x5 | b | +30% | +28% | +69% | +107% | 23.3% | 1.6% | <0.001% |
| S2 one-theme basket | a | +10% | +8% | +66% | +114% | 16.7% | 2.4% | 0.001% |
| S2i 5 unrelated themes | a | +10% | +10% | +37% | +60% | 2.9% | 0.001% | <0.001% |
| S3 seq PDUFA k=3 | a | +105% | +98% | +198% | +294% | 77.4% | 48.9% | 9.7% |
| S3 seq PDUFA k=3 | b | +120% | +105% | +233% | +387% | 79.2% | 52.8% | 15.9% |
| S4 earnings x4 | a | +12% | +7% | +60% | +130% | 14.0% | 2.6% | 0.14% |
| S4 earnings x4 | b | +12% | +7% | +59% | +129% | 13.5% | 2.5% | 0.11% |
| S5 2 theme+3 seqPDUFA | a | +67% | +61% | +143% | +225% | 57.6% | 25.7% | 2.1% |
| S5 2 theme+3 seqPDUFA | b | +63% | +56% | +138% | +225% | 54.4% | 22.8% | 2.0% |
| S6 3 theme+2 seqPDUFA | a | +48% | +42% | +116% | +190% | 44.0% | 15.1% | 0.67% |
| S6 3 theme+2 seqPDUFA | b | +41% | +37% | +105% | +174% | 39.3% | 11.6% | 0.35% |
| S7 seq Phase3 k=3 | a | +51% | +33% | +190% | +351% | 43.9% | 27.5% | 8.8% |
| S7 seq Phase3 k=3 | b | +55% | +30% | +179% | +414% | 40.7% | 23.7% | 8.0% |
| S8 weekly rotation x5 | a | +1% | -1% | +32% | +74% | 3.5% | 0.30% | 0.011% |
| S8 weekly rotation x5 | b | +1% | -1% | +31% | +72% | 3.4% | 0.24% | 0.003% |
| S9 squeeze x5 | a | +10% | +5% | +45% | +83% | 7.7% | 0.29% | <0.001% |
| S9 squeeze x5 | b | +10% | +4% | +46% | +103% | 8.7% | 1.1% | 0.030% |


cap a = no rebalancing (winners grow past 20%); b = trim to 20% after every event. S2/S2i are one-period baskets, so a = b.


### T5e. Strategy return distributions, EV-neutral world (policy a)

| Strategy | mean | median | p90 | p99 | P(>+50%) | P(>+100%) | P(>+200%) |
|---|---|---|---|---|---|---|---|
| S1 static PDUFA x5 | +0% | -1% | +34% | +61% | 2.9% | 0.002% | <0.001% |
| S2 one-theme basket | +0% | -2% | +56% | +104% | 12.1% | 1.3% | 0.001% |
| S2i 5 unrelated themes | +0% | -0% | +27% | +50% | 0.94% | <0.001% | <0.001% |
| S3 seq PDUFA k=3 | +0% | -10% | +69% | +157% | 15.5% | 4.7% | 0.28% |
| S4 earnings x4 | +0% | -5% | +44% | +110% | 8.1% | 1.4% | 0.080% |
| S5 2 theme+3 seqPDUFA | +0% | -8% | +57% | +134% | 12.2% | 3.0% | 0.085% |
| S6 3 theme+2 seqPDUFA | -0% | -6% | +53% | +125% | 11.0% | 2.3% | 0.049% |
| S7 seq Phase3 k=3 | +0% | -27% | +112% | +258% | 22.9% | 11.9% | 2.6% |
| S8 weekly rotation x5 | +1% | -1% | +32% | +74% | 3.5% | 0.30% | 0.011% |
| S9 squeeze x5 | +0% | -4% | +29% | +63% | 2.5% | 0.041% | <0.001% |


### T6. HEADLINE: P(win) by strategy, field model and N (briefed world, cap policy a)

| Strategy | F-recal N=1,000 | F-recal N=3,000 | F-recal N=5,000 | F-briefed N=1,000 | F-briefed N=3,000 | F-briefed N=5,000 |
|---|---|---|---|---|---|---|
| S1 static PDUFA x5 | 10.1% | 0.62% | 0.079% | 1.9% | 0.65% | 0.39% |
| S2 one-theme basket | 9.2% | 1.7% | 0.55% | 6.8% | 4.9% | 4.2% |
| S2i 5 unrelated themes | 3.7% | 0.10% | 0.008% | 0.16% | 0.037% | 0.020% |
| S3 seq PDUFA k=3 | 52.5% | 29.2% | 20.0% | 61.9% | 57.3% | 55.4% |
| S4 earnings x4 | 8.3% | 1.7% | 0.78% | 5.7% | 4.3% | 3.8% |
| S5 2 theme+3 seqPDUFA | 34.7% | 14.5% | 8.4% | 38.6% | 33.7% | 31.8% |
| S6 3 theme+2 seqPDUFA | 25.1% | 8.6% | 4.5% | 25.8% | 21.6% | 20.0% |
| S7 seq Phase3 k=3 | 30.6% | 17.9% | 13.2% | 34.5% | 31.9% | 30.9% |
| S8 weekly rotation x5 | 2.9% | 0.27% | 0.089% | 0.91% | 0.59% | 0.50% |
| S9 squeeze x5 | 5.1% | 0.44% | 0.099% | 1.7% | 0.95% | 0.75% |


Fair share (every team identical) = 1/(N+1): 0.100% / 0.033% / 0.020%.


### T7. Cap handling: P(win) at N=3,000, (a) no rebalancing vs (b) trim to 20% after each event

| Strategy | briefed F-recal (a) | briefed F-recal (b) | briefed F-briefed (a) | briefed F-briefed (b) | EV-neutral F-recal (a) | EV-neutral F-recal (b) | EV-neutral F-briefed (a) | EV-neutral F-briefed (b) |
|---|---|---|---|---|---|---|---|---|
| S1 static PDUFA x5 | 0.62% | 1.7% | 0.65% | 4.3% | 0.11% | 0.26% | 0.52% | 1.5% |
| S2 one-theme basket | 1.7% | 1.7% | 4.9% | 4.9% | 1.1% | 1.1% | 5.9% | 5.9% |
| S2i 5 unrelated themes | 0.10% | 0.10% | 0.037% | 0.037% | 0.035% | 0.035% | 0.090% | 0.090% |
| S3 seq PDUFA k=3 | 29.2% | 33.9% | 57.3% | 60.5% | 2.8% | 2.2% | 9.7% | 7.5% |
| S4 earnings x4 | 1.7% | 1.7% | 4.3% | 4.2% | 0.95% | 0.81% | 3.9% | 3.5% |
| S5 2 theme+3 seqPDUFA | 14.5% | 13.0% | 33.7% | 30.4% | 1.8% | 1.2% | 7.1% | 5.1% |
| S6 3 theme+2 seqPDUFA | 8.6% | 6.7% | 21.6% | 17.4% | 1.4% | 0.99% | 6.0% | 4.6% |
| S7 seq Phase3 k=3 | 17.9% | 15.8% | 31.9% | 27.8% | 7.3% | 4.7% | 17.8% | 11.9% |
| S8 weekly rotation x5 | 0.27% | 0.24% | 0.59% | 0.54% | 0.27% | 0.24% | 1.3% | 1.2% |
| S9 squeeze x5 | 0.44% | 0.84% | 0.95% | 2.1% | 0.12% | 0.20% | 0.65% | 1.1% |


### T8. EV-neutral world: P(win) by N (cap policy a)

| Strategy | F-recal N=1,000 | F-recal N=3,000 | F-recal N=5,000 | F-briefed N=1,000 | F-briefed N=3,000 | F-briefed N=5,000 |
|---|---|---|---|---|---|---|
| S1 static PDUFA x5 | 2.8% | 0.11% | 0.011% | 1.3% | 0.52% | 0.33% |
| S2 one-theme basket | 6.7% | 1.1% | 0.33% | 8.3% | 5.9% | 5.1% |
| S2i 5 unrelated themes | 1.9% | 0.035% | 0.002% | 0.35% | 0.090% | 0.047% |
| S3 seq PDUFA k=3 | 9.0% | 2.8% | 1.4% | 12.0% | 9.7% | 8.9% |
| S4 earnings x4 | 5.1% | 0.95% | 0.42% | 5.5% | 3.9% | 3.4% |
| S5 2 theme+3 seqPDUFA | 7.1% | 1.8% | 0.84% | 9.1% | 7.1% | 6.4% |
| S6 3 theme+2 seqPDUFA | 6.5% | 1.4% | 0.63% | 7.9% | 6.0% | 5.3% |
| S7 seq Phase3 k=3 | 14.8% | 7.3% | 4.9% | 19.9% | 17.8% | 16.9% |
| S8 weekly rotation x5 | 2.9% | 0.27% | 0.089% | 2.1% | 1.3% | 1.0% |
| S9 squeeze x5 | 2.2% | 0.12% | 0.019% | 1.3% | 0.65% | 0.47% |


### T9. P(win) if the winning score is typically T (field max rescaled so its median = T), N=3,000 shape

| Strategy | brief T=+40% | brief T=+60% | brief T=+100% | brief T=+168% | brief T=+310% | EVN T=+40% | EVN T=+60% | EVN T=+100% | EVN T=+168% | EVN T=+310% |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 static PDUFA x5 | 29.3% | 13.7% | 2.9% | 0.27% | 0.010% | 8.0% | 3.1% | 0.54% | 0.045% | 0.002% |
| S2 one-theme basket | 21.7% | 13.0% | 4.7% | 0.88% | 0.049% | 16.3% | 9.5% | 3.2% | 0.55% | 0.029% |
| S2i 5 unrelated themes | 10.5% | 3.8% | 0.56% | 0.043% | 0.002% | 5.0% | 1.6% | 0.20% | 0.014% | 0.001% |
| S3 seq PDUFA k=3 | 78.0% | 66.5% | 45.5% | 21.9% | 4.5% | 18.4% | 12.4% | 5.8% | 1.8% | 0.21% |
| S4 earnings x4 | 19.3% | 11.3% | 4.3% | 1.1% | 0.12% | 12.0% | 6.7% | 2.4% | 0.57% | 0.064% |
| S5 2 theme+3 seqPDUFA | 60.7% | 46.9% | 26.7% | 9.9% | 1.4% | 15.5% | 9.8% | 4.1% | 1.1% | 0.11% |
| S6 3 theme+2 seqPDUFA | 48.4% | 34.9% | 17.6% | 5.5% | 0.63% | 14.7% | 8.9% | 3.5% | 0.85% | 0.075% |
| S7 seq Phase3 k=3 | 45.2% | 38.0% | 26.4% | 14.1% | 4.1% | 24.3% | 19.2% | 12.0% | 5.5% | 1.3% |
| S8 weekly rotation x5 | 7.6% | 3.4% | 0.86% | 0.15% | 0.012% | 7.6% | 3.4% | 0.86% | 0.15% | 0.012% |
| S9 squeeze x5 | 13.7% | 6.6% | 1.6% | 0.21% | 0.010% | 6.1% | 2.5% | 0.50% | 0.053% | 0.002% |


Uses the F-recal field-max shape, stretched so its median equals T. +40/+60/+100% are the brief's alternatives; +168% and +310% are the 2024 and 2025 winners.


### T10. Sequential re-rolling: P(win) vs events per slot k (N=3,000)

| Strategy | k | mean (brief, a) | brief F-recal (a) | brief F-recal (b) | brief F-briefed (a) | EVN F-recal (a) | EVN F-recal (b) | EVN F-briefed (a) |
|---|---|---|---|---|---|---|---|---|
| S3 | 1 | +27% | 0.65% | 1.7% | 0.73% | 0.11% | 0.26% | 0.57% |
| S3 | 2 | +61% | 10.1% | 14.1% | 28.0% | 1.00% | 1.1% | 5.0% |
| S3 | 3 | +105% | 29.2% | 33.9% | 57.3% | 2.8% | 2.2% | 9.7% |
| S3 | 4 | +160% | 48.0% | 53.1% | 73.7% | 4.7% | 3.2% | 12.5% |
| S7 | 1 | +15% | 1.1% | 2.5% | 2.7% | 0.48% | 1.1% | 3.0% |
| S7 | 2 | +32% | 8.4% | 9.0% | 19.8% | 3.3% | 3.1% | 12.0% |
| S7 | 3 | +51% | 17.9% | 15.8% | 31.9% | 7.3% | 4.7% | 17.8% |
| S7 | 4 | +74% | 24.3% | 22.1% | 34.8% | 9.8% | 5.9% | 16.8% |
| S5 | 1 | +20% | 0.50% | 0.77% | 0.70% | 0.13% | 0.19% | 0.70% |
| S5 | 2 | +41% | 4.4% | 4.9% | 12.7% | 0.66% | 0.64% | 3.6% |
| S5 | 3 | +67% | 14.5% | 13.0% | 33.7% | 1.8% | 1.2% | 7.1% |
| S5 | 4 | +100% | 27.5% | 23.6% | 50.3% | 3.1% | 1.8% | 9.0% |
| S6 | 1 | +17% | 0.72% | 0.82% | 1.5% | 0.26% | 0.28% | 1.6% |
| S6 | 2 | +30% | 2.8% | 2.9% | 8.1% | 0.64% | 0.60% | 3.6% |
| S6 | 3 | +48% | 8.6% | 6.7% | 21.6% | 1.4% | 0.99% | 6.0% |
| S6 | 4 | +70% | 17.1% | 11.9% | 34.7% | 2.3% | 1.4% | 7.3% |


### T11. Sensitivities: P(win) at N=3,000, cap policy (a)


**P(approve)** (`pdufa.p_approve`)


| Strategy | value | mean (brief) | brief F-recal | brief F-briefed | EVN F-recal |
|---|---|---|---|---|---|
| S1 | 0.7 | +17% | 0.36% | 0.34% | n/a |
| S1 | 0.75 | +22% | 0.48% | 0.48% | n/a |
| S1 | 0.8 | +27% | 0.62% | 0.65% | n/a |
| S1 | 0.85 | +32% | 0.80% | 0.89% | n/a |
| S1 | 0.9 | +37% | 1.0% | 1.2% | n/a |
| S3 | 0.7 | +62% | 14.7% | 32.2% | n/a |
| S3 | 0.75 | +83% | 21.1% | 43.9% | n/a |
| S3 | 0.8 | +105% | 29.2% | 57.3% | n/a |
| S3 | 0.85 | +129% | 38.9% | 71.0% | n/a |
| S3 | 0.9 | +155% | 49.9% | 83.8% | n/a |
| S5 | 0.7 | +41% | 7.8% | 19.0% | n/a |
| S5 | 0.75 | +53% | 10.7% | 25.6% | n/a |
| S5 | 0.8 | +67% | 14.5% | 33.7% | n/a |
| S5 | 0.85 | +81% | 19.2% | 43.3% | n/a |
| S5 | 0.9 | +97% | 24.9% | 54.3% | n/a |
| S6 | 0.7 | +31% | 5.1% | 13.1% | n/a |
| S6 | 0.75 | +39% | 6.7% | 16.9% | n/a |
| S6 | 0.8 | +48% | 8.6% | 21.6% | n/a |
| S6 | 0.85 | +57% | 10.9% | 27.1% | n/a |
| S6 | 0.9 | +68% | 13.7% | 33.8% | n/a |


**Approval pop scale (1 = briefed; 0.27 = EV 0)** (`pdufa.approve_scale`)


| Strategy | value | mean (brief) | brief F-recal | brief F-briefed | EVN F-recal |
|---|---|---|---|---|---|
| S1 | 0.27 | -0% | 0.001% | <0.001% | n/a |
| S1 | 0.5 | +9% | 0.015% | <0.001% | n/a |
| S1 | 0.75 | +18% | 0.14% | 0.009% | n/a |
| S1 | 1.0 | +27% | 0.62% | 0.65% | n/a |
| S1 | 1.25 | +36% | 1.8% | 4.2% | n/a |
| S1 | 1.5 | +46% | 3.8% | 11.1% | n/a |
| S3 | 0.27 | -0% | 0.041% | 0.004% | n/a |
| S3 | 0.5 | +28% | 1.8% | 5.0% | n/a |
| S3 | 0.75 | +63% | 12.0% | 31.0% | n/a |
| S3 | 1.0 | +105% | 29.2% | 57.3% | n/a |
| S3 | 1.25 | +153% | 46.5% | 73.9% | n/a |
| S3 | 1.5 | +208% | 60.5% | 83.7% | n/a |
| S5 | 0.27 | +4% | 0.12% | 0.083% | n/a |
| S5 | 0.5 | +21% | 1.1% | 2.5% | n/a |
| S5 | 0.75 | +42% | 5.5% | 15.4% | n/a |
| S5 | 1.0 | +67% | 14.5% | 33.7% | n/a |
| S5 | 1.25 | +96% | 25.8% | 49.5% | n/a |
| S5 | 1.5 | +129% | 37.0% | 61.2% | n/a |
| S6 | 0.27 | +6% | 0.34% | 0.60% | n/a |
| S6 | 0.5 | +17% | 1.1% | 2.7% | n/a |
| S6 | 0.75 | +31% | 3.5% | 9.9% | n/a |
| S6 | 1.0 | +48% | 8.6% | 21.6% | n/a |
| S6 | 1.25 | +67% | 15.7% | 33.4% | n/a |
| S6 | 1.5 | +89% | 23.6% | 43.7% | n/a |


**Approval model** (`pdufa.approval_model`)


| Strategy | value | mean (brief) | brief F-recal | brief F-briefed | EVN F-recal |
|---|---|---|---|---|---|
| S1 | two_regime | +27% | 0.62% | 0.65% | n/a |
| S1 | normal | +10% | 0.022% | <0.001% | n/a |
| S3 | two_regime | +105% | 29.2% | 57.3% | n/a |
| S3 | normal | +33% | 2.8% | 7.9% | n/a |
| S5 | two_regime | +67% | 14.5% | 33.7% | n/a |
| S5 | normal | +24% | 1.4% | 3.7% | n/a |


**Theme rho** (`theme.rho`)


| Strategy | value | mean (brief) | brief F-recal | brief F-briefed | EVN F-recal |
|---|---|---|---|---|---|
| S2 | 0.3 | +10% | 1.2% | 3.7% | 0.74% |
| S2 | 0.5 | +10% | 1.4% | 4.3% | 0.90% |
| S2 | 0.7 | +10% | 1.7% | 4.9% | 1.1% |
| S2 | 0.9 | +10% | 1.9% | 5.5% | 1.2% |
| S5 | 0.3 | +67% | 14.4% | 33.6% | 1.8% |
| S5 | 0.5 | +67% | 14.4% | 33.6% | 1.8% |
| S5 | 0.7 | +67% | 14.5% | 33.7% | 1.8% |
| S5 | 0.9 | +67% | 14.5% | 33.7% | 1.8% |
| S6 | 0.3 | +48% | 8.3% | 21.1% | 1.4% |
| S6 | 0.5 | +48% | 8.5% | 21.3% | 1.4% |
| S6 | 0.7 | +48% | 8.6% | 21.6% | 1.4% |
| S6 | 0.9 | +48% | 8.7% | 21.8% | 1.5% |


**Binary correlation rho** (`rho_binary`)


| Strategy | value | mean (brief) | brief F-recal | brief F-briefed | EVN F-recal |
|---|---|---|---|---|---|
| S1 | 0.0 | +27% | 0.62% | 0.65% | 0.11% |
| S1 | 0.3 | +27% | 1.7% | 4.4% | 0.60% |
| S1 | 0.6 | +27% | 2.9% | 9.6% | 1.5% |
| S3 | 0.0 | +105% | 29.2% | 57.3% | 2.8% |
| S3 | 0.3 | +105% | 30.2% | 51.6% | 5.2% |
| S3 | 0.6 | +104% | 30.3% | 47.8% | 7.0% |
| S5 | 0.0 | +67% | 14.5% | 33.7% | 1.8% |
| S5 | 0.3 | +67% | 16.3% | 34.0% | 2.8% |
| S5 | 0.6 | +67% | 17.6% | 33.9% | 3.8% |
| S7 | 0.0 | +51% | 17.9% | 31.9% | 7.3% |
| S7 | 0.3 | +51% | 19.9% | 32.0% | 9.4% |
| S7 | 0.6 | +51% | 21.0% | 30.5% | 10.8% |


**Melt-up size** (`theme.melt_add`)


| Strategy | value | mean (brief) | brief F-recal | brief F-briefed | EVN F-recal |
|---|---|---|---|---|---|
| S2 | 0.3 | +6% | 0.64% | 1.5% | 0.46% |
| S2 | 0.6 | +10% | 1.7% | 4.9% | 1.1% |
| S2 | 1.0 | +16% | 4.5% | 12.0% | 3.0% |
| S2 | 1.5 | +24% | 8.8% | 15.4% | 6.6% |
| S2 | 2.0 | +31% | 11.8% | 15.6% | 9.9% |
| S5 | 0.3 | +65% | 13.9% | 32.4% | 1.7% |
| S5 | 0.6 | +67% | 14.5% | 33.7% | 1.8% |
| S5 | 1.0 | +69% | 15.4% | 35.5% | 1.9% |
| S5 | 1.5 | +72% | 16.8% | 37.6% | 2.3% |
| S5 | 2.0 | +75% | 18.2% | 39.5% | 2.8% |
| S6 | 0.3 | +45% | 7.7% | 19.6% | 1.3% |
| S6 | 0.6 | +48% | 8.6% | 21.6% | 1.4% |
| S6 | 1.0 | +51% | 10.1% | 24.6% | 1.8% |
| S6 | 1.5 | +56% | 12.4% | 28.1% | 2.8% |
| S6 | 2.0 | +60% | 14.6% | 29.8% | 4.5% |


**Melt-up probability** (`theme.p_melt`)


| Strategy | value | mean (brief) | brief F-recal | brief F-briefed | EVN F-recal |
|---|---|---|---|---|---|
| S2 | 0.05 | +4% | 0.77% | 2.0% | 0.63% |
| S2 | 0.1 | +7% | 1.2% | 3.4% | 0.88% |
| S2 | 0.15 | +10% | 1.7% | 4.9% | 1.1% |
| S2 | 0.25 | +16% | 2.5% | 7.7% | 1.3% |
| S5 | 0.05 | +65% | 13.7% | 32.2% | 1.8% |
| S5 | 0.1 | +66% | 14.1% | 32.9% | 1.8% |
| S5 | 0.15 | +67% | 14.5% | 33.7% | 1.8% |
| S5 | 0.25 | +69% | 15.3% | 35.3% | 1.8% |
| S6 | 0.05 | +44% | 7.6% | 19.2% | 1.3% |
| S6 | 0.1 | +46% | 8.1% | 20.4% | 1.4% |
| S6 | 0.15 | +48% | 8.6% | 21.6% | 1.4% |
| S6 | 0.25 | +51% | 9.6% | 23.8% | 1.5% |


**Rotation weekly E|move|** (`rotation.mean_abs_move`)


| Strategy | value | mean (brief) | brief F-recal | brief F-briefed | EVN F-recal |
|---|---|---|---|---|---|
| S8 | 0.1 | +0% | 0.054% | 0.094% | 0.054% |
| S8 | 0.15 | +1% | 0.27% | 0.59% | 0.27% |
| S8 | 0.2 | +2% | 0.80% | 1.9% | 0.80% |
| S8 | 0.25 | +4% | 1.7% | 4.1% | 1.7% |
| S8 | 0.3 | +6% | 3.0% | 6.8% | 3.0% |


**Earnings E|move|** (`earnings.mean_abs_move`)


| Strategy | value | mean (brief) | brief F-recal | brief F-briefed | EVN F-recal |
|---|---|---|---|---|---|
| S4 | 0.15 | +7% | 0.23% | 0.46% | 0.13% |
| S4 | 0.2 | +9% | 0.76% | 1.8% | 0.43% |
| S4 | 0.25 | +12% | 1.7% | 4.3% | 0.95% |
| S4 | 0.3 | +15% | 3.1% | 7.5% | 1.7% |


### T12. Theme crowding: M extra teams hold a 5-name basket in OUR theme (N=3,000, policy a)

| Strategy | F-recal M=0 | F-recal M=10 | F-recal M=30 | F-recal M=100 | F-briefed M=0 | F-briefed M=10 | F-briefed M=30 | F-briefed M=100 |
|---|---|---|---|---|---|---|---|---|
| S2 one-theme basket | 1.7% | 0.25% | 0.10% | 0.035% | 4.9% | 0.74% | 0.30% | 0.11% |
| S5 2 theme+3 seqPDUFA | 14.5% | 14.0% | 14.0% | 13.9% | 33.7% | 32.5% | 32.2% | 32.0% |
| S6 3 theme+2 seqPDUFA | 8.6% | 8.1% | 8.0% | 7.9% | 21.6% | 20.1% | 19.8% | 19.5% |


Crowd teams share our theme regime, theme factor and index draw; only their idiosyncratic name noise differs. M=30 equals the number of lottery teams in F-recal.


### T13. Key question: independent tickets vs one correlated theme vs sequential re-rolling (N=3,000)

| Book | mean | p99 | brief F-recal (a) | brief F-recal (b) | brief F-briefed (a) | EVN F-recal (a) | EVN F-recal (b) | EVN F-briefed (a) |
|---|---|---|---|---|---|---|---|---|
| S1 5 independent PDUFA tickets | +27% | +79% | 0.62% | 1.7% | 0.65% | 0.11% | 0.26% | 0.52% |
| S1 same, biotech rho=0.3 | +27% | +100% | 1.7% | 4.6% | 4.4% | 0.60% | 1.6% | 3.9% |
| S2i 5 momentum names, unrelated themes | +10% | +60% | 0.10% | 0.10% | 0.037% | 0.035% | 0.035% | 0.090% |
| S2 5 names, one theme (rho=0.7) | +10% | +114% | 1.7% | 1.7% | 4.9% | 1.1% | 1.1% | 5.9% |
| S3 sequential PDUFA k=2 | +61% | +170% | 10.1% | 14.1% | 28.0% | 1.00% | 1.1% | 5.0% |
| S3 sequential PDUFA k=3 | +105% | +294% | 29.2% | 33.9% | 57.3% | 2.8% | 2.2% | 9.7% |
| S3 sequential k=3, rho=0.3 | +105% | +392% | 30.2% | 37.4% | 51.6% | 5.2% | 6.6% | 13.3% |
| S7 sequential Phase 3 k=3 | +51% | +351% | 17.9% | 15.8% | 31.9% | 7.3% | 4.7% | 17.8% |
| S4 earnings roulette x4 | +12% | +130% | 1.7% | 1.7% | 4.3% | 0.95% | 0.81% | 3.9% |
| S8 weekly rotation x5 | +1% | +74% | 0.27% | 0.24% | 0.59% | 0.27% | 0.24% | 1.3% |
| S5 2 theme + 3 seq PDUFA | +67% | +225% | 14.5% | 13.0% | 33.7% | 1.8% | 1.2% | 7.1% |
| S6 3 theme + 2 seq PDUFA | +48% | +190% | 8.6% | 6.7% | 21.6% | 1.4% | 0.99% | 6.0% |
