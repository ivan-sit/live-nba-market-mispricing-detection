# Spurs-Knicks Game 2 Microstructure Case Study

## Scope

This is a one-game execution-microstructure supplement to the main V2/V5
mispricing project.

- Game: New York Knicks at San Antonio Spurs, NBA Finals Game 2, 2026-06-05.
- Venue: Kalshi `KXNBAGAME-26JUN05NYKSAS` game-winner markets.
- Final: Knicks 105, Spurs 104.
- Raw source: live recorder run
  `kalshi-spurs-knicks-game2-20260606T002741Z`.
- Committed outputs:
  `reports/microstructure/spurs_knicks_game2/`.

Raw JSONL is not committed because the full recorder directory is roughly 14GB.

## Data Captured

The compact derived assets contain:

| Asset | Rows | Purpose |
|---|---:|---|
| `orderbook_snapshots_compact.csv` | 33,316 | executable best bid/ask and visible depth |
| `scoring_events.csv` | 109 | final play-by-play scoring events |
| `event_reactions.csv` | 633 | event × horizon market reaction rows |
| `cadence_summary.csv` | 2 | observed per-ticker recorder cadence |
| `summary.json` | 1 | machine-readable headline summary |

Observed per-ticker book cadence:

| Ticker | Snapshots | Cadence p50 | Cadence p95 | Request p50 |
|---|---:|---:|---:|---:|
| Knicks YES | 16,659 | 956 ms | 1,284 ms | 238 ms |
| Spurs YES | 16,657 | 957 ms | 1,287 ms | 238 ms |

So the requested 250ms REST cadence became roughly 1Hz per ticker in practice.

## Headline Reaction Results

The table below is from the scorer's YES market.  A positive mid move means the
market moved in favor of the team that just scored.

| Requested horizon | Events with usable post sample | Median actual post lag | Mean mid move | Positive-move share | Profitable visible roundtrip events |
|---:|---:|---:|---:|---:|---:|
| 250 ms | 106 | 792 ms | +0.0042 | 29% | 12 |
| 500 ms | 106 | 1,027 ms | +0.0076 | 32% | 16 |
| 1 s | 106 | 1,514 ms | +0.0092 | 40% | 22 |
| 3 s | 106 | 3,606 ms | +0.0175 | 62% | 45 |
| 10 s | 105 | 10,568 ms | +0.0223 | 70% | 54 |
| 60 s | 104 | 60,533 ms | +0.0184 | 65% | 52 |

Among events that eventually moved at least +1 cent in the scorer's direction,
the median first observed +1 cent move was about 1.8 seconds after the official
play-by-play anchor.

## V5-Style Buckets

Trailing-team made threes are the cleanest overlap with the existing V5
hypothesis.

| Horizon | Events | Mean scorer-side mid move | Positive-move share | Profitable visible roundtrip events |
|---:|---:|---:|---:|---:|
| 250 ms | 13 | +0.0019 | 23% | 1 |
| 500 ms | 13 | +0.0038 | 31% | 2 |
| 1 s | 13 | +0.0069 | 46% | 3 |
| 3 s | 13 | +0.0308 | 85% | 8 |
| 10 s | 12 | +0.0454 | 100% | 10 |
| 60 s | 12 | +0.0500 | 92% | 10 |

This is directionally consistent with the V5 story: trailing-team threes
produced larger scorer-side market moves than the all-event average.  It is
not powered evidence because this is one game.

Late Q4 scoring events were also highly reactive:

| Horizon | Events | Mean scorer-side mid move | Positive-move share |
|---:|---:|---:|---:|
| 250 ms | 14 | +0.0157 | 79% |
| 500 ms | 14 | +0.0361 | 93% |
| 1 s | 14 | +0.0379 | 93% |
| 3 s | 14 | +0.0529 | 93% |

That is useful commercially, but it is mostly leverage/clock sensitivity rather
than the specific trailing-team-overreaction hypothesis.

## Direct V5 Bucket Runner

After the broader event-reaction pass, I also ran
`scripts/run_microstructure_v5_case.py`, which applies the exact H1/H4 bucket
definitions from `variant_v5_event.py` to this game's live orderbook data and
compares the observed market shift to the structural-side benchmarks already
logged for the project.

Structural benchmarks from the held-out 2024-25 V5 results:

- H1 trailing 10-15 made FG: +0.0075.
- H4 trailing 10+ made three: +0.0138.

H1 market-side result in this game:

| Horizon | Events | Mean market shift | Market minus structural |
|---:|---:|---:|---:|
| 250 ms | 9 | -0.0006 | -0.0081 |
| 500 ms | 9 | +0.0006 | -0.0069 |
| 1 s | 9 | +0.0044 | -0.0031 |
| 3 s | 9 | +0.0172 | +0.0097 |
| 10 s | 8 | +0.0194 | +0.0119 |
| 60 s | 8 | +0.0319 | +0.0244 |

