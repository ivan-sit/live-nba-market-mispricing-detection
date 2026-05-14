STATS 211 Final Project — Live NBA Market Mispricing Detection
Who I am and what I'm doing
I am Ming Yin Ivan Sit, a UCLA student in STATS 211 (Topics in Economics and Machine Learning, Prof. Xiaowu Dai). I'm working with my partner Vishnu Manathattai. We presented "Approaching Human-Level Forecasting with Language Models" (Halawi et al., NeurIPS 2024) for our midterm and did well. The final project is the rest of the grade.
We are building a calibrated in-game NBA win probability model that detects systematic mispricings in live sportsbook odds, framed as a behavioral asset pricing test in the lineage of Moskowitz (2021).
The intellectual story (this matters for everything we build)
The story has to read clean to Prof. Dai, who knows behavioral finance and ML. Here's the arc:
Midterm thesis: Halawi et al. showed LMs can approach human crowd performance on judgmental forecasting (Brier 0.179 vs crowd 0.149). Their most interesting buried result is Table 3's "Aggregate" column — a 4:1 weighted average of LM + crowd beats either alone. This works because LM and crowd errors are independent.
The deeper observation: both LMs and crowds are miscalibrated, in opposite directions.

LMs hedge (RLHF training rewards non-commitment — Halawi Figure 16 shows the model at 20% when crowd was at 1%)
Crowds overreact (Moskowitz 2021 and Ötting et al. 2022 document this systematically — bettors stake ~40% more on apparent-momentum teams even though momentum has no predictive power)

Reframing: "Match the crowd" isn't the right ceiling. The crowd is biased. A better forecaster targets the crowd's specific failure modes.
The natural laboratory: Live sports betting markets, because:

Ground truth resolves in hours (vs weeks for forecasting questions)
Crowd miscalibration is documented across decades
Multiple sportsbooks publish competing odds (fragmentation creates mispricing)
Mispricing has concrete measurable consequences (P&L net of vig)

Research question: Can we build a calibrated in-game NBA win probability model that systematically identifies live-market mispricings driven by crowd overreaction — specifically when trailing teams have higher comeback probability than implied odds suggest?
Course framing: This sits in STATS 211 territory — behavioral asset pricing, scoring rules (Brier/log-loss), wisdom-of-crowds failure modes, market microstructure (overround, line-setting under public bias).
Hard constraints (from the syllabus)

Presentation: 10 minutes, in-person, slides, June 1 or June 3, 2026. Will be followed by Q&A from instructor and class.
Report: 3 pages max (references excluded), NeurIPS conference format, due 11:59pm Sunday June 7, 2026 via Gradescope. Late submission not accepted.
Partner: Working with Vishnu. Build everything assuming two-person workload.

Deliverables we need to produce

Working code repo — well-organized, runs end-to-end, reproduces all results in the report
Cleaned dataset — NBA play-by-play + historical live odds, with proper train/val/test splits
Trained calibrated win probability model — beats baseline, well-calibrated (RMS calibration error reported)
Mispricing analysis — systematic identification of market deviations from model, broken down by situation type
Backtest — simulated betting strategy with realistic transaction costs (overround), reporting Sharpe-like metrics
3-page NeurIPS report — proper LaTeX template, abstract, figures, references
10-min slide deck — same Georgia/Calibri aesthetic as the midterm deck (navy/ocean palette)

Technical scope decisions (already locked in)

Sport: NBA only. NFL has only ~272 regular-season games, too small. NBA has ~1,230 regular-season games and possessions every 24 seconds → enormous per-game datapoints.
Seasons: Aim for 5+ recent seasons of play-by-play data. Live odds may only be available for fewer seasons — that's our test set bottleneck.
Model class: Start with logistic regression as baseline, then gradient boosting (XGBoost). Don't reach for neural networks unless we have a specific reason — for this data size, GBDT is the right tool and explanations are easier.
Target: P(home team wins game | game state at time t).
Features (initial set):

Score differential
Time remaining (seconds)
Possession indicator
Quarter
Pregame point spread (proxy for relative team strength)
Pregame total (proxy for game pace)
Recent scoring run (last 2 minutes)
Timeouts remaining (both teams)
Foul situation (if available)


Calibration metric: Brier score (primary) + log-loss + RMS calibration error + reliability diagram.
Comparison baseline: Bayesian in-game model from Lock & Nettleton or similar published model; also compare to implied probability from live odds (after de-vig).

Data sources (try in this order, fall back as needed)

