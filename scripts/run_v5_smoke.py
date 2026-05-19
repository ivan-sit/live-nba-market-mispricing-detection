"""V5 smoke: extract H1/H4 events, attach structural model shifts, bootstrap.

This is the model-side of the pre-registered behavioral tests. The market-side
will be added once odds data is wired in. For now we answer: 'When the
trailing team scores in the H1/H4 buckets, what does our calibrated structural
model say happens to the home win probability over the next 60 seconds?'

Run from repo root:
    uv run python scripts/run_v5_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.analysis.variant_v5_event import (  # noqa: E402
    BUCKET_BOUNDS_PRIMARY,
    block_bootstrap_one_sided,
    compute_structural_shift,
    extract_events_from_pbp,
    filter_h1_events,
    filter_h4_events,
    game_level_mean,
)
from src.data.build_dataset import build_minute_snapshots, build_season  # noqa: E402
from src.models.calibration import fit_isotonic  # noqa: E402
from src.models.xgb_model import fit_xgb  # noqa: E402

SEED = 42


def main() -> int:
    season = "2023-24"
    pbp_dir = REPO_ROOT / "data" / "interim" / "pbp" / season

    print(f"[1] Building snapshots from {pbp_dir} ...", flush=True)
    snaps = build_season(season=season, pbp_dir=pbp_dir)
    n_games = snaps["game_id"].nunique()
    print(f"    {n_games} games, {len(snaps)} rows", flush=True)

    # Train/val split by game (60/40 here so val has more for stability)
    rng = np.random.default_rng(SEED)
    game_ids = sorted(snaps["game_id"].unique())
    rng.shuffle(game_ids)
    cut = int(len(game_ids) * 0.6)
    train_games = set(game_ids[:cut])
    val_games = set(game_ids[cut:])
    train = snaps[snaps["game_id"].isin(train_games)].copy()
    train = train[train["y_tie_1h"] == 0]  # drop ties for clean binary fit
    print(f"    train games={len(train_games)}, val games={len(val_games)}")

    print("[2] Fitting V2 (XGB + isotonic) ...", flush=True)
    xb = fit_xgb(train)
    # Use train-set probs for isotonic calibration (1-pass; not great but OK for smoke)
    p_train = xb.predict_proba_home_wins(train)
    iso = fit_isotonic(p_train, train["y_home_wins_1h"].values)

    print("[3] Predicting p_model on all snapshots ...", flush=True)
    p_all = xb.predict_proba_home_wins(snaps)
    snaps["p_model_home_wins_1h"] = iso.transform(p_all)

    print("[4] Extracting events from PBP for all val games ...", flush=True)
    all_events = []
    for gid in sorted(val_games):
        pq = pbp_dir / f"{gid}.parquet"
        if not pq.exists():
            continue
        pbp = pd.read_parquet(pq)
        meta = snaps[snaps["game_id"] == gid].iloc[0]
        ev = extract_events_from_pbp(
            pbp=pbp,
            game_id=gid,
            season=season,
            home_team_id=int(meta["home_team_id"]),
            away_team_id=int(meta["away_team_id"]),
        )
        if not ev.empty:
            all_events.append(ev)
    events = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    print(f"    extracted {len(events)} made-FG events across {events['game_id'].nunique() if not events.empty else 0} val games")

    # Restrict to events occurring in the first half (sec_elapsed <= 1440)
    if not events.empty:
        n_pre_filter = len(events)
        events = events[events["sec_elapsed"] <= 1440].copy()
        print(f"    1H-only events: {len(events)} (filtered from {n_pre_filter})")

    if events.empty:
        print("    no events; aborting")
        return 1

    print("\n[5] H1 bucket (trailing 10-15, made FG) — structural shift only", flush=True)
    h1_events = filter_h1_events(events, *BUCKET_BOUNDS_PRIMARY)
    print(f"    {len(h1_events)} H1 events across {h1_events['game_id'].nunique()} games")
    h1_shifts = compute_structural_shift(h1_events, snaps)
    print(f"    {len(h1_shifts)} shifts computed")
    h1_per_game = game_level_mean(h1_shifts, value_col="structural_shift_for_scorer")
    point, p, ci = block_bootstrap_one_sided(h1_per_game, "structural_shift_for_scorer", alternative="greater")
    print(f"    H1 structural shift for scorer (mean of game means): {point:+.4f}  95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}]  one-sided p (≤0): {p:.4f}")

    print("\n[6] H4 bucket (trailing ≥10, made 3-pointer)", flush=True)
    h4_events = filter_h4_events(events)
    print(f"    {len(h4_events)} H4 events across {h4_events['game_id'].nunique()} games")
    h4_shifts = compute_structural_shift(h4_events, snaps)
    h4_per_game = game_level_mean(h4_shifts, value_col="structural_shift_for_scorer")
    point, p, ci = block_bootstrap_one_sided(h4_per_game, "structural_shift_for_scorer", alternative="greater")
    print(f"    H4 structural shift for scorer (mean of game means): {point:+.4f}  95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}]  one-sided p (≤0): {p:.4f}")

    print("\n[7] Sanity: shift distribution by shot_value")
    if not h1_shifts.empty:
        print(h1_shifts.groupby("shot_value")["structural_shift_for_scorer"].describe()[["count", "mean", "std", "min", "max"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
