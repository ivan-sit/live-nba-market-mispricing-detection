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
