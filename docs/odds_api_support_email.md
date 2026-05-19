# Email Draft — the-odds-api Support

**To:** `support@the-odds-api.com` (or whatever address they list on their
contact page)
**Subject:** Historical NBA in-play coverage & multi-book snapshot questions
— STATS 211 academic research

---

Hello,

I'm a UCLA student working on a STATS 211 final project (Topics in Economics
and Machine Learning, Prof. Xiaowu Dai). We're studying live-market
mispricing in NBA games as a behavioral asset-pricing test. Before we
decide on a paid tier, I have a few specific questions about your historical
NBA coverage that aren't fully clear from the public docs:

1. **In-play snapshots for NBA.** Your historical events endpoint advertises
   5-minute snapshots. For NBA *specifically*, do these snapshots include
   **in-game / in-play** moneyline (and ideally spread/total) prices during
   live game windows, or only pregame lines? If both, what fraction of
   snapshots in a typical 2023–24 or 2024–25 NBA game fall after tipoff?

2. **Suspension states.** Books suspend in-play markets around scoring
   events. Are suspended snapshots returned with an explicit `suspended`
   status flag, or are they silently omitted? If omitted, is there any way
   to distinguish "no snapshot because no movement" from "no snapshot
   because the book was paused"?

3. **Coverage percentage.** For the 2023–24 and 2024–25 NBA regular seasons
   specifically, roughly what fraction of regular-season games have at
   least one in-play snapshot in your data?

4. **Multi-book snapshots.** Our analysis design requires prices from
   **multiple sportsbooks at the same timestamp** (cross-venue consensus is
   the core of one of our methods). When we query the historical event
   endpoint, do snapshots return multiple books simultaneously, or do we
   need separate requests per book? If multi-book, which US books are
   typically present for NBA in-play?

5. **Pricing / quota.** Given the above, can you estimate the credit cost
   of pulling one full NBA regular season of in-play snapshots
   (single market = moneyline, two books, 5-min cadence)? Just an order
   of magnitude — we're trying to decide between a one-month paid
   subscription and an alternate data path.

The work is for academic use only — a class presentation and a 3-page
NeurIPS-format report — and we'll cite the-odds-api as the data source.

Thanks for your time,

Ming Yin Ivan Sit
UCLA STATS 211 (Spring 2026)
ivansit1214@gmail.com
