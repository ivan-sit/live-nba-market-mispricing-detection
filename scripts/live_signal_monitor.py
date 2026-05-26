"""LIVE PAPER-TRADING signal monitor — V2 model vs Kalshi 1H-winner market.

================== READ THIS ==================
This is PAPER TRADING. It places NO orders and touches NO money. It prints what
the model *would* do and logs (model prob, market price, edge, hypothetical
Kelly stake, outcome) so we can backtest a REAL game afterward. The model has
NOT been validated as profitable. Do not bet real money off these signals.
===============================================

Feeds:
  - Game state: ESPN scoreboard API (NBA CDN is IP-blocked here).
  - Market:     Kalshi KXNBA1HWINNER orderbook (peer-driven, ~no house vig).
  - Model:      models/v2_xgb_isotonic.joblib (P(home wins 1st half)).

Only active during the 1ST HALF (periods 1-2). After halftime the 1H market
settles, so the monitor stops.

Run (default targets tonight's SA @ OKC):
  uv run python scripts/live_signal_monitor.py --cadence 60 --threshold 0.04
  uv run python scripts/live_signal_monitor.py --once     # single snapshot
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import joblib  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402

from src.data.pull_kalshi import KalshiClient  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (stats211 research)"}
ESPN_SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
MODEL_PATH = REPO_ROOT / "models" / "v2_xgb_isotonic.joblib"
OUT_DIR = REPO_ROOT / "data" / "interim" / "live_signals"
FIELDS = [
    "ts", "state", "period", "clock_sec", "elapsed_half_sec", "minute_idx",
    "home", "away", "home_score", "away_score", "score_diff_home", "recent_run_diff",
    "p_model_home_1h", "k_okc_mid", "k_sas_mid", "k_tie_mid", "p_market_home_devig",
    "edge", "signal", "kelly_fraction", "paper_stake",
]


def parse_clock(disp: str) -> float:
    """ESPN displayClock -> seconds remaining in period. '5:23'->323, '0.0'->0."""
    if not disp:
        return 0.0
    disp = str(disp).strip()
    if ":" in disp:
        m, s = disp.split(":")
        return float(m) * 60 + float(s)
    try:
        return float(disp)
    except ValueError:
        return 0.0


def fetch_espn(home_abbr: str, away_abbr: str) -> dict | None:
    r = requests.get(ESPN_SB, headers=UA, timeout=15)
    r.raise_for_status()
    for e in r.json().get("events", []):
        c = e["competitions"][0]
        comps = {x["homeAway"]: x for x in c["competitors"]}
        h = comps.get("home", {}).get("team", {}).get("abbreviation")
        a = comps.get("away", {}).get("team", {}).get("abbreviation")
        if h == home_abbr and a == away_abbr:
            st = c["status"]
            return {
                "state": st["type"]["state"],          # pre / in / post
                "period": int(st.get("period") or 0),
                "clock_sec": parse_clock(st.get("displayClock", "0")),
                "home_score": int(comps["home"].get("score") or 0),
                "away_score": int(comps["away"].get("score") or 0),
            }
    return None


def cents_to_dollars(v) -> float | None:
    if v is None:
        return None
    return float(v) / 100.0 if float(v) > 1 else float(v)


def kalshi_mid(client: KalshiClient, ticker: str) -> float | None:
    """Mid of yes_bid/yes_ask in dollars; fall back to last_price."""
    try:
        m = client.get_market(ticker).get("market", {})
    except Exception:
        return None
    bid = cents_to_dollars(m.get("yes_bid"))
    ask = cents_to_dollars(m.get("yes_ask"))
    if bid is not None and ask is not None:
        return (bid + ask) / 2.0
    last = cents_to_dollars(m.get("last_price"))
    return last


def kelly(p_win: float, ask_dollars: float) -> float:
    """Fractional-Kelly fraction for a Kalshi YES buy at `ask` (full Kelly)."""
    if ask_dollars is None or ask_dollars <= 0 or ask_dollars >= 1:
        return 0.0
    b = (1.0 - ask_dollars) / ask_dollars      # decimal payout - 1
    f = (b * p_win - (1.0 - p_win)) / b
    return max(0.0, f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default="OKC")
    ap.add_argument("--away", default="SA")
    ap.add_argument("--event", default="KXNBA1HWINNER-26MAY26SASOKC")
    ap.add_argument("--cadence", type=int, default=60)
    ap.add_argument("--threshold", type=float, default=0.04)
    ap.add_argument("--bankroll", type=float, default=100.0)
    ap.add_argument("--kelly-mult", type=float, default=0.25)
    ap.add_argument("--max-fraction", type=float, default=0.25)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    print(__doc__.split("Feeds:")[0])  # the disclaimer banner

    bundle = joblib.load(MODEL_PATH)
    xgb, iso, feats = bundle["xgb"], bundle["iso"], bundle["features"]
    client = KalshiClient()
    tkr = {s: f"{args.event}-{s}" for s in ("OKC", "SAS", "TIE")}
    # which Kalshi side is the HOME team's YES contract
    home_side = "OKC" if args.home == "OKC" else "SAS"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / f"signals_{args.event}.csv"
    write_header = not out_csv.exists()
    f = out_csv.open("a", newline="")
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    if write_header:
        writer.writeheader()

    print(f"Model: {MODEL_PATH.name}  features={feats}")
    print(f"Game: {args.away} @ {args.home}   Kalshi event: {args.event}")
    print(f"threshold={args.threshold:.0%}  bankroll=${args.bankroll:.0f}  kelly={args.kelly_mult}x")
    print(f"Logging -> {out_csv}\n")

    score_hist: list[tuple[float, int, int]] = []  # (elapsed_half_sec, home, away)

    try:
        while True:
            ts = datetime.now(timezone.utc).isoformat()
            try:
                g = fetch_espn(args.home, args.away)
            except Exception as e:  # noqa: BLE001
                print(f"[{ts}] ESPN error: {e}")
                if args.once:
                    return 1
                time.sleep(args.cadence)
                continue

            if g is None:
                print(f"[{ts}] game {args.away}@{args.home} not on today's ESPN board.")
                break

            state, period, clock_sec = g["state"], g["period"], g["clock_sec"]

            if state == "pre":
                print(f"[{ts}] PRE-GAME — tip not yet. (re-poll in {args.cadence}s)")
                if args.once:
                    break
                time.sleep(args.cadence)
                continue
            if state == "post" or period > 2:
                print(f"[{ts}] 1st half over (state={state}, period={period}). Monitor done.")
                break

            elapsed_half = (period - 1) * 720 + (720 - clock_sec)
            minute_idx = int(min(24, max(1, elapsed_half // 60)))
            hs, as_ = g["home_score"], g["away_score"]
            score_diff_home = hs - as_

            score_hist.append((elapsed_half, hs, as_))
            # recent run over last ~120s
            run_diff = 0
            for e_sec, eh, ea in reversed(score_hist):
                if elapsed_half - e_sec >= 120:
                    run_diff = (hs - eh) - (as_ - ea)
                    break

            row = pd.DataFrame([{
                "minute_idx": minute_idx, "score_diff_home": score_diff_home,
                "recent_run_diff": run_diff, "period": period,
            }])[feats]
            p_model = float(iso.transform(xgb.predict_proba_home_wins(row))[0])

            mids = {s: kalshi_mid(client, tkr[s]) for s in ("OKC", "SAS", "TIE")}
            have = {s: v for s, v in mids.items() if v is not None}
            p_mkt_home = None
            if home_side in have and sum(have.values()) > 0:
                p_mkt_home = have[home_side] / sum(have.values())  # 3-way de-vig

            # decide signal
            signal, kf, stake = "—", 0.0, 0.0
            edge = None
            if p_mkt_home is not None:
                edge = p_model - p_mkt_home
                if edge > args.threshold:           # model likes HOME more than market
                    ask = mids[home_side]
                    kf = kelly(p_model, ask)
                    side = args.home
                elif edge < -args.threshold:         # model likes AWAY more
                    away_side = "SAS" if home_side == "OKC" else "OKC"
                    ask = mids[away_side]
                    kf = kelly(1 - p_model, ask)
                    side = args.away
                else:
                    side = None
                if side and kf > 0:
                    frac = min(args.kelly_mult * kf, args.max_fraction)
                    stake = frac * args.bankroll
                    signal = f"BUY {side} YES @ {ask:.2f}"

            edge_str = f"{edge:+.3f}" if edge is not None else "n/a"
            pm_str = f"{p_mkt_home:.3f}" if p_mkt_home is not None else "no-quote"
            print(
                f"[{ts}] P{period} {clock_sec:5.0f}s left | {args.away} {as_}-{hs} {args.home} "
                f"(diff_home {score_diff_home:+d}, run {run_diff:+d}, min{minute_idx}) | "
                f"model={p_model:.3f} market={pm_str} edge={edge_str} | "
                f"{signal}" + (f"  stake=${stake:.2f} (k={kf:.2f})" if stake else "")
            )

            writer.writerow({
                "ts": ts, "state": state, "period": period, "clock_sec": clock_sec,
                "elapsed_half_sec": elapsed_half, "minute_idx": minute_idx,
                "home": args.home, "away": args.away, "home_score": hs, "away_score": as_,
                "score_diff_home": score_diff_home, "recent_run_diff": run_diff,
                "p_model_home_1h": p_model, "k_okc_mid": mids["OKC"], "k_sas_mid": mids["SAS"],
                "k_tie_mid": mids["TIE"], "p_market_home_devig": p_mkt_home,
                "edge": edge, "signal": signal, "kelly_fraction": kf, "paper_stake": stake,
            })
            f.flush()

            if args.once:
                break
            time.sleep(args.cadence)
    except KeyboardInterrupt:
        print("\nStopped (Ctrl-C).")
    finally:
        f.close()
        print(f"Signals logged to {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
