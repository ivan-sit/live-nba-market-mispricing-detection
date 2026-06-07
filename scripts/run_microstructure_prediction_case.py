#!/usr/bin/env python3
"""Run the structural prediction pipeline on a Kalshi microstructure case study.

Inputs are the compact derived assets produced by
`analyze_kalshi_microstructure_game.py` plus a trained full-game model.  Output
is a per-snapshot model-vs-executable-price table and a de-duplicated summary of
buy-signal episodes.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def parse_clock_seconds_left(value: Any) -> float:
    text = str(value or "0").strip()
    if ":" in text:
        minutes, seconds = text.split(":", 1)
        return float(minutes) * 60.0 + float(seconds)
    return float(text or 0)


def add_live_features(books: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    events = events.sort_values("event_wall_ms").reset_index(drop=True)
    books = books.sort_values("capture_wall_ms").reset_index(drop=True)
    event_times = events["event_wall_ms"].to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for row in books.sort_values("capture_wall_ms").itertuples(index=False):
        t = float(row.capture_wall_ms)
        idx = int(np.searchsorted(event_times, t, side="right") - 1)
        if idx >= 0:
            ev = events.iloc[idx]
            home_score = int(ev["post_home_points"])
            away_score = int(ev["post_away_points"])
            period = int(ev["period"])
            seconds_left = parse_clock_seconds_left(ev["clock"])
            seconds_elapsed = (period - 1) * 720.0 + (720.0 - seconds_left)
        else:
            home_score = 0
            away_score = 0
            period = 1
            seconds_elapsed = 0.0

        recent = events[(events["event_wall_ms"] > t - 120_000) & (events["event_wall_ms"] <= t)]
        recent_home = float(recent.loc[recent["scorer_side"] == "home", "points"].sum()) if not recent.empty else 0.0
        recent_away = float(recent.loc[recent["scorer_side"] == "away", "points"].sum()) if not recent.empty else 0.0
        rows.append(
            {
                "capture_wall_ms": t,
                "period": period,
                "seconds_elapsed": seconds_elapsed,
                "minute_idx": int(min(48, max(1, math.floor(seconds_elapsed / 60.0) + 1))),
                "score_home": home_score,
                "score_away": away_score,
                "score_diff_home": home_score - away_score,
                "recent_run_diff": recent_home - recent_away,
            }
        )
    features = pd.DataFrame(rows)
    return pd.concat([books, features.drop(columns=["capture_wall_ms"])], axis=1)


def signal_episodes(df: pd.DataFrame, *, threshold: float, max_gap_ms: float = 2_500) -> pd.DataFrame:
    signals = df[df["edge_to_ask"] >= threshold].sort_values(["ticker", "capture_wall_ms"]).copy()
    if signals.empty:
        return pd.DataFrame()
    rows = []
    for ticker, group in signals.groupby("ticker"):
        episode = 0
        prev_t = None
        for _, row in group.iterrows():
            if prev_t is None or float(row["capture_wall_ms"]) - prev_t > max_gap_ms:
                episode += 1
                rows.append(row.to_dict() | {"episode_id": f"{ticker}:{episode}", "episode_start": True})
            prev_t = float(row["capture_wall_ms"])
    return pd.DataFrame(rows)


def summarize_threshold_budget(df: pd.DataFrame, threshold: float, budget: float) -> dict[str, Any]:
    episodes = signal_episodes(df, threshold=threshold)
    if episodes.empty:
        return {
            "threshold": threshold,
            "budget_per_episode": budget,
            "episodes": 0,
            "actual_pnl_1c": 0.0,
            "model_ev_1c": 0.0,
            "entry_cost": 0.0,
            "contracts_1c": 0.0,
        }
    ep = episodes.copy()
    ep["entry_cost_capped"] = np.minimum(budget, ep["buy_premium_1c"].fillna(0.0))
    ep["contracts_capped"] = np.where(
        ep["avg_entry_1c"] > 0,
        ep["entry_cost_capped"] / ep["avg_entry_1c"],
        0.0,
    )
    ep["model_ev_capped"] = ep["contracts_capped"] * (ep["p_model_yes"] - ep["avg_entry_1c"])
    ep["actual_pnl_capped"] = ep["contracts_capped"] * (ep["actual_yes_payout"] - ep["avg_entry_1c"])
    return {
        "threshold": threshold,
        "budget_per_episode": budget,
        "episodes": int(len(episodes)),
        "nyk_episodes": int((episodes["ticker_side"] == "away").sum()),
        "sas_episodes": int((episodes["ticker_side"] == "home").sum()),
        "mean_edge_to_ask": float(episodes["edge_to_ask"].mean()),
        "median_edge_to_ask": float(episodes["edge_to_ask"].median()),
        "actual_pnl": float(ep["actual_pnl_capped"].sum()),
        "model_ev": float(ep["model_ev_capped"].sum()),
        "entry_cost": float(ep["entry_cost_capped"].sum()),
        "contracts": float(ep["contracts_capped"].sum()),
        "uncapped_entry_cost_1c": float(episodes["buy_premium_1c"].sum()),
        "uncapped_actual_pnl_1c": float(episodes["actual_pnl_1c"].sum()),
        "first_signal_ts": str(episodes["ts"].min()),
        "last_signal_ts": str(episodes["ts"].max()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", type=Path, default=REPO_ROOT / "reports" / "microstructure" / "spurs_knicks_game2")
    parser.add_argument("--model", type=Path, default=REPO_ROOT / "models" / "v2_fullgame_allgame.joblib")
    parser.add_argument("--home-ticker", default="KXNBAGAME-26JUN05NYKSAS-SAS")
    parser.add_argument("--away-ticker", default="KXNBAGAME-26JUN05NYKSAS-NYK")
    parser.add_argument("--threshold", action="append", default=["0.02", "0.03", "0.05", "0.08"])
    parser.add_argument("--budget", action="append", default=["100", "1000", "10000", "100000", "500000"])
    args = parser.parse_args()

    books = pd.read_csv(args.case_dir / "orderbook_snapshots_compact.csv")
    events = pd.read_csv(args.case_dir / "scoring_events.csv")
    bundle = joblib.load(args.model)
    features = bundle["features"]

    df = add_live_features(books, events)
    p_home = bundle["iso"].transform(bundle["xgb"].predict_proba_home_wins(df[features]))
    df["p_model_home"] = p_home
    df["ticker_side"] = np.where(df["ticker"] == args.home_ticker, "home", "away")
    df["p_model_yes"] = np.where(df["ticker_side"] == "home", df["p_model_home"], 1.0 - df["p_model_home"])
    df["edge_to_ask"] = df["p_model_yes"] - df["yes_ask"]
    df["edge_to_bid"] = df["p_model_yes"] - df["yes_bid"]
    df["actual_yes_payout"] = np.where(df["ticker_side"] == "away", 1.0, 0.0)  # Knicks won this game.
    df["avg_entry_1c"] = np.where(df["buy_contracts_1c"] > 0, df["buy_premium_1c"] / df["buy_contracts_1c"], np.nan)
    df["model_ev_1c"] = df["buy_contracts_1c"] * (df["p_model_yes"] - df["avg_entry_1c"])
    df["actual_pnl_1c"] = df["buy_contracts_1c"] * (df["actual_yes_payout"] - df["avg_entry_1c"])

    prediction_path = args.case_dir / "prediction_snapshots.csv"
    keep = [
        "ts",
        "ticker",
        "ticker_side",
        "period",
        "minute_idx",
        "score_home",
        "score_away",
        "score_diff_home",
        "recent_run_diff",
        "yes_bid",
        "yes_ask",
        "mid",
        "p_model_yes",
        "edge_to_ask",
        "buy_contracts_1c",
        "buy_premium_1c",
        "model_ev_1c",
        "actual_pnl_1c",
    ]
    df[keep].to_csv(prediction_path, index=False)

    thresholds = [float(item) for raw in args.threshold for item in str(raw).split(",") if item]
    budgets = [float(item) for raw in args.budget for item in str(raw).split(",") if item]
    summary_rows = [
        summarize_threshold_budget(df, threshold, budget)
        for threshold in thresholds
        for budget in budgets
    ]
    summary = {
        "model": str(args.model),
        "model_training": bundle.get("training", {}),
        "prediction_rows": int(len(df)),
        "method_notes": [
            "Features are reconstructed from official play-by-play scoring anchors and live Kalshi book timestamps.",
            "The trained model predicts P(home wins game); NYK YES uses 1 - P(home).",
            "Signal episodes de-duplicate consecutive signal snapshots; first snapshot of each episode is used.",
            "Capped PnL assumes spending at most budget_per_episode into visible depth within 1c and holding to final settlement.",
            "Uncapped 1c depth fields are retained as capacity diagnostics, not realistic capital deployment.",
            "This is still a one-game case study and uses official PBP timestamps, not physical ground-truth timestamps.",
        ],
        "threshold_summary": summary_rows,
    }
    (args.case_dir / "prediction_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    pd.DataFrame(summary_rows).to_csv(args.case_dir / "prediction_signal_summary.csv", index=False)
    print(json.dumps({"prediction_rows": len(df), "summary": summary_rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
