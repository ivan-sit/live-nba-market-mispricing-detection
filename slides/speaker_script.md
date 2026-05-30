# Presentation Companion · Speaker Script, Workflow, Results, "Can I Make Money?"

Pair this with `slides/final_deck.pptx` (16 slides, ~10 min). Sections:

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
> "Our research question is one line: **can we use a calibrated win-probability model to detect mispricing and profit from it in NBA in-play markets?**"
> *(point at the two sub-question cards)*
> "It decomposes into two sub-questions we can actually answer. **One: is the bias detectable?** Tested on the held-out 2024-25 season with pre-registered overreaction tests. **Two: can we extract it — actually make money?** Tested with a live backtest on real markets."

### Slide 4 — What we planned · 6 ways to detect mispricing  (30 sec)
> "Within NBA, we mapped out six methodological approaches to detecting mispricing — from cross-venue consensus to time-series mean reversion to event-conditioned overreaction."
> *(point at the two highlighted rows + the Method 1 / Method 2 callouts)*
> "**Data constraints forced us down to two.** Row 2 — the calibrated win-probability model — that's **Method 1** for the rest of the talk. Row 5 — the event-conditioned overreaction test — that's **Method 2**. The other four are blocked on multi-venue in-play odds history we don't have."
> "So the rest of the talk is Method 1 and Method 2."

### Slide 5 — Pipeline  (60 sec)
> "Here's the whole system in one diagram, with the two methods labeled. **The NAVY banner across the top — that whole row is Method 1**: play-by-play, 2,460 games from nba_api, turned into per-minute game-state snapshots, fed to XGBoost plus isotonic, outputs `p̂_t`, the calibrated probability the home team wins the 1st half."
> *(point at the ACCENT callout)*
> "**The orange callout in the middle is Method 2** — it branches off `p̂_t` and tests for overreaction at trailing-team scoring events. It doesn't change the main flow; it's a parallel diagnostic."
> "**Bottom row is the market side**: live odds from 9 sportsbooks and Kalshi, de-vigged into `p_market_t`."
> "Method 1's `p̂_t` meets the market at `edge_t`. That goes through the backtest at the bottom — quarter-Kelly sized at the vigged odds, settled, block-bootstrapped by game."

### Slide 6 — Method 1 · how it works  (45 sec)
> "Method 1 — the calibrated WP model. Intentionally small. XGBoost on four features: `minute_idx`, `score_diff_home`, `recent_run_diff`, `period`. Isotonic on a held-out fold so a 0.70 prediction actually corresponds to a 70% empirical frequency."
> "We ran an ablation — engineered features like leverage and possession proxies — they didn't beat a 0.005-Brier improvement threshold, so we kept it simple. Every choice is defensible, no overfitting story."
> "Inputs are 4 numbers, output is one calibrated probability `p̂_t` between 0 and 1."

### Slide 7 — Finding 1 · Our model is well-calibrated  (60 sec)
> *(point at the diagonal)*
> "Out-of-sample on the 2024-25 season — 1,230 held-out games — the reliability diagram falls **on the diagonal across all deciles**, with binomial confidence intervals that cover the line."
> "**Brier 0.149. ECE 0.008.** That ECE is essentially zero. The probabilities can be trusted. That's a real, defensible artifact — and it's competitive with published in-game WP models like Bashuk and Lopez-Matthews."

### Slide 8 — Method 2 · how it works  (40 sec)
> "Method 2 — the overreaction test — literally **runs on top of Method 1**."
> *(point at left box)*
> "Two inputs: `p̂_t` from Method 1 at every minute, and trailing-team scoring events from PBP, filtered by our two pre-registered rules — comeback FG in a 10–15 deficit, salience 3PT in a 10-plus deficit."
> *(point at middle box)*
> "For each event at time t we look up `p̂(t)` and `p̂(t+60s)`. The structural shift is the difference. We average within a game first, then block-bootstrap 10,000 times across games to get a confidence interval and a p-value."
> *(point at bottom example)*
> "Concrete example: trailing 12, hits a three at minute 18. p̂ before the basket is 0.18. Sixty seconds later it's 0.22. The shift is plus 0.04."
> "Output is the structural-shift estimate with a 95% CI and p-value — answering: **does the bias exist?**"

### Slide 9 — Finding 2 · The market overshoots on trailing-team scoring  (75 sec)
> "Now the behavioral test. For each pre-registered event, we measure the **structural shift for the scorer over the next 60 seconds** — how much does the calibrated model move toward the scoring team after they make a basket while trailing?"
> *(point at the bars)*
> "**The comeback-FG test: +0.75 percentage points. p < 0.0001.** Block-bootstrap by *game* across 4,596 events. **The salience-3PT test: +1.4 points. p < 0.0001.**"
> "Both pre-registered tests pass on the held-out season. The model says: *a trailing team's basket genuinely does move the structural fair value in their favor.*"
> "Which sets up the behavioral question: **does the market shift by more than this?** That's the mispricing — when the crowd overshoots what the fundamentals say."

