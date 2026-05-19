# Results Log

Append-only record of headline numbers from each smoke run. Dated entries; do
NOT modify prior entries — append new ones at the bottom.

---

## 2026-05-18 — V2 first pass, 454 games (during PBP scrape)

Built per-minute 1H snapshots from in-flight PBP. Random 60/20/20 split by
game_id. Features: minute_idx, score_diff_home, recent_run_diff, period.

| Model | Val Brier | Test Brier | Test ECE |
|---|---|---|---|
| LR baseline | 0.1362 | 0.1641 | 0.041 |
| XGB raw | 0.1406 | **0.1604** | 0.049 |
| XGB + isotonic | 0.1343 | 0.1633 | 0.050 |

Isotonic overfits the val partition (91 games too small for stable monotonic
fit). Will revisit with multi-season data.

---

## 2026-05-18 — V2 feature ablation, 952 games

| Model | Test Brier | Test ECE |
|---|---|---|
| LR basic | 0.1303 | 0.066 |
| LR engineered | 0.1298 | 0.063 |
| **XGB basic** | **0.1292** | 0.062 |
| XGB engineered | 0.1298 | 0.058 |

Engineered features (leverage, abs_score_diff, score_diff_x_remaining,
possession_proxy) don't beat the 0.005-Brier threshold. **V2 default = XGB
on 4 basic features.**

---

## 2026-05-18 — V5 structural side, 784 games (during scrape)

H1 (trailing 10-15, made FG): 1,262 events / 246 games
  Mean structural shift: +0.0022  95% CI [-0.003, +0.007]  p = 0.199

H4 (trailing ≥10, made 3pt): 589 events / 207 games
  Mean structural shift: **+0.0105**  95% CI [+0.005, +0.017]  p = 0.0002

H4 significant. H1 not yet (sample size).

---

## 2026-05-18 — V5 structural side, FULL 1230 games

**Headline result of the day.**

H1 (trailing 10-15, made FG): 1,860 events / 377 games
  Mean structural shift: **+0.0062**  95% CI [+0.003, +0.010]  p = 0.0003

H4 (trailing ≥10, made 3pt): 871 events / 317 games
  Mean structural shift: **+0.0184**  95% CI [+0.014, +0.023]  p < 0.0001

Both pre-registered tests show significant POSITIVE structural shift for the
trailing team's scorer after their basket. Going from p=0.20 to p=0.0003 on
H1 was purely from doubling the sample.

By shot value within H1 bucket:
  2-pt makes (n=1269): mean shift -0.0005 (≈0)
  3-pt makes (n=591):  mean shift +0.0211

Interpretation: A trailing team's 3-pointer materially shifts our calibrated
1H-winner model in their favor over the next 60 seconds. A trailing team's
2-pointer in a 10-15 deficit barely moves the model. This is the structural
baseline for the behavioral test — the question becomes: does the market
shift MORE than this on the same event set?

**Awaiting odds data (Task #4, the-odds-api signup) to run the full
H1/H4 market-side comparison.**

---

## Notes on what's NOT in this log yet

- H2 (V1 cross-venue): blocked on multi-venue odds.
- H3 (V3 Halawi aggregate): blocked on V1 component plus odds.
- Full Brier on multi-season split (2019-22 train, 2023-24 val, 2024-25 test):
  2024-25 PBP pull in progress; will rerun V2 on the proper split once done.
