# 03 - Momentum, Speculative Heat and Explosive-Upside Themes (as of 2026-09-29)

Prepared for the Bloomberg Global Trading Challenge 2026 team. Holding window ~Oct 12 - Nov 13, 2026.
Objective: maximise the chance of a +50% month (upside tail), ignore risk.

---------------------------------------------------------------------------------------------------

## 0. READ THIS FIRST - data quality and what is NOT covered

**Tooling limits hit during this run.**
- Every WebFetch domain I tried (CNBC, Yahoo Finance, StockTitan, StockAnalysis, Forbes, TheStreet, Motley Fool, 24/7 Wall St,
  TradingEconomics, MarketBeat, Wikipedia, Al Jazeera, Seoul Economic Daily, TradingKey) returned EGRESS_BLOCKED, and `curl` to
  ~20 finance sites (finviz, tradingview, investing.com, seekingalpha, reuters, bloomberg, barchart, etc.) was refused by the proxy.
  Only WebSearch worked, and WebSearch returns **summaries of pages, not the pages**. Every number below is therefore "as reported in
  a search-result summary of the cited article", not read off a primary screen.
- The session-wide WebSearch budget (200/200) ran out after roughly 28 productive searches of mine. **Not researched at all:**
  Japan, Taiwan, Europe, Australia, Canada, India ADRs, Hong Kong single-stock gainers, quantum, space, drones/defense tech,
  humanoids, rare earths, eVTOL, crypto-equity prices, hyperscaler capex numbers, short-interest/squeeze data, technical breakouts.
  Sections that touch these are labelled **UNVERIFIED** and contain names from prior knowledge only, with NO price/performance claims.
  To finish them, the budget variable `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` needs raising (or someone with a Bloomberg terminal
  fills the gaps - a screen recipe is in section 4).

**Confidence tags used below**
- **[V]** = number appears in a search-result summary of a dated Sept-2026 (or clearly dated) article. Treat as "probably right", not audited.
- **[D]** = derived by me from [V] numbers (arithmetic or inference) - stated as such.
- **[M]** = from my memory / prior knowledge, not confirmed for Sept 2026.
- **[U]** = unverified / not researched.

**One correction to the brief:** the US 10-year yield is at **5.24%, the highest since 2007** (30-yr 5.56%, highest since 2004) [V], not
"highest since Jan 2025". The Fed has already **hiked** (Sept 16), it is not merely a fear. Details in section 1.

---------------------------------------------------------------------------------------------------

## 1. Market regime summary (late September 2026)

### 1.1 Headline dashboard

| Item | Level / move | Tag | Source |
|---|---|---|---|
| Dow (Sep 28 close) | 51,481.51, -347 pts (-0.67%) | V | CNBC / TheStreet / Yahoo via search |
| S&P 500 (Sep 28 close) | 7,683.69, -0.77%; ~flat over September, >+2% for Q3, >+12% YTD | V | same |
| Nasdaq Comp (Sep 28 close) | 26,820.38, -0.92% (Nasdaq had a record-close streak that ended ~Sep 23) | V | Yahoo Markets Sep 23 headline |
| US 10-yr yield | 5.24% (+6bp on the day), highest since 2007; 30-yr 5.56%, highest since 2004 | V | search summary of CNBC/TheStreet Sep 28 |
| Fed | Hiked 25bp to **3.75-4.00% on Sep 16**, unanimous 12-0; 16 of 18 FOMC participants expect another hike (4 see two more); futures price ~4.3% by Dec, ~4.9% by Sep-2027 | V | CNBC Sep 16, KPMG, Schwab |
| Inflation | Headline PCE 3.7% y/y (July); core PCE >3% every month of 2026 | V | KPMG Sep 2026 Fed primer |
| Brent | +2.89% to $107.34 on Sep 28 (Asia) after Trump rejected Iran's "7-day" plan to reopen Hormuz; topped ~$108.5, later trimmed to ~$105 ("Brent falls below $105" Bloomberg wrap headline). Sep 11: Brent $104.61 / WTI $100.05 | V | CNBC, Al Jazeera, Bloomberg headlines |
| Strait of Hormuz | Effectively closed since Mar 2 (IRGC); partial reopening after Apr 8 ceasefire, re-restricted Apr 19; transits down ~95% (5-12 ships/day vs 100+) as of Sep 11; war-risk premiums 7.5-10% of hull value; APPEC (Sept) consensus: standoff lasts to end of Trump's term | V | Al Jazeera, militaryspend.org, discoveryalert |
| Bitcoin | ~$83-84.5K on Sep 28 (opened $84,457, low ~$82,958); "back at $80K" | V | Yahoo Finance / Fortune / CoinDCX |
| Gold / Silver | Gold ~$4,152 (Sep 29), **-6.5% over past month**, roughly flat-to-down YTD; silver ~$64.3 (Sep 25) vs record $121.79 (Jan 29) | V | TradingEconomics, Rio Times, discoveryalert |
| Gold miners GDX | +14.7% YTD, +57.8% 1-yr | V | Yahoo/discoveryalert |
| Uranium spot | $89.30/lb (Sep 28) | V | TradingEconomics |
| KOSPI | 6,870.81 (Sep 29); was +100% YTD in early June, entered bear market (-20% from peak) ~Jul 9, record rebound Jul 31; 2026 Korean earnings growth forecast ~+300% | V | CNBC, SEDaily, Al Jazeera |
| KOSDAQ | 849.80 (Sep 29) | V | SEDaily |
| Hang Seng | 24,642 (Sep 28) - roughly flat YTD [D, from ~+4% early Feb print and current level] | V/D | bbntimes, IG |
| Mag-7 | Laggards: MSFT -20.6%, TSLA -12.7%, AMZN -11.3%, META -3.8% YTD (early Sep); group only ~+4% YTD (mid-Jul) | V | Yahoo "S&P 500's 3 best", 24/7 Wall St |
| Russell 2000 | +20-21% YTD as of mid-July, best year since 2003; unprofitable R2000 names +154% since mid-2025 vs +34% profitable | V | 24/7 Wall St Jul 16 |

