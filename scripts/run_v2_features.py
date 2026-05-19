"""V2 ablation — compare basic vs engineered features.

Same data split as run_v2_smoke.py. Reports Brier and ECE for two
feature sets and decides which becomes the V2 default going forward.

Run from repo root:
    uv run python scripts/run_v2_features.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.data.build_dataset import build_season  # noqa: E402
from src.features.feature_engineering import (  # noqa: E402
    FEATURES_BASIC,
    FEATURES_ENG_LR,
    FEATURES_ENG_XGB,
    add_basic_engineered,
)
from src.models.baseline import fit_baseline  # noqa: E402
from src.models.calibration import brier, ece, log_loss_safe  # noqa: E402
from src.models.xgb_model import fit_xgb  # noqa: E402

SEED = 42


def main() -> int:
    season = "2023-24"
    print(f"[1] Build snapshots ({season})", flush=True)
    snaps = build_season(season=season)
    snaps = add_basic_engineered(snaps)
    print(f"    {snaps['game_id'].nunique()} games, {len(snaps)} rows")
    print(f"    columns now: {list(snaps.columns)}")

    rng = np.random.default_rng(SEED)
    game_ids = sorted(snaps["game_id"].unique())
    rng.shuffle(game_ids)
    cut = int(len(game_ids) * 0.6)
    train_games = set(game_ids[:cut])
    val_games = set(game_ids[cut : cut + (len(game_ids) - cut) // 2])
    test_games = set(game_ids[cut + (len(game_ids) - cut) // 2 :])
    train = snaps[snaps["game_id"].isin(train_games)]
    train = train[train["y_tie_1h"] == 0].copy()
    val = snaps[snaps["game_id"].isin(val_games)]
    val = val[val["y_tie_1h"] == 0].copy()
    test = snaps[snaps["game_id"].isin(test_games)]
    test = test[test["y_tie_1h"] == 0].copy()
    print(f"    split: train={len(train_games)}  val={len(val_games)}  test={len(test_games)}")

    def report(name: str, p_v, p_t):
        y_v = val["y_home_wins_1h"].values
        y_t = test["y_home_wins_1h"].values
        print(
            f"  {name:30s}  Brier(v)={brier(p_v, y_v):.4f}  "
            f"LL(v)={log_loss_safe(p_v, y_v):.4f}  ECE(v)={ece(p_v, y_v):.4f}  "
            f"Brier(t)={brier(p_t, y_t):.4f}  ECE(t)={ece(p_t, y_t):.4f}"
        )

    print("\n[2] LR — basic vs engineered")
    lr_basic = fit_baseline(train, features=FEATURES_BASIC)
    report("LR basic", lr_basic.predict_proba_home_wins(val), lr_basic.predict_proba_home_wins(test))

    lr_eng = fit_baseline(train, features=FEATURES_ENG_LR)
    report("LR engineered", lr_eng.predict_proba_home_wins(val), lr_eng.predict_proba_home_wins(test))

    print("\n[3] XGB — basic vs engineered")
    xb_basic = fit_xgb(train, features=FEATURES_BASIC)
    report("XGB basic", xb_basic.predict_proba_home_wins(val), xb_basic.predict_proba_home_wins(test))

    xb_eng = fit_xgb(train, features=FEATURES_ENG_XGB)
    report("XGB engineered", xb_eng.predict_proba_home_wins(val), xb_eng.predict_proba_home_wins(test))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
