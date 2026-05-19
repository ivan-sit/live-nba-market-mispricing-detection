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

## 2026-05-18 — Methodology broadened to a multi-variant bake-off

**Decision:** Replace single-method analysis with a shared evaluation harness
that supports K mispricing-detection variants. Variants share splits, metrics,
backtest engine, and pre-registered tests. See plan at
`~/.claude/plans/indexed-bubbling-owl.md` for full design.

**Six variants (priority order if time-bounded):**
V2 (calibrated structural WP) → V5 (event-conditioned overreaction) → V1
(cross-venue consensus deviation) → V3 (Halawi-style aggregate) → V4
(time-series mean reversion) → V6 (cross-book hard arbitrage descriptive).

**Why this is methodologically stronger:** maps to Halawi's "no single source
dominates" framing. Lets us report which behavioral mechanism (overreaction
to salience events / cross-venue disagreement / fundamental mispricing) carries
the result, not just whether mispricing exists.

---

## 2026-05-18 — Secondary pre-registrations (LOCKED before test-set data is pulled)

**Status:** Locked 2026-05-18, before any live-odds data has been pulled.

**Pre-registered secondary tests (Holm-Bonferroni across all four including H1):**

**H2 (V1 — cross-venue consensus deviation):**
For any tick where median spread across venues exceeds 1.5 × pooled vig, the
expected return on the side cheaper than consensus, sized at fixed ¼-Kelly,
is positive over the next K=60s window. Test statistic: mean of game-level
mean returns. Inference: block-bootstrap by game, one-sided.

**H3 (V3 — Halawi-style aggregate):**
The Brier score of the weight-tuned aggregate `w1·p_model + w2·p_consensus`
on the test set is strictly less than min(structural Brier, market Brier).
Weights selected by Brier-minimization on the validation fold only; weights
are not re-tuned on test. Inference: paired block-bootstrap by game on
Brier differences.

**H4 (V5 — generalized event overreaction):**
For trailing-team made 3-pointers in score-differential bucket ≥10, the
60-second-forward market shift exceeds the 60-second-forward calibrated
structural model shift on average. Test statistic: mean of game-level
mean differences. Inference: block-bootstrap by game, one-sided.

**Multiple-comparisons plan:** Holm-Bonferroni across {H1, H2, H3, H4}.
H1 remains the primary; H2–H4 are secondary pre-registered. All other
results in the bake-off (V4, V6, additional buckets) are exploratory and
clearly labeled as such in the report.

**No post-hoc modification:** if a hypothesis is reformulated after looking
at any test-set odds, it is moved to the exploratory section with a dated
note here. Validation-set fits and Brier weight selection (for H3) are
permitted; test-set fits are not.

---

## Open decisions (to resolve in Week 1)

- **Tick granularity** of the game-state table: per-possession vs per-N-second.
  Leaning per-possession for the model, resampled to 5-min snapshots for the
  odds join. Lock by end of D4.
- **Final live-odds source.** Lock by end of D3 after Odds API audit + vendor survey + Kalshi smoke test.
- **Kalshi inclusion in V1/V3:** depends on in-game NBA liquidity. Smoke-test D3.
- **Feature inclusion list.** Initial set in `CLAUDE.md`. Confirm or adjust by D4.
