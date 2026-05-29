"""Backtest V2 vs Kalshi 1H-winner market on archived playoff games.

WHY THIS EXISTS: our first Kalshi candle pull saved mostly PRE-GAME quotes
(timestamps ended before tipoff). This script re-pulls candles using the
CORRECT in-play window — derived from each game's PBP period start/end
wall-clocks — then aligns them to game state and runs the verified backtest
engine (src/eval/backtest.py).

n is tiny (a handful of liquid playoff games), so the P&L is DIRECTIONAL, not a
statistically powered result. The point is a real end-to-end number from actual
Kalshi market prices.

STATUS: written while the shell was down (laptop sleep). UNTESTED until a reboot
restores Python. Expect a debug pass — every stage prints diagnostics.

Run:  uv run python scripts/backtest_kalshi_archive.py
"""

from __future__ import annotations

import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import warnings

import joblib
import numpy as np
import pandas as pd
from nba_api.stats.endpoints import playbyplayv3, scoreboardv2

warnings.filterwarnings("ignore")

from src.data.build_dataset import build_minute_snapshots
from src.data.pull_kalshi import KalshiClient
from src.eval import backtest as bt

ET = ZoneInfo("America/New_York")
SERIES = "KXNBA1HWINNER"
KALSHI_DIR = REPO_ROOT / "data" / "interim" / "kalshi" / SERIES
MODEL_PATH = REPO_ROOT / "models" / "v2_xgb_isotonic.joblib"
MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


# ----------------------------------------------------------------------------
# Ticker / game resolution
# ----------------------------------------------------------------------------

def parse_event_date(event_ticker: str) -> datetime:
    """KXNBA1HWINNER-26APR30DENMIN -> date 2026-04-30 (ET midnight)."""
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})", event_ticker)
    if not m:
        raise ValueError(f"can't parse date from {event_ticker}")
    yy, mon, dd = m.group(1), m.group(2), m.group(3)
    return datetime(2000 + int(yy), MONTHS[mon], int(dd), tzinfo=ET)


def resolve_game(event_date: datetime) -> list[dict]:
    """All games on that date via ScoreboardV2 GameHeader."""
    d = event_date.strftime("%Y-%m-%d")
    sb = scoreboardv2.ScoreboardV2(game_date=d, league_id="00", timeout=30).get_normalized_dict()
    return sb.get("GameHeader", [])


def market_suffixes(event_ticker: str) -> list[str]:
    """The two team tickers + TIE, e.g. ['DEN','MIN','TIE'].
    Tail looks like '26APR30DENMIN' = YY(2)+MON(3)+DD(2) then AWAY+HOME."""
    teams = event_ticker.split("-")[-1][7:]  # strip the 7-char date prefix
    return [teams[:3], teams[3:6], "TIE"]


# ----------------------------------------------------------------------------
# PBP wall-clock anchors -> wall_clock(epoch) <-> game_elapsed(sec) for the 1H
# ----------------------------------------------------------------------------

def period_anchors(pbp: pd.DataFrame, event_date: datetime) -> dict:
    """Parse 'Start/End of Nth Period (H:MM PM EST)' into ET epoch seconds.
    NBA stamps 'EST' year-round; we localize to America/New_York so DST is
    handled correctly. Returns {('start'|'end', period): epoch}."""
    anchors: dict = {}
    pat = re.compile(r"(Start|End) of .* \((\d{1,2}):(\d{2})\s*(AM|PM)")
    for _, r in pbp[pbp["description"].str.contains("of .* Period", na=False)].iterrows():
        m = pat.search(str(r["description"]))
        if not m:
            continue
        kind, hh, mm, ap = m.group(1).lower(), int(m.group(2)), int(m.group(3)), m.group(4)
        hh = (hh % 12) + (12 if ap == "PM" else 0)
        # games can cross midnight; if hour is small (AM) it's the next day
        day = event_date
        dt = datetime(day.year, day.month, day.day, hh, mm, tzinfo=ET)
        if ap == "AM" and hh < 12:
            dt = dt.replace(day=day.day) + pd.Timedelta(days=1)
        anchors[(kind, int(r["period"]))] = dt.timestamp()
    return anchors


def wall_to_game_elapsed(epoch: float, anchors: dict) -> float | None:
    """Map a wall-clock epoch to game-elapsed seconds within the 1st half.
    Piecewise-linear inside Q1 [0,720] and Q2 [720,1440] using period anchors."""
    s1, e1 = anchors.get(("start", 1)), anchors.get(("end", 1))
    s2, e2 = anchors.get(("start", 2)), anchors.get(("end", 2))
    if None in (s1, e1, s2, e2):
        return None
    if epoch < s1:
        return None
    if epoch <= e1:                                   # Q1
        return (epoch - s1) / (e1 - s1) * 720.0
    if epoch < s2:                                    # Q1->Q2 break
        return 720.0
    if epoch <= e2:                                   # Q2
        return 720.0 + (epoch - s2) / (e2 - s2) * 720.0
    return None                                       # past halftime -> 1H settled


