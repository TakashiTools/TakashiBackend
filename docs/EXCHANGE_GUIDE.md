# Guide: Adding a New Exchange Connector

This document explains **how to add a new exchange** (e.g., Bybit, OKX, Kraken) to the modular backend infrastructure.  
The backend is built to make this process simple, consistent, and safe — following the same pattern used by Binance.

---

## Architecture Overview

Every exchange lives in its own folder under `exchanges/`.  
Each folder contains **two modules only**:

```
exchanges/
└── {exchange_name}/
    ├── api_client.py      # Handles REST requests (historical data, snapshots)
    └── ws_client.py       # Handles WebSocket streams (live data)
```

No other files (like `exchange.py`) are needed — logic for orchestration, schema normalization, and exchange registration lives in the **core layer**.

---

## 🧠 Core Principles

1. **Each exchange must comply with the ExchangeInterface.**  
   This means implementing the methods defined in `core/exchange_interface.py` — via its `api_client` and `ws_client`.

2. **All outputs must use normalized schemas.**  
   Every REST or WS response must be converted into one of the Pydantic models from `core/schemas.py`.

3. **No hardcoded settings.**  
   Use `.env` for URLs, rate limits, and other configuration values.

4. **All I/O must be async.**  
   Both REST and WS clients must use `aiohttp` and `asyncio` for concurrency.

---

## 🪜 Step-by-Step: Adding a New Exchange

### **Step 1: Create a Folder**

```
exchanges/
└── bybit/
    ├── api_client.py
    └── ws_client.py
```

---

### **Step 2: Implement REST Client** (`api_client.py`)

Handles **historical and snapshot data**.

**Template:**

```python
# exchanges/bybit/api_client.py
import aiohttp
from core.schemas import OHLC, FundingRate, OpenInterest
from core.utils.time import to_utc_datetime
from core.logging import logger

class BybitAPIClient:
    BASE_URL = "https://api.bybit.com"

    async def get_ohlc(self, symbol: str, interval: str, limit: int = 500):
        url = f"{self.BASE_URL}/v5/market/kline"
        params = {"symbol": symbol, "interval": interval, "limit": limit}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()

        candles = []
        for c in data["result"]["list"]:
            candles.append(
                OHLC(
                    exchange="bybit",
                    symbol=symbol,
                    interval=interval,
                    timestamp=to_utc_datetime(int(c[0])),
                    open=float(c[1]),
                    high=float(c[2]),
                    low=float(c[3]),
                    close=float(c[4]),
                    volume=float(c[5]),
                    is_closed=True,
                )
            )
        logger.info(f"Fetched {len(candles)} candles for {symbol} ({interval})")
        return candles
```

**Responsibilities:**
- Fetch raw data via REST
- Parse fields into normalized `OHLC`, `FundingRate`, etc.
- Return clean, typed Python objects

---

### **Step 3: Implement WebSocket Client** (`ws_client.py`)

Handles **real-time data** streams (candles, trades, liquidations).

**Template:**

```python
# exchanges/bybit/ws_client.py
import asyncio
import websockets
import json
from core.schemas import OHLC, LargeTrade, Liquidation
from core.utils.time import to_utc_datetime
from core.logging import logger

class BybitWSClient:
    BASE_URL = "wss://stream.bybit.com/v5/public/linear"

    async def stream_ohlc(self, symbol: str, interval: str):
        stream_name = f"kline.{interval}.{symbol}"
        async with websockets.connect(self.BASE_URL) as ws:
            await ws.send(json.dumps({"op": "subscribe", "args": [stream_name]}))
            logger.info(f"Subscribed to {stream_name}")

            async for msg in ws:
                data = json.loads(msg)
                if "data" not in data:
                    continue

                d = data["data"]
                yield OHLC(
                    exchange="bybit",
                    symbol=symbol,
                    interval=interval,
                    timestamp=to_utc_datetime(int(d["start"] * 1000)),
                    open=float(d["open"]),
                    high=float(d["high"]),
                    low=float(d["low"]),
                    close=float(d["close"]),
                    volume=float(d["volume"]),
                    is_closed=d["confirm"],
                )
```

**Responsibilities:**
- Maintain async WebSocket connection
- Reconnect gracefully if connection drops
- Yield normalized data continuously

---

### **Step 4: Register Exchange in Manager**

Open `core/exchange_manager.py` and add your new exchange to the registry:

```python
from exchanges.bybit.api_client import BybitAPIClient
from exchanges.bybit.ws_client import BybitWSClient

self.exchanges["bybit"] = {
    "api": BybitAPIClient(),
    "ws": BybitWSClient(),
}
```

Once registered, your API and WS routes will automatically work for Bybit just like Binance.

---

## Example Field Mapping — Bybit → Normalized Schema

| Normalized Field | Bybit Field | Notes |
|------------------|-------------|-------|
| `timestamp` | `start` | in seconds → convert to UTC ms |
| `open` | `open` | string → float |
| `high` | `high` | string → float |
| `low` | `low` | string → float |
| `close` | `close` | string → float |
| `volume` | `volume` | string → float |
| `is_closed` | `confirm` | bool |
| `exchange` | `"bybit"` | constant |

This ensures consistent schema output across all connectors.

---

## Step 5: Add Integration Tests

Create `tests/integration/test_bybit.py`

```python
import pytest
import asyncio
from exchanges.bybit.api_client import BybitAPIClient

@pytest.mark.asyncio
async def test_get_ohlc():
    client = BybitAPIClient()
    candles = await client.get_ohlc("BTCUSDT", "1h", limit=5)
    assert len(candles) > 0
    assert candles[0].exchange == "bybit"
    assert candles[0].symbol == "BTCUSDT"
```

Confirms normalization works and API connectivity is healthy.

---

## Merge Checklist

Before merging a new exchange connector:

| Check | Status |
|--------|--------|
| Folder structure matches template | Yes |
| All data returned as normalized schemas | Yes |
| No blocking or sync code | Yes |
| Uses aiohttp (REST) and websockets (WS) | Yes |
| Configurable via `.env` | Yes |
| Integration tests pass | Yes |
| Logs appear under correct exchange name | Yes |

---

## Common Pitfalls

| Issue | Cause | Fix |
|--------|--------|-----|
| Wrong timestamp | Exchange uses seconds not ms | Use `to_utc_datetime()` |
| Invalid intervals | Exchange uses `60` instead of `1m` | Map intervals manually |
| Empty volume | No trades in candle | Allow `0.0` in validators |
| Connection drops | WS timeout | Add reconnect loop or retry policy |

---

## 🧭 Summary

Adding a new exchange is simple:
1. Create the folder (`exchanges/{exchange}/`)  
2. Implement async REST + WS clients  
3. Normalize all outputs to shared schemas  
4. Register in `ExchangeManager`  
5. Write a quick integration test  

You’ll have a **new, production-ready exchange connector** integrated in under an hour — fully consistent with the system architecture.
