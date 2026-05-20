# Data We Need

Concrete schema and acquisition status for every data source the project
depends on. Use this as the canonical "what data, from where, in what shape"
reference.

---

## 1. NBA play-by-play (PBP)  ✅ acquired

**Why:** The structural model and event extraction both consume PBP. This is
the foundation of V2 and V5.

**Source:** `nba_api.stats.endpoints.playbyplayv3` (free, no auth, public).

**Coverage:**
- 2023-24 regular season: 1,230 / 1,230 games on disk
- 2024-25 regular season: 1,230 / 1,230 games on disk
- Smoke samples for 2019-20 through 2024-25 (one game per season)

**Schema (24 cols per row, one row per PBP event):**

| column | dtype | example | use |
|---|---|---|---|
| `actionNumber` | int | 4 | event sequence within game |
| `clock` | str (ISO 8601) | `"PT07M22.00S"` | seconds remaining in period |
| `period` | int | 2 | quarter 1–4, OT 5+ |
| `teamId` | int | 1610612747 | scoring/acting team |
| `teamTricode` | str | `"LAL"` | for joins to schedules/odds |
| `personId` | int | 2544 | player |
| `playerName` | str | `"LeBron James"` | |
| `scoreHome` | str→int | `"48"` | running home score (may be `""`) |
| `scoreAway` | str→int | `"45"` | running away score |
| `pointsTotal` | int | 23 | scorer's points in this game |
| `xLegacy`, `yLegacy` | int | -141, 76 | shot coords (legacy) |
| `shotDistance` | int | 18 | feet |
| `shotResult` | str | `"Made"` / `"Missed"` | for FG events |
| `shotValue` | int | 3 | 2-pt or 3-pt |
| `isFieldGoal` | int | 1 | binary flag |
| `actionType` | str | `"Made Shot"`, `"period"` | event kind |
| `subType` | str | `"Jump Shot"`, `"start"` | event sub-kind |
| `description` | str | `"Start of 1st Period (7:11 PM EST)"` | human-readable |
| `actionId` | int | 1 | stable id |
| `location` | str | `"h"` / `""` | sometimes home/away marker |
| `videoAvailable` | int | 0 | unused |

**On-disk layout:** `data/interim/pbp/{season}/{game_id}.parquet`,
e.g., `0022300001.parquet` for the first 2023-24 game.

**Schema parity:** confirmed identical across all six seasons we smoke-tested.

---

## 2. Per-minute game-state snapshots  ✅ derived from PBP

**Why:** This is the table V2 trains on and V5 reads to compute structural
shifts. One row per (game, minute_idx) covering the 1st half.

**Source:** `src/data/build_dataset.py::build_minute_snapshots` walks each
game's PBP and captures running state at minute boundaries 1..24.

**Schema (per row):**

| column | dtype | use |
|---|---|---|
| `game_id` | str | join key |
| `season` | str | e.g. `"2023-24"` |
| `minute_idx` | int | 1..24 within 1st half |
| `seconds_elapsed` | int | minute_idx * 60 |
| `period` | int | 1 (Q1) or 2 (Q2) for 1H ticks |
| `score_home` | int | running |
| `score_away` | int | running |
| `score_diff_home` | int | feature |
| `recent_run_home` | int | home points scored in last 120s |
| `recent_run_away` | int | away points scored in last 120s |
| `recent_run_diff` | int | feature |
| `home_team_id` | int | for joins to odds |
| `away_team_id` | int | |
| `home_tricode` | str | |
| `away_tricode` | str | |
| `y_home_wins_1h` | int (0/1) | target |
| `y_tie_1h` | int (0/1) | rare, dropped from training |
| `y_home_wins_game` | int (0/1) | secondary target |
| `final_score_home_1h` | int | for sanity checks |
| `final_score_away_1h` | int | |
| `final_score_home_game` | int | |
| `final_score_away_game` | int | |

**Volume:** 24 rows × 1,230 games = 29,520 rows per season; 59,040 total
across the two seasons we have.

**Storage:** Built on-demand from PBP via `build_season(...)`; not persisted
to its own parquet yet (could be added if rebuilds become slow).

---

## 3. Pregame closing odds (one row per game)  ⏸ not yet acquired

