"""
All-Exchanges Liquidations Aggregator

Streams liquidation events from multiple exchanges and publishes normalized
events to the global event bus under topic 'liquidation'.

Implemented sources:
    - Binance (all-market): wss://fstream.binance.com/ws/!forceOrder@arr
    - OKX (SWAP liquidation orders): wss://ws.okx.com:8443/ws/v5/public

Notes:
    - Hyperliquid liquidation detection via trades has been disabled/removed.
    - Bybit "all liquidations" requires subscribing per-symbol (not included).
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import aiohttp
import websockets

from core.logging import get_logger
from core.utils.time import to_utc_datetime
from core.schemas import Liquidation
from services.event_bus import bus


class AllLiquidationsService:
    """
    Background service managing multiple exchange liquidation streams.

    Use start() to begin streaming and stop() to cancel all tasks.
    """

    BINANCE_URL = "wss://fstream.binance.com/ws/!forceOrder@arr"
    OKX_URL = "wss://ws.okx.com:8443/ws/v5/public"
    BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"
    BYBIT_SYMBOLS_URL = "https://api.bybit.com/v5/market/instruments-info?category=linear"

    def __init__(self, min_value_usd: float = 5_000.0) -> None:
        self._logger = get_logger(__name__)
        self._tasks: List[asyncio.Task] = []
        self._running = asyncio.Event()
        self._min_value_usd = float(min_value_usd)

    async def start(self) -> None:
        if self._running.is_set():
            return
        self._running.set()
        self._logger.info("Starting AllLiquidationsService...")
        self._tasks = [
            asyncio.create_task(self._binance_loop(), name="liq_binance"),
            asyncio.create_task(self._okx_loop(), name="liq_okx"),
            asyncio.create_task(self._bybit_loop(), name="liq_bybit"),
        ]

    async def stop(self) -> None:
        if not self._running.is_set():
            return
        self._logger.info("Stopping AllLiquidationsService...")
        self._running.clear()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    # ============================================
    # Binance (All Market Liquidations)
    # ============================================
    async def _binance_loop(self) -> None:
        while self._running.is_set():
            try:
                async with websockets.connect(self.BINANCE_URL) as ws:
                    self._logger.info("[Binance] Connected to all-market liquidation stream")
                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        # Binance may send a list of events or a single dict
                        events = data if isinstance(data, list) else [data]
                        for ev in events:
                            order = ev.get("o", {})
                            if not order:
                                continue
                            symbol = order.get("s")
                            side = (order.get("S") or "").lower()
                            price = float(order.get("p") or 0)
                            qty = float(order.get("q") or 0)
                            ts = order.get("T")
                            value = price * qty
                            if value < self._min_value_usd:
                                continue

                            model = Liquidation(
                                exchange="binance",
                                symbol=symbol or "",
                                side=side if side in ("buy", "sell") else "sell",
                                price=price,
                                quantity=qty,
                                value=value,
                                timestamp=to_utc_datetime(int(ts)) if ts is not None else to_utc_datetime(0),
                            )
                            await bus.publish("liquidation", {"type": "liquidation", **model.model_dump(mode="json")})
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"[Binance] All-liq stream error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    # ============================================
    # OKX (Liquidation Orders - SWAP)
    # ============================================
    async def _okx_loop(self) -> None:
        subscribe_msg = {
            "id": "liq_sub_1",
            "op": "subscribe",
            "args": [{"channel": "liquidation-orders", "instType": "SWAP"}],
        }
        while self._running.is_set():
            try:
                async with websockets.connect(self.OKX_URL) as ws:
                    self._logger.info("[OKX] Connected to liquidation stream")
                    await ws.send(json.dumps(subscribe_msg))
                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        if "arg" not in data or "data" not in data:
                            # ping/pong or event ack
                            continue

                        for entry in data.get("data", []):
                            inst = entry.get("instId") or ""
                            details = entry.get("details", [])
                            for d in details:
                                side = (d.get("side") or "").lower()
                                qty_str = d.get("sz")
                                price_str = d.get("bkPx")
                                ts = d.get("ts")
                                try:
                                    qty = float(qty_str or 0)
                                    price = float(price_str or 0)
                                except Exception:
                                    qty, price = 0.0, 0.0
                                value = qty * price
                                if value < self._min_value_usd:
                                    continue

                                model = Liquidation(
                                    exchange="okx",
                                    symbol=inst,
                                    side=side if side in ("buy", "sell") else "sell",
                                    price=price,
                                    quantity=qty,
                                    value=value,
                                    timestamp=to_utc_datetime(int(ts)) if ts is not None else to_utc_datetime(0),
                                )
                                await bus.publish("liquidation", {"type": "liquidation", **model.model_dump(mode="json")})
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"[OKX] Liq stream error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    # ============================================
    # Bybit (All Market Liquidations - per-symbol topics)
    # ============================================
    async def _fetch_bybit_symbols(self) -> List[str]:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(self.BYBIT_SYMBOLS_URL) as resp:
                    if resp.status != 200:
                        return []
                    payload = await resp.json()
                    lst = payload.get("result", {}).get("list", []) or []
                    symbols = [str(item.get("symbol")) for item in lst if item.get("symbol")]
                    return symbols
        except Exception:
            return []

    async def _bybit_loop(self) -> None:
        while self._running.is_set():
            symbols = await self._fetch_bybit_symbols()
            if not symbols:
                self._logger.warning("[Bybit] No symbols fetched; retrying in 30s")
                try:
                    await asyncio.sleep(30)
                except asyncio.CancelledError:
                    break
                continue

            topics = [f"allLiquidation.{sym}" for sym in symbols]
            batch_size = 100
            try:
                async with websockets.connect(self.BYBIT_WS_URL) as ws:
                    self._logger.info(f"[Bybit] Connected to liquidation stream. Subscribing to {len(topics)} topics...")
                    # Subscribe in batches to avoid oversize messages
                    for i in range(0, len(topics), batch_size):
                        batch = topics[i:i + batch_size]
                        sub = {"op": "subscribe", "args": batch}
                        await ws.send(json.dumps(sub))
                        await asyncio.sleep(0.05)

                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        topic = data.get("topic", "")
                        if not topic.startswith("allLiquidation.") or "data" not in data:
                            continue

                        for d in data.get("data", []):
                            try:
                                sym = d.get("s") or topic.replace("allLiquidation.", "")
                                side = (d.get("S") or "").lower()
                                price = float(d.get("p") or 0)
                                qty = float(d.get("v") or 0)
                                ts = d.get("T")
                                value = price * qty
                                if value < self._min_value_usd:
                                    continue
                                model = Liquidation(
                                    exchange="bybit",
                                    symbol=sym,
                                    side=side if side in ("buy", "sell") else "sell",
                                    price=price,
                                    quantity=qty,
                                    value=value,
                                    timestamp=to_utc_datetime(int(ts)) if ts is not None else to_utc_datetime(0),
                                )
                                await bus.publish("liquidation", {"type": "liquidation", **model.model_dump(mode="json")})
                            except Exception:
                                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"[Bybit] Liq stream error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)


# Singleton service instance (created on import)
all_liquidations_service: Optional[AllLiquidationsService] = None

def get_all_liquidations_service(min_value_usd: float = 50_000.0) -> AllLiquidationsService:
    global all_liquidations_service
    if all_liquidations_service is None:
        all_liquidations_service = AllLiquidationsService(min_value_usd=min_value_usd)
    return all_liquidations_service


