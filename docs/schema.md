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
- Live odds → game-state: match nearest snapshot ≤ tick time per venue. **Only used
  for evaluation**, never as a feature.

## Multi-venue live-odds table (long format)

For the variant bake-off we keep prices in long format — one row per
(game_id × snapshot_ts × venue). This makes the cross-venue analyses (V1, V3,
V6) natural without forcing a wide-table reshape.

| column | dtype | notes |
|---|---|---|
| game_id | str | join key |
| snapshot_ts | datetime (UTC) | exact snapshot time |
| venue | str | `pinnacle`, `draftkings`, `fanduel`, `kalshi`, etc. |
| market | str | `moneyline`, `spread`, `total` |
| home_price | float | American odds (sportsbooks) or YES contract price 0–1 (Kalshi) |
| away_price | float | "" |
| home_implied_prob_raw | float | computed |
| home_implied_prob_devig | float | computed; for Kalshi, raw ≈ devig (no vig, just spread) |
| overround | float | per-snapshot |
| market_status | str | `open`/`suspended`/`closed` |
| volume_hint | float \| null | Kalshi: 24h volume; sportsbooks: usually null |

**Consensus** is computed downstream as the median (or volume-weighted median)
of `home_implied_prob_devig` across venues per `(game_id, snapshot_ts)`.

## Leakage checks (run before every model fit)

1. Confirm `y_home_win` is constant within game and not present as any feature.
2. Confirm no future-derived feature (e.g., "comeback occurred later") sneaks in.
3. Confirm pregame features are computed strictly from data available before
   tipoff (closing line ok; in-game line not ok).
4. Confirm splits are at the game level via `GroupKFold(game_id)`.
