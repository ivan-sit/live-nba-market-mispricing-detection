# Mispricing-Detection Variant Strategies

Six methodologically distinct ways to detect mispricings in the live NBA 1st-half
winner market. They share a single evaluation harness (same splits, same
metrics, same backtest engine, same pre-registered tests) so the results are
directly comparable.

Every variant produces a scalar **fair-value estimate** `p̂_t` of P(home wins
1st half | game state at minute t). The mispricing signal is:

```
edge_t = p̂_t − p_market_devig_t
```

where `p_market_devig_t` is the de-vigged market-implied probability. Positive
edge means the variant thinks the home side is **underpriced**; negative means
overpriced.

> **Priority order if time runs out** (locked 2026-05-18):
> V2 → V5 → V1 → V3 → V4 → V6.
> The first three give us a complete publishable result; V3 completes the
> Halawi tie-back narrative; V4 and V6 are bonus.

---

## V1 — Cross-venue consensus deviation

**One-line idea:** the market's own disagreement is a mispricing signal.

**Fair-value estimator:**

```
p̂_t = EWMA( median_venue( devig(venue_prob_t) ), span = 120s )
edge_{t, venue} = devig(venue_prob_t) − p̂_t
```

At each tick, collect quotes from N venues (sportsbooks + Kalshi peer-driven
prices). Build a consensus as the **median** of de-vigged implied probabilities.
Smooth within-game via an exponentially-weighted moving average. Flag mispricing
as any individual venue's deviation from consensus beyond `k * σ_t`, where `σ_t`
is the rolling within-game volatility.

**Why Kalshi matters here:** Kalshi is CFTC-regulated, peer-driven, has no
house vig in the same form. Including it means consensus isn't dominated by
sportsbooks' shared algorithmic priors. Genuinely independent error source.

**Data required:** ≥3 venues per tick. Free Kalshi (1H winner candles) +
≥2 sportsbooks (the-odds-api). Cadence ≤60s ideal.

**Pre-registered test hosted: H2** — median spread > 1.5 × pooled vig has
positive expected reversion at 60s.

**Pros:** Model-free. Cross-venue spreads are *directly* visible mispricing.

**Cons:** Can't distinguish "consensus is wrong" from "one venue is wrong."
Captures market microstructure inefficiency, not necessarily behavioral bias.

**Lit anchor:** Hasbrouck (consolidated tape); Croxson & Reade 2014 (in-play
news incorporation); Angelini, De Angelis & Singleton 2021.

**Status:** ⏸ blocked on multi-venue odds.

---

## V2 — Calibrated structural WP vs market (the workhorse)

**One-line idea:** our calibrated XGBoost is the "fundamental value"; deviations
from it are mispricings.

**Fair-value estimator:** the calibrated XGB output.

```
p̂_t = isotonic( xgb.predict_proba(state_t) )
edge_t = p̂_t − p_market_devig_t
```

Trained on per-minute 1st-half snapshots with four basic features:
`minute_idx, score_diff_home, recent_run_diff, period`. Feature ablation
showed engineered interactions (leverage, abs_score_diff,
score_diff_x_remaining, possession_proxy) did not beat the 0.005-Brier
keep-or-drop threshold — basic features stayed.

**Data required:** PBP only (the *model* doesn't need odds; the *comparison*
does).

**Pre-registered test hosted: H1 (primary)** — trailing 10–15 made FG →
`E[Δp_market − Δp_model] > 0`.

**Pros:** Fundamentals-based. Speaks directly to behavioral economics
literature. Reproduces the Halawi midterm framing.

**Cons:** Model risk — if the structural model is itself miscalibrated, edges
are spurious. Mitigated by isotonic calibration on a held-out fold +
game-level CV + cross-check against published WP Brier numbers.

**Lit anchor:** Stern 1994 (Brownian-motion WP); Lock & Nettleton 2014 (NFL
random forest WP, adapted not copied); Bashuk possession-based WP; Lopez &
Matthews.

**Current numbers:**
- Test Brier (2024-25, out of sample): **0.149**
- Test ECE (2024-25): **0.008** — well-calibrated

**Status:** ✅ DONE.

---

## V3 — Halawi-style aggregate (the midterm tie-back)

