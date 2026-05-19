# Data Sources Survey

To be filled in by Day 3. Tag each source with: cost, coverage (years and
in-play vs pregame), license, format, and a one-line risk.

| Source | Type | Coverage | In-play? | Cost | License | Format | Risk |
|---|---|---|---|---|---|---|---|
| nba_api (stats.nba.com) | PBP | 1996–present (with caveats) | n/a | free | ToS, not commercial | JSON | rate limits, unofficial |
| the-odds-api.com | Odds (sportsbooks) | mid-2020+ featured markets | TBC via support email | tiered | commercial | JSON | snapshot cadence + cost |
| **Kalshi** | **Peer-driven prediction market** | **NBA contracts from 2024-25+** | **yes (per docs)** | **free public API** | **commercial-friendly** | **JSON (REST + WS)** | **in-game NBA liquidity unverified** |
| BigDataBall | Odds + box | varies | TBD | paid | commercial | xlsx/csv | TBD |
| SportsDataIO | Odds + stats | varies | yes (per docs) | paid | commercial | JSON | cost, terms |
| hoopR | PBP | ESPN-sourced, multi-season | n/a | free | MIT | parquet | R-first, indirect Python |
| kmd6225/NBA-Play-By-Play-Win-Probability | reference impl | n/a | n/a | free | OSS | code | implementation only |
| Kaggle: NBA Betting Data 2007–2025 | Closing odds | 2007–2025 | no (closing only) | free | varies | csv | closing-line proxy |
| Moskowitz (2021) JF replication archive | Reference | per paper | varies | TBD | academic | varies | may not be public |

### Why Kalshi matters for our bake-off

Kalshi is the cross-venue source that breaks the "sportsbooks all share the
same algorithmic prior" trap. It's CFTC-regulated, peer-driven (orderbook,
not house-set), and its prices reflect retail prediction-market participants
rather than sportsbook risk desks. For V1 (cross-venue consensus) and V3
(Halawi-style aggregate), including Kalshi gives a genuinely independent
probability signal. Free public API for market data; live WebSocket for active
markets.

**Smoke test verdict (2026-05-18): GREEN — Kalshi is committed.**

Headline numbers from Task #11:
- 219 NBA-related series total in the catalog.
- `KXNBA1HWINNER` (1st-half winner) has **978 settled markets** in the
  archive (~325 unique games), with marquee playoff games trading $148k–$268k
  per outcome in 24 hours.
- 1-minute resolution price candles confirmed via
  `/series/{s}/markets/{m}/candlesticks` — full OHLC of price, bid, ask, plus
  per-minute volume and open interest.
- Median spread ~$0.04 on $1 contracts = 4% — comparable to sportsbook vig.

Constraint: Kalshi has no per-game moneyline market for NBA — only per-half
and (potentially) per-quarter winners. Our V1/V3 cross-venue comparisons are
therefore framed at the **first-half-winner horizon**. The per-half framing
also matches sportsbook 1H markets directly, so the comparison is
apples-to-apples.

See `DECISIONS.md` (2026-05-18 entry: Kalshi smoke test result) for the full
evidence table and the impact on H1/H2/H3/H4 pre-registered tests.

References to flesh out during D3:
- the-odds-api historical docs: https://the-odds-api.com/historical-odds-data/
- nba_api: https://github.com/swar/nba_api
- hoopR: https://sportsdataverse.r-universe.dev/hoopR
- kmd6225: https://github.com/kmd6225/NBA-Play-By-Play-Win-Probability
- Moskowitz (2021) JF: https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.13082
