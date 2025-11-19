# API Reference

Complete REST and WebSocket API documentation for TAKASHI Multi-Exchange Market Data API.

---

## Base URLs

**Local Development:**
- REST API: `http://localhost:8000`
- WebSocket: `ws://localhost:8000`

**Production:**
- REST API: `https://your-domain.com`
- WebSocket: `wss://your-domain.com`

**Interactive Documentation:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## REST API Endpoints

### System Endpoints

#### `GET /`
Get API information and status.

**Response:**
```json
{
  "name": "TAKASHI Multi-Exchange Market Data API",
  "version": "1.0.0",
  "status": "operational",
  "docs": "/docs",
  "exchanges": ["binance", "bybit", "hyperliquid"]
}
```

#### `GET /health`
Check health status of all exchanges.

**Response:**
```json
{
  "status": "healthy",
  "exchanges": {
    "binance": true,
    "bybit": true,
    "hyperliquid": true
  }
}
```

#### `GET /exchanges`
List all supported exchanges and their capabilities.

**Response:**
```json
{
  "exchanges": [
    {
      "name": "binance",
      "capabilities": {
        "ohlc": true,
        "funding_rate": true,
        "open_interest": true,
        "liquidations": true,
        "large_trades": true
      }
    }
  ]
}
```

#### `GET /ws-catalog`
List available WebSocket endpoints and patterns.

---

### Market Data Endpoints (Per Exchange)

#### `GET /{exchange}/ohlc/{symbol}/{interval}`
Get historical OHLC/candlestick data.

**Parameters:**
- `exchange` (path): Exchange name (`binance`, `bybit`, `hyperliquid`)
- `symbol` (path): Trading pair (e.g., `BTCUSDT` for Binance/Bybit, `BTC` for Hyperliquid)
- `interval` (path): Timeframe (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`)
- `limit` (query, optional): Number of candles (default: 500, max: 1500)
- `start_time` (query, optional): Start time in milliseconds since epoch
- `end_time` (query, optional): End time in milliseconds since epoch

**Example:**
```bash
GET /binance/ohlc/BTCUSDT/1h?limit=100
```

**Response:**
```json
[
  {
    "exchange": "binance",
    "symbol": "BTCUSDT",
    "timestamp": "2025-11-19T12:00:00Z",
    "interval": "1h",
    "open": 101621.7,
    "high": 101958.9,
    "low": 101619.9,
    "close": 101818.8,
    "volume": 1274.0,
    "quote_volume": 129689803.5351,
    "trades_count": 39480,
    "is_closed": true
  }
]
```

---

#### `GET /{exchange}/oi/{symbol}`
Get current open interest.

**Parameters:**
- `exchange` (path): Exchange name
- `symbol` (path): Trading pair

**Example:**
```bash
GET /binance/oi/BTCUSDT
```

**Response:**
```json
{
  "exchange": "binance",
  "symbol": "BTCUSDT",
  "timestamp": "2025-11-19T12:00:00Z",
  "open_interest": 125000.5,
  "open_interest_value": 12718187500.0
}
```

---

#### `GET /{exchange}/oi-hist/{symbol}`
Get historical open interest data.

**Note:** Only supported by Binance.

**Parameters:**
- `exchange` (path): Exchange name (must be `binance`)
- `symbol` (path): Trading pair
- `period` (query): Time period (`5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `12h`, `1d`)
- `limit` (query, optional): Number of records (default: 30, max: 500)

**Example:**
```bash
GET /binance/oi-hist/BTCUSDT?period=1h&limit=24
```

---

#### `GET /{exchange}/funding/{symbol}`
Get current funding rate.

**Parameters:**
- `exchange` (path): Exchange name
- `symbol` (path): Trading pair

**Example:**
```bash
GET /binance/funding/BTCUSDT
```

**Response:**
```json
{
  "exchange": "binance",
  "symbol": "BTCUSDT",
  "timestamp": "2025-11-19T08:00:00Z",
  "funding_rate": 0.0001,
  "funding_time": "2025-11-19T16:00:00Z"
}
```

---

#### `GET /{exchange}/funding-hist/{symbol}`
Get historical funding rates.

**Parameters:**
- `exchange` (path): Exchange name
- `symbol` (path): Trading pair
- `limit` (query, optional): Number of records (default: 100, max: 1000)

**Example:**
```bash
GET /binance/funding-hist/BTCUSDT?limit=50
```

---

### Aggregated Endpoints

#### `GET /multi/ohlc/{symbol}/{interval}`
Get OHLC data from all exchanges concurrently.

**Parameters:**
- `symbol` (path): Trading pair (automatically mapped for Hyperliquid)
- `interval` (path): Timeframe
- `limit` (query, optional): Number of candles per exchange (default: 200, max: 1000)
- `start_time` (query, optional): Start time in milliseconds
- `end_time` (query, optional): End time in milliseconds

**Example:**
```bash
GET /multi/ohlc/BTCUSDT/5m?limit=200
```

