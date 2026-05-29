# Data Schema & Usage Map

Every dataset the project produces or consumes, its columns, where it lives on
disk, and which scripts read or write it. Use this when wiring a new variant or
debugging a join.

> **Storage convention.** Everything under `data/` is **gitignored** — only the
> `.gitkeep` markers go to GitHub. Acquired data lives on the local machine.

---

## Data flow at a glance

```
   SOURCE (external)            DERIVED (we build)              CONSUMERS
 ──────────────────────  ─────────────────────────────  ───────────────────────
  nba_api PBP        ──► per-minute 1H snapshots ────►  V2 model · V5 events
  (free, 2,460 games)    events table

  the-odds-api ML    ──► sportsbook odds capture  ────► live pilot backtest
  (free key, 9 books)    unified game capture           backtest_game_winner_*

  Kalshi 1H winner   ──► candle parquet (in-play) ────► archived Kalshi backtest
  (free public API)      (re-pulled from PBP anchors)

  ESPN scoreboard    ──► live game-state poll ───────►  signal monitor
  (free, live)           outcome lookups               capture_tonight

                          ┌──────────────────┐
                          │ models/ joblib    │ ◄── trained by
                          │  v2_xgb_iso       │     train_and_save_v2.py
                          │  v2_fullgame      │     train_fullgame_model.py
                          └──────────────────┘
```

---

## 1. NBA play-by-play (raw + parquet)

**Source:** `nba_api.stats.endpoints.playbyplayv3` (free, no auth).
**On disk:** `data/interim/pbp/{season}/{game_id}.parquet` — one parquet per
game; **2,460 games** (1,230 × 2 seasons).
**Pulled by:** `scripts/pull_pbp_season.py` → `src/data/pull_pbp.py::fetch_pbp`.
**Schema (24 cols, one row per PBP event):**

| column | dtype | example | used for |
|---|---|---|---|
| `gameId` | str | `"0022300001"` | join key |
| `actionNumber` | int | `4` | event sequence in game |
| `clock` | str (ISO 8601) | `"PT07M22.00S"` | seconds left in period |
| `period` | int | `2` | quarter 1–4 (5+ = OT) |
| `teamId` | int | `1610612747` | scoring/acting team |
| `teamTricode` | str | `"LAL"` | join to schedules |
| `personId` | int | `2544` | player |
| `playerName` | str | `"LeBron James"` | display |
| `scoreHome`, `scoreAway` | str→int | `"48"`, `"45"` | running scores |
| `shotResult` | str | `"Made"`/`"Missed"` | FG outcome |
| `shotValue` | int | `3` | 2- or 3-pt |
| `isFieldGoal` | int (0/1) | `1` | flag for V5 events |
| `actionType` | str | `"Made Shot"`, `"period"` | event kind |
| `subType` | str | `"Jump Shot"`, `"start"` | sub-kind |
| `description` | str | `"Start of 1st Period (9:46 PM EST)"` | wall-clock anchor parsing |
| `shotDistance`, `xLegacy`, `yLegacy` | int | `18`, `-141`, `76` | unused (kept for parity) |
| `actionId`, `videoAvailable`, `location`, `pointsTotal` | mixed | | unused |

**Schema parity:** identical columns confirmed across 2019-20 through 2024-25
(see `data/raw/smoke_test_summary.csv`).

---

## 2. Per-minute 1H snapshots (derived from PBP)

**Built by:** `src/data/build_dataset.py::build_season(season)` → walks PBP and
captures state at game-minute boundaries 1..24 of the 1st half.
**Persisted:** computed on demand (not written to disk by default; the V2
training scripts run it fresh).
**Volume:** 24 rows × 1,230 games = **29,520 rows / season** (59k total).

| column | dtype | use |
|---|---|---|
| `game_id` | str | join key |
| `season` | str | e.g. `"2023-24"` |
| `minute_idx` | int 1..24 | **model feature** |
| `seconds_elapsed` | int | `minute_idx * 60` |
| `period` | int (1 or 2) | **model feature** |
| `score_home`, `score_away` | int | running |
| `score_diff_home` | int | **model feature** |
| `recent_run_home`, `recent_run_away` | int | pts in last 120s |
| `recent_run_diff` | int | **model feature** |
| `home_team_id`, `away_team_id` | int | for joins to odds |
| `home_tricode`, `away_tricode` | str | for joins to Kalshi suffixes |
| `y_home_wins_1h` | int (0/1) | **V2 target** |
| `y_tie_1h` | int (0/1) | dropped from training |
| `y_home_wins_game` | int (0/1) | **full-game-model target** |
| `final_score_home_1h`, `final_score_away_1h` | int | sanity checks |
| `final_score_home_game`, `final_score_away_game` | int | sanity checks |