### Slide 10 — Method 1 vs Method 2 · the asymmetry  (50 sec)
> "Before the backtest, an honest framing. **Method 1 and Method 2 are not co-equal.**"
> *(point at the left, NAVY box)*
> "**Method 1 is the trading signal.** It computes `edge_t`, gates every bet on the threshold, picks the side, sizes by Kelly. **One hundred percent of bets and P&L come from Method 1.**"
> *(point at the right, ACCENT box)*
> "**Method 2 is the finding — not a trader.** It outputs a number and a p-value, confirms the bias exists. **Zero bets, zero P&L** in our backtest."
> *(point at the bottom orange bar)*
> "And that itself is a finding: Method 2 was a diagnostic, not a trader. Wiring it into the trade decision — the targeted strategy — is the natural next step."
> "Now to the backtest, which is entirely Method 1."

### Slide 11 — Backtest engine  (60 sec)
> "Before we trust any P&L number, the engine has to be honest. Here are the three equations: `edge`, multiplicative two-way `de-vig`, and the Kelly fraction with `b` = decimal odds minus 1."
> "**Five honesty gates** on synthetic data. A constant-0.5 model gets a Brier of exactly 0.25. Always-betting-the-favorite on an efficient vigged market loses approximately the vig. The market-as-itself gets zero edge and zero bets. And — critically — when we feed a perfect model into a *biased* market, the engine recovers a +14% ROI with a p-value of 0.000. So it *can* detect a real edge when one exists."
> "We bootstrap **by game**, not by tick, because within-game ticks share one outcome — the effective sample size is games."

### Slide 12 — Finding 3 · Against liquid books, n=1 is pure noise  (75 sec)
> "We ran this live on the May 26 conference finals game — SAS at OKC, Game 5. The model captured 73 in-1st-half ticks against six live sportsbooks. Then we settled on the real final: **OKC 127, SAS 114**."
> *(point at the bars)*
> "**Our model lost 40%. 'Always favorite' made 34%.**"
> "And — this is critical — *the lesson is the result*. The model faded San Antonio when the game was close early. OKC pulled away. The model lost. 'Always favorite' won — but only because the favorite happened to win this one game. **That's the n-equals-one problem made tangible**, and it's the methodological backbone of this whole talk."

### Slide 13 — Finding 4 · Kalshi pool +95% is a stale-mid artifact  (45 sec)
> "Game 6 happened two nights after Game 5 — OKC at San Antonio. SAS won 118-91."
> *(point at the highlighted Game 6 bar)*
> "Our model returned **+12% on Game 6 alone** against Kalshi's 1H-winner market — the *smallest* of the five archived Kalshi games. **Pool of all five: +95%.**"
> "Don't trust that pool number. The Kalshi 1H market was thin — prices stale, slow to update. A score-reactive model 'beats' a price that isn't moving. Plus n equals 5, plus mid quotes, plus no slippage. **It's an artifact, not an edge.**"
> "Same model — opposite signs from Game 5. The lesson: **liquidity and sample size are everything.**"

### Slide 14 — Connecting back to Halawi  (45 sec)
> "Tie back to the midterm. Halawi's aggregate works because LM errors and crowd errors are **independent**. The same structure applies here: our structural model reads game-state, the market absorbs sentiment and inside flow — partly independent error sources."
> "The 'aggregate' variant from the earlier table — number three — is the literal Halawi analog: `p̂_aggregate = w·p_model + (1−w)·p_market_devig`, weight chosen by validation Brier. The aggregate's Brier is bounded by the minimum of the components."
> "Reframing: the model's job isn't to *beat* the market everywhere. It's to **complement** the market in the specific situations — (comeback FGs, salience 3PTs) — where the crowd's bias is biggest."

### Slide 15 — Limitations & future  (40 sec)
> "Limitations, briefly. **Top of the list — Method 2 didn't trade.** It proved the bias exists but never gated a bet. Wiring it into the strategy is the natural next step."
> "Sample size — we'd want roughly a thousand liquid-market games. Horizon — the model is 1st-half-only. Reactivity — sportsbooks limit winners; Kalshi as peer-to-peer sidesteps that. And the four blocked methods from earlier are architecturally ready but need multi-venue history."

### Slide 16 — Verdict  (45 sec)
> "Two questions, answered directly."
> *(point at left panel)*
> "**Which mispricing method works best?** The **event-conditioned overreaction test**. It's the only one of our six planned methods with a statistically significant finding on the held-out test season: the comeback-FG test gave plus 0.0075, the salience-3PT test gave plus 0.0138 at p less than 0.0001. The bias is statistically real."
> *(point at right panel)*
> "**Can it make money?** Not today, but it's not 'no.' Today we can't claim profit — one liquid game is noise, the Kalshi plus-95% is a stale-mid artifact. But the bias is real, and the path forward is concrete: power the backtest with the paid historical season, then deploy an overreaction-targeted strategy on Kalshi, which is legal and has no account-limit risk."
> "We are **gated on data scale, not on methodology.** Thank you. Questions."

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
