# Backtest Findings (for the Report)

> **Scope.** This document holds the backtest material we cut from the 10-min
> deck so we could focus the talk on the statistical findings (Findings 1 & 2).
> Everything here is the *extraction* side of the story — engine, pilots,
> liquidity vs sample lesson, and the planned targeted strategy. Save for the
> 3-page NeurIPS-style report.

---

## 1. The backtest engine

### Equations

```
edge_t       =  p̂_t  −  p_market_t                     ← Method 1 vs market
p_devig      =  p_home_raw  /  (p_home_raw + p_away_raw)  ← two-way de-vig
f*           =  ( b · p  −  q ) / b                       ← Kelly fraction
                where  b = decimal_odds − 1
                       q = 1 − p
```

- **Edge** is Method 1's calibrated probability minus the de-vigged market
  probability at the same tick.
- **De-vig** removes the bookmaker's overround so we compare apples to apples.
- **Kelly** sizes each bet by the model's confidence; we use **¼-Kelly** for
  safety (a published convention in the sports-betting literature).
- We always bet at the **vigged** quoted odds — never the de-vigged probability.
- Bootstraps are taken **by GAME, not by tick**, because within-game ticks share
  a single outcome. Effective n is games.

### 5 honesty gates (synthetic verification before any real data)

| Gate | Result | What it proves |
|---|---|---|
| const-0.5 → Brier 0.25 | ✅ exactly 0.25 | metrics wired correctly |
| always-favorite on efficient vigged market | ✅ loses ≈ the vig | engine doesn't invent free money |
| random → loses ≈ vig | ✅ | same — no spurious edge |
| perfect model on biased market → +14% ROI, p=0.000 | ✅ | engine *can* detect a real edge |
| market-as-itself variant → 0 bets | ✅ | no fake edge against the market |

5/5 gates pass on synthetic data with known properties. The engine is honest.
Code: `src/eval/backtest.py`, verification: `scripts/test_backtest_engine.py`.

---

## 2. Finding 3 (cut from deck) — *Live pilot: Game 5 against liquid books*

### Setup
- **Game:** SAS @ OKC, Western Conference Finals Game 5, 2026-05-26.
- **Final:** OKC 127, SAS 114 (home team won).
- **Capture:** live, during the actual game. Game state + Kalshi 1H + 6
  sportsbook moneylines polled every 60–90 sec.
- **Ticks joined:** 73 in-1H ticks (signal log × odds log on timestamp, 2-min
  tolerance).
- **Model:** full-game variant of Method 1 (Brier 0.207 in-sample) to match the
  sportsbook moneyline horizon.
- **Settlement:** real game outcome (home win = OKC).
- **Sizing:** ¼-Kelly at 4% edge threshold.

### Per-strategy ROI

| Strategy | Bets | Total stake | P&L | ROI |
|---|---|---|---|---|
| **Method 1 @4% edge** | 34 | $1.10 | **−$0.44** | **−40%** |
| Always-favorite | 73 | — | — | +34% |
| Always-trailing | 73 | — | — | −81% |
| Random | 73 | — | — | −31% |

### What happened
The model faded SA (the underdog) early in the game because the score was
close. OKC pulled away in the 2nd half. The model lost. "Always favorite" made
+34% — but only because the favorite happened to win this one game.

### What it proves
**Nothing about edge.** This is the n=1 problem made tangible. One game is one
Bernoulli outcome — you cannot distinguish skill from luck. The lesson IS the
result: any "P&L" claim from a single liquid-market game is noise. This is the
methodological backbone of the whole project.

---

## 3. Finding 4 (cut from deck) — *Archived Kalshi pool: +95% is an artifact*

### Setup
- **Source:** Kalshi `KXNBA1HWINNER` 1-min candlesticks, re-pulled from the
  archive using **PBP period anchors** for the correct in-play window. (The
  original pull saved pre-game quotes — that fix is itself a subtle
  methodological win documented in `data_schema_and_usage.md`.)
- **Games:** 5 playoff-quality games — DEN@MIN (Apr 30), TOR@CLE (May 3),
  MIN@SAS (May 4), CLE@DET (May 13), **OKC@SAS Game 6 (May 28)**.
- **Total in-play ticks aligned to game state:** 311.
- **Model:** Method 1 (1H-winner target) vs de-vigged 3-way Kalshi consensus
  (OKC/SAS/TIE markets), 5% edge threshold.
- **Settlement:** real 1H winner of each game.

### Per-game ROI

