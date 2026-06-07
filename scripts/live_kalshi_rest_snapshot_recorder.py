#!/usr/bin/env python3
"""Record full Kalshi market/orderbook snapshots for a live event."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_URL = "https://external-api.kalshi.com/trade-api/v2"

STOP = False


def on_signal(_sig: int, _frame: object) -> None:
    global STOP
    STOP = True


def wall_ms() -> float:
    return time.time_ns() / 1_000_000


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "tensai-live-kalshi-recorder/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def write_line(handle: object, payload: dict[str, Any]) -> None:
    handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
    handle.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval-ms", type=int, default=500)
    parser.add_argument("--duration-ms", type=int, default=7_200_000)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    next_tick = start
    seq = 0
    base_url = args.base_url.rstrip("/")

    with args.output.open("a", encoding="utf-8") as output:
        write_line(
            output,
            {
                "type": "recorder_started",
                "started_at": now_iso(),
                "tickers": args.ticker,
                "interval_ms": args.interval_ms,
                "duration_ms": args.duration_ms,
            },
        )
        while not STOP and (time.monotonic() - start) * 1000 < args.duration_ms:
            now = time.monotonic()
            if now < next_tick:
                time.sleep(min(next_tick - now, 0.05))
                continue

            cycle_start_wall = wall_ms()
            for ticker in args.ticker:
                endpoints = (
                    ("orderbook_snapshot", f"{base_url}/markets/{ticker}/orderbook"),
                    ("market_snapshot", f"{base_url}/markets/{ticker}"),
                )
                for snapshot_type, url in endpoints:
                    request_start = wall_ms()
                    try:
                        payload: dict[str, Any] | None = get_json(url, args.timeout)
                        status = "ok"
                        error = None
                    except Exception as exc:  # noqa: BLE001 - recorder should log and continue.
                        payload = None
                        status = "error"
                        error = {"class": type(exc).__name__, "message": str(exc)[:500]}
                    request_end = wall_ms()
                    write_line(
                        output,
                        {
                            "type": snapshot_type,
                            "seq": seq,
                            "ticker": ticker,
                            "capture_wall_ms": request_end,
                            "cycle_start_wall_ms": cycle_start_wall,
                            "request_ms": request_end - request_start,
                            "status": status,
                            "error": error,
                            "payload": payload,
                        },
                    )
                    seq += 1

            next_tick = max(next_tick + args.interval_ms / 1000, time.monotonic() + 0.001)

        write_line(output, {"type": "recorder_finished", "finished_at": now_iso(), "seq": seq})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
