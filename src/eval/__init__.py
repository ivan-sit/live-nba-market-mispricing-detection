"""Shared evaluation harness for the multi-variant bake-off.

Every mispricing-detection variant (V1..V6) plugs into the same protocol:
fit on train+val, produce a fair-value estimate p̂_t per tick, and the harness
takes care of calibration metrics, mispricing-distribution plots, the backtest
engine, and the pre-registered H1-H4 tests.

The implementations of the metrics, splits, backtest, and harness modules are
filled in during Phase 2. The pre-registration discipline is enforced here:
test-set fits are not allowed; only val-set fits and val-set hyperparameter
selection are permitted.
"""