### 1.2 What happened in Q3 2026 (from dated headlines)
- **Jul 2:** memory "supply-glut fears" from a research shop: SNDK -11%, STX -7%, MU -4%. Roundhill Memory ETF (DRAM, launched Apr 2, 2026) sold off. [V]
- **Jul 9:** KOSPI fell into a bear market (from a ~+100% YTD peak in early June) as the AI/memory trade cracked. **Jul 10:** SK Hynix listed a record **$26.5B ADR on Nasdaq** (largest ever US share sale by a foreign issuer), +13% on debut. **Jul 29:** Korean market plunged again ("AI-driven boom fades"); **Jul 30:** memory stocks "blast off" double digits; **Jul 31:** record KOSPI rebound. [V]
- **Aug 3, Aug 6, Aug 18:** repeated memory shakeouts - WDC -16%/SNDK -11%/MU -6% on Aug 6; MU -5%/SNDK -6%/WDC -7% on Aug 18 explicitly on **higher rates** ("higher rates test the memory boom"). [V]
- **Aug 19:** Moderna +100%+ intraday (best day ever, high ~$177) on Phase 3 melanoma win (see 2.1). [V]
- **Aug:** oil averaged ~$91 (+$7 vs July). [V]
- **Sep 11:** storage profit-taking (STX -4%, SNDK -3%). **Sep 15:** handset RF chips ripped (SWKS +11%, QRVO +7%) on a pending merger/buyback. **Sep 16:** Fed hiked. **Sep 18:** SNDK +6% "storage bid concentrates in one name". **Sep 21-22:** Nasdaq record; Samsung/SK Hynix +~9% for Sept, KOSPI +2.2% open on Sep 22 (7,161). [V]
- **Sep 22-23:** Nasdaq record streak ends; 10-yr through 5%, highest since 2007. **Sep 28:** Trump rejects Iran plan, oil up, yields up, KOSPI -2.7% (Samsung -5.4%, SK Hynix -5.1% per one source) - i.e., the AI-hardware complex is being **sold on rate spikes**, bought on dips. [V]

### 1.3 Regime in one paragraph
This is a **stagflation-lite, rates-shock, war-premium market carried by an AI-hardware supercycle.** Index-level (S&P +12% YTD) hides
massive dispersion: memory/storage/servers (SNDK +695%, MU ~+280%, DELL +306%, STX +184% YTD) and a single-event biotech (MRNA +550%) are
the leaders; software/hyperscaler mega-caps (MSFT -21%, AMZN -11%, TSLA -13%) and precious metals/crypto/SMR-uranium are lagging or
in drawdown. Small caps had a great first half. Leadership is **extremely concentrated in one factor (AI memory/storage) that is highly
rate-sensitive**, so the September pattern is violent both ways. The two big macro swing factors inside the Oct 12 - Nov 13 window are
(a) **US-Iran / Hormuz** (reopening = oil and tankers crash, yields and beaten-down consumer/travel/crypto/growth rip; non-reopening =
status quo) and (b) **the Fed (Oct 27-28 FOMC) and the 10-yr at 5.2%+**.

### 1.4 Sub-regimes (what's hot / what's crashed)
- **HOT:** memory & NAND & HDD (SNDK, MU, STX, WDC, SK Hynix, Samsung), AI servers (DELL), AI optical/substrate supply chain (AXTI - 52-wk +1,529%), tankers (VLCC rates reportedly >$1M/day late Sept), US LNG exporters, single-event biotech (MRNA), Korean defense/shipbuilding/nuclear-equipment on war.
- **WARM / CHOPPY:** Korean broad market (KOSPI ~+60% YTD [D - end-2025 base ~4,200 from memory]), small-cap AI-infrastructure, handset RF/merger names, EV-charging small caps (CHPT +49% in a month to Sep 16).
- **COLD / DEAD:** Bitcoin (~$83K, roughly -35% from its Oct-2025 ATH ~$126K [M]) and by inference crypto-proxy equities [U]; gold/silver (-6.5% M/M gold; silver ~47% below Jan record); SMR/nuclear (OKLO -39% YTD at ~$44, SMR -24% YTD at ~$10.9 as of early-mid Sept; Centrus LEU ~$162 vs $464 52-wk high); Nike/travel/casino/consumer (per brief; not independently verified); Mag-7 laggards; Hong Kong/China (HSI ~flat YTD).
- **AI capex:** I could not retrieve hyperscaler capex figures (budget exhausted) [U]. Evidence on *supplier* side is overwhelming: Micron FQ3 revenue $41.46B (+346% y/y), non-GAAP EPS $25.11, FQ4 guide $50B +/- $1B, EPS $31 +/- $1, gross margin ~86%; HBM4 volume shipments for Nvidia Vera Rubin began CQ1-26; conventional DRAM contract prices up as much as 95% in Q1-26; WDC/STX 2026 HDD capacity "sold out"; Jensen Huang warned of chip shortages (Sept). On the *buyer* side, MSFT/AMZN down YTD suggests investors are rewarding suppliers over spenders [D - inference]. A "more measured pace of AI development" comment from prominent industry figures triggered a chip/memory selloff on an unspecified recent Monday [V, date unverified]. Tech-sector earnings growth expected ~+57% in 2026 [V, low confidence].
- **Iran/oil:** see 1.1. Winners: tankers, US LNG (Qatar lost ~20% of liquefaction capacity - 12.8 mtpa - for 3-5 years [V]), Korean defense. Losers: airlines/cruise/casinos/consumer discretionary (brief). Energy sector as a whole (XLE) I could not verify for Sept.

---------------------------------------------------------------------------------------------------

## 2. Top momentum stocks

### 2.1 United States (verified where tagged)