**Why:** Two uses:
- Features for the WP model (pregame spread / total proxy team strength
  beyond what game state encodes).
- A pregame anchor for de-vigging the in-play moneyline.

**Source plan:** the-odds-api historical pre-game endpoint (free tier may
suffice; if not, a Kaggle closing-line dataset works as a fallback).

**Schema:**

| column | dtype | example | notes |
|---|---|---|---|
| `game_id` | str | `0022300001` | join key (need to map api game ids → nba_api ids) |
| `game_date` | date | `2023-10-24` | venue local |
| `tipoff_utc` | datetime | `2023-10-25T00:30Z` | needed to join live odds |
| `home_team` | str | `"LAL"` | tricode |
| `away_team` | str | `"DEN"` | tricode |
| `home_ml_close` | float | -145 | American odds, closing |
| `away_ml_close` | float | +125 | American odds, closing |
| `home_spread_close` | float | -3.5 | negative = home favored |
| `home_spread_price_close` | float | -110 | American odds on spread |
| `total_close` | float | 223.5 | over/under |
| `total_over_price_close` | float | -108 | American odds on over |
| `book` | str | `"pinnacle"` | which sportsbook |

---

## 4. Kalshi 1st-half-winner candlesticks  🟡 partial

**Why:** The peer-driven cross-venue probability for V1 (consensus deviation)
and V3 (Halawi aggregate). 1-minute resolution.

**Source:** Kalshi public market-data API
(`https://external-api.kalshi.com/trade-api/v2/`), no auth required.
Endpoints used:
- `GET /markets?series_ticker=KXNBA1HWINNER&status=settled` → market list
- `GET /series/{s}/markets/{ticker}/candlesticks?period_interval=1&start_ts=...&end_ts=...` → 1-min candles

**Schema (per candle row in long-format parquet):**

| column | dtype | notes |
|---|---|---|
| `event_ticker` | str | e.g. `KXNBA1HWINNER-26MAY13CLEDET` (1 per game) |
| `market_ticker` | str | e.g. `...CLE` / `...DET` / `...TIE` (3 outcomes per event) |
| `end_ts` | int (epoch seconds) | end of 1-minute window |
| `open_dollars` | float (0–1) | price OHLC |
| `close_dollars` | float | |
| `high_dollars` | float | |
| `low_dollars` | float | |
| `mean_dollars` | float | volume-weighted within minute |
| `yes_bid_close` | float | |
| `yes_ask_close` | float | |
| `volume_fp` | float | $ traded in this minute |
| `open_interest_fp` | float | $ open interest at end of minute |

**Status / coverage:**
- Catalog: 326 unique 1H-winner events on Kalshi from 2026-03-12 to
  2026-05-18 (≈2 months — Kalshi introduced this series in March).
- Candle retrieval: spotty. ~8% of attempted markets actually return a non-empty
  candle array; the rest return `{"candlesticks": []}` from both live and
  historical endpoints. Pattern is unclear but seems related to which
  markets crossed some volume / archival threshold.
- 4 settled games successfully pulled so far (Apr 30, May 3, May 4, May 13 —
  all playoff-quality with $50k–$300k+ in 24h volume).

**Volume of useful data we expect:**
- ~30–80 NBA games with retrievable candles from the existing archive.
- Plus live capture during the remaining playoff window (mid-May → mid-June)
  if we run a daily puller during games.

**On-disk layout:** `data/interim/kalshi/KXNBA1HWINNER/{event_ticker}.parquet`
(empty 0-byte file = "we tried, nothing returned" marker).

---

## 5. Sportsbook 1H-winner in-play odds  ⏸ blocked on signup

**Why:** Cross-venue companion to Kalshi for V1/V3, full input for V4
(time-series), and the **market side** of the pre-registered H1/H4 tests
in V5.

**Source plan:** the-odds-api historical event endpoint.

**Outstanding questions for the-odds-api support (drafted in
`docs/odds_api_support_email.md`):**
1. Does the NBA historical endpoint return **in-play** snapshots, or only
   pregame?
2. Snapshot cadence in practice (5-min claim).
3. Suspension states — flagged or silently omitted?
4. Coverage % for 2023-24 and 2024-25 NBA regular seasons.
5. Multi-book snapshots — multiple books per request, or per-book queries?

