"""the-odds-api v4 client for NBA odds (pregame + live).

Free tier (500 req/mo) covers /sports and current /odds (incl. in-play games).
The /historical endpoint is PAID — calling it on a free key returns 401/422.

Key is read from ODDS_API_KEY (loaded from .env, which is gitignored).
Docs: https://the-odds-api.com/liveapi/guides/v4/
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

BASE = "https://api.the-odds-api.com/v4"
SPORT_NBA = "basketball_nba"


def _load_key() -> str:
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        # minimal .env reader so we don't add a dependency
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("ODDS_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    if not key:
        raise RuntimeError("ODDS_API_KEY not set (env or .env)")
    return key


@dataclass
class Quota:
    remaining: int | None
    used: int | None

    @classmethod
    def from_headers(cls, h: Any) -> "Quota":
        def _int(v: str | None) -> int | None:
            try:
                return int(v) if v is not None else None
            except ValueError:
                return None

        return cls(
            remaining=_int(h.get("x-requests-remaining")),
            used=_int(h.get("x-requests-used")),
        )


class OddsAPIClient:
    def __init__(self, api_key: str | None = None, timeout: int = 20) -> None:
        self.api_key = api_key or _load_key()
        self.timeout = timeout
        self.last_quota: Quota | None = None

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        params = {**params, "apiKey": self.api_key}
        r = requests.get(f"{BASE}{path}", params=params, timeout=self.timeout)
        self.last_quota = Quota.from_headers(r.headers)
        r.raise_for_status()
        return r.json()

    def list_sports(self) -> list[dict]:
        """Validates the key; cheap. Returns active sports."""
        return self._get("/sports/", {"all": "true"})

    def nba_odds(
        self,
        regions: str = "us",
        markets: str = "h2h",
        odds_format: str = "american",
    ) -> list[dict]:
        """Current NBA odds across books. Includes in-play games (commence_time
        in the past, not yet completed) — that is our live-capture source."""
        return self._get(
            f"/sports/{SPORT_NBA}/odds/",
            {"regions": regions, "markets": markets, "oddsFormat": odds_format},
        )


def american_to_prob(price: float) -> float:
    """American odds -> implied probability (still includes vig)."""
    if price < 0:
        return (-price) / (-price + 100.0)
    return 100.0 / (price + 100.0)


def flatten_h2h(games: list[dict], capture_ts: str) -> list[dict]:
    """One row per (capture_ts, game, book, team). Long format so we can pivot
    to two-sided quotes per book for de-vigging / consensus later."""
    rows: list[dict] = []
    for g in games:
        gid = g.get("id")
        home = g.get("home_team")
        away = g.get("away_team")
        commence = g.get("commence_time")
        for b in g.get("bookmakers", []):
            mk = next((m for m in b.get("markets", []) if m.get("key") == "h2h"), None)
            if not mk:
                continue
            for o in mk.get("outcomes", []):
                price = o.get("price")
                if price is None:
                    continue
                rows.append(
                    {
                        "capture_ts": capture_ts,
                        "game_id": gid,
                        "commence_time": commence,
                        "home_team": home,
                        "away_team": away,
                        "book": b.get("title"),
                        "book_last_update": b.get("last_update"),
                        "team": o.get("name"),
                        "price_american": price,
                        "implied_prob": american_to_prob(float(price)),
                    }
                )
    return rows
