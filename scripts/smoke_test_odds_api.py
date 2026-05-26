"""Smoke test the-odds-api free tier.

Answers the only questions that matter before we commit:
  1. Does the key work? How much quota is left?
  2. Is NBA active right now (any games to capture)?
  3. Which books carry NBA, and is there an in-play (live) game?

Run from repo root:
    uv run python scripts/smoke_test_odds_api.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data.pull_odds import OddsAPIClient  # noqa: E402


def main() -> int:
    client = OddsAPIClient()

    print("[1] Validate key via /sports")
    sports = client.list_sports()
    q = client.last_quota
    print(f"    OK — {len(sports)} sports listed.  quota: remaining={q.remaining} used={q.used}")
    nba = [s for s in sports if s.get("key") == "basketball_nba"]
    if nba:
        print(f"    NBA active={nba[0].get('active')}  title={nba[0].get('title')}")
    else:
        print("    WARNING: basketball_nba not in sports list")

    print("\n[2] Pull current NBA h2h (moneyline) odds")
    games = client.nba_odds(markets="h2h")
    q = client.last_quota
    print(f"    {len(games)} games returned.  quota: remaining={q.remaining} used={q.used}")

    now = datetime.now(timezone.utc)
    books = set()
    live = []
    for g in games:
        ct = g.get("commence_time", "")
        try:
            start = datetime.fromisoformat(ct.replace("Z", "+00:00"))
        except ValueError:
            start = None
        is_live = start is not None and start <= now
        for b in g.get("bookmakers", []):
            books.add(b.get("title"))
        if is_live:
            live.append(g)

    print(f"    distinct books seen: {sorted(books)}")
    print(f"    in-play (already started) games: {len(live)}")

    if games:
        g = games[0]
        print(f"\n[3] Sample game: {g.get('away_team')} @ {g.get('home_team')}  start={g.get('commence_time')}")
        for b in g.get("bookmakers", [])[:3]:
            mk = next((m for m in b.get("markets", []) if m.get("key") == "h2h"), None)
            prices = {o["name"]: o["price"] for o in mk.get("outcomes", [])} if mk else {}
            print(f"    {b.get('title'):16s} h2h={prices}")

    print("\nVERDICT:")
    if live:
        print("  GREEN — in-play NBA games available NOW. Live-capture loop is viable.")
    elif games:
        print("  AMBER — NBA games scheduled but none live this instant. Re-run during a game.")
    else:
        print("  RED — no NBA games returned (offseason or between rounds). Check back near tip-off.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
