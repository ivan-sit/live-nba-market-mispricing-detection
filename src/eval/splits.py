"""Game-level train/val/test splits.

Cross-validation is GroupKFold on `game_id` — within-game ticks share the same
outcome and are highly correlated, so row-level splits would massively overstate
performance. See DECISIONS.md (2026-05-14 entry: Cross-validation unit).

Defaults:
  train  = 2019-20, 2020-21, 2021-22 regular seasons
  val    = 2022-23, 2023-24 regular seasons (selection + calibration only)
  test   = 2024-25 regular season (touched once, at the very end)

Implemented in Phase 2.
"""
