"""Post-game backtest: full-game model vs live sportsbook game-winner odds.

Joins the two live logs on wall-clock timestamp:
  - signal monitor log -> game state (score_diff, minute, period) per minute
  - odds capture log   -> 6-book game-winner moneyline per ~90s

Applies the full-game model (models/v2_fullgame.joblib) to the game state,
de-vigs the sportsbook consensus, computes edge, runs the verified backtest
engine, and SETTLES on the final game result (fetched from ESPN; if the game
isn't final yet, it uses the current leader as a provisional outcome and says
so).

Coverage is the 1st-half window (where our model + the signal log have game
state). n = 1 game -> directional proof, not a result.

Run:  uv run python scripts/backtest_game_winner_live.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import joblib
import numpy as np
import pandas as pd
import requests

from src.eval import backtest as bt

UA = {"User-Agent": "Mozilla/5.0 (stats211 research)"}
ESPN_SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
MODEL = REPO_ROOT / "models" / "v2_fullgame.joblib"
SIGNAL_LOG = REPO_ROOT / "data" / "interim" / "live_signals" / "signals_KXNBA1HWINNER-26MAY26SASOKC.csv"
ODDS_LOG = REPO_ROOT / "data" / "interim" / "odds" / "capture_20260526.csv"
HOME_ABBR, AWAY_ABBR = "OKC", "SA"


def fetch_outcome(home="OKC", away="SA"):
    """(y_home_win, final_str, is_final). Falls back to current leader."""
    try:
        r = requests.get(ESPN_SB, headers=UA, timeout=15); r.raise_for_status()
        for e in r.json().get("events", []):
            c = e["competitions"][0]
            comp = {x["homeAway"]: x for x in c["competitors"]}
            if comp["home"]["team"]["abbreviation"] == home and comp["away"]["team"]["abbreviation"] == away:
                hs, as_ = int(comp["home"]["score"]), int(comp["away"]["score"])
                final = c["status"]["type"]["state"] == "post"
                return int(hs > as_), f"{away} {as_} - {hs} {home}", final
    except Exception as e:  # noqa: BLE001
        print(f"  ESPN outcome fetch failed: {e}")
    return None, "unknown", False


def market_consensus(odds: pd.DataFrame) -> pd.DataFrame:
    """Per capture_ts: median de-vigged home prob + median home/away american."""
    rows = []
    for ts, g in odds.groupby("capture_ts"):
        home_name = g["home_team"].iloc[0]
        away_name = g["away_team"].iloc[0]
        per_book = []
        for book, gb in g.groupby("book"):
            hp = gb.loc[gb["team"] == home_name, "implied_prob"]
            ap = gb.loc[gb["team"] == away_name, "implied_prob"]
            ha = gb.loc[gb["team"] == home_name, "price_american"]
            aa = gb.loc[gb["team"] == away_name, "price_american"]
            if len(hp) and len(ap):
                per_book.append((hp.iloc[0] / (hp.iloc[0] + ap.iloc[0]), ha.iloc[0], aa.iloc[0]))
        if per_book:
            dv = np.array([p[0] for p in per_book])
            rows.append({
                "capture_ts": pd.to_datetime(ts, utc=True),
                "p_market_home_devig": float(np.median(dv)),
                "home_odds_american": float(np.median([p[1] for p in per_book])),
                "away_odds_american": float(np.median([p[2] for p in per_book])),
                "n_books": len(per_book),
            })
    return pd.DataFrame(rows).sort_values("capture_ts")


def main() -> int:
    if not SIGNAL_LOG.exists() or not ODDS_LOG.exists():
        print("Missing a log — run the live monitors during a game first."); return 0

    bundle = joblib.load(MODEL)
    feats = bundle["features"]

    # 1) game state from the signal log -> full-game model prob
    sig = pd.read_csv(SIGNAL_LOG)
    sig = sig[sig["state"] == "in"].copy()
    sig["ts"] = pd.to_datetime(sig["ts"], utc=True)
    sig["p_hat"] = bundle["iso"].transform(bundle["xgb"].predict_proba_home_wins(sig[feats]))
    sig = sig[["ts", "minute_idx", "period", "score_diff_home", "p_hat"]].sort_values("ts")

    # 2) market consensus from the odds log
    odds = pd.read_csv(ODDS_LOG)
    cons = market_consensus(odds)
    if cons.empty:
        print("No sportsbook consensus rows."); return 0

    # 3) join game state to nearest market quote (within 2 min)
    joined = pd.merge_asof(
        sig, cons, left_on="ts", right_on="capture_ts",
        direction="nearest", tolerance=pd.Timedelta("2min"),
    ).dropna(subset=["p_market_home_devig"])
    if joined.empty:
        print("No overlapping timestamps between game state and odds."); return 0

    # 4) outcome
    y_home, final_str, is_final = fetch_outcome()
    if y_home is None:
        print("Couldn't determine outcome; aborting."); return 0
    tag = "FINAL" if is_final else "PROVISIONAL (game not over)"
    print(f"Outcome [{tag}]: {final_str}  ->  home({HOME_ABBR}) wins game = {bool(y_home)}")

    joined["game_id"] = "20260526_SASOKC"
    joined["y_home_win"] = y_home
    print(f"\nJoined {len(joined)} in-1H ticks with market quotes "
          f"({joined['ts'].min():%H:%M}-{joined['ts'].max():%H:%M}Z, {int(joined['n_books'].median())} books median)")

    # 5) backtest at several thresholds + baselines
    print(f"\n{'='*70}\nGAME-WINNER MOCK TRADES — full-game model vs sportsbook consensus\n{'='*70}")
    for thr in (0.02, 0.04, 0.06):
        rep = bt.simulate(joined, name=f"model (thr={thr:.0%})", threshold=thr, kelly_mult=0.25)
        print(f"  {rep}")
    print("\nBaselines:")
    for rule in ("favorite", "trailing", "random"):
        try:
            print(f"  {bt.baseline_simulate(joined, rule=rule)}")
        except Exception as e:  # noqa: BLE001
            print(f"  baseline {rule}: {e}")

    # 6) show the actual mock trades at the 4% threshold
    rep = bt.simulate(joined, name="model", threshold=0.04, kelly_mult=0.25)
    if not rep.bets.empty:
        print(f"\nMock trades @4% edge (settling {tag}):")
        b = rep.bets.merge(joined[["game_id"]].reset_index(drop=True), left_index=True, right_index=True, how="left")
        show = rep.bets.copy()
        show["side"] = np.where(show["side_home"], HOME_ABBR, AWAY_ABBR)
        show["result"] = np.where(show["won"], "WON", "lost")
        show["pnl"] = np.where(show["won"], show["stake"] * (show["decimal_odds"] - 1), -show["stake"])
        print(show[["side", "edge", "stake", "decimal_odds", "result", "pnl"]].round(3).to_string(index=False))
        print(f"\n  TOTAL: {len(show)} bets, staked ${show['stake'].sum():.2f}, "
              f"P&L ${show['pnl'].sum():+.2f}  (ROI {rep.roi:+.2%})")
    else:
        print("\nNo mock trades cleared the 4% edge threshold.")

    print("\n⚠️  n=1 game, 1st-half window, median lines. Directional proof, not a result.")
    if not is_final:
        print("⚠️  Outcome is PROVISIONAL — re-run after the game ends for the real settle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
