"""
Binance OI / Volume Spike Monitor

Periodically fetches Open Interest history and kline quote volume from Binance
for USDT perpetual symbols, computes z-scores, and publishes "oi_spike" events
to the global event bus under topic 'oi_spike' when thresholds are exceeded.
"""

import asyncio
import statistics
from typing import Dict, List, Tuple, Optional

import aiohttp

from core.logging import get_logger
from services.event_bus import bus


class OIVolMonitor:
    """
    Background service for detecting OI/Volume anomalies on Binance.
    """

    EXCHANGE_INFO_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    KLINES_URL = "https://fapi.binance.com/fapi/v1/klines"
    OI_URL = "https://fapi.binance.com/futures/data/openInterestHist"

    TIMEFRAMES = ("5m", "15m", "1h")
    Z_THRESHOLDS = {"5m": 3.0, "15m": 2.5, "1h": 2.0}
    MIN_VOL_USD = {"5m": 100_000, "15m": 250_000, "1h": 1_000_000}
    MIN_OI_USD = {"5m": 500_000, "15m": 1_000_000, "1h": 2_500_000}

    def __init__(self, cycle_sleep_seconds: int = 300, symbols_limit: int = 80) -> None:
        self._logger = get_logger(__name__)
        self._running = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._cycle_sleep = cycle_sleep_seconds
        self._symbols_limit = symbols_limit

    async def start(self) -> None:
        if self._running.is_set():
            return
        self._running.set()
        self._logger.info("Starting OI/Volume monitor...")
        self._task = asyncio.create_task(self._run(), name="oi_vol_monitor")

    async def stop(self) -> None:
        if not self._running.is_set():
            return
        self._logger.info("Stopping OI/Volume monitor...")
        self._running.clear()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(Exception):
                await self._task
            self._task = None

    # ============================================
    # Core Loop
    # ============================================
    async def _run(self) -> None:
        # Ensure main loop started before heavy operations
        await asyncio.sleep(0.1)
        symbols = await self._fetch_symbols()
        symbols = symbols[: self._symbols_limit]
        self._logger.info(f"OI/Vol monitor tracking {len(symbols)} Binance symbols")

        # In-memory ring buffers by symbol/timeframe
        store: Dict[str, Dict[str, Dict[str, List[float]]]] = {
            s: {tf: {"oi": [], "vol": []} for tf in self.TIMEFRAMES} for s in symbols
        }

        while self._running.is_set():
            cycle_start = asyncio.get_running_loop().time()
            try:
                for sym in symbols:
                    for tf in self.TIMEFRAMES:
                        oi_vals = await self._fetch_open_interest(sym, tf, limit=50)
                        vol_vals = await self._fetch_quote_volume(sym, tf, limit=50)
                        if not oi_vals or not vol_vals:
                            continue

                        # Append new values and cap to 100
                        store[sym][tf]["oi"].extend([v for _, v in oi_vals])
                        store[sym][tf]["vol"].extend([v for _, v in vol_vals])
                        store[sym][tf]["oi"] = store[sym][tf]["oi"][-100:]
                        store[sym][tf]["vol"] = store[sym][tf]["vol"][-100:]

                        # Basic guards
                        if (
                            store[sym][tf]["oi"][-1] < self.MIN_OI_USD[tf]
                            or store[sym][tf]["vol"][-1] < self.MIN_VOL_USD[tf]
                        ):
                            continue

                        z_oi = self._compute_z(store[sym][tf]["oi"])
                        z_vol = self._compute_z(store[sym][tf]["vol"])
                        thr = self.Z_THRESHOLDS[tf]
                        if z_oi >= thr or z_vol >= thr:
                            event = {
                                "type": "oi_spike",
                                "exchange": "binance",
                                "symbol": sym,
                                "timeframe": tf,
                                "z_oi": round(z_oi, 2),
                                "z_vol": round(z_vol, 2),
                                "confirmed": bool(z_oi >= thr and z_vol >= thr),
                            }
                            await bus.publish("oi_spike", event)
                # Gentle pacing inside the loop to avoid rate limits
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"OI/Vol monitor cycle error: {e}")
            finally:
                elapsed = asyncio.get_running_loop().time() - cycle_start
                self._logger.info(f"OI/Vol monitor cycle finished in {elapsed:.1f}s; sleeping {self._cycle_sleep}s")
                await asyncio.sleep(self._cycle_sleep)

    # ============================================
    # Fetchers
    # ============================================
    async def _fetch_symbols(self) -> List[str]:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(self.EXCHANGE_INFO_URL) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    symbols = [
                        s["symbol"]
                        for s in data.get("symbols", [])
                        if (
                            isinstance(s, dict)
                            and s.get("contractType") == "PERPETUAL"
                            and s.get("status") == "TRADING"
                            and s.get("quoteAsset") == "USDT"
                        )
                    ]
                    return symbols
        except Exception:
            return []

    async def _fetch_open_interest(self, symbol: str, period: str, limit: int = 50) -> List[Tuple[int, float]]:
        params = {"symbol": symbol, "period": period, "limit": limit}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(self.OI_URL, params=params) as resp:
                    if resp.status != 200:
                        return []
                    payload = await resp.json()
                    return [
                        (int(x["timestamp"]), float(x["sumOpenInterestValue"]))
                        for x in payload
                        if "timestamp" in x and "sumOpenInterestValue" in x
                    ]
        except Exception:
            return []

    async def _fetch_quote_volume(self, symbol: str, interval: str, limit: int = 50) -> List[Tuple[int, float]]:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(self.KLINES_URL, params=params) as resp:
                    if resp.status != 200:
                        return []
                    kl = await resp.json()
                    # Return (close time, quote volume)
                    return [(int(k[6]), float(k[7])) for k in kl if isinstance(k, list) and len(k) >= 8]
        except Exception:
            return []

    # ============================================
    # Math
    # ============================================
    def _compute_z(self, values: List[float]) -> float:
        if len(values) < 5:
            return 0.0
        try:
            mean = statistics.mean(values)
            stdev = statistics.stdev(values)
            return (values[-1] - mean) / stdev if stdev > 0 else 0.0
        except Exception:
            return 0.0


# Singleton service instance (created on demand)
import contextlib  # placed here to avoid top-level import until needed

_oi_vol_monitor: Optional[OIVolMonitor] = None

def get_oi_vol_monitor() -> OIVolMonitor:
    global _oi_vol_monitor
    if _oi_vol_monitor is None:
        _oi_vol_monitor = OIVolMonitor()
    return _oi_vol_monitor


