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

**Source plan:** the-odds-api. **Current** pregame lines come free via
`/v4/sports/basketball_nba/odds/` (same endpoint as §5, captured before tip).
**Historical** pregame/closing lines for past seasons are **paid-only** on
the-odds-api (`/v4/historical/...` returns 401/422 on the free key) — fall back
to a Kaggle closing-line dataset if we don't buy the historical plan.

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

## 5. Sportsbook in-play moneyline odds  🟢 live capture working

**Why:** Cross-venue input for V1/V3/V6, full input for V4 (time-series),
and the **market side** of the pre-registered H1/H4 tests in V5.

**Source (CONFIRMED):** the-odds-api v4 `GET /v4/sports/basketball_nba/odds/`
(`markets=h2h`, `regions=us`). Free key validated 2026-05-26 — 500 req/mo,
**9 books per game** (FanDuel, DraftKings, BetMGM, BetRivers, Bovada, BetUS,
LowVig.ag, BetOnline.ag, MyBookie.ag). The same endpoint returns *in-play*
games while they are live, so this is our live-capture source. Client:
`src/data/pull_odds.py`; capture loop: `scripts/capture_odds_live.py`.

**Resolved questions (from the smoke test, replacing the support-email asks):**
1. In-play? **Yes** — live games appear in `/odds` with `commence_time` in the
   past until they finish.
2. Market type: full-game `h2h` (moneyline). Note: this is **full-game ML, not
   per-half** — V5's structural side is 1H, so for the head-to-head test we
   either capture 1H markets if a book lists them, or re-frame V5 at the
   full-game horizon for the sportsbook side. (Kalshi is the 1H-winner venue.)
3. Cost model: 1 request returns **all** current games across all books, so one
   poll covers every live game at once.
4. Quota economics: ~1 req per poll → ~150 polls/game at 60s cadence. Free
   500/mo ≈ **3 games at 60s or ~6–7 at 120s**. Full historical season is
   paid-only (~$30–100). See §3.
5. Suspension states: the endpoint simply omits a book/market when not offered;
   no explicit "suspended" flag.

**Schema as captured (long format, one row per capture × game × book × team)
— matches `flatten_h2h` output:**

| column | dtype | example | notes |
|---|---|---|---|
| `capture_ts` | datetime (UTC, ISO) | `2026-05-26T07:41:10Z` | our poll time |
| `game_id` | str | `197dd95ba7880a2cd6...` | the-odds-api event id (stable per event; needs mapping to nba_api id) |
| `commence_time` | datetime (UTC) | `2026-05-27T00:40:00Z` | scheduled tip; `<= now` ⇒ live |
| `home_team` | str | `"Oklahoma City Thunder"` | full name |
| `away_team` | str | `"San Antonio Spurs"` | full name |
| `book` | str | `"DraftKings"` | venue |
| `book_last_update` | datetime (UTC) | | book's own price timestamp |
| `team` | str | `"Oklahoma City Thunder"` | outcome side |
| `price_american` | int | `-198` | moneyline |
| `implied_prob` | float | 0.664 | computed (still includes vig) |

De-vig and the wide two-sided form are computed downstream by pivoting on
`(capture_ts, game_id, book)` — observed median overround ≈ **4%** at pregame.

**On-disk layout:** `data/interim/odds/capture_{YYYYMMDD}.csv` (crash-safe
append, one file per capture day) + a `.parquet` mirror written on clean exit.

**Status / coverage:** key live; first pregame snapshots of SAS @ OKC captured
2026-05-26. Live in-play capture begins with that game (tip 2026-05-27 00:40Z).

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
| Sportsbook in-play odds (current/live) | 🟢 live capture working | — (free key validated 2026-05-26) |
| Pregame current lines | 🟢 free via §5 endpoint | — |
| Pregame **historical** closing odds | ⏸ | paid the-odds-api plan **or** Kaggle fallback |
| Sportsbook **historical** in-play (full season) | ⏸ | paid the-odds-api plan (~$30–100) |
| Joined live-odds long table | ⏸ | accumulate live captures (#4 + #5) |

**Where we stand (2026-05-26):** the-odds-api free key is live and richer
than expected (9 books, in-play supported). The remaining fork is **coverage,
not access**:
- **Free path:** live-capture playoff games starting tonight → small but *real*
  in-play test set across 9 books. Enough to validate the full V1/V2/V5/V6
  pipeline end-to-end on real prices.
- **Paid path (~$30–119/mo, cancelable):** unlocks the full *historical* in-play
  season → the proper held-out backtest for all six variants.

Decision deferred until we see live data flow through the backtest engine.

---

## 9. Survey: historical in-play odds options (researched 2026-05-26)

We need the **market price at each past moment** (in-play), not one
pregame/closing line per game. That distinction eliminates almost every free
source. Full survey:

| Source | In-play? | Cadence | Cost | Verdict |
|---|---|---|---|---|
| **the-odds-api historical** | ✅ confirmed | 5-min (10-min pre-Sep 2022) | $30–119/mo, **cancelable**; historical bundled; NBA from Jun 2020; Pinnacle + 50 books | **Cleanest paid path — client already built** |
| **Betfair Exchange historical** | ✅ | **1-min** (free BASIC tier) | **FREE** since 2016 | Best free option *if* viable — see caveats |
| SportsDataIO | ✅ since 2019 | varies | enterprise/paid | No advantage over odds-api |
| Kaggle NBA odds sets | ❌ pregame/closing, static | — | free | Can't backtest in-play |
| Odds Warehouse 2006–25 | ❌ open/close only | — | one-time $ | Pregame anchor only |
| sportsbookreviewsonline / OddsBase / RotoWire | ❌ closing only | — | free | Pregame anchor only |
| Moskowitz / Ötting academic data | — | — | proprietary | Unavailable |
| GitHub scrapers | ❌ closing only | — | free | Pregame only |

**Two real contenders for historical in-play:**

1. **the-odds-api historical** — in-play confirmed (a snapshot taken during a
   live game captures that game's in-play odds; completed events drop off but
   the during-game snapshots persist by timestamp). 100K plan ($59) covers a
   season's 5-min snapshots; pull then cancel. Limitation: **5-min cadence** is
   fine for V2 calibration / slow mispricings, too coarse for V5's ~60s event
   overreaction window.

2. **Betfair Exchange free BASIC tier** — 1-min in-play last-traded-price since
   2016 (covers all our PBP seasons), **free**. Caveats: (a) Betfair exchange is
   **geo-restricted in the US** — account/historic-site access from CA may be
   blocked; (b) "Match Odds" settles **full-game incl. OT** → retrain V2 to a
   full-game target; (c) data ships as `.bz2` stream files needing parsing
   (`betfairlightweight` exists).

**Non-obvious insight:** our **live capture (60–90s cadence) beats the paid
historical (5-min) for the V5 event test** — 5-min can't resolve a 1-minute
overreaction. So they're complementary: paid historical → large-sample V2
backtest; live capture → high-resolution V5 events. No single source dominates
(fittingly, the Halawi point).

**Conclusion:** no free, clean, US-accessible source for NBA historical *in-play*
odds exists. Cheapest reliable path = the-odds-api historical at **$59 for one
month**. Betfair is the only free in-play option but carries US-access + parsing
+ horizon caveats.
