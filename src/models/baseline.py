"""Logistic regression baseline for in-game 1H win probability.

Target: y_home_wins_1h (binary, 1 if home team has the higher score at end of Q2).
Features at minute t: minute_idx, score_diff_home, recent_run_diff, period.

This is the sanity floor for V2; XGBoost should beat this by a meaningful margin.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

FEATURES_BASIC = ["minute_idx", "score_diff_home", "recent_run_diff", "period"]


@dataclass
class FittedBaseline:
    model: LogisticRegression
    scaler: StandardScaler
    features: list[str]

    def predict_proba_home_wins(self, df: pd.DataFrame) -> np.ndarray:
        X = self.scaler.transform(df[self.features].values)
        return self.model.predict_proba(X)[:, 1]


def fit_baseline(train: pd.DataFrame, features: list[str] | None = None) -> FittedBaseline:
    feats = features or FEATURES_BASIC
    scaler = StandardScaler()
    X = scaler.fit_transform(train[feats].values)
    y = train["y_home_wins_1h"].astype(int).values
    model = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs")
    model.fit(X, y)
    return FittedBaseline(model=model, scaler=scaler, features=feats)