| Ticker | Name | Price | Mkt cap | YTD / other moves | Notes | Tag |
|---|---|---|---|---|---|---|
| SNDK | SanDisk | **$1,712.89** (Sep 29) | $277.3B (Sep 22) | +695% YTD; +536% (early Sep); 52-wk +1,706%; mkt cap +1,760% 1-yr | BoA PT $2,500 (from $2,100); daily swings of 6-11% are routine; NAND pricing "firm through 2027" | V |
| MU | Micron | **$1,053.29** | $1.19-1.22T | ~+280% YTD (was +225% in early Sep) | FQ4 print **Sep 30 after close** (pre-window). Consensus rev ~$51.2B, EPS ~$31.59; options imply **+/-10.3% (~$104)**; Street high PT $2,000 (24/7, Sep 23) | V |
| MRNA | Moderna | ~$185-195 [D: +550% on ~$29-30 end-2025 base from memory] | ~$70-75B [D, ~390M shs from memory]; the $25.14B figure quoted is stale (pre-spike) | +550% YTD (Motley Fool headline Sep 28), +490.6% early Sep; 52-wk +696% | INTerpath-001 (intismeran + Keytruda) Phase 3 melanoma win Aug 19; **full data ESMO Presidential Symposium Oct 24 (IN WINDOW)**; Merck-should-buy-Moderna chatter; many analysts say "No" on valuation | V/D |
| DELL | Dell Technologies | n/a | n/a | +306% YTD (early Sep) | AI servers; next earnings ~late Nov (outside window, [M]) | V |
| STX | Seagate | n/a | n/a | +184% YTD (early Sep) | 2026 HDD capacity sold out to AI DCs | V |
| WDC | Western Digital | n/a | n/a | "top performer" list; -16% on Aug 6, -7% Aug 18, +3% Sep 18 | HDD sold-out narrative | V |
| AXTI | AXT Inc | n/a | small-cap | **52-wk +1,529%** (StockTitan list) | InP/GaAs substrates (optical/AI interconnect) [M]; highest-beta liquid-ish name on the list | V (rank) / U (price) |
| CHPT | ChargePoint | n/a | small-cap | +49% over past month (as of Sep 16) | speculative flow, no news | V |
| SWKS / QRVO | Skyworks / Qorvo | n/a | | +11% / +7% on Sep 15 | pending merger, $2B buyback; low upside tail (merger-pinned) | V |
| DHT | DHT Holdings | n/a | | +18% in Sept through Sep 18; -3% Sep 22 on reopening rumours | VLCC pure-play | V |
| FRO | Frontline | NOK 420.8 (Oslo, Investing.com snippet; currency inferred) | | near 52-wk high | Q2 record net profit $659.2M; VLCC ~$152.7K/day quoted for Q2; VLCC spot reportedly >$1M/day late Sept | V |
| CEG/OKLO/SMR | nuclear | OKLO ~$44, SMR ~$10.9 (early-mid Sep) | | OKLO -39%, SMR -24% YTD | counter-trend / oversold, NOT momentum | V |

**Microcap YTD/1M lists (StockTitan, as of Sep 25; identities/liquidity NOT verified; almost certainly untradeable in size on the competition platform):**
- YTD: MGRT +1,590%, ANL +1,025%, XHLD +936% (52-wk: MGRT +2,797%, SNDK +1,706%, AXTI +1,529%, ANL +820%, MRNA +696%).
- September monthly: GLND (Greenland Energy Co.) +299%, INDP +241%, GRML +215%, TJGC +162%, SECZ +155%.
- StockTitan sector view: avg YTD gainers - Comm Services +473%, Tech +262%, Healthcare +261% (microcap-skewed averages).

**S&P 500 top-5 YTD (early Sep, Yahoo/Motley Fool):** SNDK +536%, MRNA +399%, DELL +306%, MU +225%, STX +184%.
1M and 3M returns per name were not retrievable; approximate 1M from Sept: SK Hynix/Samsung ~+9-10% in Sept [V]; DHT +18% (to Sep 18) [V]; CHPT +49% [V].

### 2.2 Korea (the most verified international market)
- KOSPI 6,870.81 (Sep 29); "up 99.65% vs a year ago"; peaked ~+100% YTD in early June; bear-market drawdown in July; rebound. [V]
- **SK Hynix (000660.KS; ADR "SKHY" on Nasdaq since Jul 10):** closed ~KRW 1.862M on Sep 26 (+9.98% in Sept from 1.693M); +300% YTD before the ADR listing; a **$26.5B ADR** raise. -5.1% on Sep 28. Roundhill DRAM ETF top-3 holdings: Samsung 25%, SK Hynix 24%, Micron 24%. [V]
- **Samsung Electronics (005930.KS):** +~9% in Sept before -5.4% on Sep 28; ex-dividend Sep 29. [V]
- Sector movers named: **Hanwha Aerospace, Doosan Enerbility** (defense/nuclear equipment; both -2% to -3% on Sep 29 open), HD Hyundai shipbuilders, LG Energy Solution, Hyundai Motor; Korean robotics (Rainbow Robotics etc.) attracted ~$590M of foreign buying in May [V, low detail]. Defense rose / shipbuilders and autos fell one month into the Iran war (Mar 29 Seoul Economic Daily). [V]
- Foreign investors were net sellers on Sep 28-29 (KRW 442.5B on Sep 29); retail and institutions buying. [V]

### 2.3 Hong Kong / China
HSI 24,642 (Sep 28) ~flat YTD - **not a momentum market**. Named Sep 28 movers: Tencent +1.8%, AIA, KE Holdings +2.6%, InSilico Medicine (HK-listed AI biotech) +0.3%, Meituan. China industrial profits +15.7% y/y Jan-Aug (vs +17.6% Jan-Jul). [V]
Top HK/China single-stock gainers list: **NOT RESEARCHED [U]**. Prior-knowledge watchlist only (no Sept-2026 performance claims): Cambricon (688256.SS), SMIC/Hua Hong, UBTech (9880.HK), Zhipu/MiniMax (HK AI IPOs) [M], Unitree (STAR IPO) [M], Pop Mart, Xiaomi.

### 2.4 Japan, Taiwan, Europe, Australia, Canada, India ADRs
**NOT RESEARCHED [U] - budget exhausted.** Prior-knowledge candidates *given the verified memory supercycle*, to be price-checked before use:
- Japan: **Kioxia (285A.T)** (NAND pure-play, the Japanese SanDisk analogue), Advantest, Tokyo Electron, Lasertec, SoftBank Group; defense: Mitsubishi Heavy, IHI, Kawasaki Heavy.
- Taiwan: **Nanya Technology (2408.TW), Winbond (2344.TW), Macronix (2337.TW), ADATA (3260.TWO), Phison (8299.TWO)** (DRAM/NAND module and controller names, historically the highest-beta memory proxies), plus TSMC (Q3 results ~mid-Oct [M]).
- Europe: Rheinmetall, Hensoldt, Renk, Saab (defense), ASML, BE Semiconductor, Soitec.
- Australia: Lynas, Iluka (rare earths), Pilbara/lithium, Paladin/Boss (uranium), Northern Star/Evolution (gold).
- Canada: Cameco, NexGen, Denison (uranium), Fortuna/Endeavour/Pan American (silver/gold), Celestica (AI hardware).
- India ADRs: unclear relevance for +50% tail; skip.

