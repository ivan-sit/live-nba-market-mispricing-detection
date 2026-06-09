#!/usr/bin/env python3
"""Analyze scorer-side price reaction timing from reconstructed Kalshi WS books."""

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

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.analysis.microstructure_reaction import load_nba_playbyplay_scoring_events  # noqa: E402


def _price(level: dict[str, Any] | None) -> float:
    if not level:
        return math.nan
    try:
        return float(level.get("price"))
    except (TypeError, ValueError):
        return math.nan


def _depth(depth: dict[str, Any], side: str, band: str, field: str) -> float:
    try:
        return float(((depth.get(side) or {}).get(band) or {}).get(field) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def load_ws_books(path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            if item.get("type") != "reconstructed_book":
                continue
            best = item.get("best") or {}
            depth = item.get("depth") or {}
            yes_bid = _price(best.get("yes_bid"))
            yes_ask = _price(best.get("yes_ask"))
            if not math.isfinite(yes_bid) or not math.isfinite(yes_ask):
                continue
            rows.append(
                {
                    "ticker": item.get("ticker"),
                    "capture_wall_ms": float(item.get("arrival_wall_ms")),
                    "seq": item.get("seq"),
                    "reason": item.get("reason"),
                    "sequence_gap": bool(item.get("sequence_gap")),
                    "yes_bid": yes_bid,
                    "yes_ask": yes_ask,
                    "mid": (yes_bid + yes_ask) / 2.0,
                    "buy_contracts_1c": _depth(depth, "buy_yes", "within_0.0100", "contracts"),
                    "buy_premium_1c": _depth(depth, "buy_yes", "within_0.0100", "premium_dollars"),
                    "sell_contracts_1c": _depth(depth, "sell_yes", "within_0.0100", "contracts"),
                    "sell_premium_1c": _depth(depth, "sell_yes", "within_0.0100", "premium_dollars"),
                    "buy_contracts_5c": _depth(depth, "buy_yes", "within_0.0500", "contracts"),
                    "buy_premium_5c": _depth(depth, "buy_yes", "within_0.0500", "premium_dollars"),
                    "sell_contracts_5c": _depth(depth, "sell_yes", "within_0.0500", "contracts"),
                    "sell_premium_5c": _depth(depth, "sell_yes", "within_0.0500", "premium_dollars"),
                }
            )
    books = pd.DataFrame(rows)
    if books.empty:
        return books
    books["ts"] = pd.to_datetime(books["capture_wall_ms"], unit="ms", utc=True)
    return books.sort_values(["ticker", "capture_wall_ms"]).reset_index(drop=True)


def latest_before(df: pd.DataFrame, ts_ms: float) -> pd.Series | None:
    idx = df["capture_wall_ms"].searchsorted(ts_ms, side="right") - 1
    if idx < 0:
        return None
    return df.iloc[int(idx)]


def first_after(df: pd.DataFrame, ts_ms: float) -> pd.Series | None:
    idx = df["capture_wall_ms"].searchsorted(ts_ms, side="left")
    if idx >= len(df):
        return None
    return df.iloc[int(idx)]


def build_reactions(
    books: pd.DataFrame,
    events: pd.DataFrame,
    *,
    home_ticker: str,
    away_ticker: str,
    horizons_ms: list[int],
    max_lag_over_horizon_ms: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    by_ticker = {ticker: g.reset_index(drop=True) for ticker, g in books.groupby("ticker")}
    for event_idx, event in events.iterrows():
        ticker = home_ticker if event["scorer_side"] == "home" else away_ticker
        g = by_ticker.get(ticker)
        if g is None or g.empty:
            continue
        pre = latest_before(g, float(event["event_wall_ms"]))
        if pre is None:
            continue
        post_window = g[
            (g["capture_wall_ms"] >= float(event["event_wall_ms"]))
            & (g["capture_wall_ms"] <= float(event["event_wall_ms"]) + 10_000)
        ]
        first_1c = post_window[post_window["mid"] >= float(pre["mid"]) + 0.01]
        first_5c = post_window[post_window["mid"] >= float(pre["mid"]) + 0.05]
        base = {
            "event_idx": int(event_idx),
            "ticker": ticker,
            "event_wall_ts": event["event_wall_ts"],
            "period": int(event["period"]),
            "clock": event["clock"],
            "description": event["description"],
            "event_type": event["event_type"],
            "scorer_side": event["scorer_side"],
            "scorer_label": event["scorer_label"],
            "points": int(event["points"]),
            "pre_score": f"{int(event['pre_away_points'])}-{int(event['pre_home_points'])}",
            "post_score": f"{int(event['post_away_points'])}-{int(event['post_home_points'])}",
            "pre_diff_for_scorer": float(event["pre_diff_for_scorer"]),
            "pre_capture_lag_ms": float(event["event_wall_ms"]) - float(pre["capture_wall_ms"]),
            "pre_yes_bid": float(pre["yes_bid"]),
            "pre_yes_ask": float(pre["yes_ask"]),
            "pre_mid": float(pre["mid"]),
            "first_plus_1c_ms": (
                float(first_1c.iloc[0]["capture_wall_ms"] - float(event["event_wall_ms"]))
                if not first_1c.empty
                else math.nan
            ),
            "first_plus_5c_ms": (
                float(first_5c.iloc[0]["capture_wall_ms"] - float(event["event_wall_ms"]))
                if not first_5c.empty
                else math.nan
            ),
        }
        for horizon in horizons_ms:
            post = first_after(g, float(event["event_wall_ms"]) + horizon)
            if post is None:
                continue
            post_lag = float(post["capture_wall_ms"]) - float(event["event_wall_ms"])
            if post_lag > horizon + max_lag_over_horizon_ms:
                continue
            row = dict(base)
            row.update(
                {
                    "horizon_ms": horizon,
                    "post_capture_lag_ms": post_lag,
                    "post_yes_bid": float(post["yes_bid"]),
                    "post_yes_ask": float(post["yes_ask"]),
                    "post_mid": float(post["mid"]),
                    "mid_move": float(post["mid"]) - float(pre["mid"]),
                    "ask_move": float(post["yes_ask"]) - float(pre["yes_ask"]),
                    "bid_move": float(post["yes_bid"]) - float(pre["yes_bid"]),
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ws-reconstructed", type=Path, required=True)
    parser.add_argument("--nba-pbp-file", type=Path, required=True)
    parser.add_argument("--home-ticker", required=True)
    parser.add_argument("--away-ticker", required=True)
    parser.add_argument("--home-label", required=True)
    parser.add_argument("--away-label", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--horizon-ms", action="append", default=[])
    parser.add_argument("--max-lag-over-horizon-ms", type=int, default=2_000)
    args = parser.parse_args()

    horizons = [int(item) for raw in (args.horizon_ms or []) for item in str(raw).split(",") if item]
    if not horizons:
        horizons = [100, 250, 500, 1000, 3000, 10_000, 60_000]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    books = load_ws_books(args.ws_reconstructed)
    events = load_nba_playbyplay_scoring_events(args.nba_pbp_file, home_label=args.home_label, away_label=args.away_label)
    reactions = build_reactions(
        books,
        events,
        home_ticker=args.home_ticker,
        away_ticker=args.away_ticker,
        horizons_ms=horizons,
        max_lag_over_horizon_ms=args.max_lag_over_horizon_ms,
    )

    reactions.to_csv(args.out_dir / "ws_event_reactions.csv", index=False)
    cadence_rows = []
    for ticker, group in books.groupby("ticker"):
        diffs = group["capture_wall_ms"].diff().dropna().to_numpy()
        cadence_rows.append(
            {
                "ticker": ticker,
                "snapshots": int(len(group)),
                "start": group["ts"].min(),
                "end": group["ts"].max(),
                "cadence_p50_ms": float(np.quantile(diffs, 0.50)) if len(diffs) else math.nan,
                "cadence_p95_ms": float(np.quantile(diffs, 0.95)) if len(diffs) else math.nan,
                "sequence_gap_events": int(group["sequence_gap"].sum()),
            }
        )
    cadence = pd.DataFrame(cadence_rows)
    cadence.to_csv(args.out_dir / "ws_cadence_summary.csv", index=False)

    horizon_summary = []
    for horizon, group in reactions.groupby("horizon_ms"):
        horizon_summary.append(
            {
                "horizon_ms": int(horizon),
                "events": int(group["event_idx"].nunique()),
                "mean_mid_move": float(group["mid_move"].mean()),
                "median_mid_move": float(group["mid_move"].median()),
                "positive_mid_move_share": float((group["mid_move"] > 0).mean()),
                "mean_post_capture_lag_ms": float(group["post_capture_lag_ms"].mean()),
                "median_post_capture_lag_ms": float(group["post_capture_lag_ms"].median()),
            }
        )
    first_plus = reactions.drop_duplicates("event_idx")["first_plus_1c_ms"].dropna()
    summary = {
        "ws_reconstructed": str(args.ws_reconstructed),
        "nba_pbp_file": str(args.nba_pbp_file),
        "snapshots": int(len(books)),
        "scoring_events": int(len(events)),
        "reaction_rows": int(len(reactions)),
        "horizons_ms": horizons,
        "first_plus_1c": {
            "events": int(len(first_plus)),
            "mean_ms": float(first_plus.mean()) if len(first_plus) else None,
            "median_ms": float(first_plus.median()) if len(first_plus) else None,
            "p25_ms": float(first_plus.quantile(0.25)) if len(first_plus) else None,
            "p75_ms": float(first_plus.quantile(0.75)) if len(first_plus) else None,
        },
        "cadence": cadence.to_dict(orient="records"),
        "horizon_summary": horizon_summary,
        "method_notes": [
            "Uses reconstructed WebSocket orderbook best bid/ask and depth summaries.",
            "Reaction timing is scorer-side YES mid movement after NBA play-by-play timeActual anchors.",
            "No filled-order claim: WS reconstructed files do not retain full level ladders for roundtrip simulation.",
        ],
    }
    (args.out_dir / "ws_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"books": len(books), "events": len(events), "reactions": len(reactions)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
