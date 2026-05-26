"""Variant protocol + orchestration.

Every variant in src/analysis/variant_v*.py implements the protocol below.
The harness consumes any conforming variant and produces the same set of
evaluation artifacts: calibration metrics, mispricing edges, and a backtest.

This is the load-bearing contract that makes the bake-off honest: same data,
same splits, same metrics, only the variant differs.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

from src.eval import backtest as bt
from src.eval.metrics import EvalReport, score

MARKET_PROB_COL = "p_market_home_devig"
OUTCOME_COL = "y_home_win"


@runtime_checkable
class VariantProtocol(Protocol):
    """The contract every mispricing-detection variant implements."""

    name: str
    pre_registered: bool

    def expected_columns(self) -> set[str]:
        """Columns this variant requires in the input frame."""
        ...

    def fit(self, train_df: pd.DataFrame, val_df: pd.DataFrame) -> None:
        """Fit on train+val. Test set is never seen here."""
        ...

    def predict_pt(self, df: pd.DataFrame) -> pd.Series:
        """Return the fair-value estimate p̂_t per row."""
        ...

    def predict_edge(self, df: pd.DataFrame) -> pd.Series:
        """Return edge_t = p̂_t − p_market_t per row (sign matters)."""
        ...


# ----------------------------------------------------------------------------
# Reference variants (sanity checks + the trivial "bet the market" control)
# ----------------------------------------------------------------------------


class ConstantVariant:
    """Always predicts a constant probability. The 0.5 case is the harness
    sanity check: on balanced outcomes its Brier must be exactly 0.25."""

    pre_registered = False

    def __init__(self, value: float = 0.5) -> None:
        self.value = value
        self.name = f"const({value})"

    def expected_columns(self) -> set[str]:
        return set()

    def fit(self, train_df: pd.DataFrame, val_df: pd.DataFrame) -> None:
        return None

    def predict_pt(self, df: pd.DataFrame) -> pd.Series:
        return pd.Series(np.full(len(df), self.value), index=df.index)

    def predict_edge(self, df: pd.DataFrame) -> pd.Series:
        return self.predict_pt(df) - df[MARKET_PROB_COL]


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------


def evaluate(
    variant: VariantProtocol,
    test_df: pd.DataFrame,
    outcome_col: str = OUTCOME_COL,
    market_prob_col: str | None = MARKET_PROB_COL,
) -> EvalReport:
    """Calibration/accuracy of the variant's p̂_t on the test set, compared to
    the market's de-vigged probability when that column is present."""
    p_hat = np.asarray(variant.predict_pt(test_df), dtype=float)
    y = test_df[outcome_col].to_numpy()
    market = (
        test_df[market_prob_col].to_numpy()
        if market_prob_col and market_prob_col in test_df.columns
        else None
    )
    return score(variant.name, p_hat, y, market_prob=market)


def backtest(
    variant: VariantProtocol,
    test_df: pd.DataFrame,
    *,
    threshold: float = 0.03,
    kelly_mult: float = 0.25,
    sizing: str = "kelly",
    market_prob_col: str = MARKET_PROB_COL,
    outcome_col: str = OUTCOME_COL,
    game_order: list | None = None,
) -> bt.BacktestReport:
    """Run the variant's p̂_t through the shared backtest engine."""
    d = test_df.copy()
    d["__p_hat__"] = np.asarray(variant.predict_pt(d), dtype=float)
    return bt.simulate(
        d,
        name=variant.name,
        p_hat_col="__p_hat__",
        market_prob_col=market_prob_col,
        outcome_col=outcome_col,
        threshold=threshold,
        sizing=sizing,  # type: ignore[arg-type]
        kelly_mult=kelly_mult,
        game_order=game_order,
    )
