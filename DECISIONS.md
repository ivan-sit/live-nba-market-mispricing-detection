# Decisions Log

Append-only log of methodological decisions. Each entry: date, decision,
rationale, alternatives considered. We use this directly when writing the
report's Methodology section.

---

## 2026-05-14 — Sport and seasons

**Decision:** NBA only, target 5 seasons of play-by-play (2019–20 through 2024–25
regular seasons). Test set will be bounded by live-odds availability, expected to
be ~3.5 seasons in practice (the-odds-api begins mid-2020 for featured markets).

**Rationale:** NBA gives ~1,230 regular-season games/season and a possession every
~24 seconds, orders of magnitude more in-game datapoints than NFL. Doing one sport
well beats doing two poorly.

**Alternatives:** NBA + NFL (rejected — NFL has only ~272 regular-season games,
and the per-game tick density is much lower).

---

## 2026-05-14 — Dependency / environment manager

**Decision:** `uv` with `pyproject.toml`. Python 3.11.

**Rationale:** Single binary, fast, lockfile, modern. Easier setup than Poetry.

---

## 2026-05-14 — Live-odds data acquisition plan

**Decision (path, not endpoint yet):**

1. Sign up for the-odds-api free tier — no payment yet.
2. Read historical-odds docs carefully; verify what "historical" covers for NBA
   in-play (vs only pregame).
3. Email the-odds-api support: "For NBA, do your historical snapshots from 2023+
   include in-play odds during games, or only pregame? At 5-minute intervals?"
4. Run one test query on a known 2024 NBA Finals game with free credits to
   validate format.
5. **Then** decide: paid the-odds-api / alternate vendor / synthetic-fair-odds
   fallback. Log the decision here before any test-set data is pulled.

**Rationale:** Avoid sunk-cost on a paid plan before confirming what we actually
get. Live in-play odds is the load-bearing piece of the project; if it doesn't
exist at sufficient cadence, the analysis design changes.

---

## 2026-05-14 — Pre-registered primary hypothesis (LOCKED before test-set odds pull)

**Hypothesis H1 (trailing-team overreaction after a scoring event):**

Conditional on a trailing team being down by 10–15 points and scoring a basket
(2 or 3 point field goal) within a single possession, the market-implied (de-vigged)
win probability for the trailing team shifts upward by *more* than our model's
posterior win-probability shift across the same event, on average. Formally:

> H1:  E[ Δp_market − Δp_model | trailing 10–15, scoring event ] > 0

**Test statistic:** Mean of game-level mean differences. (Average within game
first to control game-level correlation, then average across games.)

**Inference:** Block-bootstrap by game with 10,000 resamples; one-sided p-value.

**Pre-specified score-differential buckets** (for the broader mispricing analysis
in Phase 3): close (≤5), 5–10, 10–15, 15+. The 10–15 bucket is the headline.

**Multiple-comparisons plan:** H1 is the primary test. The other three buckets
(close / 5–10 / 15+) are exploratory and will be reported with a Holm–Bonferroni
correction across the three secondary tests.

**Edge threshold for mispricing flag:** |p_model − p_market_devig| > 0.05.

**Lock date:** 2026-05-14. **Do not modify these thresholds after looking at the
test-set odds.** Any post-hoc changes get a dated entry below and are clearly
labeled as exploratory in the report.

---

## 2026-05-14 — Calibration approach

**Decision:** XGBoost will be wrapped in a post-hoc calibration layer (isotonic
regression by default; Platt scaling as a sensitivity check) fit on a held-out
validation fold. Reliability diagrams reported pre- and post-calibration.

**Rationale:** GBDTs are routinely miscalibrated at the probability tails — and
the whole project hinges on calibrated probabilities, not classification
accuracy.

---

## 2026-05-14 — Cross-validation unit

**Decision:** All cross-validation is at the **game** level (`GroupKFold` on
`game_id`), not the tick / row level.

**Rationale:** Within-game ticks are highly correlated; row-level CV would
overstate performance dramatically.

---

## 2026-05-14 — Published-baseline comparison

**Decision:** For NBA in-game WP, baseline comparisons are Bashuk-style
possession-based WP, Stern (1994) Brownian-motion-style WP, and
inpredictable.com's published Brier numbers if reproducible from their methodology.
Lock & Nettleton was mentioned in `CLAUDE.md` but is an *NFL* model — we do not
compare to it directly for NBA.

---

## Open decisions (to resolve in Week 1)

- **Tick granularity** of the game-state table: per-possession vs per-N-second.
  Leaning per-possession for the model, resampled to 5-min snapshots for the
  odds join. Lock by end of D4.
- **Final live-odds source.** Lock by end of D3 after Odds API audit + vendor survey.
- **Feature inclusion list.** Initial set in `CLAUDE.md`. Confirm or adjust by D4.
