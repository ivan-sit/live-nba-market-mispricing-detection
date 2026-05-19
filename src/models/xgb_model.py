"""XGBoost in-game 1H win probability model.

Same target/features set as baseline (so we can compare). XGBoost handles
non-linear interactions (e.g., score_diff × time_remaining) that LR can't,
which is where most of the lift over baseline should come from.

Calibration: isotonic regression on a held-out validation fold, wrapped via
src/models/calibration.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import xgboost as xgb

FEATURES_BASIC = ["minute_idx", "score_diff_home", "recent_run_diff", "period"]


@dataclass
class FittedXGB:
    model: xgb.XGBClassifier
    features: list[str]

    def predict_proba_home_wins(self, df: pd.DataFrame) -> np.ndarray:
        X = df[self.features].values
        return self.model.predict_proba(X)[:, 1]


def fit_xgb(
    train: pd.DataFrame,
    features: list[str] | None = None,
    n_estimators: int = 300,
    max_depth: int = 4,
    learning_rate: float = 0.05,
    min_child_weight: float = 10.0,
    subsample: float = 0.85,
    colsample_bytree: float = 0.9,
    random_state: int = 42,
) -> FittedXGB:
    feats = features or FEATURES_BASIC
    X = train[feats].values
    y = train["y_home_wins_1h"].astype(int).values
    model = xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        min_child_weight=min_child_weight,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=random_state,
        n_jobs=-1,
        tree_method="hist",
    )
    model.fit(X, y, verbose=False)
    return FittedXGB(model=model, features=feats)
