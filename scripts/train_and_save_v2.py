"""Train V2 (XGB + isotonic) on 2023-24 and persist for live inference.

Saves a single joblib bundle that the live signal monitor loads. Trained on
the full 2023-24 regular season; isotonic calibration fit on the same data
(1-pass — fine for a live demo; the report-grade version uses a held-out fold).

Run:  uv run python scripts/train_and_save_v2.py
Out:  models/v2_xgb_isotonic.joblib
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.data.build_dataset import build_season  # noqa: E402
from src.models.calibration import brier, ece, fit_isotonic  # noqa: E402
from src.models.xgb_model import FEATURES_BASIC, fit_xgb  # noqa: E402

OUT = REPO_ROOT / "models" / "v2_xgb_isotonic.joblib"


def main() -> int:
    print("[1] Build 2023-24 snapshots", flush=True)
    snaps = build_season(season="2023-24")
    train = snaps[snaps["y_tie_1h"] == 0].copy()
    print(f"    {train['game_id'].nunique()} games, {len(train)} non-tie rows")

    print("[2] Fit XGB + isotonic")
    xb = fit_xgb(train, features=FEATURES_BASIC)
    p_raw = xb.predict_proba_home_wins(train)
    iso = fit_isotonic(p_raw, train["y_home_wins_1h"].values)

    y = train["y_home_wins_1h"].values
    p_cal = iso.transform(p_raw)
    print(f"    in-sample Brier raw={brier(p_raw,y):.4f} cal={brier(p_cal,y):.4f} ECE_cal={ece(p_cal,y):.4f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"xgb": xb, "iso": iso, "features": FEATURES_BASIC}, OUT)
    print(f"[3] Saved -> {OUT}")

    # round-trip sanity: load + predict on a hand-built game state
    bundle = joblib.load(OUT)
    demo = pd.DataFrame(
        [{"minute_idx": 18, "score_diff_home": -6, "recent_run_diff": -5, "period": 2}]
    )
    p = bundle["iso"].transform(bundle["xgb"].predict_proba_home_wins(demo))
    print(f"[4] Round-trip OK. Demo (home down 6, 18min in, cold run): P(home wins 1H)={float(np.ravel(p)[0]):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
