"""Verification gates for the eval harness + backtest engine (no real data).

Builds synthetic games with KNOWN properties and asserts the engine behaves:

  GATE 1  const-0.5 variant -> Brier exactly 0.25 (balanced outcomes)
  GATE 2  always-favorite on an EFFICIENT vigged market -> loses ~ the vig
  GATE 3  random baseline -> also loses ~ the vig
  GATE 4  PERFECT model on a BIASED market -> positive ROI, CI excludes 0
  GATE 5  market-as-variant (p_hat == de-vig market) -> ~no bets (no edge)

Key design point: each game has ONE outcome shared by all its ticks, so the
effective sample size is games, not ticks — exactly the correlation the
block-bootstrap-by-game is meant to respect.

Run:  uv run python scripts/test_backtest_engine.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.eval import backtest as bt  # noqa: E402
from src.eval.harness import ConstantVariant, backtest, evaluate  # noqa: E402

OVERROUND = 0.045
BIAS = 0.08


def prob_to_american(q: np.ndarray) -> np.ndarray:
    q = np.clip(np.asarray(q, dtype=float), 1e-4, 1 - 1e-4)
    return np.where(q >= 0.5, -100.0 * q / (1.0 - q), 100.0 * (1.0 - q) / q)


def make_synthetic(n_games=2000, ticks=40, market="efficient", seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # Near-even matchups: outcomes are close to coin flips, so per-game variance
    # is low and a genuine edge is detectable with a realistic game count.
    theta = rng.uniform(0.40, 0.60, size=n_games)        # true home win prob
    y = (rng.random(n_games) < theta).astype(int)        # ONE outcome per game

    rows = []
    for g in range(n_games):
        m = theta[g] if market == "efficient" else np.clip(theta[g] + BIAS, 0.02, 0.98)
        # vigged two-sided implied probs (sum = 1 + overround)
        home_imp = m * (1 + OVERROUND)
        away_imp = (1 - m) * (1 + OVERROUND)
        home_am = float(prob_to_american(np.array([home_imp]))[0])
        away_am = float(prob_to_american(np.array([away_imp]))[0])
        sd = rng.normal(0, 8, size=ticks)                # fake score diff for baselines
        rows.append(
            pd.DataFrame(
                {
                    "game_id": f"G{g:04d}",
                    "theta": theta[g],
                    "p_market_home_devig": m,
                    "home_odds_american": home_am,
                    "away_odds_american": away_am,
                    "y_home_win": y[g],
                    "score_diff_home": sd,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def ok(cond: bool, msg: str) -> bool:
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    return cond


def main() -> int:
    eff = make_synthetic(market="efficient")
    biased = make_synthetic(market="biased")
    expected_vig_roi = -OVERROUND / (1 + OVERROUND)
    print(f"Synthetic: {eff['game_id'].nunique()} games x 40 ticks. overround={OVERROUND:.1%} "
          f"(EV/favorite-bet = {expected_vig_roi:+.3%}), market bias={BIAS:.1%}\n")

    passed = []

    print("GATE 1 — const-0.5 Brier == 0.25")
    rep = evaluate(ConstantVariant(0.5), eff)
    print(f"    {rep}")
    passed.append(ok(abs(rep.brier - 0.25) < 1e-9, "Brier is exactly 0.25"))

    print("\nGATE 2 — always-favorite on efficient market loses ~vig")
    fav = bt.baseline_simulate(eff, rule="favorite")
    print(f"    {fav}")
    passed.append(ok(fav.roi < 0 and fav.roi > 2 * expected_vig_roi - 0.03,
                     f"ROI {fav.roi:+.3%} is negative and near {expected_vig_roi:+.3%}"))

    print("\nGATE 3 — random baseline on efficient market loses ~vig")
    rnd = bt.baseline_simulate(eff, rule="random")
    print(f"    {rnd}")
    passed.append(ok(rnd.roi < 0.01, f"ROI {rnd.roi:+.3%} not positive"))

    print("\nGATE 4 — PERFECT model on biased market makes money (CI excludes 0)")
    biased = biased.copy()
    biased["p_hat"] = biased["theta"]  # perfect knowledge of true prob
    perfect = bt.simulate(biased, name="perfect", threshold=0.03, kelly_mult=0.25)
    print(f"    {perfect}")
    passed.append(ok(perfect.roi > 0 and perfect.ci95[0] > 0 and perfect.p_value_gt0 < 0.05,
                     f"ROI {perfect.roi:+.3%}, CI95 [{perfect.ci95[0]:+.3%},{perfect.ci95[1]:+.3%}], p={perfect.p_value_gt0:.3f}"))

    print("\nGATE 5 — market-as-variant has ~no edge -> ~no bets")
    eff2 = eff.copy()
    eff2["p_hat"] = eff2["p_market_home_devig"]
    mkt = bt.simulate(eff2, name="market", threshold=0.03)
    print(f"    {mkt}")
    passed.append(ok(mkt.n_bets == 0, f"placed {mkt.n_bets} bets (should be 0)"))

    print(f"\n{'='*60}")
    print(f"  {sum(passed)}/{len(passed)} gates passed")
    print(f"{'='*60}")
    return 0 if all(passed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
