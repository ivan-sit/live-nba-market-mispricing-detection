"""Backtest engine — threshold + fractional-Kelly sizing + realistic vig.

Wagers are sized as `kelly_mult * kelly(p_hat, decimal_odds)` and settled at the
book's quoted (vigged) odds, never the de-vigged probability. P&L is aggregated
to per-GAME returns and block-bootstrapped by game, because within-game ticks
share one outcome — the effective sample size is games, not ticks.

Naive baselines (always-favorite, always-trailing, random) should lose roughly
the vig — that is the honesty check on the engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# Odds helpers
# ----------------------------------------------------------------------------


def american_to_decimal(price: np.ndarray | float) -> np.ndarray:
    """American odds -> decimal payout multiple (stake returned included)."""
    p = np.asarray(price, dtype=float)
    return np.where(p < 0, 1.0 + 100.0 / -p, 1.0 + p / 100.0)


def american_to_prob(price: np.ndarray | float) -> np.ndarray:
    p = np.asarray(price, dtype=float)
    return np.where(p < 0, -p / (-p + 100.0), 100.0 / (p + 100.0))


def kelly_fraction(p_win: np.ndarray, decimal_odds: np.ndarray) -> np.ndarray:
    """Full-Kelly stake fraction f* = (b·p − q)/b, b = decimal−1, q = 1−p.
    Negative (no edge) is clipped to 0 by the caller."""
    p = np.asarray(p_win, dtype=float)
    b = np.asarray(decimal_odds, dtype=float) - 1.0
    b = np.where(b <= 0, np.nan, b)
    return (b * p - (1.0 - p)) / b


# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------


@dataclass
class BacktestReport:
    name: str
    n_bets: int
    n_games: int
    total_staked: float
    total_pnl: float
    roi: float                      # total_pnl / total_staked
    mean_game_roi: float            # mean over per-game ROI
    sharpe_per_game: float          # mean/std of per-game ROI (not annualized)
    ci95: tuple[float, float]       # bootstrap CI on mean per-game ROI
    p_value_gt0: float              # one-sided P(mean per-game ROI <= 0)
    max_drawdown: float
    bets: pd.DataFrame              # per-bet detail (not printed)

    def __str__(self) -> str:
        return (
            f"{self.name:22s}  bets={self.n_bets:5d}/{self.n_games:4d}g  "
            f"ROI={self.roi:+.3%}  game-ROI={self.mean_game_roi:+.3%}  "
            f"Sharpe={self.sharpe_per_game:+.2f}  "
            f"CI95=[{self.ci95[0]:+.3%},{self.ci95[1]:+.3%}]  "
            f"p={self.p_value_gt0:.3f}  maxDD={self.max_drawdown:.3%}"
        )


def _block_bootstrap_mean(
    per_game_roi: np.ndarray, n_resamples: int = 10_000, seed: int = 42
) -> tuple[float, float, tuple[float, float]]:
    """Resample games with replacement. Returns (mean, one-sided p>0, 95% CI)."""
    vals = np.asarray(per_game_roi, dtype=float)
    n = len(vals)
    if n == 0:
        return 0.0, 1.0, (0.0, 0.0)
    rng = np.random.default_rng(seed)
    boots = rng.choice(vals, size=(n_resamples, n), replace=True).mean(axis=1)
    p_val = float((boots <= 0.0).mean())
    ci = (float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975)))
    return float(vals.mean()), p_val, ci


def _settle_and_report(name: str, bets: pd.DataFrame, game_order: list | None) -> BacktestReport:
    """bets needs columns: game_id, stake, decimal_odds, won (bool)."""
    if bets.empty:
        return BacktestReport(name, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, (0.0, 0.0), 1.0, 0.0, bets)

    bets = bets.copy()
    bets["pnl"] = np.where(
        bets["won"], bets["stake"] * (bets["decimal_odds"] - 1.0), -bets["stake"]
    )

    per_game = bets.groupby("game_id").agg(
        pnl=("pnl", "sum"), staked=("stake", "sum"), n=("stake", "size")
    )
    per_game["roi"] = np.where(per_game["staked"] > 0, per_game["pnl"] / per_game["staked"], 0.0)

    total_staked = float(bets["stake"].sum())
    total_pnl = float(bets["pnl"].sum())
    roi = total_pnl / total_staked if total_staked > 0 else 0.0

    roi_series = per_game["roi"].to_numpy()
    mean_game_roi, p_val, ci = _block_bootstrap_mean(roi_series)
    std = float(roi_series.std(ddof=1)) if len(roi_series) > 1 else 0.0
    sharpe = mean_game_roi / std if std > 0 else 0.0

    # Max drawdown on cumulative PnL ordered by game (chronological proxy).
    order = game_order if game_order is not None else sorted(per_game.index)
    cum = per_game.reindex(order)["pnl"].fillna(0.0).cumsum().to_numpy()
    if len(cum):
        running_max = np.maximum.accumulate(cum)
        dd = running_max - cum
        max_dd = float(dd.max())
    else:
        max_dd = 0.0

    return BacktestReport(
        name=name,
        n_bets=int(len(bets)),
        n_games=int(per_game.shape[0]),
        total_staked=total_staked,
        total_pnl=total_pnl,
        roi=roi,
        mean_game_roi=mean_game_roi,
        sharpe_per_game=sharpe,
        ci95=ci,
        p_value_gt0=p_val,
        max_drawdown=max_dd,
        bets=bets,
    )


# ----------------------------------------------------------------------------
# Strategies
# ----------------------------------------------------------------------------


def simulate(
    df: pd.DataFrame,
    *,
    name: str = "variant",
    p_hat_col: str = "p_hat",
    market_prob_col: str = "p_market_home_devig",
    home_odds_col: str = "home_odds_american",
    away_odds_col: str = "away_odds_american",
    outcome_col: str = "y_home_win",
    game_col: str = "game_id",
    threshold: float = 0.03,
    sizing: Literal["kelly", "flat"] = "kelly",
    kelly_mult: float = 0.25,
    flat_stake: float = 1.0,
    max_fraction: float = 0.25,
    game_order: list | None = None,
) -> BacktestReport:
    """Edge-driven backtest for any variant.

    Bet HOME when (p_hat − p_market_home) > threshold, AWAY when < −threshold.
    Stake at the chosen side's *vigged* American odds. Settle on outcome.
    """
    d = df.copy()
    edge = d[p_hat_col].to_numpy() - d[market_prob_col].to_numpy()

    bet_home = edge > threshold
    bet_away = edge < -threshold
    take = bet_home | bet_away
    d = d.loc[take].copy()
    if d.empty:
        return _settle_and_report(name, pd.DataFrame(columns=[game_col, "stake", "decimal_odds", "won"]), game_order)

    side_home = (d[p_hat_col].to_numpy() - d[market_prob_col].to_numpy()) > 0
    dec_home = american_to_decimal(d[home_odds_col].to_numpy())
    dec_away = american_to_decimal(d[away_odds_col].to_numpy())
    decimal_odds = np.where(side_home, dec_home, dec_away)

    # model's win prob for the side we bet
    p_hat = d[p_hat_col].to_numpy()
    p_side = np.where(side_home, p_hat, 1.0 - p_hat)

    if sizing == "kelly":
        f = kelly_fraction(p_side, decimal_odds)
        stake = np.clip(kelly_mult * np.nan_to_num(f, nan=0.0), 0.0, max_fraction)
    else:
        stake = np.full(len(d), flat_stake, dtype=float)

    home_won = d[outcome_col].to_numpy().astype(bool)
    won = np.where(side_home, home_won, ~home_won)

    bets = pd.DataFrame(
        {
            game_col: d[game_col].to_numpy(),
            "stake": stake,
            "decimal_odds": decimal_odds,
            "won": won,
            "side_home": side_home,
            "edge": d[p_hat_col].to_numpy() - d[market_prob_col].to_numpy(),
        }
    )
    bets = bets[bets["stake"] > 0]
    return _settle_and_report(name, bets, game_order)


def baseline_simulate(
    df: pd.DataFrame,
    *,
    rule: Literal["favorite", "trailing", "random"],
    market_prob_col: str = "p_market_home_devig",
    home_odds_col: str = "home_odds_american",
    away_odds_col: str = "away_odds_american",
    outcome_col: str = "y_home_win",
    score_diff_col: str = "score_diff_home",
    game_col: str = "game_id",
    flat_stake: float = 1.0,
    seed: int = 42,
    game_order: list | None = None,
) -> BacktestReport:
    """Naive baselines, flat stake on every tick. Should lose ~the vig.

    favorite  : bet the market favorite (de-vigged home prob > 0.5 -> home)
    trailing  : bet the team currently behind on the scoreboard
    random    : coin flip per tick
    """
    d = df.copy()
    if rule == "favorite":
        side_home = d[market_prob_col].to_numpy() > 0.5
    elif rule == "trailing":
        if score_diff_col not in d.columns:
            raise KeyError(f"'trailing' baseline needs {score_diff_col}")
        side_home = d[score_diff_col].to_numpy() < 0  # home behind -> bet home
    elif rule == "random":
        rng = np.random.default_rng(seed)
        side_home = rng.random(len(d)) < 0.5
    else:  # pragma: no cover
        raise ValueError(rule)

    dec_home = american_to_decimal(d[home_odds_col].to_numpy())
    dec_away = american_to_decimal(d[away_odds_col].to_numpy())
    decimal_odds = np.where(side_home, dec_home, dec_away)
    home_won = d[outcome_col].to_numpy().astype(bool)
    won = np.where(side_home, home_won, ~home_won)

    bets = pd.DataFrame(
        {
            game_col: d[game_col].to_numpy(),
            "stake": np.full(len(d), flat_stake, dtype=float),
            "decimal_odds": decimal_odds,
            "won": won,
        }
    )
    return _settle_and_report(f"baseline:{rule}", bets, game_order)
