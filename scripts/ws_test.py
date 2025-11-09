#!/usr/bin/env python3
"""
WebSocket test client for:
  - /ws/all/liquidations
  - /ws/oi-vol

Usage examples:
  python scripts/ws_test.py
  python scripts/ws_test.py --host 127.0.0.1 --port 8000 --min-value-usd 10000 --timeframes 5m,15m --duration 600
"""

import asyncio
import argparse
import json
import sys
from typing import Optional

import websockets


async def stream_loop(url: str, name: str, duration: Optional[int] = None) -> None:
    """
    Connect to a WebSocket URL and print incoming messages.
    Reconnects on error with exponential backoff.
    """
    attempt = 0
    end_time = (asyncio.get_running_loop().time() + duration) if duration else None

    while True:
        if end_time is not None and asyncio.get_running_loop().time() >= end_time:
            print(f"[{name}] Duration reached; stopping.")
            return

        try:
            async with websockets.connect(url) as ws:
                attempt = 0
                print(f"[{name}] Connected: {url}")
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=300)
                    try:
                        data = json.loads(msg)
                    except Exception:
                        data = msg
                    print(f"[{name}] {data}")
        except asyncio.TimeoutError:
            print(f"[{name}] No messages for 300s; reconnecting...")
        except Exception as e:
            attempt += 1
            backoff = min(2 ** (attempt - 1), 30)
            print(f"[{name}] Disconnected/error ({e}); reconnecting in {backoff}s...")
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                return


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test WS streams: all-liquidations and OI/Vol spikes")
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--min-value-usd", type=float, default=10000.0, help="Min USD value for all-liquidations")
    parser.add_argument("--timeframes", default="5m,15m,1h", help="Comma-separated TFs for OI/Vol (e.g., 5m,15m)")
    parser.add_argument("--duration", type=int, default=0, help="Seconds to run (0 = run indefinitely)")
    args = parser.parse_args()

    base = f"ws://{args.host}:{args.port}"
    liq_url = f"{base}/ws/all/liquidations?min_value_usd={args.min_value_usd}"
    oivol_url = f"{base}/ws/oi-vol?timeframes={args.timeframes}"
    duration = args.duration if args.duration and args.duration > 0 else None

    print(f"[Info] Connecting to:\n  - {liq_url}\n  - {oivol_url}\n")

    await asyncio.gather(
        stream_loop(liq_url, "ALL-LIQ", duration),
        stream_loop(oivol_url, "OI-VOL", duration),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Info] Interrupted. Bye.")
        sys.exit(0)


