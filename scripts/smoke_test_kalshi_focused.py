"""Focused Kalshi smoke test — in-game series only.

The exhaustive enumeration (smoke_test_kalshi.py) found 219 NBA-related
series but ran long. This focused pass hits only the in-game derivative
series we'd actually use for V1/V3 (cross-venue consensus) and reports
liquidity (markets count, status, bid/ask spread, 24h volume, open interest).

Run from repo root:
    uv run python scripts/smoke_test_kalshi_focused.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from src.data.pull_kalshi import KalshiClient  # noqa: E402

# Per-game in-game derivative series: per-quarter, per-half winners and
# spreads/totals. These are the ones that price during live game windows.
IN_GAME_SERIES = [
    ("KXNBA1HWINNER", "1st Half Winner"),
    ("KXNBA2HWINNER", "2nd Half Winner"),
    ("KXNBA1QWINNER", "1st Quarter Winner"),
    ("KXNBA2QWINNER", "2nd Quarter Winner"),
    ("KXNBA3QWINNER", "3rd Quarter Winner"),
    ("KXNBA4QWINNER", "4th Quarter Winner"),
    ("KXNBAFIRSTBASKET", "First Basket"),
    ("KXNBA1HSPREAD", "1st Half Spread"),
    ("KXNBA2HSPREAD", "2nd Half Spread"),
    ("KXNBA1HTOTAL", "1st Half Total"),
    ("KXNBA2HTOTAL", "2nd Half Total"),
    ("KXNBATEAMTOTAL", "Team Total"),
]


def main() -> int:
    client = KalshiClient()
    out_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for series_ticker, label in IN_GAME_SERIES:
        # Get any-status open + recent
        for status in ("open", "settled"):
            try:
                mkts = client.list_markets(series_ticker=series_ticker, status=status, limit=200)
            except Exception as exc:  # noqa: BLE001
                print(f"  {series_ticker} [{status}]: ERROR {exc!r}", flush=True)
                continue
            n_with_volume = sum(1 for m in mkts if (m.get("volume_24h") or 0) > 0)
            yes_bids = [m.get("yes_bid") for m in mkts if m.get("yes_bid") is not None]
            yes_asks = [m.get("yes_ask") for m in mkts if m.get("yes_ask") is not None]
            spreads = [a - b for a, b in zip(yes_asks, yes_bids, strict=False) if a is not None and b is not None]
            median_spread = pd.Series(spreads).median() if spreads else None
            total_vol_24h = sum((m.get("volume_24h") or 0) for m in mkts)
            print(
                f"  {series_ticker:18s} [{status:7s}] {label:25s}  "
                f"markets={len(mkts):3d}  with_vol_24h={n_with_volume:3d}  "
                f"median_spread={median_spread}  total_vol_24h={total_vol_24h}",
                flush=True,
            )
            rows.append(
                {
                    "series_ticker": series_ticker,
                    "label": label,
                    "status": status,
                    "n_markets": len(mkts),
                    "n_with_vol_24h": n_with_volume,
                    "median_spread": median_spread,
                    "total_vol_24h": total_vol_24h,
                }
            )
            if mkts and not (out_dir / f"kalshi_sample_{series_ticker}_{status}.json").exists():
                (out_dir / f"kalshi_sample_{series_ticker}_{status}.json").write_text(
                    json.dumps(mkts[:3], indent=2)
                )

    df = pd.DataFrame(rows)
    out_csv = out_dir / "kalshi_nba_ingame_liquidity.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSummary table written to {out_csv}")
    print(df.to_string(index=False))

    # Verdict
    print("\n=== Verdict inputs ===")
    open_rows = df[df["status"] == "open"]
    settled_rows = df[df["status"] == "settled"]
    if not open_rows.empty:
        print(f"OPEN: {open_rows['n_markets'].sum()} markets across {(open_rows['n_markets'] > 0).sum()} series; "
              f"{open_rows['n_with_vol_24h'].sum()} have 24h volume; "
              f"total 24h volume: {open_rows['total_vol_24h'].sum()}")
    if not settled_rows.empty:
        print(f"SETTLED (historical): {settled_rows['n_markets'].sum()} markets across "
              f"{(settled_rows['n_markets'] > 0).sum()} series")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
