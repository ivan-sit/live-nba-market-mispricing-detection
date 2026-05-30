"""Generate all PNG figures referenced by slides/build.js.

Outputs (slides/figures/):
  reliability_v2.png       — V2 reliability diagram on 2024-25 (10 deciles + binomial CI)
  v5_shifts.png            — H1 / H4 structural shifts with 95% block-bootstrap CI
  pilot_roi.png            — SAS@OKC mock-strategy ROI bars (model vs baselines)
  liquidity_sample.png     — paired ROI bars: liquid sportsbook (n=1) vs stale Kalshi (n=4)
  pipeline_flow.png        — left-to-right flow diagram of the system

Project palette: NAVY/DEEP/TEAL/SKY/CREAM/ACCENT/INK.

Run:  uv run python scripts/generate_slide_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import joblib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

from src.data.build_dataset import build_season
from src.models.calibration import brier, ece, reliability_table

OUT = REPO_ROOT / "slides" / "figures"
NAVY, DEEP, TEAL = "#0B2545", "#13315C", "#1C7293"
SKY, CREAM, ACCENT, INK = "#8DA9C4", "#F6F6F2", "#EEA02B", "#1A1A1A"

plt.rcParams.update({
    "font.family": "DejaVu Sans",  # Georgia/Calibri not always available headless
    "axes.edgecolor": INK, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
})


# ─── 1. Reliability diagram ──────────────────────────────────────────────
def make_reliability():
    print("[1] Reliability diagram (V2 on 2024-25)", flush=True)
    bundle = joblib.load(REPO_ROOT / "models" / "v2_xgb_isotonic.joblib")
    snaps = build_season(season="2024-25")
    test = snaps[snaps["y_tie_1h"] == 0].copy()
    feats = bundle["features"]
    p_raw = bundle["xgb"].predict_proba_home_wins(test[feats])
    p = bundle["iso"].transform(p_raw)
    y = test["y_home_wins_1h"].astype(int).values
    tab = reliability_table(p, y, n_bins=10)
    b, e = brier(p, y), ece(p, y, 10)
    # binomial 95% CI per bin
    n = tab["n"].values; ef = tab["emp_freq"].values
    se = np.sqrt(ef * (1 - ef) / np.maximum(n, 1))
    lo, hi = np.clip(ef - 1.96 * se, 0, 1), np.clip(ef + 1.96 * se, 0, 1)

    fig, ax = plt.subplots(figsize=(7.4, 5.4), dpi=170)
    fig.patch.set_facecolor(CREAM); ax.set_facecolor(CREAM)
    ax.plot([0, 1], [0, 1], color=SKY, lw=1.8, ls="--", zorder=1, label="perfect calibration")
    ax.errorbar(tab["mean_p"], tab["emp_freq"],
                yerr=[tab["emp_freq"] - lo, hi - tab["emp_freq"]],
                fmt="o", color=NAVY, ecolor=TEAL, capsize=4, ms=9, mfc=ACCENT,
                mec=NAVY, mew=1.3, lw=1.3, zorder=3, label="V2 (XGB + isotonic)")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xlabel("Predicted P(home wins 1H)", fontsize=12)
    ax.set_ylabel("Empirical frequency", fontsize=12)
    ax.set_title("Reliability diagram · V2 · 2024-25 held-out", fontsize=14,
                 color=NAVY, fontweight="bold", loc="left")
    ax.text(0.04, 0.94, f"Brier = {b:.4f}\nECE  = {e:.4f}\nn   = {len(y):,}",
            transform=ax.transAxes, fontsize=11, color=DEEP, va="top", family="monospace",
            bbox=dict(boxstyle="round,pad=0.5", fc=CREAM, ec=TEAL, lw=1.3))
    ax.legend(loc="lower right", frameon=False, fontsize=11)
    ax.grid(alpha=0.25, color=SKY)
    fig.tight_layout()
    fig.savefig(OUT / "reliability_v2.png", facecolor=CREAM, bbox_inches="tight")
    plt.close(fig)


# ─── 2. V5 structural shifts ─────────────────────────────────────────────
def make_v5_shifts():
    print("[2] V5 H1/H4 shift bar chart", flush=True)
    names = ["Comeback FG\ntrailing 10–15", "Salience 3PT\ntrailing ≥10"]
    point = np.array([0.0075, 0.0138])
    lo, hi = np.array([0.005, 0.011]), np.array([0.010, 0.017])
    err = np.vstack([point - lo, hi - point])
    fig, ax = plt.subplots(figsize=(7.4, 5.0), dpi=170)
    fig.patch.set_facecolor(CREAM); ax.set_facecolor(CREAM)
    x = np.arange(len(names))
    ax.bar(x, point, width=0.55, color=[ACCENT, ACCENT], edgecolor=NAVY, lw=1.2, zorder=2)
    ax.errorbar(x, point, yerr=err, fmt="none", ecolor=NAVY, lw=2, capsize=8, capthick=2, zorder=3)
    ax.axhline(0, color=INK, lw=0.8)
    for xi, p in zip(x, point):
        ax.text(xi, p + 0.0008, f"+{p:.4f}", ha="center", fontsize=12, color=NAVY, fontweight="bold")
    ax.text(0, hi[0] + 0.0035, "p < 0.0001", ha="center", fontsize=10, color=DEEP, style="italic")
    ax.text(1, hi[1] + 0.0035, "p < 0.0001", ha="center", fontsize=10, color=DEEP, style="italic")
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=11)
    ax.set_ylabel("Structural shift for scorer  (Δp over next 60s)", fontsize=11)
    ax.set_title("V5 · pre-registered tests · held-out 2024-25",
                 fontsize=14, color=NAVY, fontweight="bold", loc="left")
    ax.set_ylim(-0.001, 0.024)
    ax.grid(alpha=0.25, color=SKY, axis="y")
    fig.tight_layout()
    fig.savefig(OUT / "v5_shifts.png", facecolor=CREAM, bbox_inches="tight")
    plt.close(fig)


# ─── 3. Live pilot ROI bars ──────────────────────────────────────────────
def make_pilot_roi():
    print("[3] Pilot ROI bars", flush=True)
    names = ["Our model\n(4% edge)", "Always\nfavorite", "Always\ntrailing", "Random"]
    roi = np.array([-0.40, +0.34, -0.81, -0.31])
    colors = [ACCENT, SKY, SKY, SKY]
    fig, ax = plt.subplots(figsize=(8.0, 5.0), dpi=170)
    fig.patch.set_facecolor(CREAM); ax.set_facecolor(CREAM)
    x = np.arange(len(names))
    bars = ax.bar(x, roi, width=0.6, color=colors, edgecolor=NAVY, lw=1.2)
    ax.axhline(0, color=INK, lw=0.9)
    for b, v in zip(bars, roi):
        ax.text(b.get_x() + b.get_width() / 2, v + (0.03 if v >= 0 else -0.05),
                f"{v:+.0%}", ha="center", fontsize=13, fontweight="bold",
                color=NAVY if v >= 0 else DEEP)
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=11)
    ax.set_ylabel("ROI (1 game)", fontsize=11)
    ax.set_ylim(-1.0, 0.6)
    yt = [-1.0, -0.5, 0, 0.5]
    ax.set_yticks(yt); ax.set_yticklabels([f"{int(v*100)}%" for v in yt])
    ax.set_title("Live pilot · SAS @ OKC, 2026-05-26 · settled FINAL OKC 127–114",
                 fontsize=13, color=NAVY, fontweight="bold", loc="left")
    ax.text(0.99, 0.02, "n = 1 game  →  pure coin-flip noise", transform=ax.transAxes,
            ha="right", fontsize=10, style="italic", color=DEEP)
    ax.grid(alpha=0.25, color=SKY, axis="y")
    fig.tight_layout()
    fig.savefig(OUT / "pilot_roi.png", facecolor=CREAM, bbox_inches="tight")
    plt.close(fig)


# ─── 4. Liquidity × sample lesson (paired bars) ─────────────────────────
def make_liquidity():
    print("[4] Liquidity × sample lesson", flush=True)
    cats = ["Liquid sportsbook\n(1 game)", "Stale Kalshi 1H\n(4 games)"]
    roi = [-0.40, 1.03]
    fig, ax = plt.subplots(figsize=(7.4, 5.0), dpi=170)
    fig.patch.set_facecolor(CREAM); ax.set_facecolor(CREAM)
    x = np.arange(len(cats))
    bars = ax.bar(x, roi, width=0.55, color=[TEAL, ACCENT], edgecolor=NAVY, lw=1.3)
    ax.axhline(0, color=INK, lw=0.9)
    for b, v in zip(bars, roi):
        ax.text(b.get_x() + b.get_width() / 2, v + (0.05 if v >= 0 else -0.07),
                f"{v:+.0%}", ha="center", fontsize=14, fontweight="bold", color=NAVY)
    ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=11)
    ax.set_ylabel("Model ROI", fontsize=11)
    ax.set_ylim(-0.7, 1.4)
    yt = [-0.5, 0, 0.5, 1.0]
    ax.set_yticks(yt); ax.set_yticklabels([f"{int(v*100)}%" for v in yt])
    ax.set_title("Same model family · opposite results  →  liquidity × n are everything",
                 fontsize=13, color=NAVY, fontweight="bold", loc="left")
    ax.text(0.5, -0.55, "the +100% is a stale-mid + n=4 artifact, not an edge",
            ha="center", fontsize=10, style="italic", color=DEEP)
    ax.grid(alpha=0.25, color=SKY, axis="y")
    fig.tight_layout()
    fig.savefig(OUT / "liquidity_sample.png", facecolor=CREAM, bbox_inches="tight")
    plt.close(fig)


# ─── 5. Pipeline flowchart ──────────────────────────────────────────────
def make_pipeline():
    print("[5] Pipeline flowchart (with Method 1 / Method 2 labels)", flush=True)
    fig, ax = plt.subplots(figsize=(11.6, 5.8), dpi=170)
    fig.patch.set_facecolor(CREAM); ax.set_facecolor(CREAM)
    ax.set_xlim(0, 12); ax.set_ylim(0, 6.2); ax.axis("off")

    def box(x, y, w, h, label, fc=CREAM, ec=NAVY, fontc=NAVY, sub=None, big=False):
        p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.12",
                           fc=fc, ec=ec, lw=1.6); ax.add_patch(p)
        ax.text(x + w/2, y + h/2 + (0.15 if sub else 0),
                label, ha="center", va="center",
                fontsize=11 if not big else 13, color=fontc, fontweight="bold")
        if sub:
            ax.text(x + w/2, y + h/2 - 0.25, sub, ha="center", va="center",
                    fontsize=8.5, color=DEEP, style="italic")

    def arrow(x1, y1, x2, y2, color=TEAL, lw=2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=lw))

    # ── METHOD 1 banner over the model row ───────────────────────────────
    m1 = FancyBboxPatch((0, 5.55), 12, 0.5,
                        boxstyle="round,pad=0.02,rounding_size=0.05",
                        fc=NAVY, ec=NAVY); ax.add_patch(m1)
    ax.text(6, 5.8, "METHOD 1  ·  the calibrated WP model  ·  produces  p̂_t",
            ha="center", va="center", fontsize=12, fontweight="bold", color=CREAM)

    # Row 1 — model side (this whole row IS Method 1)
    box(0.2, 3.6, 2.2, 1.1, "PBP data", sub="2,460 games · free", fc=CREAM)
    box(3.0, 3.6, 2.4, 1.1, "Per-minute snapshots", sub="game state · 4 features")
    box(6.2, 3.6, 2.4, 1.1, "XGB + isotonic", sub="calibrated WP model", fc="#E6EEF6")
    box(9.4, 3.6, 2.4, 1.1, "p̂_t", sub="P(home wins 1H)", fc=NAVY, fontc=CREAM, big=True)
    arrow(2.4, 4.15, 3.0, 4.15); arrow(5.4, 4.15, 6.2, 4.15); arrow(8.6, 4.15, 9.4, 4.15)

    # ── METHOD 2 callout — branches off p̂_t ──────────────────────────────
    m2 = FancyBboxPatch((4.4, 2.78), 3.0, 0.72,
                        boxstyle="round,pad=0.05,rounding_size=0.1",
                        fc=ACCENT, ec=ACCENT); ax.add_patch(m2)
    ax.text(5.9, 3.32, "METHOD 2  ·  diagnostic only",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)
    ax.text(5.9, 3.04, "reads  p̂_t  at trailing-team events  ·  does NOT trade",
            ha="center", va="center", fontsize=8.5, color=NAVY, style="italic")
    # arrow from p̂_t down-left to Method 2 box
    arrow(9.5, 3.6, 7.5, 3.27, color=ACCENT, lw=2.2)

    # Row 2 — market side
    box(0.2, 1.5, 2.2, 1.1, "Live odds", sub="9 books · Kalshi", fc=CREAM)
    box(3.0, 1.5, 2.4, 1.1, "De-vig", sub="multiplicative two-way")
    box(6.2, 1.5, 2.4, 1.1, "p_market_t", sub="consensus median", fc="#E6EEF6")
    box(9.4, 1.5, 2.4, 1.1, "edge_t", sub="p̂_t − p_market_t", fc=ACCENT, fontc=NAVY, big=True)
    arrow(2.4, 2.05, 3.0, 2.05); arrow(5.4, 2.05, 6.2, 2.05); arrow(8.6, 2.05, 9.4, 2.05)

    # Diagonal merge: p̂_t → edge_t
    arrow(10.6, 3.6, 10.6, 2.6, color=NAVY)

    # Bottom — backtest (Method 1 + Method 2 both flow here)
    box(4.6, 0.05, 5.0, 1.0, "¼-Kelly · settle · block-bootstrap by game",
        sub="ROI · Sharpe · 95% CI", fc=DEEP, fontc=CREAM, ec=DEEP)
    arrow(10.6, 1.5, 7.1, 1.05, color=NAVY)

    ax.set_title("Pipeline · Method 1 produces p̂_t · Method 2 tests it · both feed the backtest",
                 fontsize=12, color=NAVY, fontweight="bold", loc="left", pad=12)
    fig.tight_layout()
    fig.savefig(OUT / "pipeline_flow.png", facecolor=CREAM, bbox_inches="tight")
    plt.close(fig)


def make_game6_pilot():
    """Game 6 (OKC@SAS, 2026-05-28) per-game model ROI on Kalshi 1H, in context of
    the 5-game archive pool. Game 6 highlighted; others as muted bars."""
    print("[6] Game 6 pilot (per-game Kalshi ROI)", flush=True)
    games = ["G1 · Apr 30\nDEN @ MIN", "G2 · May 3\nTOR @ CLE", "G3 · May 4\nMIN @ SAS",
             "G4 · May 13\nCLE @ DET", "G6 · May 28\nOKC @ SAS"]
    rois = np.array([1.098, 0.867, 2.342, 0.299, 0.117])
    colors = [SKY, SKY, SKY, SKY, ACCENT]  # Game 6 highlighted
    fig, ax = plt.subplots(figsize=(8.4, 5.0), dpi=170)
    fig.patch.set_facecolor(CREAM); ax.set_facecolor(CREAM)
    x = np.arange(len(games))
    bars = ax.bar(x, rois, width=0.62, color=colors, edgecolor=NAVY, lw=1.3)
    ax.axhline(0, color=INK, lw=0.9)
    for b, v in zip(bars, rois):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.05,
                f"{v:+.0%}", ha="center", fontsize=12, fontweight="bold", color=NAVY)
    ax.set_xticks(x); ax.set_xticklabels(games, fontsize=10)
    ax.set_ylabel("Per-game model ROI", fontsize=11)
    ax.set_ylim(-0.1, 2.7)
    yt = [0, 0.5, 1.0, 1.5, 2.0, 2.5]
    ax.set_yticks(yt); ax.set_yticklabels([f"{int(v*100)}%" for v in yt])
    ax.set_title("Game 6 vs the 4 archived Kalshi 1H games  ·  5-game pool ROI +95%",
                 fontsize=12, color=NAVY, fontweight="bold", loc="left")
    ax.text(0.99, 0.02, "model 'won' all 5 — but it's a stale-mid artifact (see next slide)",
            transform=ax.transAxes, ha="right", fontsize=10, style="italic", color=DEEP)
    ax.grid(alpha=0.25, color=SKY, axis="y")
    fig.tight_layout()
    fig.savefig(OUT / "game6_pilot.png", facecolor=CREAM, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    make_reliability()
    make_v5_shifts()
    make_pilot_roi()
    make_liquidity()
    make_pipeline()
    make_game6_pilot()
    print("\nWrote:")
    for p in sorted(OUT.glob("*.png")):
        print(f"  {p.relative_to(REPO_ROOT)}  ({p.stat().st_size//1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
