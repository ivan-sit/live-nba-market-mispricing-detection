"""Calibration utilities — isotonic regression layer, reliability diagrams, ECE.

Wraps a raw probability output (from XGB or LR) with a monotonic mapping fit
on a held-out validation fold. Reliability diagram + RMS calibration error
both before and after the layer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression


@dataclass
class FittedIsotonic:
    iso: IsotonicRegression

    def transform(self, p: np.ndarray) -> np.ndarray:
        return self.iso.transform(np.clip(p, 1e-6, 1 - 1e-6))


def fit_isotonic(p_val: np.ndarray, y_val: np.ndarray) -> FittedIsotonic:
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(np.asarray(p_val, dtype=float), np.asarray(y_val, dtype=int))
    return FittedIsotonic(iso=iso)


def brier(p: np.ndarray, y: np.ndarray) -> float:
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=int)
    return float(np.mean((p - y) ** 2))


def log_loss_safe(p: np.ndarray, y: np.ndarray, eps: float = 1e-9) -> float:
    p = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    y = np.asarray(y, dtype=int)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def reliability_table(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=int)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(p, bins) - 1, 0, n_bins - 1)
    df = pd.DataFrame({"p": p, "y": y, "bin": bin_idx})
    table = (
        df.groupby("bin")
        .agg(mean_p=("p", "mean"), emp_freq=("y", "mean"), n=("y", "size"))
        .reset_index()
    )
    table["bin_low"] = bins[table["bin"].astype(int).values]
    table["bin_high"] = bins[table["bin"].astype(int).values + 1]
    return table[["bin", "bin_low", "bin_high", "mean_p", "emp_freq", "n"]]


def rms_calibration_error(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    tab = reliability_table(p, y, n_bins=n_bins)
    diff = (tab["mean_p"] - tab["emp_freq"]).abs()
    return float(np.sqrt(np.mean(diff**2)))


def ece(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    """Expected calibration error: weighted mean abs(mean_p - emp_freq)."""
    tab = reliability_table(p, y, n_bins=n_bins)
    weights = tab["n"] / tab["n"].sum()
    return float(np.sum(weights * (tab["mean_p"] - tab["emp_freq"]).abs()))
