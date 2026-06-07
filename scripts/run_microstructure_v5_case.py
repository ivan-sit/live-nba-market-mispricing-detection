#!/usr/bin/env python3
"""Run V5-style event-overreaction buckets on a microstructure case study.

This is the market-side companion to `src/analysis/variant_v5_event.py` for a
single live-captured Kalshi game.  It does not require the trained structural
model artifact; instead it compares live market shifts to the structural-side
benchmarks already reported in `reports/results_log.md`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402


STRUCTURAL_BENCHMARKS = {
    # 2026-05-18 season-split V5 structural-side results in reports/results_log.md.
    "H1_trailing_10_15_made_fg": 0.0075,
    "H4_trailing_10_plus_made_3": 0.0138,
}


def summarize_bucket(name: str, group: pd.DataFrame, structural_shift: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if group.empty:
        return rows
    for horizon, g in group.groupby("horizon_ms"):
        market_shift = float(g["mid_move"].mean())
        rows.append(
            {
                "bucket": name,
                "horizon_ms": int(horizon),
                "events": int(g["event_idx"].nunique()),
                "mean_market_shift": market_shift,
                "median_market_shift": float(g["mid_move"].median()),
                "positive_market_shift_share": float((g["mid_move"] > 0).mean()),
                "structural_shift_benchmark": structural_shift,
                "mean_market_minus_structural": market_shift - structural_shift,
                "profitable_roundtrip_events": int((g["roundtrip_pnl"] > 0).sum()),
                "positive_roundtrip_pnl_sum": float(g.loc[g["roundtrip_pnl"] > 0, "roundtrip_pnl"].sum()),
                "positive_roundtrip_entry_cost_sum": float(
                    g.loc[g["roundtrip_pnl"] > 0, "roundtrip_entry_cost"].sum()
                ),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case-dir",
        type=Path,
        default=REPO_ROOT / "reports" / "microstructure" / "spurs_knicks_game2",
    )
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--out-csv", type=Path)
    args = parser.parse_args()

    reactions_path = args.case_dir / "event_reactions.csv"
    reactions = pd.read_csv(reactions_path)

    made_fg = reactions["event_type"].isin(["twopointmade", "threepointmade"])
    buckets = {
        "H1_trailing_10_15_made_fg": reactions[
            made_fg
            & (reactions["pre_diff_for_scorer"] >= 10)
            & (reactions["pre_diff_for_scorer"] <= 15)
        ],
        "H4_trailing_10_plus_made_3": reactions[
            reactions["event_type"].eq("threepointmade")
            & (reactions["pre_diff_for_scorer"] >= 10)
        ],
    }

    rows: list[dict[str, Any]] = []
    for name, group in buckets.items():
        rows.extend(summarize_bucket(name, group, STRUCTURAL_BENCHMARKS[name]))

    out = pd.DataFrame(rows).sort_values(["bucket", "horizon_ms"])
    out_csv = args.out_csv or args.case_dir / "v5_microstructure_summary.csv"
    out_json = args.out_json or args.case_dir / "v5_microstructure_summary.json"
    out.to_csv(out_csv, index=False)

    payload = {
        "source": str(reactions_path),
        "structural_benchmarks": STRUCTURAL_BENCHMARKS,
        "method_notes": [
            "H1 and H4 bucket definitions mirror variant_v5_event.py.",
            "Market shift is scorer-side Kalshi YES mid movement from the live orderbook case study.",
            "Structural benchmarks are held-out 2024-25 mean structural shifts from reports/results_log.md.",
            "This is n=1 game and should be read as a case-study market-side diagnostic, not powered inference.",
        ],
        "rows": out.to_dict(orient="records"),
    }
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_csv": str(out_csv), "out_json": str(out_json), "rows": len(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
