# ⚡ Guide: Adding Hyperliquid (HL) Exchange Connector (v2)

This document describes how to integrate **Hyperliquid (HL)** into the modular multi-exchange backend.  
Hyperliquid uses both REST and WebSocket endpoints and fits seamlessly into the current architecture.

---

## 🏗️ Folder Structure

```
exchanges/
└── hyperliquid/
    ├── api_client.py      # REST API implementation (funding, OI, historical candles)
    └── ws_client.py       # WebSocket streams (live candles, trades)
```

---

## 🔌 Overview of Available Data

| Data Type | Source | Endpoint / Subscription | Notes |
|------------|--------|------------------------|-------|
| OHLC (historical) | REST | `{ "type": "candleSnapshot", "req": { "coin": "BTC", "interval": "1m", "startTime": ..., "endTime": ... } }` | Fetches up to ~5000 past candles |
| OHLC (live) | WebSocket | `{ "type": "candle", "coin": "BTC", "interval": "1m" }` | Streams live and recent backfill candles |
| Open Interest | REST | `{ "type": "metaAndAssetCtxs" }` | Includes OI and mark price |
| Funding Rate (historical) | REST | `{ "type": "fundingHistory", "coin": "BTC" }` | Historical funding data |
| Funding Rate (predicted) | REST | `{ "type": "predictedFundings" }` | Predicted next funding |
| Large Trades | WebSocket | `{ "type": "trades", "coin": "BTC" }` | Stream of executed trades |
| Liquidations | ❌ Not Available | — | HL does not provide liquidation events |

---

## 🧠 Core Principles

1. Follow the same modular pattern as Binance — only `api_client.py` and `ws_client.py`.  
2. Normalize all output using schemas from `core/schemas.py`.  
3. Use `aiohttp` for REST and `websockets` for WS connections.  
4. Convert timestamps using `to_utc_datetime()` from `core/utils/time.py`.  
5. Use the unified logger from `core/logging.py`.  

---

## 🧩 REST Client (api_client.py)

Handles **open interest**, **funding rate**, and **historical OHLC** data.

```python
# exchanges/hyperliquid/api_client.py

import aiohttp
from core.schemas import OpenInterest, FundingRate, OHLC
from core.utils.time import to_utc_datetime
from core.logging import logger

class HyperliquidAPIClient:
    BASE_URL = "https://api.hyperliquid.xyz/info"

    async def get_open_interest(self, symbol: str) -> OpenInterest:
        payload = {"type": "metaAndAssetCtxs"}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.BASE_URL, json=payload) as resp:
                data = await resp.json()

        for coin in data["coins"]:
            if coin["name"].upper() == symbol.upper():
                oi = float(coin["openInterest"])
                price = float(coin["markPrice"])
                return OpenInterest(
                    exchange="hyperliquid",
                    symbol=symbol,
                    timestamp=to_utc_datetime(coin["timestamp"]),
                    open_interest=oi,
                    open_interest_value=oi * price,
                )
        logger.warning(f"No OI data for {symbol}")
        return None

    async def get_funding_rate(self, symbol: str) -> FundingRate:
        payload = {"type": "fundingHistory", "coin": symbol.upper()}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.BASE_URL, json=payload) as resp:
                data = await resp.json()

        if not data.get("funding"):
            logger.warning(f"No funding history for {symbol}")
            return None

        latest = data["funding"][-1]
        return FundingRate(
            exchange="hyperliquid",
            symbol=symbol,
            funding_rate=float(latest["fundingRate"]),
            funding_time=to_utc_datetime(latest["time"]),
            next_funding_rate=None,
        )

    async def get_historical_ohlc(self, symbol: str, interval: str, start_time: int, end_time: int):
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": symbol.upper(),
                "interval": interval,
                "startTime": start_time,
                "endTime": end_time,
            },
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.BASE_URL, json=payload) as resp:
                data = await resp.json()

        candles = data.get("candles") or data.get("data") or []
        results = []
        for c in candles:
            results.append(
                OHLC(
                    exchange="hyperliquid",
                    symbol=symbol,
                    interval=interval,
                    timestamp=to_utc_datetime(c["t"]),
                    open=float(c["o"]),
                    high=float(c["h"]),
                    low=float(c["l"]),
                    close=float(c["c"]),
                    volume=float(c["v"]),
                    is_closed=True,
                )
            )
        return results
```

---

## 🌐 WebSocket Client (ws_client.py)

