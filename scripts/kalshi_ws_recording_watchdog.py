#!/usr/bin/env python3
"""Watch a live Kalshi recording run and restart stale WebSocket recorders."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_TICKERS = ["KXNBAGAME-26JUN05NYKSAS-SAS", "KXNBAGAME-26JUN05NYKSAS-NYK"]


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def newest_dir(run_dir: Path, prefix: str) -> Path | None:
    dirs = sorted(path for path in run_dir.glob(f"{prefix}_*") if path.is_dir())
    return dirs[-1] if dirs else None


def file_age_s(path: Path) -> float | None:
    if not path.exists():
        return None
    return max(0.0, time.time() - path.stat().st_mtime)


def stop_pidfile(path: Path, log: list[str]) -> None:
    if not path.exists():
        return
    try:
        pid = int(path.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        log.append(f"stopped {path.name} pid={pid}")
    except ProcessLookupError:
        log.append(f"already stopped {path.name}")
    except Exception as exc:  # noqa: BLE001 - watchdog must keep going.
        log.append(f"stop error {path.name}: {type(exc).__name__}: {exc}")


def launch_ws(run_dir: Path, label: str, tickers: list[str], listen_ms: int, suffix: str) -> tuple[int, Path]:
    outdir = run_dir / f"{label}_{suffix}"
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = ["python3", "scripts/kalshi_ws_orderbook_recorder.py"]
    for ticker in tickers:
        cmd.extend(["--ticker", ticker])
    cmd.extend(
        [
            "--channels",
            "orderbook_delta,ticker,trade",
            "--listen-ms",
            str(listen_ms),
            "--output-dir",
            str(outdir),
        ]
    )
    stdout = (run_dir / f"{label}_{suffix}.stdout.log").open("ab", buffering=0)
    stderr = (run_dir / f"{label}_{suffix}.stderr.log").open("ab", buffering=0)
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )
    (run_dir / f"{label}_{suffix}.pid").write_text(f"{proc.pid}\n", encoding="utf-8")
    return proc.pid, outdir


def load_expanded_tickers(run_dir: Path) -> list[str]:
    manifest = json.loads((run_dir / "expanded_manifest.json").read_text(encoding="utf-8"))
    return list(manifest["all_tickers"])


def append_log(run_dir: Path, payload: dict[str, object]) -> None:
    path = run_dir / "ws_watchdog.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
        handle.flush()


def maybe_restart(args: argparse.Namespace, expanded_tickers: list[str]) -> None:
    run_dir = args.run_dir
    log: list[str] = []
    latest_main = newest_dir(run_dir, "ws_restart")
    latest_expanded = newest_dir(run_dir, "expanded_ws_restart")
    main_age = file_age_s(latest_main / "kalshi_ws_raw.jsonl") if latest_main else None
    expanded_age = file_age_s(latest_expanded / "kalshi_ws_raw.jsonl") if latest_expanded else None

    stale_main = main_age is None or main_age > args.stale_seconds
    stale_expanded = expanded_age is None or expanded_age > args.stale_seconds
    if not stale_main and not stale_expanded:
        append_log(
            run_dir,
            {
                "ts": now_iso(),
                "action": "healthy",
                "main_age_s": main_age,
                "expanded_age_s": expanded_age,
            },
        )
        return

    suffix = stamp()
    if stale_main:
        for pidfile in sorted(run_dir.glob("ws_restart_*.pid"))[-1:]:
            stop_pidfile(pidfile, log)
        pid, outdir = launch_ws(run_dir, "ws_restart", MAIN_TICKERS, args.listen_ms, suffix)
        log.append(f"started main pid={pid} outdir={outdir}")
    if stale_expanded:
        for pidfile in sorted(run_dir.glob("expanded_ws_restart_*.pid"))[-1:]:
            stop_pidfile(pidfile, log)
        pid, outdir = launch_ws(run_dir, "expanded_ws_restart", expanded_tickers, args.listen_ms, suffix)
        log.append(f"started expanded pid={pid} outdir={outdir}")

    append_log(
        run_dir,
        {
            "ts": now_iso(),
            "action": "restart",
            "main_age_s": main_age,
            "expanded_age_s": expanded_age,
            "log": log,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--check-seconds", type=float, default=30.0)
    parser.add_argument("--stale-seconds", type=float, default=120.0)
    parser.add_argument("--listen-ms", type=int, default=14_400_000)
    args = parser.parse_args()

    expanded_tickers = load_expanded_tickers(args.run_dir)
    append_log(args.run_dir, {"ts": now_iso(), "action": "watchdog_started", "stale_seconds": args.stale_seconds})
    while True:
        maybe_restart(args, expanded_tickers)
        time.sleep(args.check_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
