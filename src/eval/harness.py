"""Variant protocol + orchestration.

Every variant in src/analysis/variant_v*.py implements the protocol below.
The harness consumes any conforming variant and produces the same set of
evaluation artifacts: calibration table, reliability diagram, mispricing
distribution plot, backtest line, and the pre-registered H1-H4 tests.

This is the load-bearing contract that makes the bake-off honest: same data,
same splits, same metrics, only the variant differs.

Implemented in Phase 2.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd


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