---------------------------------------------------------------------------------------------------

## 3. Speculative theme baskets - hot or dead? (Sept 2026)

Legend: Status = HOT / WARM / COLD / UNKNOWN. Names in "verified" column come from this session; names marked [M] are from prior knowledge and are candidates only.

| Theme | Status | Evidence (this session) | 3-5 most volatile liquid names | 1-2 highest-beta small caps |
|---|---|---|---|---|
| **Memory: DRAM/HBM/NAND/HDD** | **HOT (but whipsawing)** | SNDK +695%, MU ~+280%, STX +184%, SK Hynix ADR listing $26.5B, DRAM ETF launched Apr 2; contract DRAM +95% Q1; HBM4 shortage; repeated 5-16% single-day drops on rates/supply-glut headlines (Jul 2, Jul 29, Aug 6, Aug 18) | SNDK, MU, WDC, STX, SK Hynix/SKHY (Samsung) | AXTI (supply chain, +1,529% 52-wk), [M] Kioxia, Nanya, Winbond, Netlist, Everspin |
| **Korean chips / KOSPI** | HOT but rate-sensitive | KOSPI ~7,000, earnings +300% forecast, -2.7% on Sep 28 | Samsung, SK Hynix, Hanmi Semiconductor [M], SK Square [M] | KOSDAQ chip-equipment small caps [U] |
| **Shipping / tankers** | **HOT (binary on Hormuz)** | VLCC >$1M/day late Sept (reported), Frontline record profit, DHT +18% in Sept, war-risk premia 7.5-10% of hull; DHT -3% on reopening rumours | FRO, DHT, INSW [M], NAT [M], TNK [M] | Okeanis ECO [M], Ardmore ADMT [M] |
| **LNG** | WARM-HOT | Qatar lost ~20% liquefaction for 3-5 yrs; CQP/Cheniere records in March; Rio Grande LNG ships 2027 | Cheniere LNG, Venture Global VG, Sempra | NextDecade NEXT (5+ yr build; very high beta) [M] |
| **Oil services / E&Ps** | UNKNOWN (Brent $105 supports) | not researched | [U] XOM/CVX = ~42.5% of XLE | [U] |
| **Defense / drones** | UNKNOWN for US; Korea defense mixed | Korean defense rallied on war outbreak; Hanwha Aero -2.2% Sep 29 | [M] Kratos, AeroVironment, Palantir, Rheinmetall | [M] Red Cat RCAT, Unusual Machines UMAC, Ondas ONDS |
| **Gold / silver miners** | **COLD / correcting** | Gold -6.5% M/M to ~$4,152; silver ~$64 vs $121.8 record; GDX +14.7% YTD only | [V-ish] GDX names: Newmont, Agnico, Wheaton, Pan American, First Majestic, Hecla | Endeavour Silver [V mentioned earlier in year], Coeur [M] |
| **Uranium / nuclear / SMR** | **COLD (oversold)** | OKLO -39%, SMR -24% YTD; LEU $162 vs $464 high; U3O8 $89.30; CCJ mkt cap ~C$54B, "support $73, resistance $135" (analyst); NRC approved Oklo Aurora PDC (positive); brief Sep 8 bounce (SMR +13%, OKLO +7%) then rolled over again Sep 28 (SMR -6%) | OKLO, SMR, NNE [M], LEU, CCJ | Lightbridge LTBR, Energy Fuels UUUU (>$10 = valid momentum per analyst) |
| **Bitcoin / crypto equities / treasuries / stablecoins** | **COLD** (BTC ~$83K, -35% from ATH [M]) | Crypto "dulled" by strong dollar, high yields, oil (Yahoo, Sep 28). Equity prices [U] | [M] MSTR, COIN, CRCL, GLXY, HOOD, MARA/RIOT | [M] BMNR, SBET, miners turned AI-hosts |
| **AI neoclouds / DC power** | UNKNOWN (Russell "AI infrastructure" leadership per July; rate-sensitive) | not researched | [M] CRWV, NBIS, IREN, APLD, CIFR, WULF, BE, VRT | [M] Soluna, small miners |
| **Quantum** | UNKNOWN | not researched | [M] IONQ, RGTI, QBTS, QUBT | [M] LAES, others |
| **Space** | UNKNOWN | not researched | [M] RKLB, ASTS, PL, LUNR, FLY | [M] SPCE, satellite small caps |
| **Humanoid robotics** | UNKNOWN (Korean robotics did get flows in May) | thin | [M] TSLA (-12.7% YTD), UBTech, Rainbow Robotics, Doosan Robotics | [M] SERV, Richtech |
| **Rare earths / critical minerals** | UNKNOWN | not researched | [M] MP, USAR, CRML, Lynas, Energy Fuels | [M] UAMY, NB |
| **eVTOL** | UNKNOWN | not researched | [M] JOBY, ACHR, EH | [M] EVEX, small caps |
| **Biotech rebound** | WARM, event-driven | MRNA is the standout; "InSilico Medicine" listed in HK | MRNA, [M] BNTX, NVAX | [U] |
| **Chinese tech / HK** | COLD-FLAT | HSI ~24.6K, ~flat YTD | Tencent, Meituan, Xiaomi [M], Cambricon [M] | UBTech [M] |
| **EV charging / small-cap "no-news" flow** | WARM | CHPT +49% 1M; BLNK -7%, EVGO -13% 1M | CHPT, BLNK, EVGO | - |
| **Reopening-trade (inverse of Hormuz)** | Beaten down, latent | Brief says Nike, travel, casino at 52-wk lows [not verified by me] | [M] CCL, RCL, NCLH, LVS, WYNN, MGM, UAL, DAL, NKE | [M] Melco, Sands China (Macau) |

---------------------------------------------------------------------------------------------------

## 4. Technical breakouts and squeeze candidates