**One-line idea:** combine the structural model and the market consensus the way
Halawi combined LM and crowd — the aggregate beats either alone.

**Fair-value estimator:**

```
p̂_t = w1 · p_model + w2 · p_consensus  (+ optional w3 · p_published_wp)
edge_t = p̂_t − p_market_t
```

Weights chosen by Brier-minimization on the **validation** fold, over a
constrained discrete grid `{0, 0.25, 0.5, 0.75, 1.0}` with a 1-SE rule for
shrinkage. Weights are **not** re-tuned on the test set.

**Why this is the cleanest report narrative:** Halawi showed aggregation works
because LM and crowd errors are independent. Here, the structural model gets
weight from game state; the market gets sentiment and inside information.
Those are partially-independent error sources. The aggregate is the direct
Halawi analog.

**Data required:** V2 components + multi-venue prices (for `p_consensus`).

**Pre-registered test hosted: H3** — aggregate Brier strictly less than
`min(structural Brier, market Brier)` on the test set. Paired block-bootstrap
by game on Brier differences.

**Pros:** Likely to beat any single component in Brier. The clean intellectual
through-line from the midterm to the final.

**Cons:** Adds a validation step. Weights can overfit if the validation fold
is small — discrete grid mitigates.

**Lit anchor:** Halawi et al. 2024 (NeurIPS); Bates & Granger 1969 (forecast
combination); Genest & Zidek 1986 (linear opinion pool).

**Status:** ⏸ blocked on V1 components (multi-venue odds).

---

## V4 — Time-series mean reversion / event-jump filter

**One-line idea:** treat the live market probability as a time series; bet
against transient overshoots beyond what PBP events justify.

**Fair-value estimator:**

```
p̂_t = predicted_market_t   (AR(1) + jumps from PBP events, fit on train)
edge_t = p̂_t − p_market_t  (bet on reversion to predicted level)
```

Decompose the de-vigged market probability into drift (from time/score) plus
PBP-event-driven jumps. Residuals beyond `k · σ_t` are flagged as **excess
market movement** and bet against (mean-reversion).

**Data required:** in-play odds at decent cadence. Doesn't strictly need a
structural model — only the AR(1) + jumps regression.

**Why include it:** doesn't require us to claim our model is better than the
market — only that the market temporarily overshoots. Closer to Moskowitz's
empirical setup.

**Pros:** Methodologically distinct from V2/V5 (which need a calibrated model).
Tests a different theoretical claim (delayed correction).

**Cons:** What counts as "normal" event jumps depends on training-set fit.
If PBP-event jump distributions shift season-to-season, predictions break.

**Lit anchor:** Choi & Hui 2014 (surprise → overreaction; routine → under-
reaction); Avery & Chevalier 1999 (sentiment paths); Croxson & Reade 2014
(semi-strong efficiency at goal arrival — the null we test against).

**Status:** ⏸ blocked on in-play odds time series.

---

## V5 — Event-conditioned overreaction (hosts the pre-registered behavioral test)

**One-line idea:** measure how the market reacts to specific salience events
(trailing-team scoring, runs, technicals), compare to how our calibrated model
reacts, bet against the **excess** market shift.

**Fair-value estimator:**

```
expected_market_shift = predicted from regression on event type + game state
                         (fit on training set)
observed_market_shift  = p_market(t + window) − p_market(t)
overreaction          = observed_market_shift − expected_market_shift
edge ∝ overreaction (with sign)
```

The window is **60 seconds** (pre-registered). Events: trailing-team made FG,
trailing-team made 3-pointer, 8+-point run, technical foul (initial event set;
we may add more if they remain unpre-registered as exploratory).

**Data required:** PBP events (we have it) + in-play odds at ≥60s cadence
(blocked).

**Pre-registered tests hosted:**

- **H1 (primary, locked 2026-05-14)**: trailing team in 10–15 pt deficit
  scores a basket → `E[Δp_market − Δp_model] > 0` (one-sided, game-level
  block-bootstrap).
- **H4 (secondary, locked 2026-05-18)**: trailing team in ≥10 pt deficit
  makes a 3-pointer → same direction.

**Structural-side results (already in hand, out-of-sample on 2024-25):**