# ----------------------------------------------------------------------------
# Kalshi candle re-pull + parse
# ----------------------------------------------------------------------------

def parse_candles(resp: dict) -> pd.DataFrame:
    rows = []
    for c in resp.get("candlesticks", []) or []:
        price = c.get("price", {}) or {}
        yb, ya = c.get("yes_bid", {}) or {}, c.get("yes_ask", {}) or {}

        def dollars(d, k):  # fields are already in dollars, as strings
            v = d.get(k)
            return None if v is None else float(v)

        rows.append({
            "end_ts": c.get("end_period_ts"),
            "close": dollars(price, "close_dollars"),
            "mean": dollars(price, "mean_dollars"),
            "yes_bid_close": dollars(yb, "close_dollars"),
            "yes_ask_close": dollars(ya, "close_dollars"),
            "volume": dollars(c, "volume_fp"),
        })
    return pd.DataFrame(rows)


def repull_inplay(client: KalshiClient, event_ticker: str, suffix: str,
                  start_ts: int, end_ts: int) -> pd.DataFrame:
    market = f"{event_ticker}-{suffix}"
    for fn in (lambda: client.get_candlesticks(SERIES, market, start_ts, end_ts, 1),
               lambda: client.get_historical_candlesticks(market, start_ts, end_ts, 1)):
        try:
            df = parse_candles(fn())
            if not df.empty:
                return df
        except Exception as e:  # noqa: BLE001
            print(f"    {market}: {type(e).__name__} {e}")
        time.sleep(0.2)
    return pd.DataFrame()


# ----------------------------------------------------------------------------
# Per-game pipeline
# ----------------------------------------------------------------------------

