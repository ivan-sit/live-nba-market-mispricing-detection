"""V6 — Cross-book hard arbitrage (descriptive only).

Detects ticks where sum_of_implied_probs(book_A_home, book_B_away) < 1 —
literal arbitrage. Reports frequency, magnitude, duration to close. Not a
strategy (books limit accounts that hit arb), but produces a striking
market-efficiency figure for the report.

Implemented in Phase 3 (priority slot 6 of 6, low-effort high-visual).
"""