**Response:**
```json
{
  "binance": [ /* OHLC array */ ],
  "bybit": [ /* OHLC array */ ],
  "hyperliquid": [ /* OHLC array */ ]
}
```

**Note:** Symbol `BTCUSDT` is automatically mapped to `BTC` for Hyperliquid.

---

#### `GET /hyperliquid/predicted-funding`
Get predicted funding rates across venues (HlPerp, BinPerp, BybitPerp).

**Parameters:**
- `coin` (query, optional): Filter by coin (e.g., `BTC`)

**Example:**
```bash
GET /hyperliquid/predicted-funding?coin=BTC
```

**Response:**
```json
[
  {
    "coin": "BTC",
    "venues": [
      {
        "venue": "HlPerp",
        "funding_rate": 0.0001,
        "next_funding_time": "2025-11-19T16:00:00Z"
      },
      {
        "venue": "BinPerp",
        "funding_rate": 0.00012,
        "next_funding_time": "2025-11-19T16:00:00Z"
      }
    ]
  }
]
```

---

### Proxy Endpoints (CORS-Friendly)

#### `GET /binance/tickers/24hr`
Proxy for Binance 24h ticker data (all symbols).

**Response:** Raw Binance format (array of ticker objects)

---

#### `GET /binance/mark-prices`
Proxy for Binance mark price and funding rate data (all symbols).

**Response:** Raw Binance format (array of mark price objects)

---

#### `GET /binance/klines/{symbol}/{interval}`
Proxy for Binance klines (raw format).

**Parameters:**
- `symbol` (path): Trading pair
- `interval` (path): Timeframe
- `limit` (query, optional): Number of candles (default: 500, max: 1500)
- `startTime` (query, optional): Start time in milliseconds
- `endTime` (query, optional): End time in milliseconds

**Response:** Raw Binance format (array of kline arrays)

---

#### `GET /coinmarketcap/categories`
Proxy for CoinMarketCap categories API.

**Parameters:**
- `start` (query, optional): Offset start (default: 1)
- `limit` (query, optional): Number of results (default: 100, max: 5000)

**Note:** Requires `COINMARKETCAP_API_KEY` environment variable.

---

#### `GET /coinmarketcap/category`
Proxy for CoinMarketCap category details API.

**Parameters:**
- `id` (query, required): Category ID
- `start` (query, optional): Offset start (default: 1)
- `limit` (query, optional): Number of coins (default: 100, max: 1000)

---

## WebSocket API

### Connection

Connect to WebSocket endpoints using standard WebSocket clients.

**Protocol:**
- Local: `ws://localhost:8000/ws/...`
- Production: `wss://your-domain.com/ws/...`

**Message Format:** All messages are JSON objects using Pydantic schemas.

---

### Per-Exchange Streams (Symbol-Scoped)

#### Pattern
```
ws://{host}/ws/{exchange}/{symbol}/{stream}
```

#### Available Streams

**1. OHLC/Candlestick Stream**
```
ws://{host}/ws/{exchange}/{symbol}/ohlc?interval={interval}
```

**Parameters:**
- `exchange`: Exchange name (`binance`, `bybit`, `hyperliquid`)
- `symbol`: Trading pair
- `interval` (query): Timeframe (`1m`, `5m`, `1h`, etc.)

**Example:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/binance/BTCUSDT/ohlc?interval=1m");

ws.onmessage = (event) => {
  const candle = JSON.parse(event.data);
  console.log(candle.close, candle.is_closed);
};
```

---

**2. Large Trades Stream**
```
ws://{host}/ws/{exchange}/{symbol}/large_trades
```

**Example:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/binance/BTCUSDT/large_trades");

ws.onmessage = (event) => {
  const trade = JSON.parse(event.data);
  console.log(trade.side, trade.value, trade.timestamp);
};
```

---

**3. Liquidations Stream**
```
ws://{host}/ws/{exchange}/{symbol}/liquidations
```

**Note:** Not supported by Hyperliquid.

**Example:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/binance/BTCUSDT/liquidations");

ws.onmessage = (event) => {
  const liquidation = JSON.parse(event.data);
  console.log(liquidation.side, liquidation.value);
};
```

---

### Aggregated Streams (Multi-Exchange)

#### `ws://{host}/ws/all/liquidations`
Aggregated liquidation stream across Binance, OKX, and Bybit.

**Parameters:**
- `min_value_usd` (query, optional): Filter events by minimum USD value (default: 5000)

**Example:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/all/liquidations?min_value_usd=50000");

ws.onmessage = (event) => {
  const liq = JSON.parse(event.data);
  console.log(liq.exchange, liq.symbol, liq.value);
};
```

**Message Format:**
```json
{
  "type": "liquidation",
  "exchange": "binance",
  "symbol": "BTCUSDT",
  "side": "sell",
  "price": 101500.0,
  "quantity": 2.5,
  "value": 253750.0,
  "timestamp": "2025-11-19T12:31:00Z"
}
```

---

#### `ws://{host}/ws/all/large_trades`
Aggregated large trades across Binance, Bybit, and Hyperliquid.