**Schema (long format, one row per game × snapshot × book):**

| column | dtype | example | notes |
|---|---|---|---|
| `game_id` | str | `0022300001` | join key |
| `snapshot_ts` | datetime (UTC) | | exact snapshot time |
| `book` | str | `"draftkings"` | venue id |
| `market` | str | `"1H_moneyline"` | also `1H_spread`, `1H_total` |
| `home_ml` | float | +165 | American |
| `away_ml` | float | -185 | American |
| `home_implied_prob_raw` | float | 0.377 | computed |
| `home_implied_prob_devig` | float | 0.368 | computed |
| `overround` | float | 0.026 | per-snapshot |
| `market_status` | str | `"open"` | open / suspended / closed |
| `score_home_at_snapshot` | int | for sanity check vs PBP join |
| `score_away_at_snapshot` | int | |

---

## 6. Joined long-format live-odds table  ⏸ depends on #4 + #5

**Why:** This is the unified table V1/V3/V6 read. One row per
(game_id, snapshot_ts, venue).

**Schema (long format):**

| column | dtype | notes |
|---|---|---|
| `game_id` | str | join key |
| `snapshot_ts` | datetime (UTC) | |
| `seconds_elapsed_game` | int | computed; aligns to snapshot table |
| `period` | int | for filter to 1H ticks |
| `clock_in_period` | str (ISO duration) | for joining to PBP |
| `score_home_at_snapshot` | int | sanity check |
| `score_away_at_snapshot` | int | |
| `venue` | str | `"pinnacle"`, `"draftkings"`, `"fanduel"`, `"kalshi"`, … |
| `market` | str | `"1H_moneyline"` |
| `home_price` | float | American odds (sportsbooks) or YES contract price 0–1 (Kalshi) |
| `away_price` | float | |
| `home_implied_prob_raw` | float | computed |
| `home_implied_prob_devig` | float | computed; for Kalshi, raw ≈ devig (just bid-ask spread, no house vig) |
| `overround` | float | per-snapshot |
| `market_status` | str | open / suspended / closed |
| `volume_hint` | float \| null | Kalshi: 24h volume; sportsbooks: usually null |

**Downstream:** `p_consensus_t = median(home_implied_prob_devig)` across venues per `(game_id, snapshot_ts)` → input to V1 and V3.

---

## 7. Events table  ✅ built on demand from PBP

**Why:** Salience events drive V5. One row per made FG with pre-event state
and the trailing-or-not flag.

**Source:** `src/analysis/variant_v5_event.py::extract_events_from_pbp`.

**Schema:**

| column | dtype | notes |
|---|---|---|
| `game_id` | str | |
| `season` | str | |
| `actionNumber` | int | PBP event ID |
| `sec_elapsed` | float | seconds from tipoff |
| `period` | int | quarter |
| `team_id_scoring` | int | who scored |
| `shot_value` | int | 2 or 3 |
| `pre_score_home` | int | |
| `pre_score_away` | int | |
| `pre_diff_for_scorer` | int | positive = scoring team was trailing |
| `home_scored` | bool | |
| `event_type` | str | `"made_fg2"` / `"made_fg3"` |

**Volume:** 52,039 1st-half made-FG events across the 2024-25 test season
alone. Filtered to ~4,596 H1 events and ~2,162 H4 events.

---

## Summary: what's done vs. what's blocked

| Data | Status | Blocked on |
|---|---|---|
| PBP 2023-24 + 2024-25 | ✅ acquired | — |
| Per-minute snapshots | ✅ derived | — |
| Events table | ✅ derived | — |
| Kalshi 1H candles | 🟡 partial | archival coverage outside our control; live capture works |
| Pregame closing odds | ⏸ | the-odds-api signup or Kaggle fallback |
| Sportsbook in-play odds | ⏸ | the-odds-api signup |
| Joined live-odds long table | ⏸ | #4 + #5 |

**One-line summary of what unblocks the rest:** the-odds-api free-tier
signup. That unblocks the pregame anchor (#3), the sportsbook in-play side
(#5), and by composition the joined table (#6) plus the *market side* of
every pre-registered test.