**Not researched (no verified short-interest or breakout data). I do not want to fabricate. What I do have:**
- Small-cap "unprofitable" cohort +154% since mid-2025 (24/7 Wall St, July) - i.e., the whole junk-rally regime is one where shorts got burned; squeezes are the base case in hot themes [V, secondary].
- No-news synchronized small-cap flow on Sep 16 (CHPT +4-6%, BLNK +6%) = speculative, retail-driven flow [V].
- Breakout levels quoted by analysts (not squeezes): CCJ resistance $135; UUUU needs >$10 hold, targets $23 then $50; LEU 52-wk high $464.25 (now ~$162). [V, low reliability]

**Screen recipe for whoever has a terminal (Bloomberg EQS / finviz / tradingview), run on Oct 9-12:**
1. Short interest >25% of float, days-to-cover >5, avg $ volume >$20M, price >$3, market cap $500M-$50B.
2. 1M performance >+30%, price within 5% of 52-wk high (breakout), rel. volume >1.5.
3. Exclude names with ATM/convert issuance in last 30 days (dilution kills squeezes).
4. Cross-check against theme list in section 3. Highest-probability squeezes historically come from hot-theme, high-SI names with a dated catalyst in the window.

---------------------------------------------------------------------------------------------------

## 5. Ranked list: 15 single stocks with the highest chance of a +50% month starting Oct 12

**Honest framing.** A +50% month is a low-probability event for any single stock. My subjective probabilities (NOT model output) range from ~4% to ~15% each.
Entry prices at Oct 12 will differ from Sept 29 prices; +50% from Oct 12 means very different targets. Positions 1-9 are backed by data I verified in this session; positions 10-15 are **thematic placeholders whose Sept-2026 price/status I could NOT verify** - do not size them until checked.
Also note **heavy factor correlation**: ranks 1-7 are all "AI memory/storage" (rate-sensitive). If the 10-yr keeps going up, they all fall together.

| Rank | Stock | Est. P(+50% in window) | Data quality |
|---|---|---|---|
| 1 | SanDisk (SNDK) | ~12-15% | verified |
| 2 | AXT Inc (AXTI) | ~10-12% | rank verified, price not |
| 3 | Western Digital (WDC) | ~9% | partly verified |
| 4 | Moderna (MRNA) | ~9% (fat right tail = buyout) | verified |
| 5 | Seagate (STX) | ~8% | partly verified |
| 6 | SK Hynix ADR (SKHY) / 000660.KS | ~6% | verified |
| 7 | Micron (MU) | ~6% | verified |
| 8 | DHT Holdings (DHT) | ~7% (binary) | verified |
| 9 | Frontline (FRO) | ~6% (binary) | verified |
| 10 | Kioxia (285A.T) | ~8% | UNVERIFIED |
| 11 | Nanya Technology (2408.TW) | ~8% | UNVERIFIED |
| 12 | Beaten-down reopening long (e.g., Carnival CCL / Las Vegas Sands LVS) | ~4-5% (conditional on Hormuz reopening ~25-30%) | UNVERIFIED |
| 13 | NextDecade (NEXT) | ~5% | UNVERIFIED |
| 14 | Quantum high-beta (Rigetti RGTI or D-Wave QBTS) | ~7% | UNVERIFIED |
| 15 | Space/AI-infrastructure high-beta (AST SpaceMobile ASTS or IREN) | ~7% | UNVERIFIED |

### 1) SanDisk (SNDK) - $1,712.89, ~$277B mkt cap, +695% YTD [V]
The purest, most liquid expression of the NAND/AI-storage shortage. It has done +1,700% in a year, realised vol is enormous (6-11% daily moves are routine), and Bank of America's PT is $2,500 (i.e., +46% from here) with the thesis that NAND supply/demand stays tight through 2027. **Catalysts in window:** SanDisk's fiscal Q1 print (last year's pattern was early Nov - **date to be confirmed** [M]); read-across from Micron's Sep 30 print (pre-window: it will set the entry level, and the +/-10% implied move means the Oct 12 entry price could already be materially different); SK Hynix and Samsung Q3 results in late October; contract price announcements (TrendForce) for Q4 NAND; hyperscaler capex updates in late Oct. **Risk:** each rate spike has cost this name 6-11% in a day; a BoA-style "$2,500" is the sell-side ceiling not a base case. Highest probability *because* its beta to the theme is the largest among liquid names.

### 2) AXT Inc (AXTI) - 52-week gain +1,529% [V rank; price/mcap not retrieved]
Small-cap supplier of indium-phosphide/GaAs substrates used in optical transceivers/AI networking [M]. Appears among the top three 52-week gainers with SNDK on the StockTitan list. In an AI-hardware supercycle, small-cap suppliers with tiny floats and China-export-licence sensitivity produce the fattest tails, both ways. **Catalysts:** Q3 earnings (typically late Oct/early Nov [M]), Chinese export-licence news, optical-networking read-across (Lumentum/Coherent/Broadcom) from earnings in window. Must check price, float, and short interest before entry; this is the one small-cap I would prioritise verifying.

### 3) Western Digital (WDC)
Listed in the 2026 leaders; HDD 2026 capacity reportedly "sold out" to AI data centres. Traded -16% on Aug 6 and -7% Aug 18 (rates) and +3% Sep 18, so it moves like a levered version of the theme. **Catalysts:** WDC fiscal Q1 earnings (late Oct/early Nov last year [M]), Seagate's print, any long-term-agreement announcements. **Risk:** HDD is the "cheapest" leg and gets sold first in supply-glut headlines.

### 4) Moderna (MRNA) - +550% YTD [V]
Not a theme but a **dated binary in the window**: full INTerpath-001 Phase 3 data at ESMO's Presidential Symposium on **Oct 24** (first-ever positive Phase 3 for an mRNA cancer therapy, with Merck's Keytruda), plus persistent Merck-should-buy-Moderna speculation. Already up 6-7x, so a "sell the news" outcome is the base case; the +50% path is a takeover bid or blowout secondary readouts (OS trend, HR magnitude, other tumor types, commercial-launch pricing). Probability is the highest of the non-momentum names because of the discrete event and a cap near $70-75B [D] that is small for a Merck/large-pharma bidder.