| | n events | n games | Mean structural shift | 95% CI | p |
|---|---|---|---|---|---|
| H1 | 4,596 | 947 | **+0.0075** | [+0.005, +0.010] | <0.0001 |
| H4 | 2,162 | 780 | **+0.0138** | [+0.011, +0.017] | <0.0001 |

The structural model already shifts in the predicted direction. The
behavioral test then asks: **does the market shift by MORE than this?**

**Pros:** The most direct test of the behavioral hypothesis. H1 *is* the
primary pre-registered test. Sample size at the event-bucket level is large
(thousands of events per bucket).

**Cons:** Power depends on event frequency × window length. Events are
sparser than ticks, so effective n is event-count, not tick-count.

**Lit anchor:** Moskowitz 2021 (delayed overreaction in pregame-to-close
prices); Ötting et al. 2022 (NBA momentum and handle); Choi & Hui 2014
(surprise overreaction in soccer in-play).

**Status:** 🔵 structural side done. Market side blocked on odds.

---

## V6 — Cross-book hard arbitrage (descriptive, not predictive)

**One-line idea:** when two books literally let you arb both sides, document it.

```
sum_implied_prob_raw(book_A_home, book_B_away) < 1   →   hard arbitrage
```

When the de-vigged implied probabilities from two different books sum to less
than 1 (i.e., before applying overround on either side), you can buy both
outcomes and lock a guaranteed profit. Not a strategy in practice — books limit
accounts that hit arb — but the **existence** of these moments is a striking
market-efficiency descriptor.

**Data required:** ≥2 venues per tick.

**Pre-registered test hosted:** none (descriptive).

**Pros:** Cheap to compute. Produces a striking figure for the report
("hard arbitrage existed at N% of in-play snapshots, with median magnitude X").

**Cons:** Not tradeable at scale. Says nothing about behavior — just
inefficiency.

**Lit anchor:** Kuypers 2000; Forrest, Goddard & Simmons 2005.

**Status:** ⏸ blocked on multi-book odds.

---

## Pre-registration discipline (locked before any test-set odds were touched)

All four tests below are pre-registered, locked in `DECISIONS.md`, and on the
git record before any test-set odds data was pulled. Holm-Bonferroni across
the set of four.

| ID | Variant | Claim | Inference |
|---|---|---|---|
| **H1** | V5 | Trailing 10–15 made FG → `E[Δp_market − Δp_model] > 0` | Block-bootstrap by game, one-sided |
| **H2** | V1 | Median venue spread > 1.5 × pooled vig → +ve reversion at 60s | Block-bootstrap by game, one-sided |
| **H3** | V3 | Aggregate Brier `< min(structural, market)` on test | Paired block-bootstrap by game on Brier diffs |
| **H4** | V5 (gen) | Trailing ≥10 made 3-pointer → `E[Δp_market − Δp_struct] > 0` | Block-bootstrap by game, one-sided |

All non-H1-through-H4 findings are explicitly labeled exploratory in the
report and cleanly separated from the confirmatory ones.

---

## The shared evaluation harness

All six variants plug into one harness so the comparison is honest:

```python
class VariantProtocol(Protocol):
    name: str
    pre_registered: bool
    def fit(self, train_df, val_df) -> None: ...
    def predict_pt(self, df) -> pd.Series:    # fair-value estimate p̂_t
    def predict_edge(self, df) -> pd.Series:  # edge_t = p̂_t − p_market_t

# orchestration
harness.evaluate(variant, test_df) -> EvalReport       # Brier, ECE, plot data
harness.backtest(variant, test_df, threshold, kelly_fraction) -> BacktestReport
harness.h1_test(variant, test_df) -> Bootstrap-CI'd one-sided p-value
```

Shared splits (`GroupKFold` on `game_id`, 2023-24 train, 2024-25 test), shared
metrics (Brier / log-loss / ECE / RMS calib error), shared backtest engine
(threshold + fractional-Kelly + realistic vig + block-bootstrap CI).

Right now: V2 and V5 are wired through the protocol; V1/V3/V4/V6 are stubbed
with docstrings only.

---

## What unblocks the rest

One thing: the-odds-api free-tier signup. All blocked variants connect through
that — V1/V3/V6 need multi-book in-play odds, V4 needs the in-play time series,
and V5's *market side* (the actual behavioral test) needs the same.
