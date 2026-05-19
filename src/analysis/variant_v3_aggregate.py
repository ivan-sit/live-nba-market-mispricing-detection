"""V3 — Halawi-style aggregate (the midterm tie-back).

p̂_t = w1·p_model + w2·p_consensus (+ w3·p_published_wp, optional)
Weights selected on validation by Brier-minimization over a constrained
discrete grid {0, 0.25, 0.5, 0.75, 1.0} (1-SE rule for shrinkage).

Pre-registered H3: aggregate Brier strictly less than min(structural, market)
on the test set. Paired block-bootstrap by game.

The cleanest report narrative: maps directly onto Halawi's "4 LM : 1 crowd"
result. Implemented in Phase 3 (priority slot 4 of 6).
"""
