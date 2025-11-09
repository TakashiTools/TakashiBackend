"""
All-Exchanges Large Trades Aggregator

Streams large trade events from multiple exchanges (Binance, Bybit, Hyperliquid)
for a configured set of symbols/coins and publishes normalized events to the
global event bus under topic 'large_trade'.
"""

import asyncio
import json
from typing import List, Optional

import aiohttp
import websockets

from core.logging import get_logger
from core.utils.time import to_utc_datetime
from core.schemas import LargeTrade
from services.event_bus import bus


class AllLargeTradesService:
    """
    Background service for aggregating large trades across exchanges.
    """

    BINANCE_WS_BASE = "wss://fstream.binance.com/ws"
    BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"
    HL_WS_URL = "wss://api.hyperliquid.xyz/ws"

    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._tasks: List[asyncio.Task] = []
        self._running = asyncio.Event()

        # Read symbols and threshold from settings
        from core.config import settings
        self._symbols = settings.symbols_list  # e.g., ["BTCUSDT", "ETHUSDT"]
        self._threshold = float(settings.large_trade_threshold_usd)

    async def start(self) -> None:
        if self._running.is_set():
            return
        self._running.set()
        self._logger.info(
            f"Starting AllLargeTradesService for symbols: {', '.join(self._symbols)} (threshold=${self._threshold:,.0f})"
        )

        # Launch per-exchange tasks
        # Binance: one WS per symbol (aggTrade)
        for sym in self._symbols:
            self._tasks.append(asyncio.create_task(self._binance_symbol_loop(sym), name=f"lt_binance_{sym}"))

        # Bybit: one WS with multiple topic subscriptions
        self._tasks.append(asyncio.create_task(self._bybit_loop(), name="lt_bybit"))

        # Hyperliquid: one WS with multiple coin subscriptions
        self._tasks.append(asyncio.create_task(self._hyperliquid_loop(), name="lt_hyperliquid"))

    async def stop(self) -> None:
        if not self._running.is_set():
            return
        self._logger.info("Stopping AllLargeTradesService...")
        self._running.clear()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    # ============================================
    # Binance (aggTrade per symbol)
    # ============================================
    async def _binance_symbol_loop(self, symbol: str) -> None:
        stream = f"{symbol.lower()}@aggTrade"
        url = f"{self.BINANCE_WS_BASE}/{stream}"
        while self._running.is_set():
            try:
                async with websockets.connect(url) as ws:
                    self._logger.info(f"[Binance] Connected large trade stream: {symbol}")
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if msg.get("e") != "aggTrade":
                            continue
                        try:
                            price = float(msg.get("p", 0))
                            qty = float(msg.get("q", 0))
                            value = price * qty
                            if value < self._threshold:
                                continue
                            is_buyer_maker = bool(msg.get("m", False))
                            side = "sell" if is_buyer_maker else "buy"
                            lt = LargeTrade(
                                exchange="binance",
                                symbol=symbol.upper(),
                                side=side,
                                price=price,
                                quantity=qty,
                                value=value,
                                is_buyer_maker=is_buyer_maker,
                                timestamp=to_utc_datetime(msg.get("T")),
                            )
                            await bus.publish("large_trade", {"type": "large_trade", **lt.model_dump(mode="json")})
                        except Exception:
                            continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"[Binance] Large trade stream error ({symbol}): {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    # ============================================
    # Bybit (publicTrade.{symbol})
    # ============================================
    async def _bybit_loop(self) -> None:
        topics = [f"publicTrade.{sym}" for sym in self._symbols]
        batch_size = 100
        while self._running.is_set():
            try:
                async with websockets.connect(self.BYBIT_WS_URL) as ws:
                    self._logger.info(f"[Bybit] Connected trades stream. Subscribing to {len(topics)} topics...")
                    for i in range(0, len(topics), batch_size):
                        batch = topics[i : i + batch_size]
                        sub = {"op": "subscribe", "args": batch}
                        await ws.send(json.dumps(sub))
                        await asyncio.sleep(0.05)
                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        topic = data.get("topic", "")
                        if not topic.startswith("publicTrade.") or "data" not in data:
                            continue
                        sym = topic.replace("publicTrade.", "") or ""
                        for t in data.get("data", []):
                            try:
                                price = float(t.get("p", 0))
                                qty = float(t.get("v", 0))
                                value = price * qty
                                if value < self._threshold:
                                    continue
                                lt = LargeTrade(
                                    exchange="bybit",
                                    symbol=sym.upper(),
                                    side=str(t.get("S", "")).lower(),
                                    price=price,
                                    quantity=qty,
                                    value=value,
                                    is_buyer_maker=False,
                                    timestamp=to_utc_datetime(int(t.get("T")) if t.get("T") is not None else 0),
                                )
                                await bus.publish("large_trade", {"type": "large_trade", **lt.model_dump(mode="json")})
                            except Exception:
                                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"[Bybit] Large trade stream error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    # ============================================
    # Hyperliquid (trades per coin)
    # ============================================
    def _to_hl_coin(self, symbol: str) -> str:
        s = symbol.upper()
        for suf in ["USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP"]:
            if s.endswith(suf):
                return s[: -len(suf)]
        return s

    async def _hyperliquid_loop(self) -> None:
        coins = [self._to_hl_coin(s) for s in self._symbols]
        subs = [{"method": "subscribe", "subscription": {"type": "trades", "coin": c}} for c in coins]
        while self._running.is_set():
            try:
                async with websockets.connect(self.HL_WS_URL) as ws:
                    self._logger.info(f"[Hyperliquid] Connected trades stream. Subscribing to {len(subs)} coins...")
                    for s in subs:
                        await ws.send(json.dumps(s))
                        await asyncio.sleep(0.05)
                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if data.get("channel") != "trades":
                            continue
                        for trade in data.get("data", []):
                            try:
                                coin = str(trade.get("coin", "")).upper()
                                price = float(trade.get("px", 0))
                                qty = float(trade.get("sz", 0))
                                value = price * qty
                                if value < self._threshold:
                                    continue
                                # HL doesn't expose is_buyer_maker; set False
                                lt = LargeTrade(
                                    exchange="hyperliquid",
                                    symbol=coin,
                                    side=str(trade.get("side", "")).lower(),
                                    price=price,
                                    quantity=qty,
                                    value=value,
                                    is_buyer_maker=False,
                                    timestamp=to_utc_datetime(int(trade.get("time")) if trade.get("time") is not None else 0),
                                )
                                await bus.publish("large_trade", {"type": "large_trade", **lt.model_dump(mode="json")})
                            except Exception:
                                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"[Hyperliquid] Large trade stream error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)


# Singleton access
_service: Optional[AllLargeTradesService] = None

def get_all_large_trades_service() -> AllLargeTradesService:
    global _service
    if _service is None:
        _service = AllLargeTradesService()
        get_logger(__name__).debug("Created AllLargeTradesService singleton")
    return _service