**Consumed by:**
- `scripts/train_and_save_v2.py` (target: `y_home_wins_1h`)
- `scripts/train_fullgame_model.py` (target: `y_home_wins_game`)
- `scripts/run_v5_*.py` (joined to events for `p̂` lookup)

---

## 3. Events table (V5 input · derived from PBP)

**Built by:** `src/analysis/variant_v5_event.py::extract_events_from_pbp`.
**Volume:** **52,039 1st-half made-FG events** across 2024-25 alone. Filtered to
~4,596 H1 events and ~2,162 H4 events.

| column | dtype | notes |
|---|---|---|
| `game_id` | str | join to snapshots |
| `season` | str | |
| `actionNumber` | int | PBP event id |
| `sec_elapsed` | float | seconds from tipoff |
| `period` | int | quarter |
| `team_id_scoring` | int | who scored |
| `shot_value` | int | 2 or 3 |
| `pre_score_home`, `pre_score_away` | int | state just before event |
| `pre_diff_for_scorer` | int | positive ⇒ scorer was trailing |
| `home_scored` | bool | |
| `event_type` | str | `"made_fg2"` / `"made_fg3"` |

**Consumed by:** V5 H1/H4 tests (`filter_h1_events`, `filter_h4_events` →
`compute_structural_shift` → block bootstrap).

---

## 4. Sportsbook in-play odds capture

**Source:** the-odds-api v4 `/v4/sports/basketball_nba/odds/` — full-game
moneyline (`h2h`) across 9 books (free key, 500 req/mo).
**Captured by:** `scripts/capture_odds_live.py` (per-team filter mode).
**On disk:** `data/interim/odds/capture_{YYYYMMDD}.csv` (CSV append, crash-safe).

| column | dtype | example | notes |
|---|---|---|---|
| `capture_ts` | ISO datetime (UTC) | `"2026-05-26T07:41:10Z"` | our poll time |
| `game_id` | str | `"197dd95ba7880a2cd6..."` | the-odds-api event id |
| `commence_time` | ISO datetime (UTC) | `"2026-05-27T00:40:00Z"` | scheduled tip |
| `home_team`, `away_team` | str | `"Oklahoma City Thunder"` | full names |
| `book` | str | `"DraftKings"` | venue |
| `book_last_update` | ISO datetime (UTC) | | book's own price ts |
| `team` | str | full team name | outcome side |
| `price_american` | int | `-188` | moneyline |
| `implied_prob` | float (0–1) | `0.652` | computed (includes vig) |

**Tonight's pilot:** 1,151 rows over the full SAS@OKC game from 6 books.
**Consumed by:** `scripts/backtest_game_winner_live.py` (joins to game state on
timestamp).

---

## 5. Live signal monitor log (model + Kalshi 1H · paper trading)

**Written by:** `scripts/live_signal_monitor.py` during a live game.
**On disk:** `data/interim/live_signals/signals_{event}.csv`.

| column | dtype | from | use |
|---|---|---|---|
| `ts` | ISO (UTC) | poll time | join key |
| `state` | str | ESPN | `pre`/`in`/`post` |
| `period`, `clock_sec` | int, float | ESPN | feature derivation |
| `elapsed_half_sec`, `minute_idx` | int | derived | feature |
| `home`, `away` | str | ESPN | tricode |
| `home_score`, `away_score`, `score_diff_home` | int | ESPN | feature + outcome |
| `recent_run_diff` | int | tracked across polls | feature |
| `p_model_home_1h` | float | V2 1H model | model prob |
| `k_okc_mid`, `k_sas_mid`, `k_tie_mid` | float | Kalshi mid | market prices |
| `p_market_home_devig` | float | 3-way de-vig | for edge |
| `edge`, `signal`, `kelly_fraction`, `paper_stake` | mixed | computed | paper trade |

**Tonight's pilot:** 43 rows · Kalshi 1H stayed `no-quote` all night.
**Consumed by:** `scripts/backtest_game_winner_live.py` (game-state side).

---

## 6. Unified per-game capture (the free path going forward)

**Written by:** `scripts/capture_tonight.py` (auto-detecting; one command per
game, no hardcoded teams).
**On disk:** `data/interim/games/{YYYYMMDD}_{AWAY}{HOME}.csv` (one file per game).
**Schema (one row per poll, full game):**

