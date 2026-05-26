"""Calibration and accuracy metrics for the variant bake-off.

Thin layer over src/models/calibration.py so every variant is scored through
one import surface. Adds an EvalReport bundle and a de-vig helper.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.models.calibration import (  # re-export
    brier,
    ece,
    log_loss_safe,
    reliability_table,
    rms_calibration_error,
)

__all__ = [
    "brier",
    "ece",
    "log_loss_safe",
    "reliability_table",
    "rms_calibration_error",
    "de_vig_two_way",
    "EvalReport",
    "score",
]


def de_vig_two_way(home_implied: np.ndarray, away_implied: np.ndarray) -> np.ndarray:
    """Multiplicative two-way de-vig: normalize so the two sides sum to 1.

    Returns the de-vigged HOME probability. Both inputs still include vig
    (each is an implied prob from American odds, so they sum to 1+overround).
    """
    home = np.asarray(home_implied, dtype=float)
    away = np.asarray(away_implied, dtype=float)
    total = home + away
    return np.where(total > 0, home / total, np.nan)


@dataclass
class EvalReport:
    name: str
    n: int
    brier: float
    log_loss: float
    ece: float
    rms_cal_err: float
    # market comparison (None if no market column was supplied)
    market_brier: float | None = None
    beats_market_brier: bool | None = None

    def __str__(self) -> str:
        line = (
            f"{self.name:24s}  n={self.n:6d}  Brier={self.brier:.4f}  "
            f"LL={self.log_loss:.4f}  ECE={self.ece:.4f}  RMSCE={self.rms_cal_err:.4f}"
        )
        if self.market_brier is not None:
            verdict = "BEATS" if self.beats_market_brier else "loses to"
            line += f"  | market Brier={self.market_brier:.4f} ({verdict} market)"
        return line


def score(
    name: str,
    p_hat: np.ndarray,
    y: np.ndarray,
    market_prob: np.ndarray | None = None,
    n_bins: int = 10,
) -> EvalReport:
    """Score a probability series; optionally compare its Brier to the market."""
    p_hat = np.asarray(p_hat, dtype=float)
    y = np.asarray(y, dtype=int)
    mb = None
    beats = None
    if market_prob is not None:
        mb = brier(np.asarray(market_prob, dtype=float), y)
        beats = brier(p_hat, y) < mb
    return EvalReport(
        name=name,
        n=len(y),
        brier=brier(p_hat, y),
        log_loss=log_loss_safe(p_hat, y),
        ece=ece(p_hat, y, n_bins=n_bins),
        rms_cal_err=rms_calibration_error(p_hat, y, n_bins=n_bins),
        market_brier=mb,
        beats_market_brier=beats,
    )
