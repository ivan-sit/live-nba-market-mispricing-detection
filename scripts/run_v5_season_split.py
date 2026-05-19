"""V5 with proper season-based split (closer to CLAUDE.md spec).

Train V2 on 2023-24 (in-sample), evaluate on 2024-25 (out-of-sample).
This is a stricter test than the within-season random split.

Run from repo root:
    uv run python scripts/run_v5_season_split.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
from src.data.build_dataset import build_season  # noqa: E402
from src.models.calibration import brier, ece, fit_isotonic  # noqa: E402
from src.models.xgb_model import fit_xgb  # noqa: E402


def main() -> int:
    print("[1] Build snapshots: train=2023-24, test=2024-25", flush=True)
    train_snaps = build_season(season="2023-24")
    test_snaps = build_season(season="2024-25")
    print(f"    train: {train_snaps['game_id'].nunique()} games, {len(train_snaps)} rows")
    print(f"    test:  {test_snaps['game_id'].nunique()} games, {len(test_snaps)} rows")

    # Strip ties for clean binary fit (label them in the data but don't train on)
    train = train_snaps[train_snaps["y_tie_1h"] == 0].copy()
    test_no_ties = test_snaps[test_snaps["y_tie_1h"] == 0].copy()

    print("\n[2] Fit V2 (XGB + isotonic on train)")
    xb = fit_xgb(train)
    # 1-pass isotonic on train; for the report-ready version we'll do a proper val fold.
    p_train_raw = xb.predict_proba_home_wins(train)
    iso = fit_isotonic(p_train_raw, train["y_home_wins_1h"].values)

    p_test_raw = xb.predict_proba_home_wins(test_no_ties)
    p_test_cal = iso.transform(p_test_raw)

    y_test = test_no_ties["y_home_wins_1h"].values
    print(f"    Test (2024-25)  XGB raw:  Brier={brier(p_test_raw, y_test):.4f}  ECE={ece(p_test_raw, y_test):.4f}")
    print(f"    Test (2024-25)  XGB cal:  Brier={brier(p_test_cal, y_test):.4f}  ECE={ece(p_test_cal, y_test):.4f}")

    # Attach p_model to test snapshots (incl. ties) for V5 shift lookup
    p_all_test = xb.predict_proba_home_wins(test_snaps)
    test_snaps = test_snaps.copy()
    test_snaps["p_model_home_wins_1h"] = iso.transform(p_all_test)

    print("\n[3] Extract events from 2024-25 PBP")
    pbp_dir = REPO_ROOT / "data" / "interim" / "pbp" / "2024-25"
    all_events = []
    test_game_ids = sorted(test_snaps["game_id"].unique())
    for gid in test_game_ids:
        pq = pbp_dir / f"{gid}.parquet"
        if not pq.exists():
            continue
        pbp = pd.read_parquet(pq)
        meta = test_snaps[test_snaps["game_id"] == gid].iloc[0]
        ev = extract_events_from_pbp(
            pbp=pbp,
            game_id=gid,
            season="2024-25",
            home_team_id=int(meta["home_team_id"]),
            away_team_id=int(meta["away_team_id"]),
        )
        if not ev.empty:
            all_events.append(ev)
    events = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    events = events[events["sec_elapsed"] <= 1440].copy()
    print(f"    {len(events)} 1H events across {events['game_id'].nunique()} test games")

    print("\n[4] H1 (trailing 10-15, made FG)")
    h1_events = filter_h1_events(events, *BUCKET_BOUNDS_PRIMARY)
    h1_shifts = compute_structural_shift(h1_events, test_snaps)
    h1_per_game = game_level_mean(h1_shifts, value_col="structural_shift_for_scorer")
    pt, p, ci = block_bootstrap_one_sided(h1_per_game, "structural_shift_for_scorer", alternative="greater")
    print(f"    n={len(h1_events)} events / {h1_events['game_id'].nunique()} games")
    print(f"    structural shift for scorer (game-mean of game-means): {pt:+.4f}  95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}]  one-sided p (<=0): {p:.4f}")

    print("\n[5] H4 (trailing >=10, made 3-pointer)")
    h4_events = filter_h4_events(events)
    h4_shifts = compute_structural_shift(h4_events, test_snaps)
    h4_per_game = game_level_mean(h4_shifts, value_col="structural_shift_for_scorer")
    pt, p, ci = block_bootstrap_one_sided(h4_per_game, "structural_shift_for_scorer", alternative="greater")
    print(f"    n={len(h4_events)} events / {h4_events['game_id'].nunique()} games")
    print(f"    structural shift for scorer (game-mean of game-means): {pt:+.4f}  95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}]  one-sided p (<=0): {p:.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
