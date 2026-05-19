"""V2 — Calibrated structural WP vs market.

Wraps src/models/xgb_model.py + src/models/calibration.py. The structural
model's calibrated probability is the fair-value estimate. Mispricing is
p_model − p_market_devig.

This is the highest-priority variant (slot 1 of 6) and the workhorse for
H1 (the original pre-registered hypothesis).

Implemented in Phase 2.
"""
