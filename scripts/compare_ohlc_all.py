#!/usr/bin/env python3
"""
Compare OHLC across all exchanges in this backend.

What it does:
- Calls GET /{exchange}/ohlc/{symbol}/{interval}?limit=N for:
    - binance (default: BTCUSDT)
    - bybit (default:   BTCUSDT)
    - hyperliquid (default: BTC)
- Validates response shape and basic OHLC consistency
- Prints a summary of the latest candle per exchange
- Compares last closes across venues (price spread in bps)
- Checks direction agreement (close > open vs close < open)

Usage:
  python scripts/compare_ohlc_all.py --interval 5m --limit 100
  python scripts/compare_ohlc_all.py --host 127.0.0.1 --port 8000 --interval 1h
  python scripts/compare_ohlc_all.py --binance-symbol BTCUSDT --bybit-symbol BTCUSDT --hyperliquid-symbol BTC
"""

import argparse
import sys
from typing import Any, Dict, List, Optional, Tuple

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
    p = argparse.ArgumentParser(description="Compare OHLC data across exchanges.")
    p.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    p.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    p.add_argument("--interval", default="5m", help="Interval (e.g., 1m, 5m, 1h, 4h, 1d)")
    p.add_argument("--limit", type=int, default=100, help="Number of candles to request")
    p.add_argument("--binance-symbol", default="BTCUSDT", help="Binance symbol (default: BTCUSDT)")
    p.add_argument("--bybit-symbol", default="BTCUSDT", help="Bybit symbol (default: BTCUSDT)")
    p.add_argument("--hyperliquid-symbol", default="BTC", help="Hyperliquid coin (default: BTC)")
    p.add_argument("--tolerance-bps", type=float, default=50.0, help="Allowed spread between venues (bps)")
    p.add_argument("--print-sample", type=int, default=0, help="Print first N items per exchange")
    return p.parse_args()


def is_number(x: Any) -> bool:
    return isinstance(x, (int, float))


def validate_item(item: dict, interval: str) -> Tuple[bool, str]:
    for f in REQUIRED_FIELDS:
        if f not in item:
            return False, f"missing field: {f}"
    if item["exchange"] != item["exchange"].lower():
        return False, "exchange should be lowercase"
    if item["symbol"] != item["symbol"].upper():
        return False, "symbol should be uppercase"
    if item["interval"] != interval:
        return False, f"interval mismatch: expected {interval}, got {item['interval']}"
    if not all(is_number(item[k]) for k in ("open", "high", "low", "close", "volume", "quote_volume")):
        return False, "numeric fields must be numbers"
    if not isinstance(item["trades_count"], int):
        return False, "trades_count must be int"
    if not isinstance(item["is_closed"], bool):
        return False, "is_closed must be bool"
    try:
        dateparser.isoparse(item["timestamp"])
    except Exception:
        return False, f"invalid timestamp: {item['timestamp']}"
    # Logical OHLC checks
    high, low = float(item["high"]), float(item["low"])
    opn, cls = float(item["open"]), float(item["close"])
    if high < low:
        return False, "high < low"
    if high < opn or high < cls:
        return False, "high must be >= open/close"
    if low > opn or low > cls:
        return False, "low must be <= open/close"
    if any(float(item[k]) < 0 for k in ("open", "high", "low", "close", "volume", "quote_volume")):
        return False, "negative values found"
    if item["is_closed"] is not True:
        return False, "historical candle is_closed should be True"
    if item["trades_count"] < 0:
        return False, "trades_count negative"
    return True, ""


def validate_series(items: List[dict], interval: str) -> Tuple[bool, str]:
    if not isinstance(items, list):
        return False, "response is not a list"
    if not items:
        return False, "empty list"
    for idx, it in enumerate(items):
        ok, msg = validate_item(it, interval)
        if not ok:
            return False, f"item {idx}: {msg}"
    # Monotonic timestamps
    times = [dateparser.isoparse(it["timestamp"]) for it in items]
    for i in range(1, len(times)):
        if times[i] < times[i - 1]:
            return False, f"timestamps not monotonic at {i}"
    return True, ""


def fetch_ohlc(base: str, exchange: str, symbol: str, interval: str, limit: int) -> List[dict]:
    url = f"{base}/{exchange}/ohlc/{symbol}/{interval}?limit={limit}"
    r = httpx.get(url, timeout=30.0)
    if r.status_code != 200:
        raise RuntimeError(f"{exchange} HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a - b) / b * 100.0


def main() -> int:
    args = parse_args()
    base = f"http://{args.host}:{args.port}"

    targets = [
        ("binance", args.binance_symbol),
        ("bybit", args.bybit_symbol),
        ("hyperliquid", args.hyperliquid_symbol),
    ]

    results: Dict[str, List[dict]] = {}
    latest: Dict[str, dict] = {}
    errors: Dict[str, str] = {}

    # Fetch and validate
    for ex, sym in targets:
        try:
            data = fetch_ohlc(base, ex, sym, args.interval, args.limit)
            ok, msg = validate_series(data, args.interval)
            if not ok:
                errors[ex] = msg
                continue
            results[ex] = data
            latest[ex] = max(data, key=lambda d: dateparser.isoparse(d["timestamp"]))
        except Exception as e:
            errors[ex] = str(e)

    # Report errors if any
    if errors:
        print("[Errors]")
        for ex, msg in errors.items():
            print(f"  - {ex}: {msg}")
        # Continue if we still have at least 2 exchanges
        if sum(1 for _ in results) < 1:
            return 2

    # Optional sample
    if args.print_sample > 0:
        print(f"\n[Samples per exchange (first {args.print_sample})]")
        for ex, data in results.items():
            print(f"  {ex}:")
            for it in data[: args.print_sample]:
                print(f"    {it}")

    # Per-exchange latest summary
    print("\n[Latest candle per exchange]")
    for ex, it in latest.items():
        opn = float(it["open"])
        cls = float(it["close"])
        direction = "UP " if cls > opn else ("DOWN" if cls < opn else "FLAT")
        change_pct = pct(cls, opn)
        print(
            f"  {ex:<12} ts={it['timestamp']} close={cls:,.2f} "
            f"chg={change_pct:+.3f}% dir={direction} vol={float(it['volume']):,.2f}"
        )

    # Cross-venue spread
    if len(latest) >= 2:
        closes = [float(it["close"]) for it in latest.values()]
        cmin, cmax = min(closes), max(closes)
        mid = (cmin + cmax) / 2.0 if (cmin + cmax) != 0 else 1.0
        spread_bps = (cmax - cmin) / mid * 10_000.0
        ok = spread_bps <= args.tolerance_bps
        status = "OK" if ok else "WARN"
        print(f"\n[Cross-venue spread] min={cmin:,.2f} max={cmax:,.2f} mid={mid:,.2f} spread={spread_bps:.1f} bps -> {status}")
        if not ok:
            print(f"  Spread exceeds tolerance ({args.tolerance_bps} bps).")

        # Direction agreement
        directions = [(float(v["close"]) - float(v["open"])) for v in latest.values()]
        up = sum(1 for d in directions if d > 0)
        down = sum(1 for d in directions if d < 0)
        print(f"[Direction agreement] up={up} down={down} flat={len(directions) - up - down}")

    print("\n[Done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())


