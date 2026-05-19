"""Pull Kalshi KXNBA1HWINNER + KXNBA2HWINNER settled candlesticks.

Iterates the settled markets archive, groups by event_ticker (per game), pulls
1-minute candlesticks for each of the three outcomes (HOME / AWAY / TIE) per
game. Saves long-format parquet ready for joining to PBP later.

Run from repo root:
    uv run python scripts/pull_kalshi_1h_archive.py --series KXNBA1HWINNER --max-games 50

Phase 1 data assembly. Idempotent: skips events whose parquet already exists.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from src.data.pull_kalshi import KalshiClient  # noqa: E402


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fetch_candles_for_event(
    client: KalshiClient,
    series_ticker: str,
    event_ticker: str,
    market_tickers: list[str],
    occurrence_dt: datetime,
    period_interval: int = 1,
    window_hours_before: float = 0.75,
    window_hours_after: float = 4.0,
) -> pd.DataFrame:
    """Pull candles for each outcome of one event, return long-format DF."""
    start_ts = int((occurrence_dt - timedelta(hours=window_hours_before)).timestamp())
    end_ts = int((occurrence_dt + timedelta(hours=window_hours_after)).timestamp())

    out_rows = []
    for mt in market_tickers:
        # try live endpoint first; on error/empty, try historical
        candles = None
        for attempt, fn in enumerate(("live", "historical")):
            try:
                if fn == "live":
                    data = client.get_candlesticks(
                        series_ticker=series_ticker,
                        market_ticker=mt,
                        start_ts=start_ts,
                        end_ts=end_ts,
                        period_interval=period_interval,
                    )
                else:
                    data = client.get_historical_candlesticks(
                        market_ticker=mt,
                        start_ts=start_ts,
                        end_ts=end_ts,
                        period_interval=period_interval,
                    )
            except Exception as exc:  # noqa: BLE001
                if attempt == 1:
                    print(f"    {mt}: both endpoints failed ({exc!r})", flush=True)
                continue
            if "candlesticks" in data and data["candlesticks"]:
                candles = data["candlesticks"]
                break
        if not candles:
            continue

        for c in candles:
            p = c.get("price") or {}
            yb = c.get("yes_bid") or {}
            ya = c.get("yes_ask") or {}
            out_rows.append(
                {
                    "event_ticker": event_ticker,
                    "market_ticker": mt,
                    "end_ts": c.get("end_period_ts"),
                    "open_dollars": float(p.get("open_dollars") or 0.0) if p.get("open_dollars") is not None else None,
                    "close_dollars": float(p.get("close_dollars") or 0.0) if p.get("close_dollars") is not None else None,
                    "high_dollars": float(p.get("high_dollars") or 0.0) if p.get("high_dollars") is not None else None,
                    "low_dollars": float(p.get("low_dollars") or 0.0) if p.get("low_dollars") is not None else None,
                    "mean_dollars": float(p.get("mean_dollars") or 0.0) if p.get("mean_dollars") is not None else None,
                    "yes_bid_close": float(yb.get("close_dollars") or 0.0) if yb.get("close_dollars") is not None else None,
                    "yes_ask_close": float(ya.get("close_dollars") or 0.0) if ya.get("close_dollars") is not None else None,
                    "volume_fp": float(c.get("volume_fp") or 0.0),
                    "open_interest_fp": float(c.get("open_interest_fp") or 0.0),
                }
            )
    return pd.DataFrame(out_rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXNBA1HWINNER")
    ap.add_argument("--max-games", type=int, default=20, help="Cap on number of games this run.")
    ap.add_argument("--period", type=int, default=1, help="Candle period in minutes.")
    ap.add_argument("--sleep", type=float, default=0.3, help="Sleep between API calls.")
    args = ap.parse_args()

    client = KalshiClient()
    out_dir = REPO_ROOT / "data" / "interim" / "kalshi"
    out_dir.mkdir(parents=True, exist_ok=True)
    series_out = out_dir / args.series
    series_out.mkdir(parents=True, exist_ok=True)

    print(f"[1] Listing settled markets under {args.series} ...", flush=True)
    mkts = client.list_markets(series_ticker=args.series, status="settled", limit=500)
    print(f"    {len(mkts)} settled markets total")

    # Group by event_ticker. Each event has multiple market tickers (HOME/AWAY/TIE).
    by_event: dict[str, list[dict]] = defaultdict(list)
    for m in mkts:
        et = m.get("event_ticker")
        if et:
            by_event[et].append(m)
    print(f"    {len(by_event)} unique events (games)")

    # Pull recent events first
    events_sorted = sorted(by_event.items(), key=lambda kv: max(parse_iso(x.get("settlement_ts")) or datetime.min for x in kv[1]), reverse=True)

    pulled = 0
    skipped_cached = 0
    summary_rows = []
    for event_ticker, event_markets in events_sorted:
        out_pq = series_out / f"{event_ticker}.parquet"
        if out_pq.exists():
            skipped_cached += 1
            continue
        if pulled >= args.max_games:
            break

        # Determine occurrence time from any market
        occ = parse_iso(event_markets[0].get("occurrence_datetime")) or parse_iso(event_markets[0].get("expected_expiration_time"))
        if occ is None:
            print(f"    {event_ticker}: no occurrence time, skipping")
            continue

        market_tickers = [m["ticker"] for m in event_markets]
        print(f"[{pulled + 1}/{args.max_games}] {event_ticker}  occ={occ.isoformat()}  {len(market_tickers)} outcomes", flush=True)

        df = fetch_candles_for_event(
            client=client,
            series_ticker=args.series,
            event_ticker=event_ticker,
            market_tickers=market_tickers,
            occurrence_dt=occ,
            period_interval=args.period,
        )
        n = len(df)
        if n == 0:
            print(f"    -> 0 candles; saving empty marker")
            out_pq.write_bytes(b"")  # marker so we don't retry this event
        else:
            df.to_parquet(out_pq, index=False)
            print(f"    -> {n} candle rows across outcomes, wrote {out_pq.name}")
        summary_rows.append({"event_ticker": event_ticker, "n_outcomes": len(market_tickers), "n_candles": n, "occurrence": occ.isoformat()})
        pulled += 1
        time.sleep(args.sleep)

    summary = pd.DataFrame(summary_rows)
    summary_csv = series_out / "_pull_summary.csv"
    summary.to_csv(summary_csv, index=False)
    print(f"\nDone. pulled={pulled}  skipped_cached={skipped_cached}  total_events_in_archive={len(by_event)}")
    print(f"Summary at {summary_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
