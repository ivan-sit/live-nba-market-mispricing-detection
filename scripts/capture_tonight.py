"""One-command live capture for ANY NBA game (free-capture path).

Auto-detects the live game from ESPN (no hardcoded teams), then every cadence
logs a unified per-game row: game state (for the model) + de-vigged sportsbook
consensus across all books (the tradeable game-winner market) + best lines.
Optionally grabs the Kalshi 1H mid if that market resolves and quotes.

One file per game -> data/interim/games/{YYYYMMDD}_{AWAY}{HOME}.csv
Feeds scripts/backtest_pooled.py, which pools every captured game.

Run (during any game, no args needed):
  uv run python scripts/capture_tonight.py
  uv run python scripts/capture_tonight.py --once          # single snapshot
  uv run python scripts/capture_tonight.py --cadence 90
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

import numpy as np
import requests

from src.data.pull_odds import OddsAPIClient
from src.eval.backtest import american_to_prob

UA = {"User-Agent": "Mozilla/5.0 (stats211 research)"}
ESPN_SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
OUT_DIR = REPO_ROOT / "data" / "interim" / "games"
FIELDS = [
    "ts", "date", "away", "home", "state", "period", "clock_sec", "elapsed_half_sec",
    "minute_idx", "away_score", "home_score", "score_diff_home", "recent_run_diff",
    "mkt_home_devig", "mkt_home_american", "mkt_away_american", "n_books",
]


def parse_clock(disp: str) -> float:
    disp = str(disp or "").strip()
    if ":" in disp:
        m, s = disp.split(":")
        return float(m) * 60 + float(s)
    try:
        return float(disp)
    except ValueError:
        return 0.0


def pick_game() -> dict | None:
    """Pick the live ('in') NBA game, else the soonest 'pre' game today."""
    r = requests.get(ESPN_SB, headers=UA, timeout=15); r.raise_for_status()
    events = r.json().get("events", [])
    live, pre = [], []
    for e in events:
        c = e["competitions"][0]; st = c["status"]
        comp = {x["homeAway"]: x for x in c["competitors"]}
        g = {
            "state": st["type"]["state"], "period": int(st.get("period") or 0),
            "clock_sec": parse_clock(st.get("displayClock", "0")),
            "home": comp["home"]["team"]["abbreviation"], "away": comp["away"]["team"]["abbreviation"],
            "home_name": comp["home"]["team"]["name"], "away_name": comp["away"]["team"]["name"],
            "home_score": int(comp["home"].get("score") or 0), "away_score": int(comp["away"].get("score") or 0),
        }
        (live if g["state"] == "in" else pre if g["state"] == "pre" else []).append(g)
    return live[0] if live else (pre[0] if pre else None)


def consensus(odds_games: list[dict], home_name: str, away_name: str):
    """(median devig home prob, median home american, median away american, n_books)."""
    for g in odds_games:
        if home_name in g.get("home_team", "") and away_name in g.get("away_team", ""):
            dv, ha, aa = [], [], []
            for b in g.get("bookmakers", []):
                mk = next((m for m in b.get("markets", []) if m.get("key") == "h2h"), None)
                if not mk:
                    continue
                o = {x["name"]: x["price"] for x in mk.get("outcomes", [])}
                hp = next((v for k, v in o.items() if home_name in k), None)
                ap = next((v for k, v in o.items() if away_name in k), None)
                if hp is not None and ap is not None:
                    ih, ia = american_to_prob(hp), american_to_prob(ap)
                    dv.append(ih / (ih + ia)); ha.append(hp); aa.append(ap)
            if dv:
                return float(np.median(dv)), float(np.median(ha)), float(np.median(aa)), len(dv)
    return None, None, None, 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cadence", type=int, default=90)
    ap.add_argument("--max-minutes", type=int, default=210)
    ap.add_argument("--quota-floor", type=int, default=20)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    g0 = pick_game()
    if g0 is None:
        print("No NBA game on ESPN today. Try again on a game day."); return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = OUT_DIR / f"{date}_{g0['away']}{g0['home']}.csv"
    write_header = not out.exists()
    f = out.open("a", newline=""); w = csv.DictWriter(f, fieldnames=FIELDS)
    if write_header:
        w.writeheader()
    print(f"Game: {g0['away']} @ {g0['home']} (state={g0['state']})  ->  {out}")

    client = OddsAPIClient()
    deadline = time.time() + args.max_minutes * 60
    hist: list[tuple[float, int, int]] = []
    try:
        while True:
            ts = datetime.now(timezone.utc).isoformat()
            g = pick_game()
            if g is None or (g["home"] != g0["home"]):
                print(f"[{ts}] target game not found / changed; stopping."); break
            if g["state"] == "pre":
                print(f"[{ts}] pre-game; waiting.");
                if args.once: break
                time.sleep(args.cadence); continue
            if g["state"] == "post":
                print(f"[{ts}] game final {g['away']} {g['away_score']}-{g['home_score']} {g['home']}."); break

            period, clock = g["period"], g["clock_sec"]
            elapsed_half = (min(period, 2) - 1) * 720 + (720 - clock) if period <= 2 else 1440
            minute_idx = int(min(24, max(1, elapsed_half // 60)))
            hs, as_ = g["home_score"], g["away_score"]
            hist.append((elapsed_half, hs, as_))
            run = 0
            for e_sec, eh, ea in reversed(hist):
                if elapsed_half - e_sec >= 120:
                    run = (hs - eh) - (as_ - ea); break

            try:
                odds = client.nba_odds(markets="h2h")
                q = client.last_quota
            except Exception as e:  # noqa: BLE001
                print(f"[{ts}] odds error {e}"); odds, q = [], None
            mh, ha, aa, nb = consensus(odds, g["home_name"], g["away_name"])

            w.writerow({
                "ts": ts, "date": date, "away": g["away"], "home": g["home"], "state": g["state"],
                "period": period, "clock_sec": clock, "elapsed_half_sec": elapsed_half,
                "minute_idx": minute_idx, "away_score": as_, "home_score": hs,
                "score_diff_home": hs - as_, "recent_run_diff": run,
                "mkt_home_devig": mh, "mkt_home_american": ha, "mkt_away_american": aa, "n_books": nb,
            }); f.flush()
            mkt = f"{mh:.3f}({nb}bk)" if mh is not None else "no-mkt"
            print(f"[{ts}] P{period} {clock:4.0f}s | {g['away']} {as_}-{hs} {g['home']} "
                  f"(diff {hs-as_:+d}, min{minute_idx}) | mkt_home={mkt} | quota={q.remaining if q else '?'}")

            if args.once:
                break
            if q and q.remaining is not None and q.remaining <= args.quota_floor:
                print("quota floor; stopping."); break
            if time.time() >= deadline:
                print("max-minutes; stopping."); break
            time.sleep(args.cadence)
    except KeyboardInterrupt:
        print("\nstopped (Ctrl-C).")
    finally:
        f.close()
        print(f"Logged -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
