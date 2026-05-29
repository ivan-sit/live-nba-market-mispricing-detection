# Final Presentation — Outline
10 min total · navy/ocean palette · Georgia titles, Calibri body

> **Structural choice:** the midterm→final transition is **2 slides / 60 sec total**. The remaining ~9 min is *all* NBA mispricing. Everything in the transition serves one purpose: "we chose NBA because it's the right laboratory — here's why, fast."

---

## SLIDE 1 — Title (5 sec)
**Live NBA Market Mispricing Detection**
A behavioral asset-pricing test of crowd miscalibration.
*Ming Yin Ivan Sit · Vishnu Manathattai · STATS 211 (Prof. Dai) · Spring 2026*

---

## SLIDE 2 — From Halawi to live markets *(30 sec)*

**The midterm thesis (recap, one line):**
Halawi et al. (NeurIPS 2024) showed LMs **approach** the crowd on forecasting (Brier 0.179 vs 0.149) — and the *buried* result is that a **4:1 LM+crowd aggregate beats either alone.**

**The deeper observation, in one bullet:**
- **Both are miscalibrated, in opposite directions.** LMs hedge (RLHF), crowds overreact (Moskowitz 2021, Ötting 2022).

**So the question became:**
> *Where can we cleanly test the claim that a calibrated model beats the crowd — with fast resolution, real money, and a documented bias?*

**Speaker beat:** "Forecasting questions take weeks to resolve. We needed a market that resolves in hours."

---

## SLIDE 3 — Why NBA (and not crypto) *(30 sec)*

We considered **crypto 5-min lead-lag quoting** vs **NBA in-play markets**. NBA wins on every axis that matters:

|  | NBA | Crypto 5-min |
|---|---|---|
| **Ground truth** | every game state has an outcome → **calibration problem** | proxy labels → stat-arb on noisy data |
| **Literature** | **Moskowitz 2021 (J. Finance)** documents the bias *positively* | Sifat et al. 2019 = *negative* result ("barely exploitable") |
| **Legal venue (CA)** | **Kalshi NBA event contracts** (CFTC-regulated, legal in CA) | OK but solved |
| **Sample** | ~1,230 games × hundreds of ticks/game | thinner per-event |

**Bottom line:** *trade with the literature, not against it, on the venue we can actually use.*

> **End of transition. 60 sec spent. The rest is NBA.**

---

## SLIDE 4 — Research question (30 sec)
> *Can a calibrated in-game NBA win-probability model systematically identify live-market mispricings driven by crowd overreaction — specifically in trailing-team scoring events?*

Two specific, **pre-registered** tests:
- **H1**: trailing team (10–15 pt deficit) makes a FG → market over-shifts vs structural model.
- **H4**: trailing team (≥10 pt deficit) makes a 3PT → larger shift.

---

## SLIDE 5 — Data *(45 sec)*
- **Play-by-play** (`nba_api`, free): **2,460 games** across 2023-24 + 2024-25 regular seasons.
- **Live odds**: the-odds-api free key — **9 sportsbooks**, in-play game-winner moneyline, captured during 2026 playoffs.
- **Kalshi 1H-winner** event contracts: free peer-driven market (when liquid).
- **Per-minute snapshots** of 1H game state — 4 features, 59k rows.

Splits: train on 2023-24, **held-out test on 2024-25** (touched once).

---

## SLIDE 6 — The model (V2) *(45 sec)*
- **XGBoost** on 4 features: `minute_idx, score_diff_home, recent_run_diff, period`.
- **Isotonic calibration** on validation fold.
- Engineered features (leverage, possession proxies) **did not** improve Brier by 0.005 → kept simple.

*Why simple is right for a 3-page paper: every choice defensible, no overfitting story.*

---

## SLIDE 7 — Calibration result *(60 sec)* — **headline figure #1**
**Out-of-sample (2024-25, 1,230 games):**
- **Brier = 0.149**
- **ECE = 0.008**
- Reliability diagram tracks the diagonal across deciles.

> *The model is calibrated. The probabilities can be trusted.*

---

## SLIDE 8 — Mispricing thesis (V5) *(75 sec)* — **headline figure #2**
On the **held-out 2024-25** season:

| Pre-registered test | n events / games | Structural shift for scorer | p-value |
|---|---|---|---|
| **H1** trailing 10–15, made FG | 4,596 / 947 | **+0.0075** [+0.005, +0.010] | < 0.0001 |
| **H4** trailing ≥10, made 3PT | 2,162 / 780 | **+0.0138** [+0.011, +0.017] | < 0.0001 |

Block-bootstrap by **game** (not tick). Holm-Bonferroni across the pre-registered set.

> *A trailing team's basket shifts the calibrated model in their favor over the next 60s. The behavioral question: does the market shift **more**?*

---

## SLIDE 9 — The backtest engine *(60 sec)*
Threshold → ¼-Kelly → settle at vigged odds → **block-bootstrap by game**.
5/5 honesty gates pass:
- const-0.5 → Brier 0.25 ✓
- always-favorite → loses ≈ the vig ✓
- perfect model on biased market → +14% ROI, p=0.000 ✓
- market-as-variant → 0 bets ✓

---

## SLIDE 10 — Live pilot, real money simulation *(75 sec)* — **headline figure #3**
**SAS @ OKC, 2026-05-26 (FINAL OKC 127–114).** 73 in-1H ticks, 6 books.

| Strategy | Bets | ROI (n=1) |
|---|---|---|
| **Model @4% edge** | 34 | **−40%** ❌ |
| Always-favorite | 73 | +34% ✅ |
| Random | 73 | −31% |

**The lesson is the result.** One game = one coin flip. The model lost because it faded the eventual blowout winner; "always favorite" looks brilliant only because the favorite happened to win.
**This is the n=1 problem made tangible** — and the methodological backbone of the whole project.

---

## SLIDE 11 — What this teaches: liquidity × sample size *(45 sec)*
Two backtests, opposite results:

| | Liquid sportsbook (1 game) | Stale Kalshi 1H (4 games) |
|---|---|---|
| Model ROI | **−40%** | **+100%+** |

Same model. The "+100%" against Kalshi is **stale mid-prices + n=4 + no slippage** — exactly the trap CLAUDE.md warns about.
**Liquidity quality and game count are everything.** This is the limitations frame for the whole project.

---

## SLIDE 12 — Connecting back to Halawi *(45 sec)*
Halawi's Aggregate column: 4·LM + 1·crowd > either alone, because the errors are **independent**.
Our structural model and the market are also partly independent error sources.
The Halawi-analog variant (V3): **weighted blend of model + market**, weights from validation Brier.
*Framing:* the structural model's job isn't to **beat** the market everywhere — it's to **complement** it in the specific situations where the crowd's bias is strongest (H1/H4).

---

## SLIDE 13 — Limitations + future *(30 sec)*
- **Sample size**: powered backtest needs the paid historical season (~1,000 games) or full playoff accumulation.
- **Horizon**: V2 is 1st-half; live demo extended to full-game via parallel model.
- **Market reactivity / account limits**: real deployment would face adverse selection.
- **Variants V1/V3/V4/V6** ready architecturally; need multi-venue in-play history.

---

## SLIDE 14 — Takeaways *(30 sec)*
1. **Calibrated WP model: Brier 0.149 OOS** — a real, simple, defensible artifact.
2. **Pre-registered behavioral test passed**: trailing-team overreaction is statistically real (p < 0.0001).
3. **Full pipeline runs end-to-end on real market data** (model → de-vig → edge → Kelly → settle → bootstrap).
4. **The honest backtest answer**: pipeline ready, scale gates the trustworthy P&L.
5. **Halawi-tied story**: model and crowd are *complementary* error sources, not competing oracles.

*Thank you. Questions.*

---

## Timing budget
| Block | Slides | Time |
|---|---|---|
| Title + transition (Halawi → NBA pick) | 1–3 | **65 s** |
| NBA project (data → model → mispricing → backtest → discussion → limits → takeaways) | 4–14 | **~9 min** |
| **Total** | 14 | **~10 min** |

## Build notes
- Tables → small inline `pptxgenjs` tables in TEAL/CREAM stripes.
- Three headline figures: reliability diagram (s7), V5 shift bar chart with CIs (s8), pilot-vs-baseline ROI bars (s10).
- Color palette: NAVY=#0B2545 titles, DEEP=#13315C accents, TEAL=#1C7293 highlights, SKY=#8DA9C4 secondary, CREAM=#F6F6F2 bg, ACCENT=#EEA02B emphasis, INK=#1A1A1A body.
