# Unified Game-State Schema (DRAFT — finalize by end of D4)

The model trains on a long table where each row is one in-game state observation
for one game. The exact granularity (per-possession vs per-N-second tick) is
**open** — see DECISIONS.md.

## Tentative columns

| column | dtype | description | pregame / in-game | leakage risk |
|---|---|---|---|---|
| game_id | str | NBA game identifier | identifier | n/a |
| season | str | e.g., "2023-24" | identifier | n/a |
| timestamp_idx | int | monotonic tick index within game | identifier | n/a |
| seconds_remaining | int | seconds remaining in game (0 = end) | in-game | none |
| quarter | int | 1–4, plus 5+ for OT | in-game | none |
| score_diff_home | int | home_score − away_score at tick | in-game | none |
| possession_home | bool | 1 if home has the ball at tick | in-game | none |
| recent_run_home | int | home points minus away points scored in last 120s | in-game | low |
| timeouts_home | int | home timeouts remaining | in-game | none |
| timeouts_away | int | away timeouts remaining | in-game | none |
| fouls_home | int | home team fouls (qtr) | in-game | none |
| fouls_away | int | away team fouls (qtr) | in-game | none |
| pregame_spread_home | float | closing pregame point spread for home (negative = favored) | pregame | none |
| pregame_total | float | closing pregame total | pregame | none |
| market_prob_home_devig | float | de-vigged market-implied home WP at tick (test set only) | in-game | DO NOT USE AS FEATURE |
| y_home_win | int | final outcome (1 if home won) | label | n/a |

## Joins

- PBP → game-state ticks: roll up PBP events to chosen granularity; track
  running score, possession, timeouts, fouls.
- Pregame odds → game-state: one-to-many join on `game_id`.
- Live odds → game-state: match nearest 5-min snapshot ≤ tick time. **Only used
  for evaluation**, never as a feature.

## Leakage checks (run before every model fit)

1. Confirm `y_home_win` is constant within game and not present as any feature.
2. Confirm no future-derived feature (e.g., "comeback occurred later") sneaks in.
3. Confirm pregame features are computed strictly from data available before
   tipoff (closing line ok; in-game line not ok).
4. Confirm splits are at the game level via `GroupKFold(game_id)`.
