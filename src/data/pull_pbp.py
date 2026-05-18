"""Pull NBA play-by-play via nba_api.

Phase 0 smoke test + reusable fetchers. We intentionally keep this thin —
fetch one game's PBP, save raw JSON, return a normalized DataFrame.

NBA game-id convention (regular season): "002" + last 2 digits of start year +
5-digit game number, zero-padded. Example: first game of 2023-24 is "0022300001".
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import playbyplayv3


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"

# Default request headers — stats.nba.com is finicky and rejects bare requests.
# nba_api sets these by default but we can override if needed.
DEFAULT_TIMEOUT = 30  # seconds


@dataclass
class PBPFetchResult:
    """Wrapper for one PBP fetch: the DataFrame plus telemetry."""

    game_id: str
    season: str
    df: pd.DataFrame
    elapsed_s: float
    raw_json_path: Path | None
    status: str  # "ok" or an error string


def first_game_id(season_start_year: int) -> str:
    """Game ID for the first regular-season game of season starting in `season_start_year`.

    e.g., season_start_year=2023 -> '0022300001' (2023-24 season opener).
    """
    yy = season_start_year % 100
    return f"002{yy:02d}00001"


def season_label(season_start_year: int) -> str:
    """Human-readable season label, e.g., 2023 -> '2023-24'."""
    return f"{season_start_year}-{(season_start_year + 1) % 100:02d}"


def fetch_pbp(
    game_id: str,
    season: str,
    save_raw: bool = True,
    raw_dir: Path = DATA_RAW,
    timeout: int = DEFAULT_TIMEOUT,
) -> PBPFetchResult:
    """Fetch play-by-play for one game and optionally save the raw JSON.

    Returns a PBPFetchResult — the DataFrame is the normalized 'PlayByPlay'
    table from playbyplayv3, plus telemetry (elapsed seconds, status).
    """
    t0 = time.perf_counter()
    try:
        endpoint = playbyplayv3.PlayByPlayV3(game_id=game_id, timeout=timeout)
        df = endpoint.play_by_play.get_data_frame()
        raw: dict[str, Any] = endpoint.get_dict()
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        return PBPFetchResult(
            game_id=game_id,
            season=season,
            df=pd.DataFrame(),
            elapsed_s=time.perf_counter() - t0,
            raw_json_path=None,
            status=f"error: {type(exc).__name__}: {exc}",
        )

    elapsed = time.perf_counter() - t0
    raw_path: Path | None = None
    if save_raw:
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"pbp_{season}_{game_id}.json"
        raw_path.write_text(json.dumps(raw))

    return PBPFetchResult(
        game_id=game_id,
        season=season,
        df=df,
        elapsed_s=elapsed,
        raw_json_path=raw_path,
        status=status,
    )
