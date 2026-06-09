# Results Log

Append-only record of headline numbers from each smoke run. Dated entries; do
NOT modify prior entries — append new ones at the bottom.

---

## 2026-05-18 — V2 first pass, 454 games (during PBP scrape)

Built per-minute 1H snapshots from in-flight PBP. Random 60/20/20 split by
game_id. Features: minute_idx, score_diff_home, recent_run_diff, period.

| Model | Val Brier | Test Brier | Test ECE |
|---|---|---|---|
| LR baseline | 0.1362 | 0.1641 | 0.041 |
| XGB raw | 0.1406 | **0.1604** | 0.049 |
| XGB + isotonic | 0.1343 | 0.1633 | 0.050 |

Isotonic overfits the val partition (91 games too small for stable monotonic
fit). Will revisit with multi-season data.

---

## 2026-05-18 — V2 feature ablation, 952 games

| Model | Test Brier | Test ECE |
|---|---|---|
| LR basic | 0.1303 | 0.066 |
| LR engineered | 0.1298 | 0.063 |
| **XGB basic** | **0.1292** | 0.062 |
| XGB engineered | 0.1298 | 0.058 |

Engineered features (leverage, abs_score_diff, score_diff_x_remaining,
possession_proxy) don't beat the 0.005-Brier threshold. **V2 default = XGB
on 4 basic features.**

---

## 2026-05-18 — V5 structural side, 784 games (during scrape)

H1 (trailing 10-15, made FG): 1,262 events / 246 games
  Mean structural shift: +0.0022  95% CI [-0.003, +0.007]  p = 0.199

H4 (trailing ≥10, made 3pt): 589 events / 207 games
  Mean structural shift: **+0.0105**  95% CI [+0.005, +0.017]  p = 0.0002

H4 significant. H1 not yet (sample size).

---

## 2026-05-18 — V5 structural side, FULL 1230 games

**Headline result of the day.**

H1 (trailing 10-15, made FG): 1,860 events / 377 games
  Mean structural shift: **+0.0062**  95% CI [+0.003, +0.010]  p = 0.0003

H4 (trailing ≥10, made 3pt): 871 events / 317 games
  Mean structural shift: **+0.0184**  95% CI [+0.014, +0.023]  p < 0.0001

Both pre-registered tests show significant POSITIVE structural shift for the
trailing team's scorer after their basket. Going from p=0.20 to p=0.0003 on
H1 was purely from doubling the sample.

By shot value within H1 bucket:
  2-pt makes (n=1269): mean shift -0.0005 (≈0)
  3-pt makes (n=591):  mean shift +0.0211

Interpretation: A trailing team's 3-pointer materially shifts our calibrated
1H-winner model in their favor over the next 60 seconds. A trailing team's
2-pointer in a 10-15 deficit barely moves the model. This is the structural
baseline for the behavioral test — the question becomes: does the market
shift MORE than this on the same event set?