### 5) Seagate (STX) - +184% YTD (early Sep) [V]
Second HDD leg; fell 7% on Jul 2 supply-glut fears and 4% on Sep 11; sold-out capacity narrative. **Catalysts:** fiscal Q1 earnings typically late Oct [M], pricing commentary. Lower beta than SNDK/WDC.

### 6) SK Hynix ADR (SKHY, Nasdaq) / 000660.KS - KRW ~1.86M (Sep 26) [V]
World's #2 DRAM and #1 HBM supplier [M]; +300% YTD pre-ADR, ADR raised $26.5B. Q3 earnings ~late Oct [M] should show hyper-growth (Micron guided ~86% gross margin; SK Hynix results are [U]). Foreign selling and the rates trade cut it 5% on Sep 28; if the ADR line trades at a discount/premium to the local line, there can be a flow catalyst. A +50% move for a company this large is unlikely in a month; included because the memory upcycle is the dominant profit story and the stock had a +10% September.

### 7) Micron (MU) - $1,053, $1.2T [V]
Enters Sep 30 earnings with FQ4 guide $50B/EPS $31/GM 86%; consensus slightly above ($51.2B / $31.59), options +/-10.3%. The +50% path from an Oct 12 entry requires ~$1,580 (Street high is $2,000). A search snippet claimed an after-hours pop of +14.6% to ~$1,199.5 following the print - **I cannot verify this (print has not happened as of Sep 29) and it may be a summariser error**; treat as unverified. FQ1-27 guidance and HBM4 share commentary are the swing factors, but those hit before the window opens. In-window drivers: Samsung/SK Hynix results, Nvidia-ecosystem news, DRAM contract prices, rates.

