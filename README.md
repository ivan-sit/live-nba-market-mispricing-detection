# STATS 211 Final — Live NBA Market Mispricing Detection

A calibrated in-game NBA win probability model used as a behavioral asset pricing
test of live sportsbook odds, in the lineage of Moskowitz (2021) and motivated by
the LM-vs-crowd miscalibration story from Halawi et al. (NeurIPS 2024).

**Authors:** Ming Yin Ivan Sit, Vishnu Manathattai
**Course:** STATS 211 (Topics in Economics and Machine Learning), Prof. Xiaowu Dai, UCLA

See `CLAUDE.md` for the full project brief and intellectual arc, and `DECISIONS.md`
for the running log of methodological choices.

## Setup

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# create venv and install
uv sync --extra dev

# install pre-commit hooks
uv run pre-commit install
```

## Repo layout

```
data/{raw,interim,processed}    NBA play-by-play + odds, never committed
notebooks/                       exploratory and reporting notebooks
src/data/                        data acquisition (PBP, odds, dataset build)
src/features/                    feature engineering
src/models/                      baseline LR, XGBoost, calibration
src/analysis/                    mispricing detection, backtest
src/viz/                         plotting helpers (consistent palette)
tests/                           unit tests for critical paths
reports/                         3-page NeurIPS report
slides/                          10-min slide deck
docs/                            schema and methodology docs
```

## Run order (when implemented)

1. `python -m src.data.pull_pbp` — pull play-by-play
2. `python -m src.data.pull_odds` — pull odds
3. `python -m src.data.build_dataset` — unified game-state table
4. `python -m src.models.baseline` — fit logistic regression baseline
5. `python -m src.models.xgb_model` — fit XGBoost
6. `python -m src.analysis.mispricing` — detect mispricings
7. `python -m src.analysis.backtest` — backtest betting strategy

## Status

Phase 0 — setup + data investigation (Week 1).