| Game | Bets | ROI |
|---|---|---|
| DEN @ MIN (Apr 30) | 47 | +110% |
| TOR @ CLE (May 3) | 50 | +87% |
| MIN @ SAS (May 4) | 53 | +234% |
| CLE @ DET (May 13) | 27 | +30% |
| **OKC @ SAS Game 6 (May 28)** | 27 | **+12%** |
| **Pool of 5** | 204 | **+95%**, Sharpe 1.08, CI [+35%, +168%] |

### Why we do NOT trust the +95%

1. **Stale mid-prices.** Kalshi's 1H markets are thin — the orderbook barely
   updates while the game lurches. A score-reactive model "beats" a price
   that isn't moving. You couldn't actually trade at those quotes; there's
   nothing on the other side.
2. **No slippage modeled.** We bet at mid; real execution at a thin orderbook
   would slip badly.
3. **n = 5.** Block-bootstrap p-value of 0.000 is meaningless with 5 numbers.
4. **The contrast with Finding 3.** Same model, real liquid market → lost
   −40% on 1 game. Stale thin market → "won" +95% on 5 games. That contrast
   tells you everything.

**Code:** `scripts/backtest_kalshi_archive.py`,
**Results log:** `reports/results_log.md` (entry 2026-05-26).

---

## 4. The lesson — liquidity × sample size

Two backtests, opposite signs, same model family:

| | Liquid sportsbook (Game 5) | Stale Kalshi (5 games) |
|---|---|---|
| Model ROI | **−40%** | **+95%** |
| Real number? | n=1 = noise | stale-mid artifact |

**The talk's punch-line: liquidity quality × sample size are everything.**
- Liquid market + n=1 → still noise.
- Stale market + n=5 → fake edge.
- Trustworthy answer needs **both** a liquid market **AND** many games.

---

## 5. What about Method 2 driving trades?

In the current backtest, **Method 1 drove every trade**. Method 2 was a
*statistical hypothesis test* on Method 1's output — confirmed the bias exists
but never gated, sized, or directed a single bet.

That's an honest gap. The natural extension:

### The Method-2-targeted strategy

```
   At every tick:
       compute edge_t                                     ← Method 1
       compute time_since_last_trailing_team_make          ← Method 2 window
       
       if  |edge_t| > threshold
           AND time_since_last_trailing_team_make < 60s:
           BET                                             ← BOTH gates fire
```

This narrows the trade set to exactly the 60-second windows where Finding 2
proved the bias is biggest. It's a **filter** on top of Method 1's edge —
fewer bets, but each one in the situation where the literature predicts edge
actually lives.

### Why we didn't do it
- **Scope.** We had to choose what to ship before the talk; we shipped the
  pieces (Methods 1 + 2, backtest engine, live capture) without wiring the
  targeted strategy.
- **Shape mismatch.** Method 2's natural output is a population statistic, not
  a per-tick signal. The targeted-strategy wrapping is the simple fix; the
  *full* "compare market shift to model shift per event" version needs per-event
  odds history we don't have at scale.

### The simple version is feasible with what we have
The time-filter version above doesn't need extra data — it filters
`backtest_game_winner_live.py` ticks by proximity to trailing-team makes from
`extract_events_from_pbp`. Run on Game 5 and the Kalshi pool. *That's the first
backtest table to put in the report's Results section.*

---

## 6. Conclusions for the report (gist)

- **Detection works** (Findings 1 + 2, on the deck).
- **Extraction is gated on data scale + on wiring Method 2 in** — the n=1
  pilot is honest noise; the Kalshi pool is an honest artifact.
- **The path is concrete** — paid historical for the powered backtest, then
  a Method-2-targeted strategy on Kalshi.

### Three numbered findings for the report's Results section
1. **Calibration:** Brier 0.149 on 1,230 held-out games · ECE 0.008.
2. **Behavioral test (pre-registered):** comeback FG shift +0.0075,
   salience 3PT shift +0.0138, both p < 0.0001, block-bootstrap by game.
3. **Backtest demo:** end-to-end pipeline runs on real Kalshi + sportsbook
   data; current results are *directional only* (n=1 liquid game,
   n=5 thin-market pool) — gated on data scale.

### Limitations section
1. **Method 2 didn't trade** in our backtest — wired-in future work.
2. **Sample size** — powered backtest needs ~1,000 liquid-market games.
3. **Horizon** — model is 1st-half-only; 2nd-half coverage needs rebuilding.
4. **Market reactivity / limits** — sportsbooks limit winners; Kalshi as
   peer-to-peer sidesteps this.
5. **Four blocked methods (V1 / V3 / V4 / V6)** — architecturally ready,
   need multi-venue history.
