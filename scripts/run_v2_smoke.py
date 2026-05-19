"""V2 smoke test: build snapshots from available PBP, train LR + XGB, calibrate, report.

Runs whatever games are currently in data/interim/pbp/2023-24/ (idempotent
with the background PBP pull). Splits 80/20 by game_id for now (Phase 2 will
swap in proper season-based splits once multi-season data is available).

Run from repo root:
    uv run python scripts/run_v2_smoke.py
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
from src.models.baseline import fit_baseline  # noqa: E402
from src.models.calibration import (  # noqa: E402
    brier,
    ece,
    fit_isotonic,
    log_loss_safe,
    reliability_table,
    rms_calibration_error,
)
from src.models.xgb_model import fit_xgb  # noqa: E402

SEED = 42


def main() -> int:
    season = "2023-24"
    print(f"[1] Building 1H minute snapshots for season {season}", flush=True)
    snaps = build_season(season=season)
    n_games = snaps["game_id"].nunique()
    n_rows = len(snaps)
    print(f"    {n_games} games, {n_rows} snapshot rows", flush=True)
    if n_games < 50:
        print("    NOTE: fewer than 50 games; smoke results are illustrative only", flush=True)

    # Game-level random split (80/20). Production split is by season; this is the smoke run.
    rng = np.random.default_rng(SEED)
    game_ids = sorted(snaps["game_id"].unique())
    rng.shuffle(game_ids)
    cut = int(len(game_ids) * 0.6)
    train_games = set(game_ids[:cut])
    val_games = set(game_ids[cut : cut + (len(game_ids) - cut) // 2])
    test_games = set(game_ids[cut + (len(game_ids) - cut) // 2 :])
    train = snaps[snaps["game_id"].isin(train_games)].copy()
    val = snaps[snaps["game_id"].isin(val_games)].copy()
    test = snaps[snaps["game_id"].isin(test_games)].copy()
    print(f"    split: train games={len(train_games)}  val={len(val_games)}  test={len(test_games)}")

    # Filter to non-tie outcomes for clean binary target (drop ties; report rate)
    n_ties = int(snaps.drop_duplicates("game_id")["y_tie_1h"].sum())
    print(f"    games with 1H tie: {n_ties} ({n_ties / n_games:.1%})")
    train = train[train["y_tie_1h"] == 0]
    val = val[val["y_tie_1h"] == 0]
    test = test[test["y_tie_1h"] == 0]

    # Fit baseline + XGB
    print("\n[2] Fit LR baseline ...", flush=True)
    lr = fit_baseline(train)
    p_lr_val = lr.predict_proba_home_wins(val)
    p_lr_test = lr.predict_proba_home_wins(test)

    print("[3] Fit XGB ...", flush=True)
    xb = fit_xgb(train)
    p_xb_val = xb.predict_proba_home_wins(val)
    p_xb_test = xb.predict_proba_home_wins(test)

    # Calibrate XGB on val
    print("[4] Calibrate XGB with isotonic on val ...", flush=True)
    iso = fit_isotonic(p_xb_val, val["y_home_wins_1h"].values)
    p_xb_cal_val = iso.transform(p_xb_val)
    p_xb_cal_test = iso.transform(p_xb_test)

    # Metrics
    def report(name: str, p_v: np.ndarray, p_t: np.ndarray) -> None:
        print(
            f"  {name:24s}  Brier(v)={brier(p_v, val['y_home_wins_1h'].values):.4f}  "
            f"LL(v)={log_loss_safe(p_v, val['y_home_wins_1h'].values):.4f}  "
            f"ECE(v)={ece(p_v, val['y_home_wins_1h'].values):.4f}  "
            f"Brier(t)={brier(p_t, test['y_home_wins_1h'].values):.4f}  "
            f"LL(t)={log_loss_safe(p_t, test['y_home_wins_1h'].values):.4f}  "
            f"ECE(t)={ece(p_t, test['y_home_wins_1h'].values):.4f}"
        )

    print("\n[5] Metrics (val and test):", flush=True)
    report("LR baseline", p_lr_val, p_lr_test)
    report("XGB raw", p_xb_val, p_xb_test)
    report("XGB + isotonic", p_xb_cal_val, p_xb_cal_test)

    print("\n[6] Reliability table — XGB calibrated, test set:")
    print(reliability_table(p_xb_cal_test, test["y_home_wins_1h"].values, n_bins=10).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