H4 market-side result in this game:

| Horizon | Events | Mean market shift | Market minus structural |
|---:|---:|---:|---:|
| 250 ms | 3 | -0.0050 | -0.0188 |
| 500 ms | 3 | -0.0017 | -0.0155 |
| 1 s | 3 | +0.0083 | -0.0055 |
| 3 s | 3 | +0.0300 | +0.0162 |
| 10 s | 2 | +0.0300 | +0.0162 |
| 60 s | 2 | +0.0250 | +0.0112 |

Interpretation: in this one game, the V5 market-side overreaction signal does
not show up in the first sampled sub-second states, but it does show up by
roughly the 3-second horizon.  That is consistent with the broader case-study
read: the current REST recorder can support event-overreaction diagnostics, but
not definitive 250-500ms execution conclusions.

## Full Prediction Pipeline Replay

The recorder data can also be run through the project's actual structural
prediction pipeline rather than only event buckets.  For this replay I trained
an all-game full-game win-probability model on the 2023-24 NBA play-by-play
season:

- Training set: 1,230 games, 59,040 regulation-minute snapshots.
- Target: final home-team game winner.
- Features: `minute_idx`, `score_diff_home`, `recent_run_diff`, `period`.
- In-sample Brier: raw 0.1607, calibrated 0.1603.

Then I replayed all 33,316 Kalshi book snapshots from this game through that
model.  The replay converts `P(home wins)` to `P(YES)` for each Kalshi ticker,
compares it to the executable YES ask, and opens a buy episode when:

`p_model_yes - yes_ask >= threshold`

Consecutive signal snapshots are de-duplicated into episodes.  The budget rows
below assume spending at most the listed budget into visible depth within 1
cent of the best ask, then holding to final settlement.  Knicks won, so NYK YES
pays 1.00 and SAS YES pays 0.00.

| Edge threshold | Budget / episode | Episodes | NYK / SAS episodes | Entry cost | Actual P&L | Model EV |
|---:|---:|---:|---:|---:|---:|---:|
| 3c | $100 | 65 | 45 / 20 | $6.2k | $5.6k | $10.7k |
| 3c | $1k | 65 | 45 / 20 | $57.4k | $58.0k | $106.6k |
| 3c | $10k | 65 | 45 / 20 | $474.9k | $536.7k | $1.04M |
| 5c | $100 | 60 | 49 / 11 | $5.9k | $6.6k | $10.9k |
| 5c | $1k | 60 | 49 / 11 | $56.8k | $66.9k | $108.9k |
| 5c | $10k | 60 | 49 / 11 | $471.8k | $606.1k | $1.06M |
| 8c | $100 | 56 | 47 / 9 | $5.6k | $7.1k | $11.2k |
| 8c | $1k | 56 | 47 / 9 | $54.6k | $72.0k | $111.9k |
| 8c | $10k | 56 | 47 / 9 | $457.3k | $665.4k | $1.09M |

This is the closest analysis in the repo to the commercial question: did the
model identify executable Kalshi asks below structural fair value on the live
book?  In this game, yes.  The 5c threshold with $1k per signal episode spent
about $56.8k and replayed to about $66.9k actual settlement P&L, while the
model expected about $108.9k.

However, this is still not a deployment P&L claim.  It assumes perfect fills at
recorded visible depth, no queue loss, no fees, no order-entry latency, no
adverse selection from our own activity, and final-settlement holding.  It also
uses official play-by-play scoring anchors to reconstruct live features, not
physical ground-truth event timestamps.  Read it as a high-signal one-game
replay that justifies scaling the live recorder across many games.

## Executability Read

The roundtrip columns are diagnostic upper bounds:

1. buy scorer YES through visible pre-event asks;
2. sell through visible post-event bids;
3. stop when marginal exit bid is no longer above marginal entry ask.

These are not filled-order claims.  They do show that the book often had real
visible size, so the movement was not merely a mid-price artifact.

At the 3-second horizon:

- 45 of 106 scoring events had positive visible roundtrip capacity.
- Total diagnostic profitable P&L across independent event windows was about
  $19.1k on about $669k of visible entry cost.
- The median profitable-event diagnostic P&L was about $188.

Longer horizons show much larger capacity, but they are more confounded by
subsequent plays, timeouts, and clock decay.

## Interpretation

This case study supports three practical conclusions:

1. The main V5 pipeline can be pushed from minute-level odds into sampled
   orderbook microstructure.
2. The scorer-side market move becomes much more visible by roughly 3 seconds
   than in the first sampled sub-second state.
3. For this recorder, REST polling is not enough to prove a 250-500ms edge;
   the next version needs a stable WebSocket recorder or lower-latency book
   capture for true sub-second inference.

The result is promising as a case study, but it is not a trading-performance
claim.  The powered test still needs many games and game-level bootstrap.
