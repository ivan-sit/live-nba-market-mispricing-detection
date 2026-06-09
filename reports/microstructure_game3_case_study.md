# Spurs-Knicks Game 3 Microstructure Case Study

## Scope

This is the second live Kalshi game-winner microstructure replay.  It uses the
Game 3 San Antonio at New York recording started during live play on
2026-06-08.

- Game: San Antonio Spurs at New York Knicks, NBA Finals Game 3.
- Final: Spurs 115, Knicks 111.
- Kalshi event: `KXNBAGAME-26JUN08SASNYK`.
- Markets: `KXNBAGAME-26JUN08SASNYK-SAS` and
  `KXNBAGAME-26JUN08SASNYK-NYK`.
- Raw recording: `recordings/kalshi-game3-sas-nyk-20260609T011130Z`.
- Committed outputs: `reports/microstructure/spurs_knicks_game3/`.

The raw recording is not committed because it is roughly 8.6GB.  The committed
case-study outputs are compact CSV/JSON/SVG artifacts.

Important timing caveat: the recording was attached after Q1 had already
ended.  The final NBA play-by-play contains 122 scoring events, but only 95 had
usable pre-event Kalshi book state in the recording.

## Data Captured

| Feed | Rows / states | Purpose |
|---|---:|---|
| Kalshi REST snapshots | 36,751 orderbook rows | Full level ladders for executable depth and roundtrip diagnostics |
| Kalshi WebSocket reconstructed books | 803,452 book states | High-frequency best bid/ask timing |
| NBA final play-by-play | 122 scoring events | Score/game-clock anchors |

Observed REST cadence was similar to Game 2:

| Ticker | Snapshots | Cadence p50 | Cadence p95 | Request p50 |
|---|---:|---:|---:|---:|
| NYK YES | 18,375 | 953 ms | 1,051 ms | 237 ms |
| SAS YES | 18,376 | 953 ms | 1,052 ms | 236 ms |

The WebSocket recorder was much finer:

| Ticker | Reconstructed states | Cadence p50 | Cadence p95 | Sequence gaps |
|---|---:|---:|---:|---:|
| NYK YES | 446,956 | 5.8 ms | 78.1 ms | 0 |
| SAS YES | 356,496 | 5.9 ms | 104.3 ms | 0 |

## WebSocket Reaction Timing

The WebSocket timing result is the cleanest latency signal from this game.  For
scorer-side YES markets, among events that eventually moved at least +1 cent
within 10 seconds:

| Metric | First observed +1c move |
|---|---:|
| Events | 66 |
| Mean | 1,487 ms |
| Median | 929 ms |
| p25 | 480 ms |
| p75 | 1,907 ms |

Scorer-side mid-price movement by horizon:

| Horizon | Events | Mean mid move | Positive-move share | Median actual sample lag |
|---:|---:|---:|---:|---:|
| 100 ms | 95 | +0.0002 | 5% | 113 ms |
| 250 ms | 95 | +0.0007 | 12% | 268 ms |
| 500 ms | 95 | +0.0027 | 22% | 512 ms |
| 1 s | 95 | +0.0078 | 44% | 1,017 ms |
| 3 s | 95 | +0.0147 | 68% | 3,022 ms |
| 10 s | 95 | +0.0184 | 75% | 10,020 ms |
| 60 s | 95 | +0.0203 | 63% | 60,025 ms |

Compared with the REST-only Game 2 capture, this confirms that sub-second
measurement matters: the book often has not fully moved at 250-500ms, but the
reaction becomes very visible by 1-3 seconds.

## REST Depth / Executability

REST snapshots retain the full visible level ladder, so they are better for
depth and roundtrip diagnostics even though the cadence is only about 1Hz.

At scorer-side horizons:

| Horizon | Usable events | Mean mid move | Positive-move share | Positive roundtrip events | Diagnostic positive P&L | Entry cost |
|---:|---:|---:|---:|---:|---:|---:|
| 250 ms | 95 | +0.0053 | 36% | 16 | $730 | $36.6k |
| 500 ms | 95 | +0.0067 | 41% | 22 | $1.6k | $72.3k |
| 1 s | 95 | +0.0103 | 54% | 32 | $4.4k | $172.2k |
| 3 s | 95 | +0.0166 | 73% | 42 | $16.3k | $438.5k |
| 10 s | 95 | +0.0203 | 80% | 49 | $29.9k | $615.8k |
| 60 s | 95 | +0.0222 | 63% | 50 | $144.9k | $2.53M |

These are diagnostic upper bounds: buy before the scoring event through visible
asks, sell after through visible bids, and ignore queue position, placement
latency, fees, and market impact.

## V5 Buckets

Game 3 had very few events in the exact V5 buckets, so this is descriptive.

H1 trailing 10-15 made FG:

| Horizon | Events | Mean market shift | Market minus structural |
|---:|---:|---:|---:|
| 250 ms | 3 | +0.0000 | -0.0075 |
| 500 ms | 3 | +0.0000 | -0.0075 |
| 1 s | 3 | +0.0067 | -0.0008 |
| 3 s | 3 | +0.0100 | +0.0025 |
| 10 s | 3 | +0.0167 | +0.0092 |
| 60 s | 3 | +0.0333 | +0.0258 |

H4 trailing 10+ made three:

| Horizon | Events | Mean market shift | Market minus structural |
|---:|---:|---:|---:|
| 250 ms | 1 | +0.0000 | -0.0138 |
| 500 ms | 1 | +0.0000 | -0.0138 |
| 1 s | 1 | +0.0200 | +0.0062 |
| 3 s | 1 | +0.0300 | +0.0162 |
| 10 s | 1 | +0.0400 | +0.0262 |
| 60 s | 1 | +0.1100 | +0.0962 |

The exact V5 buckets again do not show a reliable 250-500ms overreaction in
this one-game sample, but they do become positive by the 1-3 second window.

## Prediction Replay

I replayed the all-game structural model against all 36,751 REST book snapshots.
For Game 3, home is NYK, away is SAS, and SAS won.

Headline capped replay rows:

| Edge threshold | Budget / episode | Episodes | NYK / SAS episodes | Entry cost | Actual P&L | Model EV |
|---:|---:|---:|---:|---:|---:|---:|
| 3c | $1k | 60 | 37 / 23 | $54.4k | $3.3k | $5.9k |
| 3c | $10k | 60 | 37 / 23 | $463.9k | $59.4k | $42.0k |
| 5c | $1k | 68 | 42 / 26 | $63.5k | $1.1k | $9.8k |
| 5c | $10k | 68 | 42 / 26 | $537.4k | $76.9k | $56.8k |
| 8c | $1k | 43 | 28 / 15 | $41.1k | -$1.7k | $5.9k |
| 8c | $10k | 43 | 28 / 15 | $334.4k | -$7.4k | $46.5k |

This is much less clean than Game 2.  The moderate 3c-5c thresholds were
positive at larger sizing, but the higher 8c threshold lost money because it
overselected NYK-side signals despite SAS winning.  That is a useful warning:
larger model-vs-ask edge did not monotonically translate to better realized
outcome in this game.

## Interpretation

Game 3 supports the latency/microstructure thesis more strongly than the model
P&L thesis:

1. The WebSocket recorder worked and gave true high-frequency book states, with
   no observed sequence gaps and p50 inter-state cadence around 6ms.
2. The average first observed +1c scorer-side move was about 1.49s after the
   NBA play-by-play anchor, with median about 0.93s.
3. Most scorer-side reaction is still not fully visible at 250-500ms, but it is
   clearly visible by 1-3 seconds.
4. The full prediction replay was mixed.  It did not reproduce the huge clean
   Game 2 result, which is exactly why the next step needs many-game aggregation
   rather than relying on one spectacular case.

Commercially, the encouraging signal is that executable price movement is
measurable and often delayed enough to analyze.  The caution is that the
current structural model can be directionally wrong at exactly the wrong times;
latency only helps if the state/prediction layer is right.
