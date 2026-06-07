#!/usr/bin/env python3
"""Analyze one live Kalshi game recording at orderbook granularity.

Example:
  uv run python scripts/analyze_kalshi_microstructure_game.py \
    --run-dir /path/to/kalshi-spurs-knicks-game2-20260606T002741Z \
    --home-ticker KXNBAGAME-26JUN05NYKSAS-SAS \
    --away-ticker KXNBAGAME-26JUN05NYKSAS-NYK \
    --home-label SAS --away-label NYK \
    --home-team-id ad36c3e8-4194-4e63-920f-7c50f46191a6 \
    --away-team-id 67468ecc-b868-43a4-b9dc-751a52894bb0 \
    --out-dir reports/microstructure/spurs_knicks_game2
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

try:  # noqa: SIM105 - keep optional plotting dependency explicit.
    import matplotlib.dates as mdates  # type: ignore  # noqa: E402
    import matplotlib.pyplot as plt  # type: ignore  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - environment dependent.
    mdates = None
    plt = None

from src.analysis.microstructure_reaction import (  # noqa: E402
    cadence_summary,
    event_reactions,
    load_final_game_events,
    load_orderbook_snapshots,
)


def finite(value: float) -> float | None:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def plot_price_series(books: pd.DataFrame, events: pd.DataFrame, out: Path, home_ticker: str, away_ticker: str) -> None:
    if plt is None:
        plot_price_series_svg(books, events, out.with_suffix(".svg"), home_ticker, away_ticker)
        return
    fig, ax = plt.subplots(figsize=(12, 5))
    for ticker, label in ((home_ticker, "Home YES mid"), (away_ticker, "Away YES mid")):
        g = books[books["ticker"] == ticker]
        ax.plot(g["ts"], g["mid"], linewidth=1.2, label=label)
    scoring = events[events["points"] > 0]
    for _, ev in scoring.iterrows():
        color = "#4c78a8" if ev["scorer_side"] == "home" else "#f58518"
        ax.axvline(ev["event_wall_ts"], color=color, alpha=0.12, linewidth=0.8)
    ax.set_title("Kalshi game-winner prices around scoring events")
    ax.set_ylabel("YES mid price")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(loc="upper left")
    ax.grid(alpha=0.2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_event_pnl(reactions: pd.DataFrame, out: Path) -> None:
    if reactions.empty:
        return
    if plt is None:
        plot_event_pnl_svg(reactions, out.with_suffix(".svg"))
        return
    latest = reactions.sort_values("horizon_ms").groupby("event_idx").tail(1).copy()
    latest = latest.sort_values("roundtrip_pnl", ascending=False).head(20)
    labels = [f"Q{r.period} {r.clock} {r.scorer_label} +{int(r.points)}" for r in latest.itertuples()]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(labels[::-1], latest["roundtrip_pnl"].iloc[::-1], color="#4c78a8")
    ax.set_title("Best visible buy-before / sell-after roundtrip by scoring event")
    ax.set_xlabel("Visible executable roundtrip P&L at final horizon ($)")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def _svg_polyline(points: list[tuple[float, float]], color: str) -> str:
    if not points:
        return ""
    text = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{text}" fill="none" stroke="{color}" stroke-width="2" />'


def plot_price_series_svg(books: pd.DataFrame, events: pd.DataFrame, out: Path, home_ticker: str, away_ticker: str) -> None:
    width, height = 1200, 520
    margin = 55
    x_min = float(books["capture_wall_ms"].min())
    x_max = float(books["capture_wall_ms"].max())

    def sx(value: float) -> float:
        return margin + (value - x_min) / (x_max - x_min) * (width - 2 * margin)

    def sy(value: float) -> float:
        return height - margin - value * (height - 2 * margin)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white" />',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#999" />',
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#999" />',
        '<text x="55" y="28" font-family="Arial" font-size="18" font-weight="700">Kalshi game-winner mid prices around scoring events</text>',
        '<text x="55" y="49" font-family="Arial" font-size="12" fill="#555">Vertical lines mark official play-by-play scoring anchors.</text>',
    ]
    for _, ev in events.iterrows():
        color = "#4c78a8" if ev["scorer_side"] == "home" else "#f58518"
        x = sx(float(ev["event_wall_ms"]))
        parts.append(f'<line x1="{x:.1f}" y1="{margin}" x2="{x:.1f}" y2="{height-margin}" stroke="{color}" stroke-opacity="0.13" />')
    for ticker, color, label, y in (
        (home_ticker, "#4c78a8", "Home YES", 78),
        (away_ticker, "#f58518", "Away YES", 98),
    ):
        g = books[books["ticker"] == ticker]
        points = [(sx(float(row.capture_wall_ms)), sy(float(row.mid))) for row in g.itertuples() if pd.notna(row.mid)]
        parts.append(_svg_polyline(points, color))
        parts.append(f'<circle cx="{width-170}" cy="{y-4}" r="5" fill="{color}" /><text x="{width-158}" y="{y}" font-family="Arial" font-size="13">{label}</text>')
    for value in (0, 0.25, 0.5, 0.75, 1.0):
        y = sy(value)
        parts.append(f'<line x1="{margin}" y1="{y:.1f}" x2="{width-margin}" y2="{y:.1f}" stroke="#ddd" />')
        parts.append(f'<text x="16" y="{y+4:.1f}" font-family="Arial" font-size="11" fill="#555">{value:.2f}</text>')
    parts.append("</svg>")
    out.write_text("\n".join(parts), encoding="utf-8")


def plot_event_pnl_svg(reactions: pd.DataFrame, out: Path) -> None:
    latest = reactions.sort_values("horizon_ms").groupby("event_idx").tail(1).copy()
    latest = latest.sort_values("roundtrip_pnl", ascending=False).head(20)
    width = 1200
    row_h = 26
    height = 90 + row_h * max(len(latest), 1)
    margin_l = 310
    margin_r = 40
    max_pnl = float(max(latest["roundtrip_pnl"].max(), 1.0))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white" />',
        '<text x="24" y="30" font-family="Arial" font-size="18" font-weight="700">Top visible buy-before / sell-after roundtrips</text>',
        '<text x="24" y="50" font-family="Arial" font-size="12" fill="#555">Uses actual visible entry asks and exit bids at sampled book states.</text>',
    ]
    scale = (width - margin_l - margin_r) / max_pnl
    for i, row in enumerate(latest.itertuples()):
        y = 78 + i * row_h
        label = f"Q{row.period} {row.clock} {row.scorer_label} +{int(row.points)}"
        bar_w = max(0, float(row.roundtrip_pnl) * scale)
        parts.append(f'<text x="24" y="{y+15}" font-family="Arial" font-size="12">{label}</text>')
        parts.append(f'<rect x="{margin_l}" y="{y}" width="{bar_w:.1f}" height="18" fill="#4c78a8" />')
        parts.append(f'<text x="{margin_l + bar_w + 6:.1f}" y="{y+14}" font-family="Arial" font-size="12">${float(row.roundtrip_pnl):,.0f}</text>')
    parts.append("</svg>")
    out.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--rest-file", default="kalshi_rest_orderbook_market_snapshots.jsonl")
    parser.add_argument("--sports-file", default="kalshi_sports_state_live_data_game_stats.jsonl")
    parser.add_argument("--home-ticker", required=True)
    parser.add_argument("--away-ticker", required=True)
    parser.add_argument("--home-label", required=True)
    parser.add_argument("--away-label", required=True)
    parser.add_argument("--home-team-id", required=True)
    parser.add_argument("--away-team-id", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--horizon-ms", action="append", default=[])
    args = parser.parse_args()

    horizons = [int(item) for raw in (args.horizon_ms or []) for item in str(raw).split(",") if item]
    if not horizons:
        horizons = [250, 500, 1000, 3000, 10_000, 60_000]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rest_path = args.run_dir / args.rest_file
    sports_path = args.run_dir / args.sports_file

    books = load_orderbook_snapshots(rest_path)
    events = load_final_game_events(
        sports_path,
        home_team_id=args.home_team_id,
        away_team_id=args.away_team_id,
        home_label=args.home_label,
        away_label=args.away_label,
    )
    reactions = event_reactions(
        books,
        events,
        home_ticker=args.home_ticker,
        away_ticker=args.away_ticker,
        horizons_ms=horizons,
    )
    cadence = cadence_summary(books)

    books_export = books.drop(columns=["buy_levels", "sell_levels"])
    books_export.to_csv(args.out_dir / "orderbook_snapshots_compact.csv", index=False)
    events.to_csv(args.out_dir / "scoring_events.csv", index=False)
    reactions.to_csv(args.out_dir / "event_reactions.csv", index=False)
    cadence.to_csv(args.out_dir / "cadence_summary.csv", index=False)

    horizon_summary = []
    if not reactions.empty:
        for horizon, group in reactions.groupby("horizon_ms"):
            profitable = group[group["roundtrip_pnl"] > 0]
            horizon_summary.append(
                {
                    "horizon_ms": int(horizon),
                    "events": int(len(group)),
                    "mean_mid_move": finite(group["mid_move"].mean()),
                    "median_mid_move": finite(group["mid_move"].median()),
                    "positive_mid_move_share": finite((group["mid_move"] > 0).mean()),
                    "profitable_roundtrip_events": int(len(profitable)),
                    "total_visible_roundtrip_pnl": finite(profitable["roundtrip_pnl"].sum()),
                    "max_visible_roundtrip_pnl": finite(profitable["roundtrip_pnl"].max()),
                    "median_visible_roundtrip_pnl": finite(profitable["roundtrip_pnl"].median()),
                    "total_profitable_entry_cost": finite(profitable["roundtrip_entry_cost"].sum()),
                    "total_profitable_contracts": finite(profitable["roundtrip_contracts"].sum()),
                }
            )

    top_events = []
    if not reactions.empty:
        top = reactions.sort_values("roundtrip_pnl", ascending=False).head(15)
        for row in top.to_dict(orient="records"):
            top_events.append(
                {
                    "event_idx": row["event_idx"],
                    "horizon_ms": row["horizon_ms"],
                    "event_wall_ts": row["event_wall_ts"],
                    "clock": row["clock"],
                    "scorer_label": row["scorer_label"],
                    "points": row["points"],
                    "description": row["description"],
                    "pre_mid": finite(row["pre_mid"]),
                    "post_mid": finite(row["post_mid"]),
                    "mid_move": finite(row["mid_move"]),
                    "roundtrip_contracts": finite(row["roundtrip_contracts"]),
                    "roundtrip_entry_cost": finite(row["roundtrip_entry_cost"]),
                    "roundtrip_pnl": finite(row["roundtrip_pnl"]),
                    "roundtrip_avg_entry": finite(row["roundtrip_avg_entry"]),
                    "roundtrip_avg_exit": finite(row["roundtrip_avg_exit"]),
                }
            )

    summary = {
        "run_dir": str(args.run_dir),
        "rest_path": str(rest_path),
        "sports_path": str(sports_path),
        "home_ticker": args.home_ticker,
        "away_ticker": args.away_ticker,
        "home_label": args.home_label,
        "away_label": args.away_label,
        "snapshots": int(len(books)),
        "scoring_events": int(len(events)),
        "reaction_rows": int(len(reactions)),
        "horizons_ms": horizons,
        "cadence": cadence.to_dict(orient="records"),
        "horizon_summary": horizon_summary,
        "top_roundtrip_events": top_events,
        "method_notes": [
            "Event times are Kalshi/Sportradar-style play-by-play wall_clock anchors, not true in-arena optical ground truth.",
            "Orderbook prices are visible public CLOB depth from recorded REST snapshots.",
            "The 250ms requested REST cadence was request-limited; use cadence_summary for actual observed cadence.",
            "Roundtrip P&L is a diagnostic upper bound for buy-before/sell-after visibility at the sampled snapshots; it is not a filled-order claim.",
        ],
    }
    write_json(args.out_dir / "summary.json", summary)

    plot_price_series(books, events, args.out_dir / "price_series.png", args.home_ticker, args.away_ticker)
    plot_event_pnl(reactions, args.out_dir / "top_event_roundtrip_pnl.png")

    print(json.dumps({"out_dir": str(args.out_dir), "events": len(events), "snapshots": len(books)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