Handles **live candles (OHLC)** and **large trade streams**.

```python
# exchanges/hyperliquid/ws_client.py

import asyncio
import websockets
import json
from core.schemas import OHLC, LargeTrade
from core.utils.time import to_utc_datetime
from core.logging import logger

class HyperliquidWSClient:
    BASE_URL = "wss://api.hyperliquid.xyz/ws"

    async def stream_ohlc(self, symbol: str, interval: str):
        sub = {"type": "candle", "coin": symbol.upper(), "interval": interval}
        async with websockets.connect(self.BASE_URL) as ws:
            await ws.send(json.dumps(sub))
            logger.info(f"Subscribed to {symbol} {interval} candles on Hyperliquid")

            async for msg in ws:
                data = json.loads(msg)
                if "data" not in data:
                    continue

                c = data["data"]
                yield OHLC(
                    exchange="hyperliquid",
                    symbol=symbol,
                    interval=interval,
                    timestamp=to_utc_datetime(c["t"]),
                    open=float(c["o"]),
                    high=float(c["h"]),
                    low=float(c["l"]),
                    close=float(c["c"]),
                    volume=float(c["v"]),
                    is_closed=c.get("closed", True),
                )

    async def stream_trades(self, symbol: str):
        sub = {"type": "trades", "coin": symbol.upper()}
        async with websockets.connect(self.BASE_URL) as ws:
            await ws.send(json.dumps(sub))
            logger.info(f"Subscribed to trades for {symbol}")

            async for msg in ws:
                data = json.loads(msg)
                if "data" not in data:
                    continue

                for trade in data["data"]:
                    yield LargeTrade(
                        exchange="hyperliquid",
                        symbol=symbol,
                        side="buy" if trade["side"] == "B" else "sell",
                        price=float(trade["px"]),
                        quantity=float(trade["sz"]),
                        value=float(trade["px"]) * float(trade["sz"]),
                        is_buyer_maker=trade["side"] == "S",
                        timestamp=to_utc_datetime(trade["time"]),
                    )
```

---

## 🧪 Integration Test Example

**File:** `tests/integration/test_hyperliquid.py`

```python
import pytest
import asyncio
from exchanges.hyperliquid.api_client import HyperliquidAPIClient

@pytest.mark.asyncio
async def test_open_interest():
    client = HyperliquidAPIClient()
    data = await client.get_open_interest("BTC")
    assert data.exchange == "hyperliquid"
    assert data.open_interest > 0

@pytest.mark.asyncio
async def test_funding_rate():
    client = HyperliquidAPIClient()
    data = await client.get_funding_rate("BTC")
    assert data.exchange == "hyperliquid"
    assert isinstance(data.funding_rate, float)

@pytest.mark.asyncio
async def test_historical_ohlc():
    client = HyperliquidAPIClient()
    data = await client.get_historical_ohlc("BTC", "1m", 1720000000000, 1720010000000)
    assert len(data) > 0
    assert all(c.exchange == "hyperliquid" for c in data)
```

---

## ✅ Merge Checklist

| Check | Status |
|--------|--------|
| Folder structure matches template | ✅ |
| REST endpoints implemented | ✅ |
| Historical OHLC implemented (`candleSnapshot`) | ✅ |
| WS streams implemented (candles, trades) | ✅ |
| Data normalized using core schemas | ✅ |
| All timestamps normalized (UTC) | ✅ |
| Integration tests pass | ✅ |
| No blocking code (async only) | ✅ |
| No liquidations (not supported) | ✅ |

---

## ⚠️ Known Limitations (Hyperliquid)

| Feature | Status | Notes |
|----------|--------|-------|
| Liquidation Stream | ❌ Not available |
| Market Depth / Order Book | Partial | Not required yet |
| Trade Stream | ✅ Works well |
| Funding Data | ✅ REST only |
| OHLC Historical | ✅ Limited to ~5000 candles per request |
| OHLC Live | ✅ WS supported |

---

## 🧭 Summary

Hyperliquid now supports both **historical** and **live** OHLC integration through `candleSnapshot` and `candle` respectively.

Steps to add:
1. Create folder: `exchanges/hyperliquid/`
2. Add `api_client.py` and `ws_client.py` using templates above  
3. Register in `ExchangeManager`
4. Run integration tests

You’ll now have unified access to funding, OI, live candles, and limited historical OHLC data directly through your backend.
