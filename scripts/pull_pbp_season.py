"""Pull NBA play-by-play for a full regular season.

Iterates game_ids "002{YY}{NNNNN}" for NNNNN = 1..1230 (typical reg-season size).
Saves one parquet per game and a season-level concat at the end.
Idempotent: existing per-game parquets are skipped.

Run from repo root:
    uv run python scripts/pull_pbp_season.py --season-start 2023 --max-games 1230
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from src.data.pull_pbp import fetch_pbp, first_game_id, season_label  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season-start", type=int, default=2023)
    ap.add_argument("--max-games", type=int, default=1230)
    ap.add_argument("--sleep", type=float, default=0.5, help="Seconds between requests.")
    ap.add_argument("--retry-on-fail", type=int, default=2)
    args = ap.parse_args()

    season = season_label(args.season_start)
    out_dir = REPO_ROOT / "data" / "interim" / "pbp" / season
    out_dir.mkdir(parents=True, exist_ok=True)
    yy = args.season_start % 100

    print(f"Pulling season {season} regular-season PBP up to {args.max_games} games", flush=True)
    rows = []
    n_ok = n_skip = n_fail = 0
    consecutive_failures = 0

    for n in range(1, args.max_games + 1):
        game_id = f"002{yy:02d}{n:05d}"
        out_pq = out_dir / f"{game_id}.parquet"
        if out_pq.exists():
            n_skip += 1
            continue

        # try with retries
        last_err = None
        for attempt in range(args.retry_on_fail + 1):
            res = fetch_pbp(game_id=game_id, season=season, save_raw=False)
            if res.status == "ok" and len(res.df) > 0:
                res.df["game_id"] = game_id
                res.df["season"] = season
                res.df.to_parquet(out_pq, index=False)
                rows.append({"game_id": game_id, "n_events": len(res.df), "elapsed_s": res.elapsed_s})
                if n_ok % 25 == 0:
                    print(f"  [{n_ok + 1:4d}] {game_id}  events={len(res.df)}  t={res.elapsed_s:.1f}s", flush=True)
                n_ok += 1
                consecutive_failures = 0
                break
            last_err = res.status
            time.sleep(1.0 * (attempt + 1))
        else:
            print(f"  [FAIL] {game_id}: {last_err}", flush=True)
            n_fail += 1
            consecutive_failures += 1
            # The NBA's regular season game IDs run out at some point well before 1230 if
            # the season was shortened. After 20 consecutive failures we conclude we've
            # hit the end of valid game IDs.
            if consecutive_failures >= 20:
                print(f"  -> 20 consecutive failures, assuming end of season; stopping at n={n}")
                break

        time.sleep(args.sleep)

    summary = pd.DataFrame(rows)
    summary_csv = out_dir / "_pull_summary.csv"
    summary.to_csv(summary_csv, index=False)
    print(f"\nDone. season={season}  ok={n_ok}  skipped_cached={n_skip}  failed={n_fail}")
    print(f"Per-game parquets in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
