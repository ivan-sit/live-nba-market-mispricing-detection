#!/usr/bin/env python3
"""Train a full-game win-probability model over all regulation minutes.

The original `train_fullgame_model.py` predicts final winner from first-half
states because it was built for sportsbook captures during a 1H pilot.  The
Kalshi game-winner microstructure case study needs the same structural idea
across the whole game, including late Q4.

Output: `models/v2_fullgame_allgame.joblib`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import joblib  # noqa: E402
import pandas as pd  # noqa: E402
import xgboost as xgb  # noqa: E402

from src.data.build_dataset import (  # noqa: E402
    END_OF_REGULATION_S,
    SECONDS_PER_QUARTER,
    identify_teams,
    seconds_elapsed_in_game,
)
from src.models.calibration import brier, ece, fit_isotonic  # noqa: E402
from src.models.xgb_model import FEATURES_BASIC, FittedXGB  # noqa: E402


def build_game_snapshots_allgame(pbp: pd.DataFrame, game_id: str, season: str) -> pd.DataFrame:
    teams = identify_teams(pbp)
    if teams is None:
        return pd.DataFrame()

    df = pbp.copy()
    df["scoreHome_i"] = pd.to_numeric(df["scoreHome"], errors="coerce").ffill().fillna(0).astype(int)
    df["scoreAway_i"] = pd.to_numeric(df["scoreAway"], errors="coerce").ffill().fillna(0).astype(int)
    df["sec_elapsed"] = df.apply(
        lambda r: seconds_elapsed_in_game(int(r["period"]) if pd.notna(r["period"]) else 1, r["clock"]),
        axis=1,
    )
    df = df.dropna(subset=["sec_elapsed"]).sort_values("sec_elapsed").reset_index(drop=True)
    if df.empty:
        return pd.DataFrame()

    final_home = int(df["scoreHome_i"].iloc[-1])
    final_away = int(df["scoreAway_i"].iloc[-1])
    rows = []
    for minute in range(1, 49):
        boundary_s = minute * 60
        prior = df[df["sec_elapsed"] <= boundary_s]
        if prior.empty:
            score_home = 0
            score_away = 0
        else:
            score_home = int(prior["scoreHome_i"].iloc[-1])
            score_away = int(prior["scoreAway_i"].iloc[-1])

        window = df[(df["sec_elapsed"] > boundary_s - 120) & (df["sec_elapsed"] <= boundary_s)]
        recent_home = int(window["scoreHome_i"].max() - window["scoreHome_i"].min()) if not window.empty else 0
        recent_away = int(window["scoreAway_i"].max() - window["scoreAway_i"].min()) if not window.empty else 0
        rows.append(
            {
                "game_id": game_id,
                "season": season,
                "minute_idx": minute,
                "seconds_elapsed": boundary_s,
                "period": min(4, (boundary_s - 1) // SECONDS_PER_QUARTER + 1),
                "score_home": score_home,
                "score_away": score_away,
                "score_diff_home": score_home - score_away,
                "recent_run_home": recent_home,
                "recent_run_away": recent_away,
                "recent_run_diff": recent_home - recent_away,
                "home_team_id": teams.home_team_id,
                "away_team_id": teams.away_team_id,
                "home_tricode": teams.home_tricode,
                "away_tricode": teams.away_tricode,
                "y_home_wins_game": int(final_home > final_away),
                "final_score_home_game": final_home,
                "final_score_away_game": final_away,
            }
        )
        if boundary_s >= END_OF_REGULATION_S:
            break
    return pd.DataFrame(rows)


def build_season_allgame(season: str, pbp_dir: Path) -> pd.DataFrame:
    frames = []
    for pq in sorted(pbp_dir.glob("00*.parquet")):
        try:
            pbp = pd.read_parquet(pq)
            snap = build_game_snapshots_allgame(pbp, pq.stem, season)
        except Exception as exc:  # noqa: BLE001
            print(f"skip {pq.stem}: {exc!r}", flush=True)
            continue
        if not snap.empty:
            frames.append(snap)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", default="2023-24")
    parser.add_argument("--pbp-dir", type=Path)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "models" / "v2_fullgame_allgame.joblib")
    args = parser.parse_args()

    pbp_dir = args.pbp_dir or REPO_ROOT / "data" / "interim" / "pbp" / args.season
    snaps = build_season_allgame(args.season, pbp_dir)
    if snaps.empty:
        raise SystemExit(f"No snapshots built from {pbp_dir}")

    X = snaps[FEATURES_BASIC].values
    y = snaps["y_home_wins_game"].astype(int).values
    print(
        f"Training all-game full-game WP model: games={snaps['game_id'].nunique()} "
        f"rows={len(snaps)} home_win_rate={y.mean():.3f}",
        flush=True,
    )
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        min_child_weight=10.0,
        subsample=0.85,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )
    model.fit(X, y, verbose=False)
    fx = FittedXGB(model=model, features=FEATURES_BASIC)
    p_raw = fx.predict_proba_home_wins(snaps)
    iso = fit_isotonic(p_raw, y)
    p_cal = iso.transform(p_raw)
    print(f"in-sample Brier raw={brier(p_raw, y):.4f} cal={brier(p_cal, y):.4f} ECE={ece(p_cal, y):.4f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "xgb": fx,
            "iso": iso,
            "features": FEATURES_BASIC,
            "training": {
                "season": args.season,
                "games": int(snaps["game_id"].nunique()),
                "rows": int(len(snaps)),
                "target": "y_home_wins_game",
                "window": "all regulation minutes 1..48",
                "brier_raw_in_sample": float(brier(p_raw, y)),
                "brier_cal_in_sample": float(brier(p_cal, y)),
                "ece_cal_in_sample": float(ece(p_cal, y)),
            },
        },
        args.out,
    )
    print(f"saved {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
