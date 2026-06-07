# Kalshi Microstructure Extension

This extension connects the project's V5 event-overreaction hypothesis to
high-frequency prediction-market orderbook data.

The main project asks whether salient NBA events make live markets overreact
relative to a structural win-probability model.  The microstructure extension
asks a narrower execution question:

> When a scoring event occurs, how quickly does the Kalshi game-winner orderbook
> move, how much visible liquidity is available before/after the move, and would
> the move have been executable through the book rather than only visible at the
> mid?

## Data Flow

```
Kalshi REST orderbook snapshots  ─┐
                                  ├─► executable YES bid/ask/depth table
Kalshi game_stats play-by-play  ──┘
                                  ├─► event-aligned reaction table
                                  ├─► visible buy-before / sell-after walk
                                  └─► case-study figures + summaries
```

The analysis is intentionally book-based:

- Buying YES consumes the opposite side's NO bids, so `YES ask = 1 - NO bid`.
- Selling YES hits visible YES bids.
- Roundtrip diagnostics walk actual entry asks and exit bids; they do not use
  midpoint prices.

## How It Extends V5

V5 currently has strong structural-side evidence: trailing-team made threes
move the calibrated model in the scoring team's favor.  The missing market-side
question is whether the market moves more, less, or later than that structural
change.

For a live captured game, `scripts/analyze_kalshi_microstructure_game.py`
builds event windows at:

```
250ms, 500ms, 1s, 3s, 10s, 60s
```

For each scoring event it records:

- scorer side and pre-event deficit;
- pre-event executable best bid/ask and visible depth;
- post-event bid/ask/mid movement;
- first observed +1 cent move after the official play-by-play anchor;
- optimal visible buy-before / sell-after roundtrip through sampled books.

## Important Limits

The current case study uses Kalshi/Sportradar-style `wall_clock` timestamps from
public play-by-play as event anchors.  These are not true in-arena optical
ground-truth timestamps.  Results therefore measure reaction relative to the
public PBP anchor, not the physical moment the ball went through the hoop.

The Spurs-Knicks recorder requested 250ms REST cadence, but two tickers plus
request latency produced approximately 956ms median per-ticker orderbook
cadence.  Treat sub-second rows as "first sampled post-event state", not proof
of a 250ms trading opportunity.

## Going Forward

The next powered version should:

1. collect many games with the same recorder;
2. add a true ground-truth event clock when available;
3. join each event to the structural model's predicted shift;
4. compare `market_shift - model_shift` by V5 buckets;
5. bootstrap by game, not by event or tick;
6. report executable depth and slippage for every simulated trade.
