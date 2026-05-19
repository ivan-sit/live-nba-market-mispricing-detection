"""Calibration and accuracy metrics.

Provides Brier, log-loss, accuracy at thresholds, reliability binning, and
RMS calibration error. Reliability diagrams and ECE are computed from the
binned data. All functions accept aligned arrays of `p` and `y` and return
either a scalar or a small DataFrame depending on the metric.

Implemented in Phase 2.
"""
