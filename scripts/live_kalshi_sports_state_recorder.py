#!/usr/bin/env python3
"""Poll Kalshi milestone live-data/game-stats with receive timestamps."""

from __future__ import annotations

import argparse
import json
import signal
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
    request = urllib.request.Request(url, headers={"User-Agent": "tensai-kalshi-sports-state-recorder/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def write_line(handle: object, payload: dict[str, Any]) -> None:
    handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
    handle.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--milestone-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration-ms", type=int, default=7_200_000)
    parser.add_argument("--live-interval-ms", type=int, default=500)
    parser.add_argument("--stats-interval-ms", type=int, default=2_000)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip("/")
    endpoints = {
        "milestone": f"{base}/milestones/{args.milestone_id}",
        "live_data": f"{base}/live_data/milestone/{args.milestone_id}",
        "game_stats": f"{base}/live_data/milestone/{args.milestone_id}/game_stats",
    }
    intervals = {
        "milestone": 30_000,
        "live_data": args.live_interval_ms,
        "game_stats": args.stats_interval_ms,
    }
    next_due = {name: 0.0 for name in endpoints}

    start = time.monotonic()
    seq = 0
    with args.output.open("a", encoding="utf-8") as output:
        write_line(
            output,
            {
                "type": "recorder_started",
                "started_at": now_iso(),
                "milestone_id": args.milestone_id,
                "duration_ms": args.duration_ms,
                "live_interval_ms": args.live_interval_ms,
                "stats_interval_ms": args.stats_interval_ms,
            },
        )

        while not STOP and (time.monotonic() - start) * 1000 < args.duration_ms:
            now = time.monotonic()
            due_names = [name for name, due in next_due.items() if now >= due]
            if not due_names:
                time.sleep(0.025)
                continue

            for name in due_names:
                request_start = wall_ms()
                try:
                    payload: dict[str, Any] | None = get_json(endpoints[name], args.timeout)
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
                        "type": name,
                        "seq": seq,
                        "capture_wall_ms": request_end,
                        "request_ms": request_end - request_start,
                        "status": status,
                        "error": error,
                        "payload": payload,
                    },
                )
                seq += 1
                next_due[name] = time.monotonic() + intervals[name] / 1000

        write_line(output, {"type": "recorder_finished", "finished_at": now_iso(), "seq": seq})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