def build_game(client: KalshiClient, bundle: dict, event_ticker: str) -> pd.DataFrame:
    feats = bundle["features"]
    event_date = parse_event_date(event_ticker)
    suff = market_suffixes(event_ticker)
    print(f"\n=== {event_ticker}  ({event_date:%Y-%m-%d}, markets {suff}) ===")

    games = resolve_game(event_date)
    if not games:
        print("  no games found on date"); return pd.DataFrame()
    # match by tricode appearing in the ticker
    gid = home_tri = away_tri = None
    for g in games:
        code = g.get("GAMECODE", "")  # e.g. 20260430/DENMIN
        tail = code.split("/")[-1]
        if suff[0] in tail and suff[1] in tail:
            gid = g["GAME_ID"]; break
    if gid is None:
        print(f"  couldn't match {suff} to any GAMECODE on date"); return pd.DataFrame()

    pbp = playbyplayv3.PlayByPlayV3(game_id=gid, timeout=30).get_data_frames()[0]
    snaps = build_minute_snapshots(pbp, game_id=gid, season="2025-26")
    if snaps.empty:
        print("  no snapshots"); return pd.DataFrame()
    home_tri = snaps.iloc[0]["home_tricode"]; away_tri = snaps.iloc[0]["away_tricode"]
    y_home = int(snaps.iloc[0]["y_home_wins_1h"])
    print(f"  game_id={gid}  home={home_tri} away={away_tri}  1H winner: {'HOME' if y_home else 'AWAY'}")

    anchors = period_anchors(pbp, event_date)
    if ("start", 1) not in anchors or ("end", 2) not in anchors:
        print("  missing period anchors"); return pd.DataFrame()
    win_start = int(anchors[("start", 1)]) - 120
    win_end = int(anchors[("end", 2)]) + 120
    print(f"  in-play window ET {datetime.fromtimestamp(win_start,ET):%H:%M}->{datetime.fromtimestamp(win_end,ET):%H:%M}")

    # re-pull all three markets for the in-play window
    prices = {}
    for s in suff:
        c = repull_inplay(client, event_ticker, s, win_start, win_end)
        prices[s] = c
        print(f"  {s}: {len(c)} in-play candles re-pulled")
    if all(c.empty for c in prices.values()):
        print("  NO in-play candles available (market didn't trade in-play)"); return pd.DataFrame()

    # 1-min grid over in-play window; forward-fill each market's mid price
    grid = pd.DataFrame({"end_ts": range(int(anchors[("start", 1)]), int(anchors[("end", 2)]) + 1, 60)})
    def mid_series(c: pd.DataFrame) -> pd.Series:
        if c.empty:
            return pd.Series([np.nan] * len(grid), index=grid.index)
        c = c.dropna(subset=["end_ts"]).sort_values("end_ts")
        c["mid"] = c[["yes_bid_close", "yes_ask_close"]].mean(axis=1).fillna(c["close"]).fillna(c["mean"])
        merged = pd.merge_asof(grid, c[["end_ts", "mid", "yes_ask_close"]], on="end_ts", direction="backward")
        return merged

    # map the two team suffixes to home/away by tricode match
    home_suf = next((s for s in suff[:2] if s == home_tri or s[:2] == home_tri[:2]), suff[1])
    away_suf = next((s for s in suff[:2] if s != home_suf), suff[0])
    print(f"  home_suffix={home_suf} away_suffix={away_suf}")

    mh, ma, mt = mid_series(prices[home_suf]), mid_series(prices[away_suf]), mid_series(prices["TIE"])
    g = grid.copy()
    g["home_mid"], g["away_mid"], g["tie_mid"] = mh["mid"], ma["mid"], mt["mid"]
    g["home_ask"], g["away_ask"] = mh["yes_ask_close"], ma["yes_ask_close"]
    g = g.dropna(subset=["home_mid", "away_mid"])  # need both sides priced
    if g.empty:
        print("  no minutes with both sides priced"); return pd.DataFrame()

    denom = g["home_mid"] + g["away_mid"] + g["tie_mid"].fillna(0.0)
    g["p_market_home_devig"] = g["home_mid"] / denom

    # align each grid minute to game state -> V2 p_hat
    rows = []
    for _, r in g.iterrows():
        ge = wall_to_game_elapsed(r["end_ts"], anchors)
        if ge is None:
            continue
        midx = int(min(24, max(1, round(ge / 60))))
        snap = snaps[snaps["minute_idx"] == midx]
        if snap.empty:
            continue
        x = snap[feats].iloc[[0]]
        phat = float(bundle["iso"].transform(bundle["xgb"].predict_proba_home_wins(x))[0])
        # convert Kalshi YES ask -> american-equivalent for the payout engine
        ha = prob_to_american(r["home_ask"] if pd.notna(r["home_ask"]) else r["home_mid"])
        aa = prob_to_american(r["away_ask"] if pd.notna(r["away_ask"]) else r["away_mid"])
        rows.append({
            "game_id": gid, "minute_idx": midx,
            "p_hat": phat, "p_market_home_devig": r["p_market_home_devig"],
            "home_odds_american": ha, "away_odds_american": aa,
            "y_home_win": y_home,
        })
    out = pd.DataFrame(rows)
    print(f"  -> {len(out)} aligned in-play ticks")
    return out


def prob_to_american(q: float) -> float:
    q = float(np.clip(q, 1e-4, 1 - 1e-4))
    return -100.0 * q / (1.0 - q) if q >= 0.5 else 100.0 * (1.0 - q) / q


# ----------------------------------------------------------------------------

def main() -> int:
    bundle = joblib.load(MODEL_PATH)
    client = KalshiClient()

    # archived candle data + Game 6 (just settled today)
    events = ["KXNBA1HWINNER-26APR30DENMIN", "KXNBA1HWINNER-26MAY03TORCLE",
              "KXNBA1HWINNER-26MAY04MINSAS", "KXNBA1HWINNER-26MAY13CLEDET",
              "KXNBA1HWINNER-26MAY28OKCSAS"]  # Game 6 OKC@SAS
    print(f"Processing {len(events)} known events with archived candles")

    frames = []
    for ev in events:
        try:
            df = build_game(client, bundle, ev)
            if not df.empty:
                frames.append(df)
        except Exception as e:  # noqa: BLE001
            print(f"  {ev}: FAILED {type(e).__name__}: {e}")

    if not frames:
        print("\nNo games yielded in-play ticks. Likely no in-play Kalshi liquidity.")
        return 0

    allt = pd.concat(frames, ignore_index=True)
    print(f"\n{'='*64}\nPooled: {len(allt)} ticks across {allt['game_id'].nunique()} games\n{'='*64}")

    for thr in (0.03, 0.05, 0.08):
        rep = bt.simulate(allt, name=f"V2 (thr={thr:.0%})", threshold=thr, kelly_mult=0.25)
        print(f"  {rep}")
    print("\nBaselines:")
    for rule in ("favorite", "trailing", "random"):
        try:
            print(f"  {bt.baseline_simulate(allt, rule=rule)}")
        except Exception as e:  # noqa: BLE001
            print(f"  baseline {rule}: {e}")

    print("\n⚠️  n is tiny — this is a DIRECTIONAL proof-of-concept, not a result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
