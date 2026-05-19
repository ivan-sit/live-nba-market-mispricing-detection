"""Backtest engine — threshold + fractional-Kelly sizing + realistic vig.

Wagers are sized as `kelly_fraction * kelly(edge, american_odds)` and applied
at the book's quoted (vigged) odds, never the de-vigged probability. Returns
are computed per-bet and aggregated to per-game P&L. Block-bootstrap by game
gives Sharpe / drawdown CIs that respect the true unit of correlation.

Naive baseline strategies (always-bet-favorite, always-bet-trailing, random)
are included for sanity — they should lose roughly the vig.

Implemented in Phase 4.
"""
