"""V4 — Time-series mean reversion / AR(1) + event-jumps.

Treat de-vigged market probability as a time series. Decompose into drift
predicted from PBP events (AR(1) with event-jump regressors) plus residual.
Residuals beyond k·σ flagged as excess movement; bet on reversion.

Compares against Croxson & Reade 2014 (semi-strong efficiency) null and
Choi & Hui 2014 (surprise overreaction) alternative.

Implemented in Phase 3 (priority slot 5 of 6).
"""