| column | dtype | notes |
|---|---|---|
| `ts` | ISO (UTC) | poll time |
| `date`, `away`, `home` | str | game id parts |
| `state` | str | `pre`/`in`/`post` |
| `period`, `clock_sec`, `elapsed_half_sec`, `minute_idx` | int/float | game time |
| `away_score`, `home_score`, `score_diff_home`, `recent_run_diff` | int | features |
| `mkt_home_devig` | float | **median de-vigged consensus across books** |
| `mkt_home_american`, `mkt_away_american` | float | median american prices |
| `n_books` | int | books available at that tick |

**Consumed by:** `scripts/backtest_pooled.py` — scans all unified game logs,
settles each on its ESPN final, pools through the engine.

---

## 7. Kalshi 1H-winner candles (peer market · 1-min OHLC)

**Source:** Kalshi public market-data API
(`https://external-api.kalshi.com/trade-api/v2/markets/{ticker}/candlesticks`).
**On disk:** `data/interim/kalshi/KXNBA1HWINNER/{event_ticker}.parquet`.
**Important fix:** the **original** pull window was wrong (saved pre-game
quotes). The re-pull in `scripts/backtest_kalshi_archive.py` uses the PBP
period-start/end anchors as the **in-play** window — now yields 60–70 real
candles per market per game.

**Schema (one row per (market_ticker, end_ts), long-format parquet):**

| column | dtype | notes |
|---|---|---|
| `event_ticker` | str | e.g. `"KXNBA1HWINNER-26MAY28OKCSAS"` (one per game) |
| `market_ticker` | str | `...-OKC` / `...-SAS` / `...-TIE` (3 outcomes per event) |
| `end_ts` | int (epoch s) | end of the 1-minute window |
| `open_dollars`, `close_dollars`, `high_dollars`, `low_dollars`, `mean_dollars` | float (0–1) | OHLC prices in **dollars** (not cents) |
| `yes_bid_close`, `yes_ask_close` | float (0–1) | mid from these = market prob |
| `volume_fp` | float | $ traded that minute |
| `open_interest_fp` | float | $ open interest at end of minute |

**5 games with in-play candles** retrieved so far (DENMIN Apr 30, TORCLE May 3,
MINSAS May 4, CLEDET May 13, **OKCSAS May 28 = Game 6**).
**Consumed by:** `scripts/backtest_kalshi_archive.py` — re-pulls with the
correct in-play window, builds a 1-min grid, forward-fills, de-vigs 3 ways,
joins to game state via piecewise-linear wall-clock↔game-elapsed mapping.

---

## 8. Trained model artifacts

**On disk:** `models/v2_*.joblib` (gitignored, regenerated by the train scripts).

| file | predicts | features | trained on | OOS Brier |
|---|---|---|---|---|
| `v2_xgb_isotonic.joblib` | P(home wins **1st half**) | `[minute_idx, score_diff_home, recent_run_diff, period]` | 2023-24 | **0.149** (on 2024-25) |
| `v2_fullgame.joblib` | P(home wins **full game**) | same | 2023-24 | 0.207 (in-sample) |

**Bundle shape:** `{"xgb": FittedXGB, "iso": FittedIsotonic, "features": list[str]}`.
**Built by:** `scripts/train_and_save_v2.py` and `scripts/train_fullgame_model.py`.
**Consumed by:** every backtest script + the live signal monitor.

---

## 9. Outputs (results, figures, deck)

| | path | produced by |
|---|---|---|
| append-only results log | `reports/results_log.md` | manually after each backtest |
| deck figures (PNG) | `slides/figures/*.png` | `scripts/generate_slide_figures.py` |
| PowerPoint deck | `slides/final_deck.pptx` | `node slides/build.js` |
| speaker script | `slides/speaker_script.md` | manual |

---

## How the joins actually work

The two non-obvious joins are worth spelling out:

**Live game-winner backtest** (`backtest_game_winner_live.py`):
```
signal_log[ts, game_state, features] ──┐
                                       ├─► merge_asof on ts (≤2 min)
odds_log[capture_ts, book consensus] ──┘    → per-tick (p̂_game, p_market_devig)
                                            → edge, Kelly, settle, bootstrap
```

**Archived Kalshi backtest** (`backtest_kalshi_archive.py`):
```
PBP descriptions ──► "Start of Nth Period (H:MM PM)" → period-anchor epochs
                                                        ↓
                                            piecewise-linear map
                                            wall-clock ↔ game-elapsed
                                                        ↓
Kalshi candles[end_ts] ──► forward-fill to 1-min grid → mid per market
                                                        ↓
                       de-vig 3-way → p_market_devig
                                                        ↓
                              snapshots[minute_idx] → V2 p̂
                                                        ↓
                              edge, Kelly, settle (via 1H winner)
```
