"""Game-level train/val/test splits.

Cross-validation is GroupKFold on `game_id` — within-game ticks share the same
outcome and are highly correlated, so row-level splits would massively overstate
performance. See DECISIONS.md (2026-05-14 entry: Cross-validation unit).

Defaults:
  train  = 2019-20, 2020-21, 2021-22 regular seasons
  val    = 2022-23, 2023-24 regular seasons (selection + calibration only)
  test   = 2024-25 regular season (touched once, at the very end)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

TRAIN_SEASONS = ("2019-20", "2020-21", "2021-22")
VAL_SEASONS = ("2022-23", "2023-24")
TEST_SEASONS = ("2024-25",)


@dataclass
class SeasonSplit:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame

    def summary(self) -> str:
        def g(d: pd.DataFrame) -> int:
            return d["game_id"].nunique() if len(d) else 0

        return (
            f"train: {g(self.train)} games / {len(self.train)} rows | "
            f"val: {g(self.val)} games / {len(self.val)} rows | "
            f"test: {g(self.test)} games / {len(self.test)} rows"
        )


def season_split(
    df: pd.DataFrame,
    train_seasons: tuple[str, ...] = TRAIN_SEASONS,
    val_seasons: tuple[str, ...] = VAL_SEASONS,
    test_seasons: tuple[str, ...] = TEST_SEASONS,
) -> SeasonSplit:
    """Split by `season` column. Whatever seasons are present get routed; the
    rest are dropped. Use whichever seasons we actually have on disk."""
    if "season" not in df.columns:
        raise KeyError("df needs a 'season' column for season_split")
    return SeasonSplit(
        train=df[df["season"].isin(train_seasons)].copy(),
        val=df[df["season"].isin(val_seasons)].copy(),
        test=df[df["season"].isin(test_seasons)].copy(),
    )


def game_kfold(
    df: pd.DataFrame,
    n_splits: int = 5,
    game_col: str = "game_id",
    seed: int = 42,
):
    """Yield (train_idx, val_idx) positional arrays, grouped by game so no game
    straddles a fold. Shuffles games deterministically first."""
    games = df[game_col].to_numpy()
    # GroupKFold is deterministic but not shuffled; shuffle group order via a
    # deterministic remap so folds aren't season-ordered.
    rng = np.random.default_rng(seed)
    uniq = pd.unique(games)
    perm = rng.permutation(len(uniq))
    remap = {g: perm[i] for i, g in enumerate(uniq)}
    shuffled_groups = np.array([remap[g] for g in games])
    gkf = GroupKFold(n_splits=n_splits)
    yield from gkf.split(df, groups=shuffled_groups)
