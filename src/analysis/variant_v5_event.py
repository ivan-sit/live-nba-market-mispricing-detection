"""V5 — Event-conditioned overreaction.

Define salience events (trailing-team 3-pointer, dunk by trailing team,
8+ pt run, technical foul). For each event, measure (a) market shift over
the next 60-120s window and (b) calibrated structural model shift over the
same window. Overreaction = observed − expected.

Hosts both:
  H1 (primary, original pre-registration): trailing-team scoring in 10-15 pt
      deficits yields positive E[Δp_market − Δp_model].
  H4 (secondary pre-registration): trailing-team made 3-pointers in score-
      differential ≥10 yield positive E[Δp_market − Δp_structural] over 60s.

Block-bootstrap by game; one-sided p-values; Holm-Bonferroni across the
pre-registered set.

Implemented in Phase 3 (priority slot 2 of 6 — highest behavioral payoff).
"""
