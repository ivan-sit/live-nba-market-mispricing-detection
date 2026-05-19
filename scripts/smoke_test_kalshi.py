"""Kalshi free-API smoke test.

Goals (per Phase 0 D3):
  1. Enumerate currently-active NBA-related markets on Kalshi.
  2. For each, capture status, bid/ask spread, 24h volume, open interest.
  3. Estimate in-game NBA liquidity: how many in-play markets per game, what's
     the typical spread.
  4. Output a single summary table; decide whether Kalshi enters V1/V3 as a
     real cross-venue source or pregame-anchor-only.

Run from repo root:
    uv run python scripts/smoke_test_kalshi.py
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


def main() -> int:
    client = KalshiClient()
    out_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) List Sports-category series and find NBA-related ones.
    print("[1] Listing Sports-category series ...", flush=True)
    try:
        sports_series = client.list_series(category="Sports")
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR: {exc!r}", file=sys.stderr)
        print("  Falling back to listing ALL series (no category filter)")
        sports_series = client.list_series()

    nba_series = [
        s for s in sports_series
        if "nba" in s.get("ticker", "").lower() or "nba" in s.get("title", "").lower()
    ]
    print(f"    found {len(sports_series)} sports series total; {len(nba_series)} NBA-related")
    for s in nba_series:
        print(f"      - {s.get('ticker', '?'):20s}  {s.get('title', '?')}")

    if not nba_series:
        print("\nNo NBA series found via 'Sports' category. Trying ticker search 'KXNBA' ...")
        try:
            s_ticker = client.get_series("KXNBA")
            print(f"  KXNBA series: {s_ticker.get('series', s_ticker)}")
            nba_series = [s_ticker.get("series", s_ticker)]
        except Exception as exc:  # noqa: BLE001
            print(f"  KXNBA fetch failed: {exc!r}")

    # 2) For each NBA series, pull markets with various statuses.
    rows: list[dict] = []
    sample_markets_dumped = False
    for s in nba_series:
        st = s.get("ticker") or s.get("series_ticker")
        if not st:
            continue
        print(f"\n[2] Markets under series {st}:")
        for status in ("open", "unopened", "closed", "settled"):
            try:
                mkts = client.list_markets(series_ticker=st, status=status, limit=200)
            except Exception as exc:  # noqa: BLE001
                print(f"    status={status}: ERROR {exc!r}")
                continue
            print(f"    status={status}: {len(mkts)} markets")
            for m in mkts:
                rows.append(
                    {
                        "series_ticker": st,
                        "market_ticker": m.get("ticker"),
                        "title": m.get("title") or m.get("subtitle"),
                        "status": m.get("status"),
                        "yes_bid": m.get("yes_bid"),
                        "yes_ask": m.get("yes_ask"),
                        "no_bid": m.get("no_bid"),
                        "no_ask": m.get("no_ask"),
                        "last_price": m.get("last_price"),
                        "volume": m.get("volume"),
                        "volume_24h": m.get("volume_24h"),
                        "open_interest": m.get("open_interest"),
                        "expiration_time": m.get("expiration_time") or m.get("close_time"),
                    }
                )
            if mkts and not sample_markets_dumped:
                sample_path = out_dir / f"kalshi_sample_markets_{st}_{status}.json"
                sample_path.write_text(json.dumps(mkts[:5], indent=2))
                print(f"      sample dumped to {sample_path.name}")
                sample_markets_dumped = True

    if not rows:
        print("\nNo NBA markets found via series filter. Last resort: search /markets directly.")
        try:
            all_open = client.list_markets(status="open", limit=1000)
            nba_open = [
                m for m in all_open
                if "nba" in (m.get("title", "") or "").lower()
                or "nba" in (m.get("ticker", "") or "").lower()
            ]
            print(f"    /markets?status=open returned {len(all_open)} total, {len(nba_open)} NBA-matching by title/ticker")
            for m in nba_open[:50]:
                rows.append(
                    {
                        "series_ticker": m.get("series_ticker"),
                        "market_ticker": m.get("ticker"),
                        "title": m.get("title"),
                        "status": m.get("status"),
                        "yes_bid": m.get("yes_bid"),
                        "yes_ask": m.get("yes_ask"),
                        "no_bid": m.get("no_bid"),
                        "no_ask": m.get("no_ask"),
                        "last_price": m.get("last_price"),
                        "volume": m.get("volume"),
                        "volume_24h": m.get("volume_24h"),
                        "open_interest": m.get("open_interest"),
                        "expiration_time": m.get("expiration_time") or m.get("close_time"),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            print(f"    /markets fallback failed: {exc!r}")

    # 3) Summarize.
    if not rows:
        print("\n*** No NBA markets found. Kalshi may not have NBA in-play at this moment, or API surface differs. ***")
        return 2

    df = pd.DataFrame(rows)
    # Derive spread in cents (prices on Kalshi are in cents 1-99).
    df["spread"] = pd.to_numeric(df["yes_ask"], errors="coerce") - pd.to_numeric(df["yes_bid"], errors="coerce")

    print("\n=== Summary ===")
    print(f"NBA-related markets found: {len(df)}")
    print(df["status"].value_counts(dropna=False).to_string())
    print("\nTop 15 by volume_24h:")
    print(
        df.sort_values("volume_24h", ascending=False, na_position="last")
        .head(15)[["market_ticker", "title", "status", "yes_bid", "yes_ask", "spread", "volume_24h", "open_interest"]]
        .to_string(index=False)
    )

    out_csv = out_dir / "kalshi_nba_markets_smoke.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}")

    # 4) Verdict heuristic.
    n_open = (df["status"] == "open").sum()
    n_active_24h = (pd.to_numeric(df["volume_24h"], errors="coerce") > 0).sum()
    print(f"\nVerdict inputs: n_open={n_open}, n_with_24h_volume={n_active_24h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
