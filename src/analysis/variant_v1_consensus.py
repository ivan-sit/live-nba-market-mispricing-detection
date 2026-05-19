"""V1 — Cross-venue consensus deviation.

p̂_t = EWMA( median_venue( devig(venue_prob_t) ), span=120s )
edge_{t, venue} = devig(venue_t) − p̂_t

Pre-registered H2: median spread > 1.5 × pooled vig has positive expected
reversion over the next 60s.

Implemented in Phase 3 (priority slot 3 of 6).
"""
