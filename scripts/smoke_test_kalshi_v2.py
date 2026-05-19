"""Kalshi smoke test v2 — corrected field names + candlestick pull.

The earlier scripts read wrong field names: Kalshi uses *_dollars suffixes
(yes_bid_dollars, yes_ask_dollars) and *_fp suffixes for floating-point
counters (volume_24h_fp, open_interest_fp). Re-running with the right
schema and adding a 1-minute candlestick pull for one sample market
to confirm we have in-game price-history access.

Goal: enough evidence to make the D3 GO/NO-GO call on Kalshi.

Run from repo root:
    uv run python scripts/smoke_test_kalshi_v2.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from src.data.pull_kalshi import KalshiClient  # noqa: E402

IN_GAME_SERIES = [
    ("KXNBA1HWINNER", "1st Half Winner"),
    ("KXNBA2HWINNER", "2nd Half Winner"),
    ("KXNBA1HSPREAD", "1st Half Spread"),
    ("KXNBA1HTOTAL", "1st Half Total"),
    ("KXNBA2HTOTAL", "2nd Half Total"),
    ("KXNBATEAMTOTAL", "Team Total"),
]


def num(x: str | float | None) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main() -> int:
    client = KalshiClient()
    out_dir = REPO_ROOT / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    sample_for_candles: dict | None = None

    for series_ticker, label in IN_GAME_SERIES:
        for status in ("open", "settled"):
            try:
                mkts = client.list_markets(series_ticker=series_ticker, status=status, limit=500)
            except Exception as exc:  # noqa: BLE001
                print(f"  {series_ticker} [{status}]: ERROR {exc!r}", flush=True)
                continue

            n_with_vol = sum(1 for m in mkts if num(m.get("volume_24h_fp")) and num(m.get("volume_24h_fp")) > 0)
            volumes_24h = [num(m.get("volume_24h_fp")) for m in mkts if num(m.get("volume_24h_fp")) is not None]
            volumes_total = [num(m.get("volume_fp")) for m in mkts if num(m.get("volume_fp")) is not None]
            ois = [num(m.get("open_interest_fp")) for m in mkts if num(m.get("open_interest_fp")) is not None]

            spreads = []
            for m in mkts:
                yb = num(m.get("yes_bid_dollars"))
                ya = num(m.get("yes_ask_dollars"))
                if yb is not None and ya is not None and ya >= yb:
                    spreads.append(ya - yb)

            row = {
                "series_ticker": series_ticker,
                "label": label,
                "status": status,
                "n_markets": len(mkts),
                "n_with_vol_24h": n_with_vol,
                "median_vol_24h_$": pd.Series(volumes_24h).median() if volumes_24h else None,
                "p95_vol_24h_$": pd.Series(volumes_24h).quantile(0.95) if volumes_24h else None,
                "median_total_vol_$": pd.Series(volumes_total).median() if volumes_total else None,
                "median_oi_$": pd.Series(ois).median() if ois else None,
                "median_spread_$": pd.Series(spreads).median() if spreads else None,
                "n_spread_obs": len(spreads),
            }
            print(
                f"  {series_ticker:18s} [{status:7s}] n={row['n_markets']:4d}  "
                f"vol24h_med=${row['median_vol_24h_$']!s}  "
                f"spread_med=${row['median_spread_$']!s}  "
                f"OI_med=${row['median_oi_$']!s}",
                flush=True,
            )
            rows.append(row)

            # Stash a settled market with real volume for the candlestick pull
            if status == "settled" and sample_for_candles is None:
                for m in mkts:
                    if (num(m.get("volume_24h_fp")) or 0) > 1000 and m.get("ticker"):
                        sample_for_candles = m
                        break

    df = pd.DataFrame(rows)
    out_csv = out_dir / "kalshi_nba_ingame_liquidity_v2.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nLiquidity table written to {out_csv}")

    # Candlestick pull on one sample market — proves 1-min price history is available.
    if sample_for_candles is None:
        print("\nNo settled market with >$1000 24h volume found for candle test.")
        return 0

    sample = sample_for_candles
    market_ticker = sample["ticker"]
    series_ticker = market_ticker.split("-")[0]
    occurrence = sample.get("occurrence_datetime")
    settlement = sample.get("settlement_ts")
    print(f"\n[candle] sample market: {market_ticker}")
    print(f"  title: {sample.get('title')}")
    print(f"  occurrence: {occurrence}  settlement: {settlement}")
    print(f"  volume_24h: ${sample.get('volume_24h_fp')}  OI: ${sample.get('open_interest_fp')}")

    # Use occurrence_datetime ± window for the candle pull
    try:
        from datetime import datetime, timezone

        # occurrence_datetime is like "2026-05-19T03:30:00Z"
        if occurrence and occurrence.endswith("Z"):
            occ_dt = datetime.fromisoformat(occurrence.replace("Z", "+00:00"))
        else:
            occ_dt = datetime.now(tz=timezone.utc)
        # Pull 4-hour window starting ~30 min before tipoff
        start_ts = int(occ_dt.timestamp()) - 30 * 60
        end_ts = start_ts + 4 * 60 * 60

        candles = client.get_candlesticks(
            series_ticker=series_ticker,
            market_ticker=market_ticker,
            start_ts=start_ts,
            end_ts=end_ts,
            period_interval=1,
        )
        n_candles = len(candles.get("candlesticks", []))
        print(f"  candlesticks (1-min): {n_candles} candles returned for the 4-hour window")
        if n_candles:
            first = candles["candlesticks"][0]
            mid = candles["candlesticks"][n_candles // 2]
            last = candles["candlesticks"][-1]
            print(f"  first candle keys: {list(first.keys())}")
            print(f"  first: {first}")
            print(f"  mid:   {mid}")
            print(f"  last:  {last}")
        # Persist for inspection
        (out_dir / f"kalshi_sample_candles_{market_ticker}.json").write_text(json.dumps(candles, indent=2))
        time.sleep(0.5)
    except Exception as exc:  # noqa: BLE001
        print(f"  candle fetch failed: {exc!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