Play-by-play: nba_api (Python package, scrapes stats.nba.com). Free. Has every event with timestamps. Most reliable.
Pregame odds: the-odds-api.com has historical NBA odds (limited free tier; may need to upgrade or scrape alternatives).
Live odds: This is the bottleneck. Options:

the-odds-api.com historical endpoint (paid, may be required)
Scrape archived sportsbook pages (legally gray, last resort)
Use closing odds + interpolation as a proxy (weaker, but doable)
Reach out to academic datasets — Moskowitz used data from Sportsinsights/Pinnacle, Ötting et al. have a dataset


Backup synthetic approach: If live odds are truly unavailable, generate "fair" odds from a published in-game model and study deviations between our model and theirs. Less ideal but still publishable.

Investigate data availability first before committing to a specific data approach — Week 1's top priority.
Required deliverables, by phase
Phase 0 — Setup (Day 1)

Initialize repo with proper structure (see below)
Set up Python environment with pyproject.toml (poetry or uv)
Initial dependencies: nba_api, pandas, numpy, scikit-learn, xgboost, matplotlib, seaborn, pyarrow
Pre-commit hooks for ruff/black/mypy
README with project description, setup instructions, run order
Reference the Halawi deck's color palette (NAVY=#0B2545, DEEP=#13315C, TEAL=#1C7293, SKY=#8DA9C4, CREAM=#F6F6F2, ACCENT=#EEA02B, INK=#1A1A1A) for any figures

Phase 1 — Data acquisition (Weeks 1–2)

Pull NBA play-by-play for 2019–2024 seasons (5 seasons)
Pull pregame odds for the same period
Investigate and acquire live odds data — top priority
Build a unified game-state table: one row per (game, possession or 10-second tick), columns include all features above + target (final outcome)
Save as Parquet for fast loading
Sanity checks: distribution plots, missingness audit, leakage check (no future info in features)

Phase 2 — Baseline win probability model (Week 3)

Implement logistic regression baseline on game-state features
Implement XGBoost model with same features
Train on 2019–2022, validate on 2023, hold out 2024 as test
Report Brier, log-loss, accuracy, RMS calibration error
Plot reliability diagrams (predicted vs empirical probability)
Compare to published baseline (Lock & Nettleton style)
Save trained models with joblib/pickle

Phase 3 — Mispricing analysis (Weeks 4–5)

For each test-set game, compute model probability and implied market probability (after removing vig) at each timestep
Define "mispricing event" as |model_prob − market_prob| > threshold (start with 0.05)
Stratify mispricing events by:

Score differential bucket (close / 5-10 / 10-15 / 15+ trailing)
Quarter
Time elapsed since last scoring event
Public-side flag (which team is the "public" favorite based on betting volume if available)


Test specific hypothesis: After a trailing team scores a basket in a 10+ point deficit, does the market over-shift toward the trailing team relative to our model's update?
Generate the headline plot: model_prob − market_prob distribution, by situation type

Phase 4 — Backtest (Week 6)

Implement a betting strategy: bet on the side our model favors when |edge| > threshold, sized by Kelly criterion (with fractional Kelly for safety)
Apply realistic transaction costs: 5-7.5% overround typical of live markets
Compute returns, Sharpe, max drawdown
Compare against naive baselines: always-bet-favorite, always-bet-trailing, random
Sensitivity analysis on edge threshold and Kelly fraction

Phase 5 — Writing & slides (Weeks 7–8)

Draft NeurIPS-format 3-page report in LaTeX (template: NeurIPS 2024 style)
Build 10-min slide deck (similar aesthetic to midterm — Georgia titles, Calibri body, ocean palette)
Rehearse and time

Report outline (3 pages, NeurIPS format)
Plan the report from the start so we build to it:

Introduction (0.5 pages) — motivation: Halawi shows LMs match crowds; we ask where models beat crowds. Live sports markets as a behavioral asset pricing laboratory.
Related work (0.25 pages) — Halawi 2024, Moskowitz 2021, Ötting 2022, in-game WP literature (Lock & Nettleton, iWinRNFL).
Method (0.75 pages) — feature engineering, XGBoost model, calibration approach, mispricing detection methodology, backtest design.
Results (1 page) — calibration metrics, mispricing patterns (figures by situation), backtest performance.
Discussion (0.4 pages) — what the results say about crowd miscalibration, limitations (overround, account limits, market reactivity), connection to Halawi's Aggregate column.
Conclusion (0.1 pages) — brief.

Slide deck outline (10 min, 12-14 slides)
Mirror the midterm deck's structure and aesthetic:

Title + names + course context
The midterm setup — Halawi's result + the buried finding (LM+crowd > either)
The deeper observation — LMs hedge, crowds overreact (cite Moskowitz, Ötting)
Research question — formal statement
Why live NBA markets — laboratory advantages
Data — play-by-play + odds, splits
Model — features + XGBoost + calibration
Calibration results — reliability diagram + Brier
Mispricing patterns — the headline plot
Specific hypothesis test — trailing-team scoring scenarios
Backtest — returns, Sharpe, vs baselines
Discussion — what does this say about crowd biases
Limitations + future work
Takeaways + Q&A

Repo structure I want
stats211-final/
├── CLAUDE.md                    # this file
├── README.md                    # human-readable project description
├── pyproject.toml               # dependencies
├── data/
│   ├── raw/                     # never modify; original pulls
│   ├── interim/                 # cleaned but not feature-engineered
│   └── processed/               # ready for modeling (parquet)
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_baseline_model.ipynb
│   ├── 03_xgboost_model.ipynb
│   ├── 04_mispricing_analysis.ipynb
│   └── 05_backtest.ipynb
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── pull_pbp.py          # play-by-play scraper
│   │   ├── pull_odds.py         # odds data acquisition
│   │   └── build_dataset.py     # unified game-state table
│   ├── features/
│   │   └── feature_engineering.py
│   ├── models/
│   │   ├── baseline.py          # logistic regression
│   │   ├── xgb_model.py         # XGBoost
│   │   └── calibration.py       # reliability diagrams, ECE
│   ├── analysis/
│   │   ├── mispricing.py        # detection logic
│   │   └── backtest.py          # betting simulation
│   └── viz/
│       └── plots.py             # consistent styling
├── tests/                       # unit tests for critical paths
├── reports/
│   ├── final_report.tex         # NeurIPS template
│   ├── final_report.pdf
│   └── figures/                 # all figures saved here
├── slides/
│   ├── build.js                 # pptxgenjs build script
│   └── final_deck.pptx
└── .pre-commit-config.yaml
How I want you (Claude Code) to work with me

Always confirm understanding before coding. When I give you a task, restate the goal in one sentence and flag any decisions you're making.
Test as you go. When you build a function, also write a small test or sanity check. Don't accumulate untested code.
Plot defensively. Every model output should come with a calibration plot, distribution plot, or comparison-to-baseline plot. We need these for the report anyway.
Save intermediates. After every meaningful computation, save the output to data/processed/ or data/interim/. We don't want to re-run 30-minute pulls every time.
Watch for data leakage. This is the #1 way the project can fail. Triple-check that no future information leaks into features. Make this an explicit step before each model fit.
Beware overfitting to backtest noise. Sports markets have small effective sample sizes due to game-level correlation. If results look too good, they probably are. Always cross-validate at the game level, not the row level.
Reproduce existing results before going beyond them. First reproduce a published in-game WP model's Brier score on our data. Only then claim improvements.
Document decisions. Whenever we make a methodological choice (threshold, hyperparameter, exclusion rule), add a note in a DECISIONS.md file. We'll need this for the report's methodology section.
Keep the academic framing live. Periodically remind me how a result connects to the report narrative (Halawi → crowd miscalibration → live markets → mispricing). Don't let this become a generic betting model — the academic story is what gets us the grade.
Push back if I ask for something dumb. I've never built a model like this before. If I ask for something that's a methodological mistake, tell me. I'd rather get challenged than ship a broken project.

What success looks like
A project: well-calibrated model, statistically significant mispricing patterns identified, clean backtest showing edge exists (even if smaller than vig), tight 3-page report with proper figures, polished 10-min talk, working repo.
A+ project: all of the above, plus a novel/surprising finding (e.g., a specific situation where mispricing is larger than vig, or a mechanism design insight about why books leave money on the table), plus clean exposition that ties cleanly to Halawi.
Things to avoid

Don't overcomplicate the model. Logistic regression and XGBoost are right. No transformers.
Don't try to do both NBA and NFL. Pick one and do it well.
Don't focus on prediction accuracy at the expense of calibration. The whole project hinges on calibrated probabilities.
Don't over-trust the backtest. Markets adapt and accounts get limited. We're documenting that mispricing exists, not running a hedge fund.
Don't bury the academic story under engineering. Every section of the report should explicitly tie back to behavioral asset pricing / Halawi / scoring rules.

My first ask
Read this entire document. Then:

Confirm you understand the project's intellectual arc (midterm → crowd biases → live markets → mispricing).
Audit the technical plan for anything you'd change.
Generate a Week 1 task list — concrete, prioritized, with the specific data investigation first.
Set up the repo scaffold above.

Do not start writing model code yet. Phase 0 (setup + data investigation) is everything for the first few days.
