#!/usr/bin/env python3
"""Record and reconstruct Kalshi WebSocket orderbooks.

Writes two JSONL files:
- raw WebSocket messages with arrival timestamps
- reconstructed book/depth events after every snapshot/delta
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import signal
import time
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import websockets
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


DEFAULT_CONFIG = Path.home() / ".config" / "tensai-latency" / "kalshi.env"
DEFAULT_WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
WS_SIGN_PATH = "/trade-api/ws/v2"
STOP = False


def on_signal(_sig: int, _frame: object) -> None:
    global STOP
    STOP = True


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def wall_ms() -> float:
    return time.time_ns() / 1_000_000


def monotonic_ms() -> float:
    return time.perf_counter_ns() / 1_000_000


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def load_private_key(path: Path) -> rsa.RSAPrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise TypeError("Kalshi private key is not an RSA private key")
    return key


def sign_request(private_key: rsa.RSAPrivateKey, timestamp_ms: str, method: str, path: str) -> str:
    message = f"{timestamp_ms}{method.upper()}{path.split('?', 1)[0]}".encode("utf-8")
    digest = hashes.SHA256()
    signature = private_key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(digest), salt_length=digest.digest_size),
        digest,
    )
    return base64.b64encode(signature).decode("ascii")


async def connect_with_headers(ws_url: str, headers: dict[str, str], timeout: float):
    kwargs = {
        "open_timeout": timeout,
        "ping_interval": None,
        "close_timeout": min(timeout, 5),
        "max_queue": None,
    }
    try:
        return await websockets.connect(ws_url, additional_headers=headers, **kwargs)
    except TypeError:
        return await websockets.connect(ws_url, extra_headers=headers, **kwargs)


def decimal_or_zero(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def money(value: Decimal) -> str:
    return f"{value:.4f}"


class BookReconstructor:
    def __init__(self) -> None:
        self.books: dict[str, dict[str, dict[Decimal, Decimal]]] = defaultdict(lambda: {"yes": {}, "no": {}})
        self.seqs_by_sid: dict[int, int] = {}

    def apply(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        msg_type = payload.get("type")
        msg = payload.get("msg") if isinstance(payload.get("msg"), dict) else {}
        ticker = msg.get("market_ticker") or msg.get("ticker")
        if not ticker:
            return None
        seq = payload.get("seq")
        sid = payload.get("sid")
        if isinstance(seq, int) and isinstance(sid, int):
            previous_seq = self.seqs_by_sid.get(sid)
            self.seqs_by_sid[sid] = seq
        else:
            previous_seq = None

        if msg_type == "orderbook_snapshot":
            self.books[ticker] = {"yes": {}, "no": {}}
            for side, keys in (
                ("yes", ("yes_dollars_fp", "yes_dollars")),
                ("no", ("no_dollars_fp", "no_dollars")),
            ):
                levels = []
                for key in keys:
                    if isinstance(msg.get(key), list):
                        levels = msg[key]
                        break
                self.books[ticker][side] = self._levels_to_dict(levels)
            return self.snapshot(ticker, "orderbook_snapshot", seq, previous_seq, sid)

        if msg_type == "orderbook_delta":
            side = str(msg.get("side") or msg.get("book_side") or "").lower()
            if side not in {"yes", "no"}:
                return None
            price = decimal_or_zero(msg.get("price_dollars") or msg.get("price"))
            delta = decimal_or_zero(msg.get("delta_fp") or msg.get("delta") or msg.get("count_delta_fp"))
            old = self.books[ticker][side].get(price, Decimal("0"))
            new = old + delta
            if new <= 0:
                self.books[ticker][side].pop(price, None)
            else:
                self.books[ticker][side][price] = new
            out = self.snapshot(ticker, "orderbook_delta", seq, previous_seq, sid)
            out["delta"] = {"side": side, "price": money(price), "delta_fp": str(delta), "old_fp": str(old), "new_fp": str(max(new, Decimal("0")))}
            return out

        return None

    @staticmethod
    def _levels_to_dict(levels: list[Any]) -> dict[Decimal, Decimal]:
        out: dict[Decimal, Decimal] = {}
        for level in levels:
            if not isinstance(level, list) or len(level) < 2:
                continue
            price = decimal_or_zero(level[0])
            size = decimal_or_zero(level[1])
            if size > 0:
                out[price] = size
        return out

    def snapshot(self, ticker: str, reason: str, seq: int | None, previous_seq: int | None, sid: int | None) -> dict[str, Any]:
        book = self.books[ticker]
        yes_bid_levels = sorted(book["yes"].items(), key=lambda item: item[0], reverse=True)
        no_bid_levels = sorted(book["no"].items(), key=lambda item: item[0], reverse=True)
        yes_ask_levels = [(Decimal("1") - price, size) for price, size in no_bid_levels]
        no_ask_levels = [(Decimal("1") - price, size) for price, size in yes_bid_levels]
        yes_ask_levels.sort(key=lambda item: item[0])
        no_ask_levels.sort(key=lambda item: item[0])
        return {
            "type": "reconstructed_book",
            "reason": reason,
            "ticker": ticker,
            "sid": sid,
            "seq": seq,
            "previous_seq": previous_seq,
            "sequence_gap": bool(isinstance(seq, int) and isinstance(previous_seq, int) and seq != previous_seq + 1),
            "best": {
                "yes_bid": self._level(yes_bid_levels, 0),
                "yes_ask": self._level(yes_ask_levels, 0),
                "no_bid": self._level(no_bid_levels, 0),
                "no_ask": self._level(no_ask_levels, 0),
            },
            "depth": {
                "buy_yes": self._depth(yes_ask_levels),
                "sell_yes": self._depth(yes_bid_levels),
                "buy_no": self._depth(no_ask_levels),
                "sell_no": self._depth(no_bid_levels),
            },
            "level_counts": {"yes_bid": len(yes_bid_levels), "no_bid": len(no_bid_levels)},
        }

    @staticmethod
    def _level(levels: list[tuple[Decimal, Decimal]], index: int) -> dict[str, str] | None:
        if len(levels) <= index:
            return None
        price, size = levels[index]
        return {"price": money(price), "size_fp": str(size), "premium_dollars": str(price * size)}

    @staticmethod
    def _depth(levels: list[tuple[Decimal, Decimal]]) -> dict[str, Any]:
        bands = [Decimal("0.00"), Decimal("0.01"), Decimal("0.02"), Decimal("0.05"), Decimal("0.10")]
        out: dict[str, Any] = {}
        if not levels:
            for band in bands:
                out[f"within_{money(band)}"] = {"contracts": "0", "premium_dollars": "0", "worst_price": None}
            return out
        best = levels[0][0]
        for band in bands:
            contracts = Decimal("0")
            premium = Decimal("0")
            worst: Decimal | None = None
            for price, size in levels:
                if price <= best + band:
                    contracts += size
                    premium += price * size
                    worst = price
            out[f"within_{money(band)}"] = {
                "contracts": str(contracts),
                "premium_dollars": str(premium),
                "worst_price": money(worst) if worst is not None else None,
            }
        return out


def write_jsonl(handle: Any, payload: dict[str, Any]) -> None:
    handle.write(json.dumps(payload, separators=(",", ":"), default=str) + "\n")
    handle.flush()


async def run(args: argparse.Namespace) -> None:
    load_env_file(args.config)
    key_id = os.environ["KALSHI_KEY_ID"]
    private_key = load_private_key(Path(os.environ["KALSHI_PRIVATE_KEY_PATH"]))
    timestamp_ms = str(int(time.time() * 1000))
    headers = {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
        "KALSHI-ACCESS-SIGNATURE": sign_request(private_key, timestamp_ms, "GET", WS_SIGN_PATH),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.output_dir / "kalshi_ws_raw.jsonl"
    recon_path = args.output_dir / "kalshi_ws_reconstructed_books.jsonl"
    manifest_path = args.output_dir / "manifest.json"
    manifest = {
        "started_at": now_iso(),
        "ws_url": args.ws_url,
        "tickers": args.ticker,
        "listen_ms": args.listen_ms,
        "channels": args.channels,
        "raw_path": str(raw_path),
        "reconstructed_path": str(recon_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    reconstructor = BookReconstructor()
    channels = [item.strip() for item in args.channels.split(",") if item.strip()]
    subscribe = {
        "id": 1,
        "cmd": "subscribe",
        "params": {
            "channels": channels,
            "market_tickers": args.ticker,
            "use_yes_price": False,
        },
    }

    started = monotonic_ms()
    async with await connect_with_headers(args.ws_url, headers, args.timeout) as websocket:
        await websocket.send(json.dumps(subscribe, separators=(",", ":")))
        with raw_path.open("a", encoding="utf-8") as raw_out, recon_path.open("a", encoding="utf-8") as recon_out:
            write_jsonl(raw_out, {"type": "recorder_started", **manifest})
            write_jsonl(recon_out, {"type": "recorder_started", **manifest})
            deadline = started + args.listen_ms
            while not STOP and monotonic_ms() < deadline:
                try:
                    raw_message = await asyncio.wait_for(websocket.recv(), timeout=max((deadline - monotonic_ms()) / 1000, 0.1))
                except asyncio.TimeoutError:
                    break
                arrival_wall = wall_ms()
                arrival_elapsed = monotonic_ms() - started
                try:
                    payload = json.loads(raw_message)
                except json.JSONDecodeError:
                    payload = {"type": "non_json", "raw": str(raw_message)[:1000]}
                raw_item = {
                    "arrival_wall_ms": arrival_wall,
                    "arrival_elapsed_ms": arrival_elapsed,
                    "raw_bytes": len(raw_message),
                    "payload": payload,
                }
                write_jsonl(raw_out, raw_item)
                book_event = reconstructor.apply(payload)
                if book_event is not None:
                    book_event["arrival_wall_ms"] = arrival_wall
                    book_event["arrival_elapsed_ms"] = arrival_elapsed
                    write_jsonl(recon_out, book_event)

            finished = {"type": "recorder_finished", "finished_at": now_iso(), "elapsed_ms": monotonic_ms() - started}
            write_jsonl(raw_out, finished)
            write_jsonl(recon_out, finished)
    manifest["finished_at"] = now_iso()
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--ws-url", default=DEFAULT_WS_URL)
    parser.add_argument("--ticker", action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--channels", default="orderbook_delta,ticker,trade")
    parser.add_argument("--listen-ms", type=int, default=14_400_000)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    asyncio.run(run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
