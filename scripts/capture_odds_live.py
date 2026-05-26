"""Live in-play odds capture for the-odds-api free tier.

Polls NBA h2h (moneyline) across all books every ~90s and appends per-tick
rows to a crash-safe CSV (one row per game x book x team). Designed to run
during a live game, e.g. tonight's SAS @ OKC.

USAGE (run from repo root):

  # single snapshot to confirm it works (1 request):
  uv run python scripts/capture_odds_live.py --once

  # capture tonight's game, only Thunder/Spurs, 90s cadence, stop after 3.5h:
  uv run python scripts/capture_odds_live.py --teams "Thunder,Spurs" --cadence 90 --max-minutes 210

  # capture every NBA game currently returned:
  uv run python scripts/capture_odds_live.py --cadence 90

Stops automatically when: quota floor hit, max-minutes elapsed, or Ctrl-C.
Output: data/interim/odds/capture_<YYYYMMDD>.csv  (+ .parquet on clean exit)
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data.pull_odds import OddsAPIClient, flatten_h2h  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "interim" / "odds"
FIELDNAMES = [
    "capture_ts",
    "game_id",
    "commence_time",
    "home_team",
    "away_team",
    "book",
    "book_last_update",
    "team",
    "price_american",
    "implied_prob",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _matches(game: dict, team_filters: list[str], match_all: bool) -> bool:
    if not team_filters:
        return True
    blob = f"{game.get('home_team','')} {game.get('away_team','')}".lower()
    hits = [t.lower() in blob for t in team_filters]
    return all(hits) if match_all else any(hits)


def _is_live(game: dict, now: datetime) -> bool:
    ct = game.get("commence_time", "")
    try:
        start = datetime.fromisoformat(ct.replace("Z", "+00:00"))
    except ValueError:
        return False
    return start <= now


def _overround_readout(rows: list[dict]) -> str:
    """Quick console signal: median two-sided overround across books, per game."""
    by_gb: dict[tuple, float] = {}
    for r in rows:
        by_gb.setdefault((r["game_id"], r["book"]), 0.0)
        by_gb[(r["game_id"], r["book"])] += r["implied_prob"]
    if not by_gb:
        return "no quotes"
    ovr = [v - 1.0 for v in by_gb.values()]
    ovr.sort()
    med = ovr[len(ovr) // 2]
    return f"{len(by_gb)} game-books, median overround {med*100:.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", default="", help="comma-separated substrings to match (default: all games)")
    ap.add_argument("--match-all", action="store_true", help="require ALL --teams substrings (default: any)")
    ap.add_argument("--cadence", type=int, default=90, help="seconds between polls")
    ap.add_argument("--max-minutes", type=int, default=210, help="hard stop after this many minutes")
    ap.add_argument("--quota-floor", type=int, default=20, help="stop if remaining requests <= this")
    ap.add_argument("--once", action="store_true", help="single poll then exit")
    ap.add_argument("--include-pregame", action="store_true", help="capture even before tip-off (burns quota)")
    args = ap.parse_args()

    team_filters = [t.strip() for t in args.teams.split(",") if t.strip()]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / f"capture_{datetime.now().strftime('%Y%m%d')}.csv"
    write_header = not out_csv.exists()

    client = OddsAPIClient()
    deadline = time.time() + args.max_minutes * 60
    polls = 0
    rows_written = 0

    print(f"Writing -> {out_csv}")
    print(f"teams={team_filters or 'ALL'}  cadence={args.cadence}s  max={args.max_minutes}m  quota_floor={args.quota_floor}")
    print("Ctrl-C to stop early (data is flushed every poll).\n")

    f = out_csv.open("a", newline="")
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    if write_header:
        writer.writeheader()

    try:
        while True:
            now = datetime.now(timezone.utc)
            ts = _now_iso()
            try:
                games = client.nba_odds(markets="h2h")
            except Exception as e:  # noqa: BLE001
                print(f"[{ts}] poll failed: {e} — retrying next cadence")
                if args.once:
                    return 1
                time.sleep(args.cadence)
                continue

            polls += 1
            q = client.last_quota
            sel = [g for g in games if _matches(g, team_filters, args.match_all)]
            live = [g for g in sel if _is_live(g, now)]
            target = sel if args.include_pregame else live

            rows = flatten_h2h(target, capture_ts=ts)
            for r in rows:
                writer.writerow(r)
            f.flush()
            rows_written += len(rows)

            status = "LIVE" if live else ("pregame" if sel else "no match")
            print(
                f"[{ts}] poll#{polls} {status}: {len(target)} games, "
                f"{_overround_readout(rows)} | wrote {len(rows)} rows "
                f"(total {rows_written}) | quota left={q.remaining if q else '?'}"
            )

            if args.once:
                break
            if q and q.remaining is not None and q.remaining <= args.quota_floor:
                print(f"\nStopping: quota floor reached (remaining={q.remaining}).")
                break
            if time.time() >= deadline:
                print(f"\nStopping: max-minutes ({args.max_minutes}) elapsed.")
                break
            time.sleep(args.cadence)
    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl-C).")
    finally:
        f.close()

    # Convert the session CSV to parquet for downstream loading.
    try:
        import pandas as pd

        df = pd.read_csv(out_csv)
        pq = out_csv.with_suffix(".parquet")
        df.to_parquet(pq, index=False)
        print(f"\nDone. {rows_written} rows this session. Parquet -> {pq} ({len(df)} total rows)")
    except Exception as e:  # noqa: BLE001
        print(f"\nDone. CSV saved. (parquet conversion skipped: {e})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
