"""Feature engineering on the per-minute snapshot table.

Adds interaction and derived features on top of the raw build_dataset.py
columns. Kept conservative — every added feature has a clear interpretation
and we test marginal Brier lift before keeping it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Reg-season 1H is 24 minutes. We treat the snapshot table as covering minute_idx 1..24.
MINUTES_IN_1H = 24


def add_basic_engineered(df: pd.DataFrame) -> pd.DataFrame:
    """Add the conservative engineered feature set.

    Columns added:
      minutes_remaining_1h:  24 - minute_idx
      abs_score_diff:         |score_diff_home|
      leverage:               abs_score_diff * (minutes_remaining_1h / 24)
      score_diff_x_remaining: score_diff_home * minutes_remaining_1h
      possession_proxy:       sign(recent_run_diff)  (rough proxy; PBP doesn't expose explicit possession in v3)
    """
    out = df.copy()
    out["minutes_remaining_1h"] = MINUTES_IN_1H - out["minute_idx"]
    out["abs_score_diff"] = out["score_diff_home"].abs()
    out["leverage"] = out["abs_score_diff"] * (out["minutes_remaining_1h"] / MINUTES_IN_1H)
    out["score_diff_x_remaining"] = out["score_diff_home"] * out["minutes_remaining_1h"]
    out["possession_proxy"] = np.sign(out["recent_run_diff"])
    return out


FEATURES_BASIC = ["minute_idx", "score_diff_home", "recent_run_diff", "period"]
FEATURES_ENG_LR = FEATURES_BASIC + [
    "minutes_remaining_1h",
    "abs_score_diff",
    "score_diff_x_remaining",
    "leverage",
]
FEATURES_ENG_XGB = FEATURES_ENG_LR + ["possession_proxy"]
