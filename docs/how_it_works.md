# How It All Works — System Walkthrough & Usage Guide

A plain-language tour of the whole project: what each piece does, how data flows
through it, how to run everything, and **why we can't backtest on historical
games yet.**

> One-sentence version: we train a calibrated win-probability model on historical
> play-by-play, compare its probability to the live betting market, and measure
> whether the gap ("mispricing") is real and profitable — a behavioral
> asset-pricing test, not a betting bot.

---

## Contents
1. [The big picture](#1-the-big-picture)
2. [The core idea in one equation](#2-the-core-idea-in-one-equation)
3. [Component map](#3-component-map-what-each-file-does)
4. [Flow A — Training the model (offline, done)](#4-flow-a--training-the-model)
5. [Flow B — The backtest engine (built + verified)](#5-flow-b--the-backtest-engine)
6. [Flow C — Live signals tonight (paper trading)](#6-flow-c--live-signals)
7. [The six variants](#7-the-six-variants)
8. [How to run everything](#8-how-to-run-everything)
9. [Why we can't backtest on historical data yet](#9-why-we-cant-backtest-on-historical-data-yet)

---

## 1. The big picture

```
                          ┌──────────────────────────────────────────┐
                          │              DATA SOURCES                  │
                          ├──────────────────────────────────────────┤
   historical (have it)   │  nba_api play-by-play   →  2 seasons       │
   live (tonight)         │  ESPN scoreboard        →  game state      │
   live + current (free)  │  the-odds-api           →  9 sportsbooks   │
   live + tiny history    │  Kalshi 1H-winner       →  peer market     │
                          └───────────────┬──────────────────────────┘
                                          │
                  ┌───────────────────────┼───────────────────────┐
                  ▼                       ▼                        ▼
          ┌──────────────┐       ┌────────────────┐       ┌───────────────┐
          │  MODEL SIDE  │       │   MARKET SIDE  │       │   OUTCOME     │
          │  V2 win-prob │       │  de-vigged     │       │  who won the  │
          │  p̂_t         │       │  price p_mkt_t │       │  1st half     │
          └──────┬───────┘       └───────┬────────┘       └──────┬────────┘
                 │                       │                       │
                 └───────────┬───────────┘                       │
                             ▼                                   │
                    edge_t = p̂_t − p_mkt_t                       │
                             │                                   │
                             ▼                                   ▼
                    ┌─────────────────────────────────────────────────┐
                    │  BACKTEST ENGINE (src/eval/)                     │
                    │  threshold → ¼-Kelly → settle → bootstrap-by-game│
                    │  → ROI, Sharpe, CI, "does edge beat the vig?"    │
                    └─────────────────────────────────────────────────┘
```

The project has **two sides that meet at the edge**:
- **Model side** — what *should* the probability be? (built from fundamentals: score, time, momentum)
- **Market side** — what is the crowd actually pricing? (sportsbooks + Kalshi)

When they disagree by more than the vig, that's a candidate **mispricing**. The
behavioral story (Halawi → crowds overreact → live markets) predicts the gap is
*systematic* in specific situations (e.g., right after a trailing team scores).

---

## 2. The core idea in one equation

At every moment `t` in a game:

```
   edge_t  =  p̂_t   −   p_market_t
              ▲          ▲
              │          └─ market's de-vigged P(home wins), from odds
              └─ OUR model's calibrated P(home wins)
```

- `edge_t > 0` → model thinks home is **underpriced** → bet home
- `edge_t < 0` → model thinks home is **overpriced** → bet away
- `|edge_t| < threshold` → no bet (gap too small to beat the vig)

Everything else — calibration, the six variants, the backtest — is machinery to
estimate `p̂_t` well and to test whether acting on `edge_t` actually makes money.

---

## 3. Component map (what each file does)

```
src/
├── data/
│   ├── pull_pbp.py          fetch historical play-by-play (nba_api)
│   ├── pull_odds.py         the-odds-api client (9 sportsbooks)   [live/current]
│   ├── pull_kalshi.py       Kalshi public market-data client       [peer market]
│   └── build_dataset.py     PBP → per-minute 1H game-state snapshots
├── models/
│   ├── baseline.py          logistic regression (floor to beat)
│   ├── xgb_model.py         XGBoost win-prob model  ← V2's engine
│   └── calibration.py       isotonic calibration + Brier/ECE/reliability
├── eval/                    ← THE SHARED HARNESS (all variants plug in here)
│   ├── splits.py            game-level GroupKFold (never row-level!)
│   ├── metrics.py           Brier / log-loss / ECE + EvalReport
│   ├── backtest.py          P&L engine: Kelly + vig + bootstrap-by-game
│   └── harness.py           VariantProtocol + evaluate() + backtest()
└── analysis/
    ├── variant_v2_structural.py  V2 (model vs market)        [built]
    ├── variant_v5_event.py       V5 (event overreaction)     [built]
    └── variant_v1/v3/v4/v6_*.py  the other four              [stubs]

scripts/
├── train_and_save_v2.py     train V2, save models/v2_xgb_isotonic.joblib
├── test_backtest_engine.py  5 honesty gates on synthetic data   ← run this
├── live_signal_monitor.py   LIVE paper-trading signals (tonight)
├── capture_odds_live.py     live 9-book odds capture
└── smoke_test_odds_api.py   validate the-odds-api key
```

---

## 4. Flow A — Training the model

**(offline, already done — needs only historical PBP, which we have)**

```
  data/interim/pbp/2023-24/*.parquet   (1,230 games)
              │
              ▼
   build_dataset.build_season()        walk each game's events, snapshot the
              │                        state at minutes 1..24 of the 1st half
              ▼
   per-minute snapshots  ── columns: minute_idx, score_diff_home,
              │                       recent_run_diff, period, y_home_wins_1h
              ▼
   xgb_model.fit_xgb()                 XGBoost (300 trees, depth 4, lr .05)
              │
              ▼
   calibration.fit_isotonic()          monotonic squashing so 0.70 really
              │                        means 70% of the time
              ▼
   models/v2_xgb_isotonic.joblib       ← the saved model, loaded for live use
```

**Result (true out-of-sample, train 2023-24 → test 2024-25):**
- Brier **0.149**, ECE **0.008** — well-calibrated. This is the model side, done.

Why these 4 features? An ablation (see `reports/results_log.md`) showed fancier
engineered features didn't beat a 0.005-Brier bar, so we kept the model simple
and interpretable — the right call for a 3-page report.

---

## 5. Flow B — The backtest engine

**(built + verified; waiting only on market-price data to produce real numbers)**

```
  per-tick table:  game_id │ p̂_t │ p_market_t │ home_odds │ away_odds │ outcome
                                    │
                                    ▼
                       edge_t = p̂_t − p_market_t
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        |edge|<thr            edge>thr               edge<−thr
         no bet              bet HOME                bet AWAY
                                    │
                                    ▼
                     stake = ¼ · Kelly(p̂, decimal_odds)     ← sized by confidence
                                    │
                                    ▼
                  settle at the VIGGED odds you'd really get
                                    │
                                    ▼
              group by GAME  →  per-game ROI series
                                    │
                                    ▼
              block-bootstrap by game (10,000 resamples)
                                    │
                                    ▼
        ROI · Sharpe · 95% CI · p-value · max drawdown
```

**Why bootstrap by GAME, not by tick?** Every tick in a game shares one outcome,
so 100 ticks from one game ≈ **1 independent data point**, not 100. Resampling
by game is the only honest way to get confidence intervals. This is the single
biggest statistical trap in the whole project.

**Verification (run `scripts/test_backtest_engine.py` — 5/5 pass):**

| Gate | What it proves |
|---|---|
| const-0.5 → Brier 0.25 | metrics are wired right |
| always-favorite → loses ≈ vig | the engine doesn't invent free money |
| random → loses ≈ vig | same |
| perfect model on biased market → +14% ROI, CI excludes 0 | engine *can* detect real edge |
| market-as-variant → 0 bets | no fake edge against the market itself |

---

## 6. Flow C — Live signals

**(`scripts/live_signal_monitor.py` — PAPER TRADING, runs tonight)**

```
  every 60s during the 1st half:

   ESPN scoreboard ──► period, clock, score ──► build feature row
                                                      │
   models/v2_xgb_isotonic.joblib ───────────────────►│──► p̂_t  (P OKC wins 1H)
                                                      │
   Kalshi KXNBA1HWINNER orderbook ──► 3-way de-vig ──►│──► p_market_t
                                                      │
                                                      ▼
                                         edge = p̂_t − p_market_t
                                                      │
                                                      ▼
                          print  "BUY SA YES @ 0.61  stake=$6.82 (k=0.27)"
                                                      │
                                                      ▼
                          append row to data/interim/live_signals/*.csv
```

**It places no orders.** It prints what the model *would* do and logs everything,
so after the game we can run that one real game through the backtest engine (Flow
B). Stops automatically at halftime (V2 is a 1st-half model).

---

## 7. The six variants

All six produce a `p̂_t` and plug into the **same** harness (Flow B), so they're
directly comparable. Full detail in `docs/variant_strategies.md`.

| # | Variant | Idea | Needs live odds? | Status |
|---|---|---|---|---|
| **V2** | Structural WP | XGBoost fundamentals vs market | only at eval | ✅ built |
| **V5** | Event overreaction | market over-shifts after a trailing team scores | only at eval | ✅ built (significant) |
| **V1** | Cross-venue consensus | flag books that deviate from the median of 9+ venues | yes | ⏳ |
| **V3** | Halawi aggregate | weighted blend of model + market (the midterm tie-back) | yes | ⏳ |
| **V4** | Time-series reversion | bet against odds that overshoot a fitted path | yes + **trains on odds** | ⏳ |
| **V6** | Cross-book arbitrage | document guaranteed-profit gaps across books | yes | ⏳ |

Decision rule for "which variant wins": it must (1) beat the market's Brier
**and** (2) show positive backtest ROI with a bootstrap CI excluding zero. Only
then do we trust it.

---

## 8. How to run everything

From the repo root. (Python env via `uv`.)

```bash
# 0. one-time: validate the odds API key (already done)
uv run python scripts/smoke_test_odds_api.py

# 1. train + save the model  (re-run anytime; ~1 min)
uv run python scripts/train_and_save_v2.py

# 2. verify the backtest engine is honest  (synthetic, no data needed)
uv run python scripts/test_backtest_engine.py     # expect 5/5 gates pass

# 3. TONIGHT, at tip-off (~5:30pm PT) — two terminals:

#    Terminal 1: model vs Kalshi 1H market (the live signals, paper)
uv run python scripts/live_signal_monitor.py --cadence 60 --threshold 0.04

#    Terminal 2: capture all 9 sportsbooks in parallel (full game)
uv run python scripts/capture_odds_live.py --teams "Thunder,Spurs" --match-all --cadence 90

# 4. after the game: backtest that single game end-to-end
#    (hand the logged files back; n=1 game = pipeline proof, not a result)
```

Outputs land in:
- `models/v2_xgb_isotonic.joblib` — the model
- `data/interim/odds/capture_YYYYMMDD.csv` — sportsbook captures
- `data/interim/live_signals/signals_<event>.csv` — model-vs-market signals

---

## 9. Why we can't backtest on historical data yet

**Short answer: a backtest needs the market's price at each past moment, and we
don't have historical in-play odds — only historical play-by-play.**

A backtest replays the past. For each tick of each past game it needs **three**
things lined up:

```
   ┌─────────────────────┬──────────────────────────────┬─────────────┐
   │ 1. model p̂_t        │ 2. market price p_market_t    │ 3. outcome  │
   │    (we can compute   │    (the in-play odds at that  │  (who won)  │
   │     it from PBP)     │     past moment)              │             │
   ├─────────────────────┼──────────────────────────────┼─────────────┤
   │   ✅ HAVE IT          │   ❌ DON'T HAVE IT             │  ✅ HAVE IT  │
   │   from historical    │   this is the missing piece   │  from PBP   │
   │   play-by-play       │                               │             │
   └─────────────────────┴──────────────────────────────┴─────────────┘
                                     │
                                     ▼
              No column #2  →  no edge_t  →  no bet  →  no P&L
```

We have **historical play-by-play** (2 full seasons, free from nba_api) — that
gives us columns #1 and #3. What we **don't** have is a recording of what the
betting line *was* at minute 18 of a game played last year. That's a different,
harder-to-get dataset, and here's why each source falls short right now:

| Source | Why it can't give us historical in-play odds today |
|---|---|
| **the-odds-api (free tier)** | The live `/odds` endpoint only returns **current** games. Past in-play snapshots live behind the **paid** `/historical` endpoint (free key returns 401/422). Cost ≈ $30–100. |
| **Kalshi** | The 1H-winner series only **launched March 2026**, and the candlestick archive is spotty — only ~**4 games** returned usable 1-minute history out of ~300 attempts. Enough for a demo, not a backtest. |
| **Closing-line proxy** | We could fake an in-play path by interpolating from a pregame closing line, but that's a *made-up* market path — fine as a robustness check, not a real result. |

**So the model side runs on history fine** (that's how we got Brier 0.149 on the
held-out 2024-25 season). It's specifically the **market side of history** that's
missing — and without it there's no `edge_t` to backtest.

### The two ways forward

```
   ┌────────────────────────────┐        ┌────────────────────────────┐
   │  FREE path                 │        │  PAID path (~$30–100)      │
   │  capture live games        │        │  the-odds-api historical   │
   │  going forward (playoffs)  │   vs   │  full 2024-25 in-play      │
   │                            │        │                            │
   │  → a handful of real games │        │  → ~1,000 games            │
   │  → wide CIs, suggestive    │        │  → tight CIs, real answer  │
   └────────────────────────────┘        └────────────────────────────┘
```

Tonight's live capture is the **free path** in action: every game we record adds
one real data point. The **paid path** is the only way to get a statistically
powered historical backtest before the season ends — but as shown in
[§7](#7-the-six-variants), it's an *upgrade for the backtest*, not a requirement
to have a working, trained, calibrated pipeline. Our headline model-side results
(V2 calibration, V5 overreaction) need none of it.
