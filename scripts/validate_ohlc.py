#!/usr/bin/env python3
"""
Validate the OHLC endpoint of the server.

Checks performed:
- HTTP 200 and JSON array
- Required fields present with correct types
- interval matches request; exchange is lowercase; symbol uppercase
- Logical OHLC consistency (high/low vs open/close; non-negative values)
- is_closed is True for historical data
- Monotonic non-decreasing timestamps (oldest → newest)

Usage examples:
  python scripts/validate_ohlc.py --exchange binance --symbol BTCUSDT --interval 1h --limit 100
  python scripts/validate_ohlc.py --host 127.0.0.1 --port 8000 --exchange hyperliquid --symbol BTC --interval 1m --limit 50
"""

import argparse
import sys
from typing import Any, List, Tuple

import httpx
from dateutil import parser as dateparser


REQUIRED_FIELDS = [
    "exchange",
    "symbol",
    "timestamp",
    "interval",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trades_count",
    "is_closed",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate OHLC endpoint response.")
    p.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    p.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    p.add_argument("--exchange", required=True, help="Exchange name (e.g., binance, bybit, hyperliquid)")
    p.add_argument("--symbol", required=True, help="Symbol (e.g., BTCUSDT for Binance/Bybit, BTC for Hyperliquid)")
    p.add_argument("--interval", required=True, help="Interval (e.g., 1m, 5m, 1h, 4h, 1d)")
    p.add_argument("--limit", type=int, default=100, help="Number of candles to request")
    p.add_argument("--allow-empty", action="store_true", help="Do not fail if endpoint returns empty list")
    p.add_argument("--print-sample", type=int, default=0, help="Print first N items for visual inspection")
    return p.parse_args()


def is_number(x: Any) -> bool:
    return isinstance(x, (int, float))


def validate_item(item: dict, req_exchange: str, req_symbol: str, req_interval: str) -> Tuple[bool, str]:
    # Required fields
    for f in REQUIRED_FIELDS:
        if f not in item:
            return False, f"missing field: {f}"

    # Types
    if not isinstance(item["exchange"], str):
        return False, "exchange must be string"
    if not isinstance(item["symbol"], str):
        return False, "symbol must be string"
    if not isinstance(item["interval"], str):
        return False, "interval must be string"
    if not is_number(item["open"]) or not is_number(item["high"]) or not is_number(item["low"]) or not is_number(item["close"]):
        return False, "OHLC must be numbers"
    if not is_number(item["volume"]) or not is_number(item["quote_volume"]):
        return False, "volume/quote_volume must be numbers"
    if not isinstance(item["trades_count"], int):
        return False, "trades_count must be int"
    if not isinstance(item["is_closed"], bool):
        return False, "is_closed must be bool"

    # Exchange formatting
    if item["exchange"] != item["exchange"].lower():
        return False, "exchange should be lowercase"

    # Symbol formatting (normalize to uppercase)
    if item["symbol"] != item["symbol"].upper():
        return False, "symbol should be uppercase"

    # Interval must match requested
    if item["interval"] != req_interval:
        return False, f"interval mismatch: expected {req_interval}, got {item['interval']}"

    # Parse timestamp
    try:
        dateparser.isoparse(item["timestamp"])
    except Exception:
        return False, f"invalid timestamp: {item['timestamp']}"

    # Logical OHLC constraints
    high = float(item["high"])
    low = float(item["low"])
    opn = float(item["open"])
    cls = float(item["close"])
    vol = float(item["volume"])
    qvol = float(item["quote_volume"])
    if high < low:
        return False, f"high < low ({high} < {low})"
    if high < opn or high < cls:
        return False, f"high must be >= open/close ({high} < {opn}/{cls})"
    if low > opn or low > cls:
        return False, f"low must be <= open/close ({low} > {opn}/{cls})"
    if any(v < 0 for v in (opn, high, low, cls, vol, qvol)):
        return False, "negative values not allowed in OHLC/volume"

    # Historical candles should be closed
    if item["is_closed"] is not True:
        return False, "historical candle is_closed should be True"

    # trades_count non-negative
    if item["trades_count"] < 0:
        return False, "trades_count negative"

    return True, ""


def validate_ordering(items: List[dict]) -> Tuple[bool, str]:
    times = []
    try:
        for it in items:
            times.append(dateparser.isoparse(it["timestamp"]))
    except Exception as e:
        return False, f"timestamp parse failed: {e}"
    # Non-decreasing order (oldest → newest)
    for i in range(1, len(times)):
        if times[i] < times[i - 1]:
            return False, f"timestamps not monotonic at index {i}: {times[i-1]} -> {times[i]}"
    return True, ""


def main() -> int:
    args = parse_args()
    url = f"http://{args.host}:{args.port}/{args.exchange}/ohlc/{args.symbol}/{args.interval}?limit={args.limit}"
    print(f"[Info] Requesting: {url}")

    try:
        resp = httpx.get(url, timeout=30.0)
    except Exception as e:
        print(f"[Error] Request failed: {e}")
        return 2

    if resp.status_code != 200:
        print(f"[Error] HTTP {resp.status_code}: {resp.text[:300]}")
        return 2

    try:
        data = resp.json()
    except Exception as e:
        print(f"[Error] Invalid JSON: {e}")
        return 2

    if not isinstance(data, list):
        print("[Error] Response is not a list")
        return 2

    if not data:
        if args.allow_empty:
            print("[Warn] Empty list (allowed by flag).")
            return 0
        print("[Error] Empty list (use --allow-empty to accept).")
        return 1

    # Validate items
    for idx, item in enumerate(data):
        ok, msg = validate_item(item, args.exchange, args.symbol, args.interval)
        if not ok:
            print(f"[Error] Item {idx} invalid: {msg}")
            return 1

    # Validate time ordering
    ok, msg = validate_ordering(data)
    if not ok:
        print(f"[Error] Ordering check failed: {msg}")
        return 1

    if args.print_sample > 0:
        sample = data[: args.print_sample]
        print(f"[Info] Sample ({len(sample)} of {len(data)}):")
        for it in sample:
            print(it)

    print(f"[OK] Validated {len(data)} OHLC candles for {args.exchange} {args.symbol} {args.interval}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