**Awaiting odds data (Task #4, the-odds-api signup) to run the full
H1/H4 market-side comparison.**

---

## 2026-05-18 — V2 + V5 with proper season split (TRAIN 2023-24, TEST 2024-25)

**The cleanest model-side result we can produce.** True out-of-sample.

V2 (XGB + isotonic, trained on 1,230 2023-24 games):
  Test (2024-25, 1,230 games)  Brier 0.1494   ECE 0.0082

V5 pre-registered tests on 2024-25 events:

  H1 (trailing 10-15, made FG)
    n = 4,596 events / 947 games
    structural shift for scorer: **+0.0075**  95% CI [+0.005, +0.010]  p < 0.0001

  H4 (trailing >=10, made 3-pointer)
    n = 2,162 events / 780 games
    structural shift for scorer: **+0.0138**  95% CI [+0.011, +0.017]  p < 0.0001

Effect sizes are consistent across the in-sample (2023-24 random split) and
out-of-sample (2024-25 season hold-out) runs within bootstrap noise. The
behavioral hypothesis is now well-positioned on a real held-out test season
and a large event count (k_thousand events).

## Notes on what's NOT in this log yet

- H2 (V1 cross-venue): blocked on multi-venue odds.
- H3 (V3 Halawi aggregate): blocked on V1 component plus odds.
- Full Brier on multi-season split (2019-22 train, 2023-24 val, 2024-25 test):
  2024-25 PBP pull in progress; will rerun V2 on the proper split once done.

---

## 2026-05-26 — FIRST REAL BACKTESTS on live market data (n tiny → directional)

Backtest engine (src/eval) verified 5/5 honesty gates on synthetic data, then
run on real market prices for the first time. Two games, opposite results —
which is exactly the n=1 lesson.

**(A) Live game-winner backtest — SAS @ OKC, 2026-05-26 (FINAL OKC 127-114).**
Full-game model (models/v2_fullgame.joblib, Brier 0.207 in-sample) vs live
sportsbook consensus (6 books, de-vigged), 1st-half window, 73 joined ticks,
settled on the real outcome.
  model @4% edge: 34 bets, staked $1.10, P&L -$0.44, **ROI -40%**
  always-favorite: +34% (only because the favorite won this one game)
Model faded SA (underdog) early when the game was close; OKC pulled away.
n=1 -> pure noise. Kalshi 1H market was DEAD all night (no-quote) -> sportsbook
was the only tradeable venue.

**(B) Archived Kalshi 1H backtest — 4 playoff games.**
Fix: the original candle pull saved PRE-GAME quotes; re-pulling with the correct
in-play window (from PBP period anchors) yields ~60-70 in-play candles/market.
V2 (1H model) vs de-vigged Kalshi 1H, 250 ticks / 4 games:
  V2 @3%: ROI +103%, Sharpe 1.25, CI [+42%,+193%]  (@8%: +135%)
  favorite: +59% (CI incl 0); random: +8%
**DO NOT TRUST THIS NUMBER.** Almost certainly an artifact: Kalshi 1H is thin
and the mid prices are stale/laggy, so a score-reactive model "beats" a price
that isn't updating -- on mid quotes, no slippage, with n=4. The block-bootstrap
p=0.000 is meaningless over 4 games. Contrast with (A): against a LIQUID
sportsbook the same family of model LOST. Liquidity + n are everything.

Takeaway: the pipeline works end-to-end on real data. Neither number is a
result. The real answer needs many liquid-market games (paid historical season
or accumulated live captures).

---

## 2026-06-06 — Kalshi microstructure case study, Knicks @ Spurs Game 2

Added a one-game high-frequency supplement using a live Kalshi game-winner
recorder.  This extends the V5 event-overreaction question from minute-level
odds/candles to sampled executable orderbook states.

Game: Knicks 105, Spurs 104.  Markets: `KXNBAGAME-26JUN05NYKSAS-NYK` and
`KXNBAGAME-26JUN05NYKSAS-SAS`.

Derived data:
- 33,316 compact orderbook snapshots.
- 109 final play-by-play scoring events.
- 633 event × horizon reaction rows.

Important measurement caveat: the REST recorder requested 250ms cadence, but
the observed per-ticker orderbook cadence was about 956ms p50 / 1.28s p95.
So this is sub-second-ish sampled market analysis, not proof of a 250ms book
edge.

Headline scorer-side moves:
- 250ms requested horizon (median actual sample lag 792ms): mean move +0.0042,
  positive-move share 29%.
- 1s horizon (median actual lag 1.51s): mean move +0.0092, positive share 40%.
- 3s horizon (median actual lag 3.61s): mean move +0.0175, positive share 62%.

V5-style trailing-team made threes were stronger:
- n = 13 events.
- 3s horizon: mean scorer-side move +0.0308, positive share 85%.
- 10s horizon: mean scorer-side move +0.0454, positive share 100% over 12 usable
  events.

Executable-book diagnostic at 3s:
- 45 / 106 usable scoring events had positive visible buy-before / sell-after
  roundtrip capacity.
- Sum of positive diagnostic P&L was about $19.1k on about $669k visible entry
  cost.

Do not read this as P&L proof.  Event timestamps are public play-by-play
`wall_clock` anchors, not physical in-arena ground truth; long horizons are
confounded by later plays and clock decay; n = 1 game.  Read it as evidence
that the project can now test V5 at executable orderbook granularity.

---

## 2026-06-06 — Full prediction replay on Kalshi microstructure capture

Ran the actual structural prediction pipeline against every compact Kalshi book
snapshot from Knicks @ Spurs Game 2, not just event buckets.

New model: all-game full-game WP model trained on 2023-24 PBP.
- Training set: 1,230 games / 59,040 regulation-minute snapshots.
- Features: minute_idx, score_diff_home, recent_run_diff, period.
- In-sample Brier: raw 0.1607, calibrated 0.1603.

Replay method:
- 33,316 live Kalshi book snapshots.
- Convert model P(home wins) into P(YES) for NYK/SAS tickers.
- Buy YES when `p_model_yes - yes_ask` exceeds the threshold.
- De-duplicate consecutive signal snapshots into one episode.
- Spend up to a fixed budget per episode into visible depth within 1c.
- Hold to final settlement. Knicks won 105-104.

Headline capped replay rows:

| Edge threshold | Budget / episode | Episodes | NYK / SAS episodes | Entry cost | Actual P&L | Model EV |
|---:|---:|---:|---:|---:|---:|---:|
| 3c | $1k | 65 | 45 / 20 | $57.4k | $58.0k | $106.6k |
| 5c | $1k | 60 | 49 / 11 | $56.8k | $66.9k | $108.9k |
| 8c | $1k | 56 | 47 / 9 | $54.6k | $72.0k | $111.9k |
| 5c | $10k | 60 | 49 / 11 | $471.8k | $606.1k | $1.06M |

Interpretation: this one-game replay says the model found live Kalshi asks
materially below structural fair value, especially on Knicks YES.  This is the
crucial bridge between the repo's model thesis and the live recorder data.

Caveat: this is still idealized. It assumes recorded visible depth is fillable,
ignores queue position and order-entry latency, ignores fees, and uses official
play-by-play scoring anchors rather than physical event timestamps.  The right
next result is the same replay across many games with fill simulation and
latency-aware entry rules.

---

## 2026-06-08 — Kalshi WebSocket microstructure replay, Spurs @ Knicks Game 3

Second live game-winner microstructure case study.  Game: Spurs 115, Knicks
111.  Event: `KXNBAGAME-26JUN08SASNYK`.  Recording started after Q1, so 95 of
122 final NBA scoring events had usable pre-event Kalshi book state.

Data:
- 36,751 REST orderbook snapshots with full visible ladders.
- 803,452 reconstructed WebSocket book states.
- 122 NBA final play-by-play scoring events.

WebSocket cadence:
- NYK YES: 446,956 states, p50 cadence 5.8ms, p95 78.1ms, sequence gaps 0.
- SAS YES: 356,496 states, p50 cadence 5.9ms, p95 104.3ms, sequence gaps 0.

First observed scorer-side +1c move after NBA play-by-play anchor:
- n = 66 events.
- Mean 1,487ms, median 929ms, p25 480ms, p75 1,907ms.

WS scorer-side mean mid move:
- 250ms: +0.0007, positive share 12%.
- 500ms: +0.0027, positive share 22%.
- 1s: +0.0078, positive share 44%.
- 3s: +0.0147, positive share 68%.
- 10s: +0.0184, positive share 75%.

REST executable-depth diagnostic:
- 3s horizon: 42 / 95 positive roundtrip events, +$16.3k diagnostic P&L on
  $438.5k visible entry cost.
- 10s horizon: 49 / 95 positive, +$29.9k on $615.8k entry cost.
- 60s horizon: 50 / 95 positive, +$144.9k on $2.53M entry cost.

Prediction replay was mixed, unlike the very clean Game 2 replay:
- 3c edge, $1k/episode: +$3.3k P&L on $54.4k entry cost.
- 3c edge, $10k/episode: +$59.4k P&L on $463.9k entry cost.
- 5c edge, $1k/episode: +$1.1k P&L on $63.5k entry cost.
- 5c edge, $10k/episode: +$76.9k P&L on $537.4k entry cost.
- 8c edge, $10k/episode: -$7.4k P&L on $334.4k entry cost.

Interpretation: Game 3 strongly validates the recording stack and sub-second
reaction measurement, but it weakens the claim that the current structural
model alone is sufficient.  Higher model edge did not monotonically improve
realized outcome because the 8c bucket overselected losing NYK-side signals.
The next serious result must aggregate many games and add latency/fill-aware
entry rules.
