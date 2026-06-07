"""High-frequency Kalshi orderbook reaction analysis.

This module extends the V5 event-overreaction idea from minute-level market
prices to recorder-level market microstructure.  It deliberately works from
visible executable orderbook levels rather than mids, because the old Kalshi
candle backtests showed that stale/thin mids can create fake edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Level:
    price: float
    size: float


def _money(value: Any) -> float:
    if value in (None, ""):
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _levels(rows: list[Any], *, reverse: bool) -> list[Level]:
    out: list[Level] = []
    for row in rows or []:
        if not isinstance(row, list) or len(row) < 2:
            continue
        price = _money(row[0])
        size = _money(row[1])
        if math.isfinite(price) and math.isfinite(size) and size > 0:
            out.append(Level(price, size))
    return sorted(out, key=lambda item: item.price, reverse=reverse)


def buy_yes_levels(orderbook_fp: dict[str, Any]) -> list[Level]:
    """Executable YES asks inferred from NO bids."""
    no_bids = _levels(orderbook_fp.get("no_dollars") or orderbook_fp.get("no_dollars_fp") or [], reverse=True)
    return sorted([Level(1.0 - lvl.price, lvl.size) for lvl in no_bids], key=lambda item: item.price)


def sell_yes_levels(orderbook_fp: dict[str, Any]) -> list[Level]:
    """Executable YES bids."""
    return _levels(orderbook_fp.get("yes_dollars") or orderbook_fp.get("yes_dollars_fp") or [], reverse=True)


def best_price(levels: list[Level]) -> float:
    return levels[0].price if levels else math.nan


def depth_within(levels: list[Level], band: float) -> dict[str, float]:
    if not levels:
        return {"contracts": 0.0, "premium": 0.0, "worst_price": math.nan}
    best = levels[0].price
    selected = [lvl for lvl in levels if lvl.price <= best + band] if levels[0].price <= levels[-1].price else [
        lvl for lvl in levels if lvl.price >= best - band
    ]
    contracts = float(sum(lvl.size for lvl in selected))
    premium = float(sum(lvl.price * lvl.size for lvl in selected))
    worst = selected[-1].price if selected else math.nan
    return {"contracts": contracts, "premium": premium, "worst_price": worst}


def roundtrip_profit(entry_asks: list[Level], exit_bids: list[Level]) -> dict[str, float]:
    """Optimal buy-then-sell through visible books.

    Entry asks are ascending prices; exit bids are descending prices. The optimal
    one-shot roundtrip stops as soon as the next marginal exit bid is not above
    the next marginal entry ask.
    """
    i = 0
    j = 0
    entry_remaining = entry_asks[0].size if entry_asks else 0.0
    exit_remaining = exit_bids[0].size if exit_bids else 0.0
    contracts = 0.0
    cost = 0.0
    proceeds = 0.0
    worst_entry = math.nan
    worst_exit = math.nan

    while i < len(entry_asks) and j < len(exit_bids):
        ask = entry_asks[i]
        bid = exit_bids[j]
        if bid.price <= ask.price:
            break
        qty = min(entry_remaining, exit_remaining)
        contracts += qty
        cost += qty * ask.price
        proceeds += qty * bid.price
        worst_entry = ask.price
        worst_exit = bid.price
        entry_remaining -= qty
        exit_remaining -= qty
        if entry_remaining <= 1e-9:
            i += 1
            entry_remaining = entry_asks[i].size if i < len(entry_asks) else 0.0
        if exit_remaining <= 1e-9:
            j += 1
            exit_remaining = exit_bids[j].size if j < len(exit_bids) else 0.0

    return {
        "contracts": contracts,
        "entry_cost": cost,
        "exit_proceeds": proceeds,
        "pnl": proceeds - cost,
        "avg_entry": cost / contracts if contracts else math.nan,
        "avg_exit": proceeds / contracts if contracts else math.nan,
        "worst_entry": worst_entry,
        "worst_exit": worst_exit,
    }


def load_orderbook_snapshots(path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            if item.get("type") != "orderbook_snapshot" or item.get("status") != "ok":
                continue
            payload = item.get("payload") or {}
            book = payload.get("orderbook_fp") or payload.get("orderbook") or {}
            buy_levels = buy_yes_levels(book)
            sell_levels = sell_yes_levels(book)
            buy_1c = depth_within(buy_levels, 0.01)
            buy_5c = depth_within(buy_levels, 0.05)
            sell_1c = depth_within(sell_levels, 0.01)
            sell_5c = depth_within(sell_levels, 0.05)
            rows.append(
                {
                    "ticker": item.get("ticker"),
                    "capture_wall_ms": float(item.get("capture_wall_ms")),
                    "request_ms": float(item.get("request_ms") or math.nan),
                    "yes_ask": best_price(buy_levels),
                    "yes_bid": best_price(sell_levels),
                    "mid": (best_price(buy_levels) + best_price(sell_levels)) / 2.0,
                    "buy_levels": buy_levels,
                    "sell_levels": sell_levels,
                    "buy_contracts_1c": buy_1c["contracts"],
                    "buy_premium_1c": buy_1c["premium"],
                    "buy_contracts_5c": buy_5c["contracts"],
                    "buy_premium_5c": buy_5c["premium"],
                    "sell_contracts_1c": sell_1c["contracts"],
                    "sell_premium_1c": sell_1c["premium"],
                    "sell_contracts_5c": sell_5c["contracts"],
                    "sell_premium_5c": sell_5c["premium"],
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["capture_wall_ms"], unit="ms", utc=True)
    return df.sort_values(["ticker", "capture_wall_ms"]).reset_index(drop=True)


def load_final_game_events(
    sports_state_path: Path,
    *,
    home_team_id: str,
    away_team_id: str,
    home_label: str,
    away_label: str,
) -> pd.DataFrame:
    """Extract score-changing events from the final game_stats payload."""
    last_stats: dict[str, Any] | None = None
    with sports_state_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            if item.get("type") == "game_stats" and item.get("status") == "ok":
                last_stats = item
    if not last_stats:
        return pd.DataFrame()

    periods = ((last_stats.get("payload") or {}).get("pbp") or {}).get("periods") or []
    ordered: list[dict[str, Any]] = []
    # Kalshi returns periods newest-first in the final payload. Reverse to get
    # chronological Q1..Q4 ordering, then reverse each period's newest-first
    # event list.
    for period_idx, period in enumerate(reversed(periods), start=1):
        events = list(period.get("events") or [])
        for within_idx, event in enumerate(reversed(events)):
            event = dict(event)
            event["_period_order"] = period_idx
            event["_within_period_order"] = within_idx
            ordered.append(event)

    rows: list[dict[str, Any]] = []
    prev_home = 0
    prev_away = 0
    for event in ordered:
        home_points = int(event.get("home_points") or prev_home)
        away_points = int(event.get("away_points") or prev_away)
        d_home = home_points - prev_home
        d_away = away_points - prev_away
        prev_home = home_points
        prev_away = away_points
        if d_home <= 0 and d_away <= 0:
            continue
        if d_home > 0 and d_away > 0:
            continue
        scorer = "home" if d_home > 0 else "away"
        points = d_home if scorer == "home" else d_away
        team_id = str(event.get("attribution") or "")
        if scorer == "home":
            label = home_label
            expected_team_id = home_team_id
            pre_diff_for_scorer = prev_away - d_away - (prev_home - d_home)
        else:
            label = away_label
            expected_team_id = away_team_id
            pre_diff_for_scorer = prev_home - d_home - (prev_away - d_away)
        rows.append(
            {
                "event_wall_ms": float(event.get("wall_clock")) * 1000.0,
                "event_wall_ts": pd.to_datetime(float(event.get("wall_clock")), unit="s", utc=True),
                "period": int(event.get("_period_order")),
                "clock": event.get("clock"),
                "description": event.get("description"),
                "event_type": event.get("event_type"),
                "scorer_side": scorer,
                "scorer_label": label,
                "scorer_team_id": team_id,
                "expected_team_id": expected_team_id,
                "team_id_matches_side": team_id == expected_team_id if team_id else None,
                "points": points,
                "pre_home_points": home_points - d_home,
                "pre_away_points": away_points - d_away,
                "post_home_points": home_points,
                "post_away_points": away_points,
                "pre_diff_for_scorer": pre_diff_for_scorer,
            }
        )
    return pd.DataFrame(rows).sort_values("event_wall_ms").reset_index(drop=True)


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


def event_reactions(
    books: pd.DataFrame,
    events: pd.DataFrame,
    *,
    home_ticker: str,
    away_ticker: str,
    horizons_ms: list[int],
) -> pd.DataFrame:
    by_ticker = {ticker: g.reset_index(drop=True) for ticker, g in books.groupby("ticker")}
    rows: list[dict[str, Any]] = []
    for event_idx, event in events.iterrows():
        ticker = home_ticker if event["scorer_side"] == "home" else away_ticker
        g = by_ticker.get(ticker)
        if g is None or g.empty:
            continue
        pre = latest_before(g, float(event["event_wall_ms"]))
        if pre is None:
            continue
        base: dict[str, Any] = {
            "event_idx": int(event_idx),
            "ticker": ticker,
            "event_wall_ts": event["event_wall_ts"],
            "period": event["period"],
            "clock": event["clock"],
            "description": event["description"],
            "event_type": event["event_type"],
            "scorer_side": event["scorer_side"],
            "scorer_label": event["scorer_label"],
            "points": event["points"],
            "pre_score": f"{int(event['pre_away_points'])}-{int(event['pre_home_points'])}",
            "post_score": f"{int(event['post_away_points'])}-{int(event['post_home_points'])}",
            "pre_diff_for_scorer": event["pre_diff_for_scorer"],
            "pre_capture_lag_ms": float(event["event_wall_ms"]) - float(pre["capture_wall_ms"]),
            "pre_yes_bid": pre["yes_bid"],
            "pre_yes_ask": pre["yes_ask"],
            "pre_mid": pre["mid"],
            "pre_buy_premium_1c": pre["buy_premium_1c"],
            "pre_sell_premium_1c": pre["sell_premium_1c"],
            "pre_buy_premium_5c": pre["buy_premium_5c"],
            "pre_sell_premium_5c": pre["sell_premium_5c"],
        }
        post_window = g[
            (g["capture_wall_ms"] >= float(event["event_wall_ms"]))
            & (g["capture_wall_ms"] <= float(event["event_wall_ms"]) + 10_000)
        ]
        first_1c = post_window[post_window["mid"] >= float(pre["mid"]) + 0.01]
        if not first_1c.empty:
            base["first_plus_1c_ms"] = float(first_1c.iloc[0]["capture_wall_ms"] - float(event["event_wall_ms"]))
        else:
            base["first_plus_1c_ms"] = math.nan

        for horizon in horizons_ms:
            post = first_after(g, float(event["event_wall_ms"]) + horizon)
            if post is None:
                continue
            rt = roundtrip_profit(pre["buy_levels"], post["sell_levels"])
            row = dict(base)
            row.update(
                {
                    "horizon_ms": horizon,
                    "post_capture_lag_ms": float(post["capture_wall_ms"]) - float(event["event_wall_ms"]),
                    "post_yes_bid": post["yes_bid"],
                    "post_yes_ask": post["yes_ask"],
                    "post_mid": post["mid"],
                    "mid_move": float(post["mid"]) - float(pre["mid"]),
                    "ask_move": float(post["yes_ask"]) - float(pre["yes_ask"]),
                    "bid_move": float(post["yes_bid"]) - float(pre["yes_bid"]),
                    "post_buy_premium_1c": post["buy_premium_1c"],
                    "post_sell_premium_1c": post["sell_premium_1c"],
                    "post_buy_premium_5c": post["buy_premium_5c"],
                    "post_sell_premium_5c": post["sell_premium_5c"],
                    **{f"roundtrip_{key}": value for key, value in rt.items()},
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def cadence_summary(books: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, group in books.groupby("ticker"):
        diffs = group["capture_wall_ms"].diff().dropna().to_numpy()
        rows.append(
            {
                "ticker": ticker,
                "snapshots": int(len(group)),
                "start": group["ts"].min(),
                "end": group["ts"].max(),
                "cadence_p50_ms": float(np.quantile(diffs, 0.50)) if len(diffs) else math.nan,
                "cadence_p95_ms": float(np.quantile(diffs, 0.95)) if len(diffs) else math.nan,
                "request_p50_ms": float(group["request_ms"].median()),
                "request_p95_ms": float(group["request_ms"].quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)