### 8) DHT Holdings (DHT) and 9) Frontline (FRO) - tanker binary
VLCC spot rates reportedly exceeded **$1M/day in late September** with Hormuz traffic down ~95%; Frontline posted a record Q2 (net profit $659.2M, $2.96/sh) and quotes exceptional Q3; DHT revenue +135% y/y. I could not retrieve tanker share prices to judge how much of the spot-rate spike is priced in; Q3 results in November (DHT/FRO typically mid/late Nov - largely after Nov 13, [M]) will not be in window, so the driver is spot-rate prints and Hormuz headlines. **The trade is binary:** a real reopening (Iran's "7-day plan" was rejected Sep 28, talks "expected to resume") can knock 15-30% off; continued closure into winter with $1M/day spot (Q4 earnings would be astronomical) can push +50% on a re-rating of forward earnings. Dividend yields quoted at 14-15% (DHT 14.75%, FRO 14.2%) - a sign the market is discounting normalisation. DHT is the cleaner VLCC pure-play; FRO is the higher-liquidity, Oslo/NYSE dual-listed alternative.

### 10) Kioxia (285A.T) - UNVERIFIED
NAND pure-play; if SanDisk is +695% YTD on NAND pricing, Kioxia is the Tokyo-listed twin (Kioxia and SanDisk share fabs [M]). Kioxia's earnings typically around Nov 12-14 [M] - possibly at the very end of the window. Verify price, YTD, float before use.

### 11) Nanya Technology (2408.TW) - UNVERIFIED
Taiwan DRAM pure-play (commodity DRAM/DDR4/DDR5); historically the highest-beta DRAM contract-price proxy. Taiwan price limits (10%/day) make gap-ups easy to hold. Verify.

### 12) Reopening long (CCL / LVS / airlines) - UNVERIFIED
Insurance against the mirror-image scenario. If US-Iran reach a deal (I estimate perhaps 25-30% within the window - a judgment, not sourced), oil drops toward $80, yields fall, and Nike/travel/casino names at 52-week lows (per brief) squeeze. +50% in a month for a cruise line is a stretch but the most plausible of the reopening group; needs a verified price.

### 13) NextDecade (NEXT) - UNVERIFIED
LNG developer with Rio Grande LNG shipping in 2027; benefits from Qatar's 12.8 mtpa outage lasting 3-5 years. High beta to LNG price/FID headlines.

### 14) Quantum (RGTI / QBTS) and 15) Space/AI-infrastructure (ASTS / IREN) - UNVERIFIED
These were 2025's speculative leaders (and remain the classic +50% month candidates) but I did not obtain a single Sept-2026 data point on them. The regime evidence (5.2% 10-yr, Fed hiking, "unprofitable small caps +154% since mid-2025") says they are either extended or repriced; verify before using.

---------------------------------------------------------------------------------------------------

## 6. Catalyst calendar inside the Oct 12 - Nov 13 window

| Date | Event | Tag |
|---|---|---|
| Sep 30 (pre-window, sets entry level) | Micron FQ4 results; options +/-10.3% | V |
| ~Oct 14-15 | US Sept CPI; ASML/TSMC Q3 results (typical mid-Oct timing) | M |
| Oct 16 | Deadline for initial positions (competition) | brief |
| ~Oct 22-23 | SK Hynix Q3 results (typical late-Oct) | M |
| **Oct 24** | **Moderna INTerpath-001 full data, ESMO Presidential Symposium** | **V** |
| **Oct 27-28** | **FOMC** - 16/18 participants pencilled another hike; futures ~4.3% by Dec (per Fed 2026 calendar from memory) | V/M |
| Late Oct | Big Tech Q3 earnings + capex guidance; Samsung final Q3; Seagate/WDC fiscal Q1 (last year's pattern late Oct) | M |
| ~Nov 5-6 | SanDisk fiscal Q1 (last year's pattern early Nov); US October jobs report (Nov 6) | M |
| **Nov 3** | **US midterm elections** | known |
| ~Nov 12-14 | Kioxia results (pattern); tanker Q3 results mostly mid/late Nov | M |
| Continuous | US-Iran / Hormuz talks (7-day plan rejected Sep 28; talks expected to resume); Brent $105-108 | V |
| Outside window | Nvidia (~Nov 18-19), Dell (~late Nov) | M |

---------------------------------------------------------------------------------------------------

## 7. Implications for portfolio construction (short)

1. **Concentration risk is the trade.** Max 20% per stock, min 5 stocks = at least 5 x 20%. The verified-hot complex (memory/storage) is one factor. If you want the +50% tail but want to avoid a single rates-driven sell-off killing the book, pair 2-3 memory names (SNDK, AXTI, WDC/STX) with 1-2 **orthogonal event/binary** names (MRNA on Oct 24; a tanker on Hormuz; or a reopening long) so the book pays in more than one macro state.
2. **Rates are the tell:** all four memory drawdowns in Jul-Sep coincided with yield spikes or supply-glut headlines. The 10-yr is at 5.24% and the Fed hiked; the Oct 27-28 FOMC is the biggest single macro risk for the factor.
3. **Entry timing:** the Micron print on Sep 30 will reset the entire memory complex two weeks before entry; re-rank 1-7 on Oct 9-12 with fresh prices.
4. **Do not use** microcaps from the StockTitan lists (GLND, INDP, GRML, MGRT, ANL etc.) without confirming they are tradable on the challenge platform, have >$1M daily volume, and are in the Bloomberg-eligible universe.

---------------------------------------------------------------------------------------------------

## 8. What still needs to be done (if search budget is restored)

1. Prices, market caps, 1M/3M/YTD for WDC, STX, AXTI, DELL, SKHY, Samsung, tankers (DHT/FRO/NAT/TNK/INSW/ECO), LNG (VG/NEXT/LNG).
2. Full sweep of: quantum, space, drones/defense tech, humanoids, rare earths, eVTOL, neoclouds, bitcoin treasuries/crypto exchanges/stablecoin names - all currently [U].
3. Japan/Taiwan/Europe/Australia/Canada/HK top-gainer lists (Kioxia, Nanya/Winbond, Rheinmetall, Lynas, Cambricon, etc.).
4. Short-interest/squeeze screen (section 4) and technical breakouts.
5. Verify the "Micron +14.6% after-hours to $1,199.52" claim after the Sep 30 close; re-price the whole memory group.
6. Confirm earnings dates for SNDK, WDC, STX, SK Hynix, Kioxia, AXTI (all inferred from last year's pattern).
7. Verify the brief's claims on Japan 10-yr (highest since 1996), Bund yields (2011 highs), Nike/travel/casino 52-wk lows - I did not test these.

---------------------------------------------------------------------------------------------------

## 9. Sources (search-result URLs; content seen only as search-engine summaries)

**Market wrap / macro**
- CNBC, Sep 28: https://www.cnbc.com/2026/09/28/stock-market-today-live-updates.html
- CNBC, Sep 27 (Dow slides, yields): https://www.cnbc.com/2026/09/27/stock-market-today-live-updates.html
- TheStreet Sep 28: https://www.thestreet.com/stock-market-today/stock-market-today-dow-jones-sp-500-nasdaq-updates-sept-28-2026
- TheStreet Sep 29: https://www.thestreet.com/stock-market-today/stock-market-today-dow-jones-sp-500-nasdaq-updates-sept-29-2026
- Yahoo Finance Sep 28 live blog: https://finance.yahoo.com/markets/live/stock-market-today-monday-september-28-dow-sp-500-nasdaq-080420627.html
- Bloomberg Sep 28 markets wrap: https://www.bloomberg.com/news/articles/2026-09-28/stock-market-today-dow-s-p-live-updates
- Yahoo Markets Sep 23 (Nasdaq record streak ends, yields highest since 2007): https://finance.yahoo.com/markets/stocks/articles/stock-market-today-futures-little-104021073.html
- TradingKey weekly: https://www.tradingkey.com/analysis/stocks/us-stocks/262188606-nasdaq-mu-oil-usd-btc-weekly-tradingkey
- CNBC Fed decision Sep 16: https://www.cnbc.com/2026/09/16/fed-rate-decision-september-2026.html
- KPMG Fed primer: https://kpmg.com/us/en/articles/2026/september-2026-fed-primer.html
- Schwab (12-0 hike): https://www.schwab.com/learn/story/fomc-meeting
- Yahoo Finance rate-hike odds: https://finance.yahoo.com/economy/policy/articles/fomc-september-2026-odds-rate-201618784.html

**Oil / Iran / energy**
- CNBC oil Sep 28: https://www.cnbc.com/2026/09/28/oil-price-today-wti-brent-trump-iran.html
- Al Jazeera Sep 28: https://www.aljazeera.com/economy/2026/9/28/oil-prices-surge-after-trump-rejects-iran-s-plan-to-reopen-strait-of-hormuz
- Bloomberg oil Sep 29: https://www.bloomberg.com/news/articles/2026-09-28/latest-oil-market-news-and-analysis-for-sept-29
- Wikipedia 2026 Strait of Hormuz crisis: https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis
- militaryspend.org tracker: https://militaryspend.org/strait-of-hormuz
- discoveryalert Sept oil: https://discoveryalert.com/analysis/us-iran-war-oil-prices-september-2026/
- Motley Fool DHT Sep 22: https://www.fool.com/investing/2026/09/22/why-dht-holdings-stock-dropped-today/
- MarketBeat FRO/DHT: https://www.marketbeat.com/articles/strait-of-hormuz-tensions-spike-tanker-trade-these-2-stocks-are-set-to-benefit/
- 24/7 Wall St tankers (Mar 9): https://247wallst.com/investing/2026/03/09/tankers-surge-on-rising-oil-prices-fro-nat-dht-add-to-massive-2026-returns/
- US News LNG/Qatar (Mar 19): https://money.usnews.com/investing/news/articles/2026-03-19/cheniere-venture-global-shares-surge-amid-iran-attacks-on-qatar-lng-infrastructure

**Memory / AI hardware**
- Yahoo "S&P 500's 3 best performers": https://finance.yahoo.com/news/p-500s-3-best-performing-122400879.html
- 24/7 Wall St memory moves: https://247wallst.com/investing/2026/07/02/sandisk-sinks-11-seagate-falls-7-micron-slides-4-on-memory-supply-glut-fears/ ; https://247wallst.com/investing/2026/08/06/western-digital-sinks-16-sandisk-falls-11-micron-drops-6-as-memory-selloff-hits-storage-stocks/ ; https://247wallst.com/investing/2026/08/18/micron-technology-falls-5-sandisk-sinks-6-western-digital-drops-7-as-higher-rates-test-the-memory-boom/ ; https://247wallst.com/investing/2026/09/18/sandisk-jumps-6-as-storage-bid-concentrates-in-one-name-western-digital-rises-3-micron-ticks-up/ ; https://247wallst.com/investing/2026/09/11/storage-stocks-slide-as-profit-taking-follows-big-run-seagate-falls-4-sandisk-drops-3-micron-holds-flat/
- 24/7 Wall St Micron $2,000 target: https://247wallst.com/investing/2026/09/23/micron-wall-street-target-hits-2000-as-traders-pile-in-before-earnings/
- Motley Fool Micron end-2026: https://www.fool.com/investing/2026/09/28/prediction-this-will-be-micron-technology-s-stock-price-by-the-end-of-2026/
- TipRanks options move: https://www.tipranks.com/news/why-micron-stock-options-signal-a-10-3-move-after-q4-results
- Trefis Micron: https://www.trefis.com/stock/mu/articles/616786/your-micron-shares-could-swing-hundreds-of-dollars-and-that-is-the-calm-case/2026-09-28
- Micron 8-K FQ3: https://www.sec.gov/Archives/edgar/data/0000723125/000072312526000013/a2026q3ex991-pressrelease.htm
- StockAnalysis SNDK: https://stockanalysis.com/stocks/sndk/
- Roundhill DRAM ETF: https://www.roundhillinvestments.com/etf/dram/
- StockTitan rankings: https://www.stocktitan.net/rankings/stock-gains-ytd/2026 ; https://www.stocktitan.net/rankings/stock-gains-monthly/2026/september ; https://www.stocktitan.net/rankings/stock-gains
- 24/7 Wall St handset chips Sep 15; EV charging Sep 16 (URLs from search): https://247wallst.com/investing/2026/09/15/smartphone-chip-stocks-rally-while-large-cap-technology-slips-skyworks-jumps-11-qorvo-rises-7-qualcomm-climbs-4/ ; https://247wallst.com/investing/2026/09/16/ev-charging-stocks-climb-as-small-caps-catch-a-bid-blink-charging-jumps-6-chargepoint-rises-4-evgo-ticks-up/

**Moderna**
- Motley Fool Sep 28: https://www.fool.com/investing/2026/09/28/up-over-550-in-2026-is-it-too-late-to-buy-moderna-stock/
- 24/7 Wall St Sep 22: https://247wallst.com/investing/2026/09/22/moderna-adds-another-5-and-is-up-500-in-2026-can-mrna-stock-continue-the-melt-up/
- Forbes Aug 19: https://www.forbes.com/sites/tylerroush/2026/08/19/moderna-shares-skyrocket-85-toward-best-day-ever-on-success-of-cancer-drug-trial/

**Korea / Asia**
- CNBC KOSPI +100%: https://www.cnbc.com/2026/06/03/the-kospi-is-up-100percent-in-2026-goldman-sachs-still-see-more-upside.html
- CNBC KOSPI bear: https://www.cnbc.com/2026/07/09/kospi-bear-territory-ai-samsung-skhynix-chipmakers.html
- CNBC KOSPI rebound: https://www.cnbc.com/2026/07/31/south-korea-kospi-samsung-sk-hynix-meltdown-record-rebound.html
- Al Jazeera Korea plunge: https://www.aljazeera.com/economy/2026/7/29/south-koreas-stock-market-plunges-as-ai-driven-boom-fades
- CNBC SK Hynix ADR: https://www.cnbc.com/2026/06/24/sk-hynix-nasdaq-adr-listing-south-korea.html
- Bloomberg SK Hynix ADR pricing: https://www.bloomberg.com/news/articles/2026-07-10/sk-hynix-indicated-to-climb-17-after-26-5-billion-adr-offering
- BigGo Samsung/SK Hynix September: https://finance.biggo.com/news/8f804215-7858-4005-85d4-a73b055ead5d
- Seoul Economic Daily Sep 29: https://en.sedaily.com/finance/2026/09/29/kospi-closes-027-percent-lower-at-687081 ; https://en.sedaily.com/finance/2026/09/29/kosdaq-closes-up-038-percent-at-84980
- Sunday Guardian Korea Sep 28/29: https://sundayguardianlive.com/business/korea-stock-market-krx-today-september-29-why-is-the-korean-stock-market-down-today-kospi-falls-110-kosdaq-drops-samsung-electronics-rebounds-sk-hynix-slides-check-top-gainers-losers-294978/
- Seoul Economic Daily defense vs shipbuilding: https://en.sedaily.com/news/2026/03/29/defense-stocks-rise-shipbuilding-and-auto-stocks-fall-as
- bbntimes Hang Seng Sep 28: https://www.bbntimes.com/global-economy/hong-kong-stock-exchange-hang-seng-rises-0-54-to-24-642-snapping-a-three-day-losing-streak

**Crypto / metals / nuclear**
- Yahoo Finance Bitcoin Sep 28: https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-monday-september-28-2026-bitcoin-loses-ground-after-trump-rejects-irans-7-day-plan-113444329.html
- Fortune BTC Sep 28: https://fortune.com/article/price-of-bitcoin-09-28-2026/
- TradingEconomics gold: https://tradingeconomics.com/commodity/gold ; silver record via Yahoo/CNBC (Jan 2026): https://www.cnbc.com/2026/01/14/silver-mining-stocks-jump-as-metal-holds-above-90-milestone.html
- Rio Times gold/silver Sep 28: https://www.riotimesonline.com/gold-silver-precious-metals-monday-september-28-2026/
- discoveryalert GDX: https://discoveryalert.com/analysis/gold-miners-outperform-bullion-september-2026/
- TradingEconomics uranium: https://tradingeconomics.com/commodity/uranium
- discoveryalert uranium levels: https://discoveryalert.com/analysis/uranium-mining-stocks-price-levels-september-2026/
- 24/7 Wall St nuclear Sep 8: https://247wallst.com/investing/2026/09/08/nuscale-power-spikes-13-oklo-climbs-7-is-the-nuclear-selloff-finally-exhausted/
- Defense World nuclear lists Sep 25/26: https://www.defenseworld.net/2026/09/27/nuclear-stocks-to-follow-now-september-26th.html

**Small caps**
- 24/7 Wall St Russell 2000: https://247wallst.com/investing/2026/07/16/the-russell-2000-is-having-its-best-year-in-23-years-heres-why-small-caps-are-winning-again/
