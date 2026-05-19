"""Build the unified game-state table from raw PBP.

The table is long-format: one row per (game_id, minute_index) covering the
first half (24 minutes / 1440 seconds of regulation, or until end of Q2).
This is the granularity that joins naturally to Kalshi's 1-minute candles
and is the target horizon for the V1/V3/V5 1H-anchored analyses.

Per-game pipeline:
  1. Parse PBP `clock` (ISO 8601 PT##M##.##S) -> seconds_elapsed_in_game
  2. Forward-fill score and team-state at minute boundaries
  3. Compute features: score_diff, recent_run, possession_home (best-effort)
  4. Derive both 1H-winner and full-game-winner targets

This module is the upstream dependency for the structural model (V2) and
the cross-venue analyses (V1, V3, V5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

# Regulation: 4 quarters × 12 minutes × 60 seconds = 2880 seconds.
SECONDS_PER_QUARTER = 12 * 60
END_OF_FIRST_HALF_S = 2 * SECONDS_PER_QUARTER  # 1440
END_OF_REGULATION_S = 4 * SECONDS_PER_QUARTER  # 2880

ISO_CLOCK_RE = re.compile(r"PT(\d+)M([\d.]+)S")


@dataclass
class GameTeams:
    home_team_id: int
    away_team_id: int
    home_tricode: str
    away_tricode: str


def parse_clock(clock: str | None) -> float | None:
    """Parse ISO 8601 duration like 'PT07M22.00S' into seconds remaining in period."""
    if not clock or not isinstance(clock, str):
        return None
    m = ISO_CLOCK_RE.match(clock)
    if not m:
        return None
    return int(m.group(1)) * 60 + float(m.group(2))


def seconds_elapsed_in_game(period: int, clock: str | None) -> float | None:
    """Cumulative seconds since tipoff. Regulation only; OT periods append at 2880+."""
    rem = parse_clock(clock)
    if rem is None or period is None:
        return None
    if period <= 4:
        # within a regulation quarter
        return (period - 1) * SECONDS_PER_QUARTER + (SECONDS_PER_QUARTER - rem)
    # OT: each OT is 5 minutes = 300s
    return END_OF_REGULATION_S + (period - 5) * 300 + (300 - rem)


def identify_teams(pbp: pd.DataFrame) -> GameTeams | None:
    """Figure out home/away team ids from the PBP frame.

    Convention in playbyplayv3: the row has 'location' = '' for league events
    and one of the teams' tricodes for play events. The home team's tricode
    typically appears for events where `location` is 'h' or similar; we use
    the heuristic that the team with more events listed first as 'h' is home.
    For now we treat the team whose tricode appears in the *second* play
    (after tip-off) as one of the two and the first scoring team's `location`
    tells us home vs away. Best-effort; we cross-check with score deltas.
    """
    team_rows = pbp[pbp["teamId"].fillna(0) > 0]
    if team_rows.empty:
        return None
    team_ids = team_rows["teamId"].astype(int).unique().tolist()
    if len(team_ids) != 2:
        return None
    # Identify which team's score moves first per scoreHome/scoreAway changes.
    # Convert score strings to int (they can be "" for non-scoring events).
    pbp = pbp.copy()
    pbp["scoreHome_i"] = pd.to_numeric(pbp["scoreHome"], errors="coerce").ffill().fillna(0).astype(int)
    pbp["scoreAway_i"] = pd.to_numeric(pbp["scoreAway"], errors="coerce").ffill().fillna(0).astype(int)
    pbp["d_home"] = pbp["scoreHome_i"].diff().fillna(0)
    pbp["d_away"] = pbp["scoreAway_i"].diff().fillna(0)
    home_scoring = team_rows[pbp.loc[team_rows.index, "d_home"] > 0]
    away_scoring = team_rows[pbp.loc[team_rows.index, "d_away"] > 0]
    if home_scoring.empty or away_scoring.empty:
        return None
    home_team_id = int(home_scoring["teamId"].iloc[0])
    away_team_id = int(away_scoring["teamId"].iloc[0])
    if home_team_id == away_team_id:
        return None
    home_tri = (team_rows[team_rows["teamId"] == home_team_id]["teamTricode"].dropna().iloc[0] if not team_rows.empty else "")
    away_tri = (team_rows[team_rows["teamId"] == away_team_id]["teamTricode"].dropna().iloc[0] if not team_rows.empty else "")
    return GameTeams(
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_tricode=str(home_tri),
        away_tricode=str(away_tri),
    )


def build_minute_snapshots(pbp: pd.DataFrame, game_id: str, season: str) -> pd.DataFrame:
    """Build a per-minute long-format snapshot table for one game.

    Returns a DataFrame with one row per minute boundary (1, 2, ..., 24 in 1H;
    optionally extended into 2H if requested). Each row has the running score
    and state as of that boundary.
    """
    teams = identify_teams(pbp)
    if teams is None:
        return pd.DataFrame()

    pbp = pbp.copy()
    pbp["scoreHome_i"] = pd.to_numeric(pbp["scoreHome"], errors="coerce").ffill().fillna(0).astype(int)
    pbp["scoreAway_i"] = pd.to_numeric(pbp["scoreAway"], errors="coerce").ffill().fillna(0).astype(int)
    pbp["sec_elapsed"] = pbp.apply(
        lambda r: seconds_elapsed_in_game(int(r["period"]) if pd.notna(r["period"]) else 1, r["clock"]),
        axis=1,
    )
    pbp = pbp.dropna(subset=["sec_elapsed"]).sort_values("sec_elapsed").reset_index(drop=True)

    # Take state at each minute boundary 60, 120, ..., 1440 (end of 1H)
    rows = []
    final_home_1h = None
    final_away_1h = None
    final_home_game = int(pbp["scoreHome_i"].iloc[-1])
    final_away_game = int(pbp["scoreAway_i"].iloc[-1])

    for minute in range(1, 25):  # 1..24 minutes of 1H
        boundary_s = minute * 60
        prior = pbp[pbp["sec_elapsed"] <= boundary_s]
        if prior.empty:
            score_home = 0
            score_away = 0
        else:
            score_home = int(prior["scoreHome_i"].iloc[-1])
            score_away = int(prior["scoreAway_i"].iloc[-1])

        # recent run: home_pts - away_pts in last 120s
        window = pbp[(pbp["sec_elapsed"] > boundary_s - 120) & (pbp["sec_elapsed"] <= boundary_s)]
        recent_home = int(window["scoreHome_i"].max() - window["scoreHome_i"].min()) if not window.empty else 0
        recent_away = int(window["scoreAway_i"].max() - window["scoreAway_i"].min()) if not window.empty else 0

        rows.append(
            {
                "game_id": game_id,
                "season": season,
                "minute_idx": minute,
                "seconds_elapsed": boundary_s,
                "period": (boundary_s - 1) // SECONDS_PER_QUARTER + 1,
                "score_home": score_home,
                "score_away": score_away,
                "score_diff_home": score_home - score_away,
                "recent_run_home": recent_home,
                "recent_run_away": recent_away,
                "recent_run_diff": recent_home - recent_away,
                "home_team_id": teams.home_team_id,
                "away_team_id": teams.away_team_id,
                "home_tricode": teams.home_tricode,
                "away_tricode": teams.away_tricode,
            }
        )

        if minute == 24:
            final_home_1h = score_home
            final_away_1h = score_away

    out = pd.DataFrame(rows)
    out["y_home_wins_1h"] = int((final_home_1h or 0) > (final_away_1h or 0))
    out["y_tie_1h"] = int((final_home_1h or 0) == (final_away_1h or 0))
    out["y_home_wins_game"] = int(final_home_game > final_away_game)
    out["final_score_home_1h"] = final_home_1h
    out["final_score_away_1h"] = final_away_1h
    out["final_score_home_game"] = final_home_game
    out["final_score_away_game"] = final_away_game
    return out


def build_season(season: str = "2023-24", pbp_dir: Path | None = None) -> pd.DataFrame:
    """Build the per-minute snapshot table for an entire season.

    Reads all per-game PBP parquets from data/interim/pbp/{season}/ and
    returns the concatenated frame.
    """
    pbp_dir = pbp_dir or (REPO_ROOT / "data" / "interim" / "pbp" / season)
    if not pbp_dir.exists():
        raise FileNotFoundError(f"PBP dir not found: {pbp_dir}")

    frames = []
    for pq in sorted(pbp_dir.glob("00*.parquet")):
        pbp = pd.read_parquet(pq)
        game_id = pq.stem
        try:
            snap = build_minute_snapshots(pbp, game_id=game_id, season=season)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {game_id}: {exc!r}")
            continue
        if not snap.empty:
            frames.append(snap)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
