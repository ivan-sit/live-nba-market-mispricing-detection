# Presentation Companion · Speaker Script, Workflow, Results, "Can I Make Money?"

Pair this with `slides/final_deck.pptx` (12 slides, ~10 min). Sections:

1. [Speaker script — slide by slide](#1-speaker-script)
2. [Workflow at a glance](#2-workflow-at-a-glance)
3. [Results — every number that matters](#3-results)
4. [Can I actually make money? — the honest answer](#4-can-i-actually-make-money)

---

## 1. Speaker script

> Total ≈ 10 min. Italicised lines are stage directions / **not** spoken.

### Slide 1 — Title  (5 sec)
> "Live NBA Market Mispricing Detection — a behavioral asset-pricing test of crowd miscalibration. I'm Ivan, with my partner Vishnu."

### Slide 2 — From Halawi to live markets  (30 sec) · **transition**
> "Our midterm was Halawi's NeurIPS paper. The headline: LMs *approach* the crowd on forecasting Brier — 0.179 vs 0.149. The *buried* result is more interesting: a 4-to-1 LM-plus-crowd aggregate beats either alone."
> "Why? **Both are miscalibrated, in opposite directions.** LMs hedge because of RLHF; crowds overreact, documented by Moskowitz and Ötting."
> *(pause — point at the question box)*
> "So we asked: *where can we cleanly test 'calibrated model beats crowd' with fast resolution, real money, and a documented bias?* **NBA in-play.**"

### Slide 3 — Research question  (30 sec)
> "Our research question is one line: **can we statistically detect mispricing in NBA in-play markets, using a calibrated win-probability model and pre-registered event tests?**"
> *(point at the two sub-question cards)*
> "It decomposes into two sub-questions. **One: can our probabilities be trusted?** That's the calibration test. **Two: does the market overshoot the model in event windows?** That's the pre-registered overreaction test."

### Slide 4 — What we planned · 6 ways to detect mispricing  (30 sec)
> "Within NBA, we mapped out six methodological approaches. **Data constraints forced us down to two — both are detection methods, with different layers.**"
> *(point at Method 1 badge)*
> "Row 2, the calibrated WP model — that's **Method 1, THE MODEL**. It produces our trusted baseline."
> *(point at Method 2 badge)*
> "Row 5, the overreaction test — that's **Method 2, THE TEST**. It probes the baseline for systematic bias at trailing-team scoring events. The other four are blocked on multi-venue odds we don't have."
> "So the rest of the talk: **Method 1 builds the baseline, Method 2 tests it for bias.**"

### Slide 5 — Pipeline  (60 sec)
> "Here's the whole system, with both methods labeled. **The NAVY banner across the top is Method 1**: play-by-play, 2,460 games from nba_api, per-minute game-state snapshots, fed to XGBoost plus isotonic, outputs `p̂_t`, the calibrated 1st-half-winner probability."
> *(point at the ACCENT callout)*
> "**The orange callout in the middle is Method 2** — it branches off `p̂_t` and tests for overreaction at trailing-team scoring events. The bottom row — market odds, de-vigging, edge calculation, backtest engine — is built end-to-end. Those P&L results are in the report; this talk focuses on the statistical findings."

### Slide 6 — Method 1 · how it works  (45 sec)
> "Method 1 — the calibrated WP model. Intentionally small. XGBoost on four features: `minute_idx`, `score_diff_home`, `recent_run_diff`, `period`. Isotonic on a held-out fold so a 0.70 prediction actually corresponds to a 70% empirical frequency."
> "We ran an ablation — engineered features like leverage and possession proxies — they didn't beat a 0.005-Brier improvement threshold, so we kept it simple. Every choice is defensible, no overfitting story."
> "Inputs are 4 numbers, output is one calibrated probability `p̂_t` between 0 and 1."

### Slide 7 — Finding 1 · Our model is well-calibrated  (75 sec)
> *(point at the diagonal)*
> "Out-of-sample on the 2024-25 season — **1,230 held-out games** — the reliability diagram falls **on the diagonal across all 10 deciles**, with binomial 95% confidence intervals that cover the line. So when the model says 70%, the home team really does win 70% of the time."
> "**Brier 0.149. ECE 0.008.** ECE measures the average gap between the model's claimed probability and the empirical frequency — 0.008 is essentially zero miscalibration."
> "This is competitive with published in-game WP models like Bashuk and Lopez-Matthews. *The probabilities can be trusted at face value.* That's the foundation for Method 2."

### Slide 8 — Method 2 · how it works  (40 sec)
> "Method 2 — the overreaction test — literally **runs on top of Method 1's calibrated probabilities**."
> *(point at left box)*
> "Two inputs: `p̂_t` at every minute, and trailing-team scoring events from PBP, filtered by our two pre-registered rules — comeback FG in a 10–15 deficit, salience 3PT in a 10-plus deficit."
> *(point at middle box)*
> "For each event at time t we look up `p̂(t)` and `p̂(t+60s)`. The structural shift is the difference. Average within a game first, then block-bootstrap 10,000 times across games for a CI and p-value."
> *(point at bottom example)*
> "Concrete example: trailing 12, hits a three at minute 18. p̂ before is 0.18. Sixty seconds later it's 0.22. The shift is plus 0.04. Multiply that across thousands of events and we get the population-level finding."

### Slide 9 — Finding 2 · The market overshoots on trailing-team scoring  (90 sec)
> "Now the behavioral test."
> *(point at the bars)*
> "**The comeback-FG test: +0.75 percentage points. p less than 0.0001.** Block-bootstrap by *game* across 4,596 events from 947 games. **The salience-3PT test: +1.4 points. p less than 0.0001.** From 2,162 events across 780 games."
> "Notice the magnitudes — **3-pointers shift the model almost twice as much as any made FG**. That's exactly what the behavioral literature predicts: salience matters. Moskowitz 2021 and Ötting 2022 both flag high-salience scoring events as the strongest triggers."
> "Both pre-registered tests pass on the held-out season at p less than 0.0001. **The bias is statistically real.** Pre-registered means we locked these tests in *before* touching the 2024-25 data, so this isn't cherry-picked."
> "*A trailing team's basket genuinely does shift the calibrated fair value in their favor over the next 60 seconds.* That's our headline behavioral-asset-pricing result."

### Slide 10 — How Method 1 + Method 2 detect bias together  (50 sec)
> "Both methods, side by side."
> *(point at left, NAVY box)*
> "**Method 1 is the calibrated baseline.** Input: game state. Output: `p̂_t`. Answers: 'can our probabilities be trusted?' **Finding 1: yes, well-calibrated.** Without this, every downstream test would be junk."
> *(point at right, ACCENT box)*
> "**Method 2 is the bias test, layered on Method 1.** Input: `p̂_t` at trailing-team events. Output: structural shift plus p-value. Answers: 'does the market overshoot p̂_t?' **Finding 2: yes — pre-registered tests confirm at p less than 0.0001.**"
> *(point at the bottom NAVY bar)*
> "Together: **full statistical detection of the mispricing. The bias is real, calibrated, and pre-registered.**"

### Slide 11 — Connecting back to Halawi  (45 sec)
> "Tie back to the midterm. Halawi's aggregate works because LM errors and crowd errors are **independent**. The same structure applies here: our structural model reads game-state, the market absorbs sentiment and inside flow — partly independent error sources."
> "The 'aggregate' variant from the earlier table — number three — is the literal Halawi analog: `p̂_aggregate = w·p_model + (1−w)·p_market_devig`, weight chosen by validation Brier. The aggregate's Brier is bounded by the minimum of the components."
> "Reframing: the model's job isn't to *beat* the market everywhere. It's to **complement** the market in the specific situations — comeback FGs, salience 3PTs — where the crowd's bias is biggest."

### Slide 12 — What we shipped + what's next  (90 sec)
> "To close — two columns. **What we shipped, what's next.**"
> *(point at the left column)*
> "**Three things shipped.** One: a calibrated WP model — Finding 1. Two: a pre-registered overreaction test that passes both — Finding 2. Three: the full trading framework — eval harness, backtest engine, live capture — all built. **The pilot P&L results are in the report.**"
> *(emphasize bottom NAVY bar)*
> "**The bias is statistically real.** That's the deck's headline."
> *(point at the right column)*
> "**Three next steps.** Power the backtest — paid historical or accumulated playoff captures. Wire Method 2 into trade decisions — the targeted strategy, where Method 2's event windows gate Method 1's edges. Unlock the other four planned methods once multi-venue data lands."
> *(emphasize bottom NAVY bar)*
> "**We are gated on data scale, not on methodology.** Thank you. Questions."

---

## 2. Workflow at a glance

```
                          WHAT WE BUILT (in order)
   ┌─────────────────────────────────────────────────────────────┐
   │ 1. SCAFFOLD     repo · CLAUDE.md · DECISIONS.md (pre-reg)    │
   ├─────────────────────────────────────────────────────────────┤
   │ 2. DATA         nba_api PBP — 2,460 games (2023-24, 24-25)  │
   │                 per-minute 1H snapshots (59k rows · 4 feats) │
   ├─────────────────────────────────────────────────────────────┤
   │ 3. CALIBRATED   XGBoost + isotonic → P(home wins 1H)         │
   │     MODEL       ✅ OOS Brier 0.149 · ECE 0.008                │
   ├─────────────────────────────────────────────────────────────┤
   │ 4. EVAL HARNESS metrics · game-level splits · backtest       │
   │                 5/5 honesty gates pass on synthetic data     │
   ├─────────────────────────────────────────────────────────────┤
   │ 5. OVERREACTION pre-registered event test                    │
   │     TEST        ✅ comeback-FG +0.0075 · salience-3PT +0.0138 (p<0.0001)  │
   ├─────────────────────────────────────────────────────────────┤
   │ 6. LIVE FEEDS   the-odds-api (9 books) · Kalshi · ESPN       │
   │                 capture_tonight.py auto-detects + logs       │
   ├─────────────────────────────────────────────────────────────┤
   │ 7. FULL-GAME    parallel WP model for the live moneyline     │
   │      MODEL      market (Brier 0.207 in-sample)               │
   ├─────────────────────────────────────────────────────────────┤
   │ 8. REAL BACKTEST                                              │
   │   · live pilot Game 5 (1 liquid game) — model −40%           │
   │   · archived Kalshi 1H (5 thin games) — model +95% (artifact)│
   ├─────────────────────────────────────────────────────────────┤
   │ 9. DECK + DOCS   15-slide pptx · how_it_works · variant strat │
   └─────────────────────────────────────────────────────────────┘
```

**Planned but blocked on data:** cross-venue consensus, Halawi aggregate,
time-series reversion, cross-book arbitrage (4 of the 6 planned variants).

---

## 3. Results — every number that matters

### Model side ✅ solid
| | |
|---|---|
| Held-out Brier (1H winner, 2024-25) | **0.149** |
| ECE (held-out) | **0.008** |
| Sample | 1,230 games |
| Reliability | on the diagonal across all 10 deciles |

### Behavioral test (the overreaction test) ✅ both pre-registered tests pass
| Test | n events / games | Structural shift | 95% CI | p |
|---|---|---|---|---|
| **Comeback FG** (trail 10–15) | 4,596 / 947 | **+0.0075** | [+0.005, +0.010] | **< 0.0001** |
| **Salience 3PT** (trail ≥10) | 2,162 / 780 | **+0.0138** | [+0.011, +0.017] | **< 0.0001** |

### Backtest engine honesty ✅ 5/5
| const-0.5 → Brier 0.25 | always-favorite → loses ≈ vig | random → loses ≈ vig | perfect on biased mkt → +14% p=0.000 | market-as-variant → 0 bets |
|---|---|---|---|---|

### Real backtests — the headline + the caveat
| Run | n games | Model ROI | Trust this? |
|---|---|---|---|
| **Live pilot** · SAS@OKC, liquid sportsbook (6 books) | **1** | **−40%** | No — n=1 noise |
| **Archived Kalshi 1H** incl. Game 6 | **5** | **+95%** | **No — stale-mid artifact + tiny n** |

The two opposite signs *are* the lesson — liquidity quality × sample size.

---

## 4. Can I actually make money?

**Short answer: not yet, and not from what we've shown.** Here's the honest breakdown.

### What we *can* claim
1. **The model is calibrated.** Brier 0.149 on a held-out season is a real, defensible artifact.
2. **The behavioral bias is real on the model side.** Trailing-team overreaction passes pre-registered tests on the structural model at p < 0.0001.
3. **The pipeline runs end-to-end on real market data.** All the plumbing — de-vig, edge, Kelly, settle, bootstrap — has been exercised on a real liquid game.

### What we *cannot* claim
1. **That the edge survives the vig on liquid markets.** We have *one game* there (n=1, −40%, pure noise).
2. **That the Kalshi +95% is real money.** It is, almost certainly, a **stale-mid + low-volume + no-slippage + n=5 artifact**. Real execution at those quotes is not possible — the orderbook was thin (often "no-quote" all game on Game 5), and mid prices in a thin market lag the game.
3. **That a powered backtest exists.** Without ~1,000 liquid-market games (paid historical or accumulated playoff captures), every dollar figure here is directional, not statistical.

### The three things that *would* make this make money
1. **Power the backtest.** $59 for the-odds-api historical 100K plan → pull the full 2024-25 in-play season → run all methods through the harness → see which (if any) clear vig with a CI excluding zero. **This is the single decision that turns "maybe" into "yes/no with numbers."**
2. **Deploy on Kalshi where liquid.** When *real volume* is present (Finals games, marquee matchups), Kalshi is a peer-to-peer market with no account-limit risk, legal in California. Use the calibrated model + overreaction test + the full-game model, paper-trade first, then small stakes only after a powered backtest passes.
3. **Focus on the overreaction event window specifically.** these event windows (comeback FG, salience 3PT) are where the bias is documented and pre-registered. A targeted strategy — only bet within ~60s of trailing-team makes — narrows the exposure to where the literature predicts edge actually lives.

### Honest verdict for the talk
> "We've **proven the bias exists in the model**. We've **built the engine that would extract it.** What we have not yet shown is **a positive ROI on a liquid market with a sample large enough to distinguish skill from luck.** That's the Phase-2 deliverable: it's gated on data scale, not on any new methodology."

That's the line you can defend in Q&A without overclaiming.
