"""Pooled game-winner backtest across every captured game.

Scans data/interim/games/*.csv (written by capture_tonight.py), applies the
full-game model to each game's 1st-half ticks, settles each game on its real
final (fetched from ESPN by date), and pools everything through the verified
backtest engine. Re-run after each new game — the CI tightens as games add up.

Run:  uv run python scripts/backtest_pooled.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import joblib
import pandas as pd
import requests

from src.eval import backtest as bt

UA = {"User-Agent": "Mozilla/5.0 (stats211 research)"}
ESPN_SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
GAMES_DIR = REPO_ROOT / "data" / "interim" / "games"
MODEL = REPO_ROOT / "models" / "v2_fullgame.joblib"


def final_outcome(date: str, home: str, away: str):
    """(y_home_win, 'AWAY a - h HOME', is_final) for a game on YYYYMMDD."""
    try:
        r = requests.get(ESPN_SB, headers=UA, params={"dates": date}, timeout=15); r.raise_for_status()
        for e in r.json().get("events", []):
            c = e["competitions"][0]
            comp = {x["homeAway"]: x for x in c["competitors"]}
            if comp["home"]["team"]["abbreviation"] == home and comp["away"]["team"]["abbreviation"] == away:
                hs, as_ = int(comp["home"]["score"]), int(comp["away"]["score"])
                is_final = c["status"]["type"]["state"] == "post"
                return int(hs > as_), f"{away} {as_}-{hs} {home}", is_final
    except Exception as e:  # noqa: BLE001
        print(f"  ESPN final fetch failed for {date} {away}@{home}: {e}")
    return None, "unknown", False


def main() -> int:
    files = sorted(GAMES_DIR.glob("*.csv")) if GAMES_DIR.exists() else []
    if not files:
        print(f"No captured games in {GAMES_DIR}. Run capture_tonight.py during a game.")
        print("(Tonight's SAS@OKC used the older split logs — see backtest_game_winner_live.py.)")
        return 0

    bundle = joblib.load(MODEL)
    feats = bundle["features"]
    frames, summary = [], []

    for fp in files:
        df = pd.read_csv(fp)
        df = df[(df["state"] == "in") & (df["period"] <= 2) & df["mkt_home_devig"].notna()].copy()
        if df.empty:
            print(f"  {fp.name}: no in-1H ticks with a market quote — skip"); continue
        date, home, away = str(df["date"].iloc[0]), df["home"].iloc[0], df["away"].iloc[0]
        y, final_str, is_final = final_outcome(date, home, away)
        if y is None:
            print(f"  {fp.name}: no outcome yet — skip"); continue
        df["p_hat"] = bundle["iso"].transform(bundle["xgb"].predict_proba_home_wins(df[feats]))
        df = df.rename(columns={"mkt_home_devig": "p_market_home_devig",
                                "mkt_home_american": "home_odds_american",
                                "mkt_away_american": "away_odds_american"})
        df["game_id"] = fp.stem
        df["y_home_win"] = y
        frames.append(df[["game_id", "p_hat", "p_market_home_devig", "home_odds_american",
                          "away_odds_american", "y_home_win", "score_diff_home"]])
        summary.append((fp.stem, len(df), final_str, "FINAL" if is_final else "live"))
        print(f"  {fp.name}: {len(df)} ticks, {final_str} ({'FINAL' if is_final else 'not final'})")

    if not frames:
        print("No settled games to pool yet."); return 0
    allt = pd.concat(frames, ignore_index=True)
    ng = allt["game_id"].nunique()
    print(f"\n{'='*70}\nPOOLED across {ng} game(s), {len(allt)} ticks\n{'='*70}")
    for thr in (0.02, 0.04, 0.06):
        print(f"  {bt.simulate(allt, name=f'model (thr={thr:.0%})', threshold=thr, kelly_mult=0.25)}")
    print("\nBaselines:")
    for rule in ("favorite", "trailing", "random"):
        try:
            print(f"  {bt.baseline_simulate(allt, rule=rule)}")
        except Exception as e:  # noqa: BLE001
            print(f"  baseline {rule}: {e}")
    print(f"\n⚠️  {ng} game(s) — still directional. CI tightens as you capture more.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