**Parameters:**
- `min_value_usd` (query, optional): Filter trades by minimum USD value (default: 100000)

**Example:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/all/large_trades?min_value_usd=100000");

ws.onmessage = (event) => {
  const trade = JSON.parse(event.data);
  console.log(trade.exchange, trade.value);
};
```

---

#### `ws://{host}/ws/oi-vol`
Binance OI/Volume spike alerts (statistical anomaly detection).

**Parameters:**
- `timeframes` (query, optional): Comma-separated timeframes (default: `5m,15m,1h`)

**Example:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/oi-vol?timeframes=5m,15m");

ws.onmessage = (event) => {
  const alert = JSON.parse(event.data);
  console.log(alert.symbol, alert.z_oi, alert.confirmed);
};
```

**Message Format:**
```json
{
  "type": "oi_spike",
  "exchange": "binance",
  "symbol": "BTCUSDT",
  "timeframe": "5m",
  "z_oi": 3.1,
  "z_vol": 2.9,
  "confirmed": true
}
```

**Thresholds:**
- 5m: z-score > 3.0
- 15m: z-score > 2.5
- 1h: z-score > 2.0

---

## Data Models (Schemas)

### OHLC
```typescript
{
  exchange: string;          // "binance" | "bybit" | "hyperliquid"
  symbol: string;            // "BTCUSDT"
  timestamp: string;         // ISO 8601 UTC
  interval: string;          // "1m" | "5m" | "1h" | etc.
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  quote_volume: number;
  trades_count: number;
  is_closed: boolean;        // true if candle is finalized
}
```

### OpenInterest
```typescript
{
  exchange: string;
  symbol: string;
  timestamp: string;
  open_interest: number;
  open_interest_value?: number;  // Optional, in USD
}
```

### FundingRate
```typescript
{
  exchange: string;
  symbol: string;
  timestamp: string;
  funding_rate: number;      // Decimal (0.0001 = 0.01%)
  funding_time: string;      // When funding is applied
}
```

### Liquidation
```typescript
{
  type: "liquidation";
  exchange: string;
  symbol: string;
  side: "buy" | "sell";      // "sell" = long liquidated
  price: number;
  quantity: number;
  value: number;             // USD value
  timestamp: string;
}
```

### LargeTrade
```typescript
{
  type: "large_trade";
  exchange: string;
  symbol: string;
  side: "buy" | "sell";
  price: number;
  quantity: number;
  value: number;             // USD value
  is_buyer_maker: boolean;
  timestamp: string;
}
```

---

## Error Handling

### HTTP Status Codes

- `200 OK` - Success
- `404 Not Found` - Exchange or symbol not found
- `422 Unprocessable Entity` - Validation error
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Exchange API unavailable

### Error Response Format

```json
{
  "detail": "Error message description"
}
```

---

## Rate Limits

**Server-side rate limiting is handled automatically.** The backend implements:
- Exponential backoff for exchange API requests
- Automatic retry on rate limit errors (429, 418, 503)
- Request queuing and throttling

**Recommended client-side practices:**
- Reuse WebSocket connections
- Batch REST API requests when possible
- Implement reconnection logic for WebSocket disconnects

---

## Examples

### Fetch OHLC Data (JavaScript)
```javascript
async function fetchOHLC(exchange, symbol, interval, limit = 100) {
  const url = `http://localhost:8000/${exchange}/ohlc/${symbol}/${interval}?limit=${limit}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return await response.json();
}

const candles = await fetchOHLC("binance", "BTCUSDT", "1h", 100);
```

### Stream Live Candles (JavaScript)
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/binance/BTCUSDT/ohlc?interval=1m");

ws.onopen = () => console.log("Connected");
ws.onmessage = (event) => {
  const candle = JSON.parse(event.data);
  console.log(`${candle.close} (closed: ${candle.is_closed})`);
};
ws.onerror = (error) => console.error("WebSocket error:", error);
ws.onclose = () => console.log("Disconnected");
```

### Multi-Exchange Aggregation (Python)
```python
import httpx
import asyncio

async def fetch_multi_ohlc(symbol: str, interval: str, limit: int = 200):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/multi/ohlc/{symbol}/{interval}",
            params={"limit": limit}
        )
        return response.json()

data = asyncio.run(fetch_multi_ohlc("BTCUSDT", "5m"))
print(data.keys())  # ['binance', 'bybit', 'hyperliquid']
```

---

## Symbol Mapping

**Binance & Bybit:** Use trading pair format (`BTCUSDT`, `ETHUSDT`)  
**Hyperliquid:** Use coin symbol format (`BTC`, `ETH`)

The API automatically maps symbols for multi-exchange endpoints:
- `BTCUSDT` → `BTC` (Hyperliquid)
- `ETHUSDT` → `ETH` (Hyperliquid)

---

## Need Help?

- **Issues:** [GitHub Issues](https://github.com/TakashiTools/TakashiBackend/issues)
- **Discussions:** [GitHub Discussions](https://github.com/TakashiTools/TakashiBackend/discussions)
- **Interactive Docs:** http://localhost:8000/docs (when running locally)

