"""V5 — Event-conditioned overreaction.

Define salience events from PBP, then for each event compute:
  - the calibrated structural model's WP shift over the next K-second window
  - (when odds data is wired in) the market's WP shift over the same window

The pre-registered tests live in this module:
  H1 (primary): trailing-team made FG in 10-15 pt deficit → E[Δp_market − Δp_model] > 0
  H4 (secondary): trailing-team made 3 in ≥10 pt deficit → same direction

Block-bootstrap by game; one-sided p-values; Holm-Bonferroni across the
pre-registered set when combined with H2/H3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from src.data.build_dataset import (
    ISO_CLOCK_RE,
    SECONDS_PER_QUARTER,
    parse_clock,
    seconds_elapsed_in_game,
)

# Pre-registered bucket boundaries (locked in DECISIONS.md 2026-05-14)
BUCKET_BOUNDS_PRIMARY = (10, 15)   # H1 trailing-by 10-15
BUCKET_BOUNDS_H4 = (10, None)      # H4 trailing-by ≥10
WINDOW_SECONDS = 60                # post-event window for shift measurement


@dataclass
class EventRow:
    """One salience event: a made shot by the trailing team in a score-diff bucket."""

    game_id: str
    season: str
    actionNumber: int
    sec_elapsed: float
    period: int
    team_id_scoring: int
    shot_value: int               # 1 (FT), 2 (FG2), 3 (FG3)
    pre_score_home: int
    pre_score_away: int
    pre_diff_for_scorer: int      # positive = scoring team was trailing by this much
    home_scored: bool
    event_type: Literal["made_fg2", "made_fg3"]


def _to_int(s):
    return pd.to_numeric(s, errors="coerce").ffill().fillna(0).astype(int)


def extract_events_from_pbp(
    pbp: pd.DataFrame,
    game_id: str,
    season: str,
    home_team_id: int,
    away_team_id: int,
) -> pd.DataFrame:
    """Identify made FG2 and FG3 events.

    Returns one row per scoring event with the pre-event score state and
    a flag for whether the scoring team was trailing (and by how much).
    """
    if pbp.empty:
        return pd.DataFrame()

    df = pbp.copy()
    df["scoreHome_i"] = _to_int(df["scoreHome"])
    df["scoreAway_i"] = _to_int(df["scoreAway"])
    df["sec_elapsed"] = df.apply(
        lambda r: seconds_elapsed_in_game(int(r["period"]) if pd.notna(r["period"]) else 1, r["clock"]),
        axis=1,
    )
    df = df.dropna(subset=["sec_elapsed"]).reset_index(drop=True)

    # Pre-event score: shift by 1 row to capture state BEFORE the action
    df["pre_score_home"] = df["scoreHome_i"].shift(1).fillna(0).astype(int)
    df["pre_score_away"] = df["scoreAway_i"].shift(1).fillna(0).astype(int)
    df["d_home"] = df["scoreHome_i"] - df["pre_score_home"]
    df["d_away"] = df["scoreAway_i"] - df["pre_score_away"]

    events = []
    for _, r in df.iterrows():
        d_home = int(r["d_home"])
        d_away = int(r["d_away"])
        # Only made FGs that scored 2 or 3 points
        shot_value = None
        home_scored = False
        if d_home in (2, 3) and d_away == 0:
            shot_value = d_home
            home_scored = True
        elif d_away in (2, 3) and d_home == 0:
            shot_value = d_away
            home_scored = False
        else:
            continue

        team_id_scoring = home_team_id if home_scored else away_team_id
        pre_diff_home = int(r["pre_score_home"]) - int(r["pre_score_away"])
        # For the scorer, positive pre_diff_for_scorer = scoring team was trailing
        pre_diff_for_scorer = -pre_diff_home if home_scored else pre_diff_home

        events.append(
            {
                "game_id": game_id,
                "season": season,
                "actionNumber": int(r.get("actionNumber") or 0),
                "sec_elapsed": float(r["sec_elapsed"]),
                "period": int(r["period"]) if pd.notna(r["period"]) else 1,
                "team_id_scoring": team_id_scoring,
                "shot_value": shot_value,
                "pre_score_home": int(r["pre_score_home"]),
                "pre_score_away": int(r["pre_score_away"]),
                "pre_diff_for_scorer": pre_diff_for_scorer,
                "home_scored": home_scored,
                "event_type": "made_fg3" if shot_value == 3 else "made_fg2",
            }
        )
    return pd.DataFrame(events)


def filter_h1_events(events: pd.DataFrame, bucket_low: int = 10, bucket_high: int = 15) -> pd.DataFrame:
    """H1: scoring-team trailing by 10-15 (inclusive of both bounds), made FG (any value).

    Pre-event score_diff_for_scorer >= bucket_low and <= bucket_high.
    """
    mask = (events["pre_diff_for_scorer"] >= bucket_low) & (events["pre_diff_for_scorer"] <= bucket_high)
    return events[mask].copy()


def filter_h4_events(events: pd.DataFrame, bucket_low: int = 10) -> pd.DataFrame:
    """H4: scoring-team trailing by ≥10 (inclusive), made 3-pointer specifically."""
    mask = (events["pre_diff_for_scorer"] >= bucket_low) & (events["shot_value"] == 3)
    return events[mask].copy()


def compute_structural_shift(
    events: pd.DataFrame,
    snapshots: pd.DataFrame,
    p_model_col: str = "p_model_home_wins_1h",
    window_seconds: int = WINDOW_SECONDS,
) -> pd.DataFrame:
    """For each event, look up the structural model's p̂ at sec_elapsed (anchor)
    and at sec_elapsed + window_seconds, return the shift in p̂ from the
    scoring team's perspective.

    `snapshots` must be the same long-format minute table we built from PBP,
    augmented with a column `p_model_col` containing the model's predicted
    P(home wins 1H) at each minute boundary.
    """
    out_rows = []
    snap_by_game = {gid: g for gid, g in snapshots.groupby("game_id")}
    for _, ev in events.iterrows():
        g = snap_by_game.get(ev["game_id"])
        if g is None:
            continue
        anchor_s = ev["sec_elapsed"]
        end_s = anchor_s + window_seconds

        # Anchor minute = last minute boundary at or before anchor_s
        anchor_idx = int(np.floor(anchor_s / 60))
        end_idx = int(np.floor(end_s / 60))
        anchor_idx = max(1, min(24, anchor_idx))
        end_idx = max(1, min(24, end_idx))
        if anchor_idx == end_idx:
            # Event and window-end fall in same snapshot bin — model shift is 0 by construction
            shift_home = 0.0
        else:
            try:
                p_anchor = float(g.loc[g["minute_idx"] == anchor_idx, p_model_col].iloc[0])
                p_end = float(g.loc[g["minute_idx"] == end_idx, p_model_col].iloc[0])
            except (IndexError, KeyError):
                continue
            shift_home = p_end - p_anchor

        # Convert to scorer's perspective: if home scored, the "scorer's shift" is + shift_home;
        # if away scored, it's -shift_home.
        shift_for_scorer = shift_home if ev["home_scored"] else -shift_home

        out_rows.append(
            {
                "game_id": ev["game_id"],
                "actionNumber": ev["actionNumber"],
                "sec_elapsed": ev["sec_elapsed"],
                "pre_diff_for_scorer": ev["pre_diff_for_scorer"],
                "shot_value": ev["shot_value"],
                "structural_shift_for_scorer": shift_for_scorer,
                "anchor_minute": anchor_idx,
                "end_minute": end_idx,
            }
        )
    return pd.DataFrame(out_rows)


def game_level_mean(shifts: pd.DataFrame, value_col: str = "structural_shift_for_scorer") -> pd.DataFrame:
    """Average within-game first (controls for game-level correlation).

    Returns DataFrame with one row per game and the mean value column.
    """
    return shifts.groupby("game_id")[value_col].mean().reset_index()


def block_bootstrap_one_sided(
    per_game: pd.DataFrame,
    value_col: str,
    n_resamples: int = 10000,
    alternative: Literal["greater", "less"] = "greater",
    seed: int = 42,
) -> tuple[float, float, tuple[float, float]]:
    """Block-bootstrap by game. Returns (point estimate, p-value, 95% CI).

    Resamples `per_game` with replacement, computes the mean, and reports
    the one-sided p-value as P(resampled_mean <= 0) (for 'greater')
    or P(resampled_mean >= 0) (for 'less').
    """
    rng = np.random.default_rng(seed)
    vals = per_game[value_col].astype(float).values
    n = len(vals)
    point = float(np.mean(vals))
    samples = rng.choice(vals, size=(n_resamples, n), replace=True)
    boots = samples.mean(axis=1)
    if alternative == "greater":
        p_value = float((boots <= 0.0).mean())
    else:
        p_value = float((boots >= 0.0).mean())
    ci = (float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975)))
    return point, p_value, ci
