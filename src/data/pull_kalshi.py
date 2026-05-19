"""Kalshi public market-data client.

Read-only — no auth required. Free public API. Base URL is
`https://external-api.kalshi.com/trade-api/v2`.

We use Kalshi as a cross-venue source for the V1/V3 variants. Its prices are
peer-driven (orderbook), CFTC-regulated, and structurally independent from
sportsbook-set prices — exactly what V1's consensus-deviation framing needs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
DEFAULT_TIMEOUT = 30


@dataclass
class KalshiClient:
    """Thin wrapper over Kalshi's public market-data endpoints."""

    base_url: str = BASE_URL
    timeout: int = DEFAULT_TIMEOUT
    user_agent: str = "stats211-final-research/0.1 (academic; ivan-sit github)"

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        r = requests.get(url, params=params or {}, timeout=self.timeout, headers={"User-Agent": self.user_agent})
        r.raise_for_status()
        return r.json()

    def list_series(self, category: str | None = None) -> list[dict[str, Any]]:
        """List series. Optionally filter by category (e.g., 'Sports')."""
        params: dict[str, Any] = {}
        if category:
            params["category"] = category
        data = self._get("/series", params=params)
        return data.get("series", []) or data.get("data", [])

    def list_markets(
        self,
        series_ticker: str | None = None,
        event_ticker: str | None = None,
        status: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """List markets, optionally filtered by series, event, or status.

        status one of: 'open', 'closed', 'settled', 'unopened'.
        """
        out: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": limit}
            if series_ticker:
                params["series_ticker"] = series_ticker
            if event_ticker:
                params["event_ticker"] = event_ticker
            if status:
                params["status"] = status
            if cursor:
                params["cursor"] = cursor
            data = self._get("/markets", params=params)
            out.extend(data.get("markets", []))
            cursor = data.get("cursor")
            if not cursor:
                break
            time.sleep(0.2)  # be polite
        return out

    def get_event(self, event_ticker: str) -> dict[str, Any]:
        return self._get(f"/events/{event_ticker}")

    def get_series(self, series_ticker: str) -> dict[str, Any]:
        return self._get(f"/series/{series_ticker}")

    def get_orderbook(self, market_ticker: str, depth: int = 10) -> dict[str, Any]:
        return self._get(f"/markets/{market_ticker}/orderbook", params={"depth": depth})

    def get_market(self, market_ticker: str) -> dict[str, Any]:
        return self._get(f"/markets/{market_ticker}")

    def get_candlesticks(
        self,
        series_ticker: str,
        market_ticker: str,
        start_ts: int,
        end_ts: int,
        period_interval: int = 1,
    ) -> dict[str, Any]:
        """Get OHLC candles for a market. period_interval in minutes (1, 60, 1440).

        Recent/live markets only. For settled-past-cutoff markets, use
        get_historical_candlesticks below.
        """
        return self._get(
            f"/series/{series_ticker}/markets/{market_ticker}/candlesticks",
            params={"start_ts": start_ts, "end_ts": end_ts, "period_interval": period_interval},
        )

    def get_historical_candlesticks(
        self,
        market_ticker: str,
        start_ts: int,
        end_ts: int,
        period_interval: int = 1,
    ) -> dict[str, Any]:
        """Historical candlesticks for markets settled before the historical cutoff."""
        return self._get(
            f"/historical/markets/{market_ticker}/candlesticks",
            params={"start_ts": start_ts, "end_ts": end_ts, "period_interval": period_interval},
        )
