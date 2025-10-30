# 📖 Hyperliquid Exchange Connector - Documentation

Complete guide for using the Hyperliquid exchange connector in the itabackend system.

---

## 📑 Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [API Reference](#api-reference)
4. [Testing](#testing)
5. [Examples](#examples)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

The Hyperliquid connector provides unified access to Hyperliquid's perpetual futures exchange through both REST API and WebSocket streams.

### Features

| Feature | REST API | WebSocket | Status |
|---------|----------|-----------|--------|
| Historical OHLC | ✅ | - | `candleSnapshot` |
| Live OHLC | - | ✅ | `candle` subscription |
| Open Interest | ✅ | - | `metaAndAssetCtxs` |
| Funding Rate | ✅ | - | `fundingHistory` |
| Predicted Funding | ✅ | - | `predictedFundings` |
| Trades | - | ✅ | `trades` subscription |
| Liquidations | ❌ | ❌ | Not available on Hyperliquid |

### Key Differences from Other Exchanges

1. **Symbol Format**: Uses coin names (e.g., `BTC`, `ETH`) instead of pairs (e.g., `BTCUSDT`)
2. **HTTP Method**: Uses POST requests with JSON payloads instead of GET with query params
3. **No Liquidations**: Hyperliquid does not expose public liquidation data
4. **Historical Limits**: Historical OHLC limited to ~5000 candles per request

---

## 🚀 Quick Start

### 1. Using ExchangeManager (Recommended)

```python
from core.exchange_manager import ExchangeManager

# Create manager and initialize
manager = ExchangeManager()
await manager.initialize_all()

# Get Hyperliquid exchange
hl = manager.get_exchange("hyperliquid")

# Fetch open interest
oi = await hl.get_open_interest("BTC")
print(f"BTC Open Interest: {oi.open_interest:,.2f}")

# Shutdown when done
await manager.shutdown_all()
```

### 2. Using HyperliquidExchange Directly

```python
from exchanges.hyperliquid import HyperliquidExchange

# Create and initialize
exchange = HyperliquidExchange()
await exchange.initialize()

# Fetch funding rate
fr = await exchange.get_funding_rate("BTC")
print(f"Funding Rate: {fr.funding_rate * 100:.4f}%")

# Shutdown
await exchange.shutdown()
```

### 3. Using API Client Directly (Advanced)

```python
from exchanges.hyperliquid.api_client import HyperliquidAPIClient

async with HyperliquidAPIClient() as client:
    # Fetch historical OHLC
    end_time = current_utc_timestamp(milliseconds=True)
    start_time = end_time - (60 * 60 * 1000)  # 1 hour ago

    candles = await client.get_historical_ohlc("BTC", "1m", start_time, end_time)
    print(f"Fetched {len(candles)} candles")
```

---

## 📚 API Reference

### HyperliquidExchange Class

Main class implementing the `ExchangeInterface`.

#### Properties

```python
exchange.name           # "hyperliquid"
exchange.capabilities   # Dict of supported features
exchange.base_url       # REST API URL
exchange.ws_url         # WebSocket URL
```

#### Methods

##### initialize()
```python
await exchange.initialize()
```
Initialize the exchange connector (creates HTTP session).

##### shutdown()
```python
await exchange.shutdown()
```
Gracefully shutdown the connector and close connections.

##### health_check()
```python
is_healthy = await exchange.health_check()
```
**Returns**: `bool` - True if API is reachable

##### get_ohlc()
```python
ohlc_data = await exchange.get_ohlc(
    symbol="BTC",
    interval="1m",  # "1m", "5m", "15m", "1h", "4h", "1d"
    limit=500,
    start_time=None,  # Optional: milliseconds timestamp
    end_time=None     # Optional: milliseconds timestamp
)
```
**Returns**: `List[OHLC]` - List of candlestick data

**Fields in OHLC**:
- `exchange`: "hyperliquid"
- `symbol`: Trading symbol (e.g., "BTC")
- `interval`: Timeframe (e.g., "1m")
- `timestamp`: UTC datetime of candle open
- `open`, `high`, `low`, `close`: Prices
- `volume`: Trading volume in base asset
- `quote_volume`: Trading volume in quote asset
- `trades_count`: Number of trades
- `is_closed`: Whether candle is finalized

##### get_open_interest()
```python
oi = await exchange.get_open_interest("BTC")
```
**Returns**: `Optional[OpenInterest]` - Current open interest or None

**Fields in OpenInterest**:
- `exchange`: "hyperliquid"
- `symbol`: Trading symbol
- `timestamp`: UTC datetime
- `open_interest`: Total open interest in base asset
- `open_interest_value`: OI value in USD (optional)

##### get_funding_rate()
```python
fr = await exchange.get_funding_rate("BTC")
```
**Returns**: `Optional[FundingRate]` - Latest funding rate or None

**Fields in FundingRate**:
- `exchange`: "hyperliquid"
- `symbol`: Trading symbol
- `timestamp`: UTC datetime
- `funding_rate`: Rate as decimal (0.0001 = 0.01%)
- `funding_time`: When funding was applied
- `next_funding_rate`: Predicted next rate (if available)
- `next_funding_time`: Next funding time (if available)

##### stream_ohlc()
```python
async for candle in exchange.stream_ohlc("BTC", "1m"):
    print(f"Close: ${candle.close:,.2f}")
    if candle.is_closed:
        print("Candle closed!")
```
**Yields**: `OHLC` - Live candlestick updates

**Note**: This is an infinite async generator. Use `break` to stop.

##### stream_large_trades()
```python
async for trade in exchange.stream_large_trades("BTC"):
    print(f"{trade.side}: ${trade.value:,.2f}")
```
**Yields**: `LargeTrade` - Real-time trade executions

**Fields in LargeTrade**:
- `exchange`: "hyperliquid"
- `symbol`: Trading symbol
- `side`: "buy" or "sell"
- `price`: Execution price
- `quantity`: Trade size in base asset
- `value`: Trade value (price × quantity)
- `is_buyer_maker`: True if buyer was maker
- `timestamp`: UTC datetime

##### stream_liquidations()
```python
# ⚠️ NOT SUPPORTED
await exchange.stream_liquidations("BTC")  # Raises NotImplementedError
```
**Raises**: `NotImplementedError` - Hyperliquid doesn't provide liquidation data

---

### HyperliquidAPIClient Class

Low-level REST API client.

#### Methods

##### get_historical_ohlc()
```python
async with HyperliquidAPIClient() as client:
    candles = await client.get_historical_ohlc(
        symbol="BTC",
        interval="1m",
        start_time=1720000000000,  # Milliseconds timestamp
        end_time=1720010000000     # Milliseconds timestamp
    )
```

##### get_open_interest()
```python
async with HyperliquidAPIClient() as client:
    oi = await client.get_open_interest("BTC")
```

##### get_funding_rate()
```python
async with HyperliquidAPIClient() as client:
    rates = await client.get_funding_rate("BTC", limit=100)
```

##### get_predicted_funding()
```python
async with HyperliquidAPIClient() as client:
    predictions = await client.get_predicted_funding()
    # Returns: {"BTC": 0.00015, "ETH": 0.0002, ...}
```

---

### HyperliquidWSClient Class

Low-level WebSocket client.

#### Methods

##### stream_ohlc()
```python
client = HyperliquidWSClient()
async for candle in client.stream_ohlc("BTC", "1m"):
    print(candle)
```

##### stream_trades()
```python
client = HyperliquidWSClient()
async for trade in client.stream_trades("BTC"):
    print(trade)
```

**Features**:
- Automatic reconnection with exponential backoff
- Error handling and logging
- Graceful shutdown

---

## 🧪 Testing

### Manual Testing Script

Run the comprehensive test script:

```bash
# Test everything
python test_hyperliquid.py all

# Test only REST API
python test_hyperliquid.py rest

# Test only WebSocket OHLC stream
python test_hyperliquid.py ws-ohlc

# Test only WebSocket trades stream
python test_hyperliquid.py ws-trades

# Test Exchange Interface
python test_hyperliquid.py interface

# Test Exchange Manager integration
python test_hyperliquid.py manager

# Show help
python test_hyperliquid.py help
```

### Unit Tests

Run the automated unit tests:

```bash
# Run all Hyperliquid tests
pytest tests/unit/test_hyperliquid_api_client.py -v

# Run specific test
pytest tests/unit/test_hyperliquid_api_client.py::TestGetOpenInterest -v

# Run with coverage
pytest tests/unit/test_hyperliquid_api_client.py --cov=exchanges/hyperliquid
```

---

## 💡 Examples

### Example 1: Fetch and Display Market Data

```python
import asyncio
from exchanges.hyperliquid import HyperliquidExchange

async def show_market_data():
    exchange = HyperliquidExchange()
    await exchange.initialize()

    # Get current data
    oi = await exchange.get_open_interest("BTC")
    fr = await exchange.get_funding_rate("BTC")

    print(f"BTC Market Data:")
    print(f"  Open Interest: {oi.open_interest:,.2f} BTC")
    print(f"  OI Value: ${oi.open_interest_value:,.2f}")
    print(f"  Funding Rate: {fr.funding_rate * 100:.4f}%")
    print(f"  Funding Time: {fr.funding_time}")

    await exchange.shutdown()

asyncio.run(show_market_data())
```

### Example 2: Monitor Live Prices

```python
import asyncio
from exchanges.hyperliquid import HyperliquidExchange

async def monitor_price():
    exchange = HyperliquidExchange()
    await exchange.initialize()

    print("Monitoring BTC price (1m candles)...")
    async for candle in exchange.stream_ohlc("BTC", "1m"):
        if candle.is_closed:
            print(f"[{candle.timestamp}] Closed at ${candle.close:,.2f}")
        else:
            print(f"Current: ${candle.close:,.2f}", end="\r")

    await exchange.shutdown()

asyncio.run(monitor_price())
```

### Example 3: Track Large Trades

```python
import asyncio
from exchanges.hyperliquid import HyperliquidExchange

async def track_whale_trades():
    exchange = HyperliquidExchange()
    await exchange.initialize()

    print("Tracking large BTC trades...")
    async for trade in exchange.stream_large_trades("BTC"):
        # Filter for trades > $100k
        if trade.value > 100_000:
            emoji = "🟢" if trade.side == "buy" else "🔴"
            print(f"{emoji} {trade.side.upper()}: ${trade.value:,.2f} @ ${trade.price:,.2f}")

    await exchange.shutdown()

asyncio.run(track_whale_trades())
```

### Example 4: Compare Multiple Symbols

```python
import asyncio
from exchanges.hyperliquid.api_client import HyperliquidAPIClient

async def compare_funding_rates():
    async with HyperliquidAPIClient() as client:
        symbols = ["BTC", "ETH", "SOL", "ARB"]

        for symbol in symbols:
            rates = await client.get_funding_rate(symbol, limit=1)
            if rates:
                fr = rates[0]
                print(f"{symbol:6s}: {fr.funding_rate * 100:+.4f}%")

asyncio.run(compare_funding_rates())
```

### Example 5: Historical Data Analysis

```python
import asyncio
from exchanges.hyperliquid.api_client import HyperliquidAPIClient
from core.utils.time import current_utc_timestamp

async def analyze_volatility():
    async with HyperliquidAPIClient() as client:
        # Get last 24 hours of 1h candles
        end_time = current_utc_timestamp(milliseconds=True)
        start_time = end_time - (24 * 60 * 60 * 1000)

        candles = await client.get_historical_ohlc("BTC", "1h", start_time, end_time)

        if not candles:
            print("No data")
            return

        # Calculate metrics
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        high_24h = max(highs)
        low_24h = min(lows)
        range_24h = high_24h - low_24h
        volatility = (range_24h / low_24h) * 100

        print(f"BTC 24h Analysis ({len(candles)} candles):")
        print(f"  High: ${high_24h:,.2f}")
        print(f"  Low: ${low_24h:,.2f}")
        print(f"  Range: ${range_24h:,.2f}")
        print(f"  Volatility: {volatility:.2f}%")

asyncio.run(analyze_volatility())
```

---

## 🔧 Troubleshooting

### Common Issues

#### Issue: "ModuleNotFoundError: No module named 'pydantic'"

**Solution**: Install dependencies:
```bash
pip install pydantic aiohttp websockets
```

#### Issue: "RuntimeError: Client session not initialized"

**Solution**: Use async context manager:
```python
# ❌ Wrong
client = HyperliquidAPIClient()
await client.get_open_interest("BTC")

# ✅ Correct
async with HyperliquidAPIClient() as client:
    await client.get_open_interest("BTC")
```

#### Issue: WebSocket disconnects frequently

**Solution**: This is normal. The client automatically reconnects with exponential backoff. Check your internet connection if it happens too often.

#### Issue: "No OI data found for symbol"

**Solution**: Make sure you're using the coin name (e.g., "BTC") not the pair (e.g., "BTCUSDT"). Hyperliquid uses coin symbols.

#### Issue: Rate limited (HTTP 429)

**Solution**: The client automatically retries with backoff. If it persists, reduce request frequency.

#### Issue: Empty OHLC response

**Solution**:
- Check your time range (start_time/end_time)
- Ensure timestamps are in milliseconds, not seconds
- Hyperliquid has limits on historical data (~5000 candles)

---

## 📊 Supported Intervals

| Interval | Description |
|----------|-------------|
| `1m` | 1 minute |
| `3m` | 3 minutes |
| `5m` | 5 minutes |
| `15m` | 15 minutes |
| `30m` | 30 minutes |
| `1h` | 1 hour |
| `2h` | 2 hours |
| `4h` | 4 hours |
| `6h` | 6 hours |
| `12h` | 12 hours |
| `1d` | 1 day |

---

## 🔗 Resources

- **Hyperliquid API Docs**: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
- **Exchange Interface**: `core/exchange_interface.py`
- **Schemas**: `core/schemas.py`
- **Test Script**: `test_hyperliquid.py`
- **Unit Tests**: `tests/unit/test_hyperliquid_api_client.py`

---

## 📝 Notes

1. **No Authentication Required**: All endpoints used are public (no API key needed)
2. **UTC Timestamps**: All timestamps are in UTC timezone
3. **Normalized Schemas**: All data conforms to standard schemas in `core/schemas.py`
4. **Async Only**: All methods are async and must be awaited
5. **Error Handling**: Methods return `None` or empty lists on error, check logs for details

---

## 🆘 Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Run `python test_hyperliquid.py all` to verify setup
3. Review logs (enable debug logging with `LOG_LEVEL=DEBUG`)
4. Check Hyperliquid API status at https://status.hyperliquid.xyz/

---

**Last Updated**: 2025-10-27
**Version**: 1.0.0
