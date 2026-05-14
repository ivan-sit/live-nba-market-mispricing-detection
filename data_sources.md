# Data Sources Survey

To be filled in by Day 3. Tag each source with: cost, coverage (years and
in-play vs pregame), license, format, and a one-line risk.

| Source | Type | Coverage | In-play? | Cost | License | Format | Risk |
|---|---|---|---|---|---|---|---|
| nba_api (stats.nba.com) | PBP | 1996–present (with caveats) | n/a | free | ToS, not commercial | JSON | rate limits, unofficial |
| the-odds-api.com | Odds | mid-2020+ featured markets | TBC via support email | tiered | commercial | JSON | snapshot cadence + cost |
| BigDataBall | Odds + box | varies | TBD | paid | commercial | xlsx/csv | TBD |
| SportsDataIO | Odds + stats | varies | yes (per docs) | paid | commercial | JSON | cost, terms |
| hoopR | PBP | ESPN-sourced, multi-season | n/a | free | MIT | parquet | R-first, indirect Python |
| kmd6225/NBA-Play-By-Play-Win-Probability | reference impl | n/a | n/a | free | OSS | code | implementation only |
| Kaggle: NBA Betting Data 2007–2025 | Closing odds | 2007–2025 | no (closing only) | free | varies | csv | closing-line proxy |
| Moskowitz (2021) JF replication archive | Reference | per paper | varies | TBD | academic | varies | may not be public |

References to flesh out during D3:
- the-odds-api historical docs: https://the-odds-api.com/historical-odds-data/
- nba_api: https://github.com/swar/nba_api
- hoopR: https://sportsdataverse.r-universe.dev/hoopR
- kmd6225: https://github.com/kmd6225/NBA-Play-By-Play-Win-Probability
- Moskowitz (2021) JF: https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.13082
