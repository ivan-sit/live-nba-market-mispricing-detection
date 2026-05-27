"""Backtest the live signal monitor's log after a game finishes.

Takes the CSV that scripts/live_signal_monitor.py wrote during a game, derives
the 1H outcome from the last in-half row (home led at the half?), and runs the
logged (p_model, market price) pairs through the verified backtest engine.

This is the clean version of the Kalshi backtest: the monitor recorded in-play
prices WITH synced game state, so there is no alignment problem.

n = 1 game (or however many logs you pass) → pipeline proof, not a result.

Run:  uv run python scripts/backtest_live_log.py [path/to/signals_*.csv ...]
      (no args = backtest every CSV in data/interim/live_signals/)
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from src.eval import backtest as bt

LOG_DIR = REPO_ROOT / "data" / "interim" / "live_signals"


def prob_to_american(q: float) -> float:
    q = float(np.clip(q, 1e-4, 1 - 1e-4))
    return -100.0 * q / (1.0 - q) if q >= 0.5 else 100.0 * (1.0 - q) / q


def prep_one(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    game_id = path.stem.replace("signals_", "")
    # keep in-play rows that actually have a market quote
    df = df[df["p_market_home_devig"].notna()].copy()
    if df.empty:
        print(f"  {path.name}: no rows with a market quote — skipped")
        return pd.DataFrame()

    # 1H outcome: home led at the last logged (latest elapsed) in-half row
    last = df.sort_values("elapsed_half_sec").iloc[-1]
    y_home = int(last["home_score"] > last["away_score"])

    # home YES mid -> the OKC/SAS mid that corresponds to the home team
    home_tri = str(last["home"])
    home_mid = df["k_okc_mid"] if home_tri == "OKC" else df["k_sas_mid"]
    away_mid = df["k_sas_mid"] if home_tri == "OKC" else df["k_okc_mid"]

    out = pd.DataFrame({
        "game_id": game_id,
        "p_hat": df["p_model_home_1h"].to_numpy(),
        "p_market_home_devig": df["p_market_home_devig"].to_numpy(),
        "home_odds_american": [prob_to_american(x) for x in home_mid.to_numpy()],
        "away_odds_american": [prob_to_american(x) for x in away_mid.to_numpy()],
        "y_home_win": y_home,
        "score_diff_home": df["score_diff_home"].to_numpy(),
    })
    print(f"  {path.name}: {len(out)} ticks, 1H winner = {'HOME' if y_home else 'AWAY'} "
          f"(final logged {int(last['away_score'])}-{int(last['home_score'])})")
    return out


def main() -> int:
    paths = [Path(a) for a in sys.argv[1:]] or sorted(LOG_DIR.glob("signals_*.csv"))
    if not paths:
        print(f"No logs found in {LOG_DIR}. Run the live monitor during a game first.")
        return 0

    frames = [prep_one(p) for p in paths]
    frames = [f for f in frames if not f.empty]
    if not frames:
        print("No usable ticks (market never quoted). Likely thin Kalshi 1H liquidity.")
        return 0

    allt = pd.concat(frames, ignore_index=True)
    print(f"\n{'='*64}\nPooled: {len(allt)} ticks across {allt['game_id'].nunique()} game(s)\n{'='*64}")

    for thr in (0.03, 0.05, 0.08):
        print(f"  {bt.simulate(allt, name=f'V2 (thr={thr:.0%})', threshold=thr, kelly_mult=0.25)}")
    print("\nBaselines:")
    for rule in ("favorite", "trailing", "random"):
        try:
            print(f"  {bt.baseline_simulate(allt, rule=rule)}")
        except Exception as e:  # noqa: BLE001
            print(f"  baseline {rule}: {e}")

    print("\n⚠️  Using mid prices (slightly optimistic vs ask). n tiny → directional only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
