"""Train a FULL-GAME win-prob model from 1st-half game state.

V2 predicts the 1st-half winner; the live sportsbook market is full-game
moneyline ("who wins the game"), so to trade it apples-to-apples we need
P(home wins GAME | 1H state). Same features, same 2023-24 train data, target =
y_home_wins_game. Valid at 1H timestamps (periods 1-2) — the live window our
snapshots cover.

Out: models/v2_fullgame.joblib
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
import xgboost as xgb

from src.data.build_dataset import build_season
from src.models.calibration import brier, ece, fit_isotonic
from src.models.xgb_model import FEATURES_BASIC, FittedXGB

OUT = REPO_ROOT / "models" / "v2_fullgame.joblib"


def main() -> int:
    print("[1] Build 2023-24 snapshots", flush=True)
    snaps = build_season(season="2023-24")
    train = snaps[snaps["y_tie_1h"] == 0].copy()
    X = train[FEATURES_BASIC].values
    y = train["y_home_wins_game"].astype(int).values
    print(f"    {train['game_id'].nunique()} games, {len(train)} rows, home-wins-game rate={y.mean():.3f}")

    print("[2] Fit XGB + isotonic on full-game target")
    model = xgb.XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05, min_child_weight=10.0,
        subsample=0.85, colsample_bytree=0.9, objective="binary:logistic",
        eval_metric="logloss", random_state=42, n_jobs=-1, tree_method="hist",
    )
    model.fit(X, y, verbose=False)
    fx = FittedXGB(model=model, features=FEATURES_BASIC)
    p_raw = fx.predict_proba_home_wins(train)
    iso = fit_isotonic(p_raw, y)
    p_cal = iso.transform(p_raw)
    print(f"    in-sample Brier raw={brier(p_raw,y):.4f} cal={brier(p_cal,y):.4f} ECE={ece(p_cal,y):.4f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"xgb": fx, "iso": iso, "features": FEATURES_BASIC}, OUT)
    print(f"[3] Saved -> {OUT}")
    demo = pd.DataFrame([{"minute_idx": 20, "score_diff_home": 8, "recent_run_diff": 4, "period": 2}])
    print(f"[4] Demo (home +8, 20min in): P(home wins GAME)={float(np.ravel(iso.transform(fx.predict_proba_home_wins(demo)))[0]):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
