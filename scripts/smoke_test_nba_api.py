"""Smoke test for nba_api PBP fetcher.

Pulls one game per season 2019-20 through 2024-25 (six seasons), saves raw JSON
to data/raw/, and prints a summary table of schema parity + timing. Designed
to be safe to re-run: skips fetches whose raw JSON already exists.

Run from repo root:
    uv run python scripts/smoke_test_nba_api.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from src.data.pull_pbp import DATA_RAW, fetch_pbp, first_game_id, season_label

SEASON_START_YEARS = [2019, 2020, 2021, 2022, 2023, 2024]
SLEEP_BETWEEN_REQUESTS_S = 1.0  # be polite to stats.nba.com


def main() -> int:
    rows = []
    schemas: dict[str, tuple[str, ...]] = {}

    for start_year in SEASON_START_YEARS:
        season = season_label(start_year)
        game_id = first_game_id(start_year)
        cached = DATA_RAW / f"pbp_{season}_{game_id}.json"

        if cached.exists():
            raw = json.loads(cached.read_text())
            df_dict = next(
                rs for rs in raw["resultSets"] if rs.get("name", "").lower() in ("playbyplay", "play_by_play")
            ) if "resultSets" in raw else None
            n_events = len(df_dict["rowSet"]) if df_dict else None
            cols: tuple[str, ...] = tuple(df_dict["headers"]) if df_dict else ()
            rows.append(
                {
                    "season": season,
                    "game_id": game_id,
                    "status": "cached",
                    "elapsed_s": 0.0,
                    "n_events": n_events,
                    "n_cols": len(cols),
                }
            )
            schemas[season] = cols
            print(f"[cached] {season}  game={game_id}  events={n_events}  cols={len(cols)}")
            continue

        print(f"[fetch]  {season}  game={game_id} ...", end="", flush=True)
        res = fetch_pbp(game_id=game_id, season=season)
        if res.status != "ok":
            print(f" FAIL ({res.status})")
            rows.append(
                {
                    "season": season,
                    "game_id": game_id,
                    "status": res.status,
                    "elapsed_s": res.elapsed_s,
                    "n_events": None,
                    "n_cols": None,
                }
            )
            time.sleep(SLEEP_BETWEEN_REQUESTS_S)
            continue

        cols = tuple(res.df.columns)
        schemas[season] = cols
        rows.append(
            {
                "season": season,
                "game_id": game_id,
                "status": "ok",
                "elapsed_s": round(res.elapsed_s, 2),
                "n_events": len(res.df),
                "n_cols": len(cols),
            }
        )
        print(f" ok  {res.elapsed_s:.2f}s  events={len(res.df)}  cols={len(cols)}")
        time.sleep(SLEEP_BETWEEN_REQUESTS_S)

    summary = pd.DataFrame(rows)
    print("\n=== Summary ===")
    print(summary.to_string(index=False))

    # Schema parity check
    if len(schemas) >= 2:
        reference_season = next(iter(schemas))
        reference_cols = schemas[reference_season]
        all_match = all(cols == reference_cols for cols in schemas.values())
        print(
            f"\nSchema parity: {'IDENTICAL' if all_match else 'DIFFERS'} across "
            f"{len(schemas)} seasons (reference={reference_season}, {len(reference_cols)} cols)"
        )
        if not all_match:
            for s, cols in schemas.items():
                diff = set(cols) ^ set(reference_cols)
                if diff:
                    print(f"  {s}: differs by {sorted(diff)}")

    out_csv = Path(__file__).resolve().parents[1] / "data" / "raw" / "smoke_test_summary.csv"
    summary.to_csv(out_csv, index=False)
    print(f"\nWrote summary to {out_csv}")

    n_ok = (summary["status"] == "ok").sum() + (summary["status"] == "cached").sum()
    return 0 if n_ok == len(SEASON_START_YEARS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
