# TAKASHI Backend — Frontend Integration Reference

Base URL (local):
- REST: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc


## REST Endpoints

System
- GET /
- GET /health
- GET /exchanges
- GET /ws-catalog  // documents WS routes (WS is not in OpenAPI)

Market Data (per exchange)
- GET /{exchange}/ohlc/{symbol}/{interval}?limit=…
  - exchange: binance | bybit | hyperliquid
  - symbol: e.g., BTCUSDT (binance/bybit), BTC (hyperliquid)
  - interval: 1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M
  - returns: List[OHLC]

- GET /{exchange}/oi/{symbol}
  - returns: OpenInterest

- GET /{exchange}/oi-hist/{symbol}?period=5m|15m|30m|1h|2h|4h|6h|12h|1d&limit=…
  - returns: List[OpenInterest]
  - note: Binance only; others 404

- GET /{exchange}/funding/{symbol}
  - returns: FundingRate (most recent)

- GET /{exchange}/funding-hist/{symbol}?limit=…
  - returns: List[FundingRate]

Aggregated / utilities
- GET /multi/ohlc/{symbol}/{interval}?limit=…
  - returns: { "binance": List[OHLC], "bybit": List[OHLC], "hyperliquid": List[OHLC] }
  - symbol mapping: Hyperliquid auto‑maps BTCUSDT→BTC

- GET /hyperliquid/predicted-funding?coin=BTC
  - returns: List[{ coin, venues: [{ venue, funding_rate, next_funding_time }] }]


## WebSocket Streams

Per‑exchange (symbol‑scoped)
- Pattern: ws://{host}/ws/{exchange}/{symbol}/{stream}
- Streams:
  - ohlc (requires query: ?interval=1m|5m|1h|…)
  - large_trades
  - liquidations (if supported by the exchange)
- Examples:
  - ws://localhost:8000/ws/binance/BTCUSDT/ohlc?interval=1m
  - ws://localhost:8000/ws/bybit/BTCUSDT/large_trades
  - ws://localhost:8000/ws/binance/ETHUSDT/liquidations

Aggregated / derived (not symbol‑scoped)
- Liquidations firehose (Binance, OKX, Bybit):
  - ws://{host}/ws/all/liquidations?min_value_usd=50000
  - per‑connection filter: min_value_usd (server will drop smaller events)

- OI / Volume spike alerts (Binance‑wide):
  - ws://{host}/ws/oi-vol?timeframes=5m,15m,1h
  - per‑connection filter: timeframes (comma‑separated)

- Large trades (Binance, Bybit, Hyperliquid):
  - ws://{host}/ws/all/large_trades?min_value_usd=100000
  - per‑connection filter: min_value_usd (server will drop smaller events)

Notes on thresholds
- Global minimum for “large trade” size is configured on the server (env LARGE_TRADE_THRESHOLD_USD; default 100000). The effective minimum on the aggregated WS is max(global, ?min_value_usd).


## Message Shapes (JSON)

OHLC
```json
{
  "exchange": "binance",
  "symbol": "BTCUSDT",
  "timestamp": "2025-11-06T17:50:00Z",
  "interval": "5m",
  "open": 101621.7,
  "high": 101958.9,
  "low": 101619.9,
  "close": 101818.8,
  "volume": 1274.0,
  "quote_volume": 129689803.5351,
  "trades_count": 39480,
  "is_closed": true
}
```

OpenInterest
```json
{
  "exchange": "bybit",
  "symbol": "BTCUSDT",
  "timestamp": "2025-11-08T12:10:30Z",
  "open_interest": 10659.509,
  "open_interest_value": null
}
```

FundingRate
```json
{
  "exchange": "hyperliquid",
  "symbol": "BTC",
  "timestamp": "2025-11-08T08:00:00Z",
  "funding_rate": 0.0000125,
  "funding_time": "2025-11-08T08:00:00Z"
}
```

Liquidation
```json
{
  "type": "liquidation",
  "exchange": "okx",
  "symbol": "BTC-USDT-SWAP",
  "side": "sell",
  "price": 101500.0,
  "quantity": 2.5,
  "value": 253750.0,
  "timestamp": "2025-11-08T12:31:00Z"
}
```

LargeTrade
```json
{
  "type": "large_trade",
  "exchange": "binance",
  "symbol": "BTCUSDT",
  "timestamp": "2025-11-08T12:31:00Z",
  "side": "buy",
  "price": 101800.0,
  "quantity": 3.0,
  "value": 305400.0,
  "is_buyer_maker": false
}
```

OI / Volume Spike (alerts)
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


## Quick usage snippets

REST (fetch OHLC; TypeScript)
```ts
const base = "http://localhost:8000";
async function fetchOhlc(exchange: string, symbol: string, interval: string, limit = 100) {
  const url = `${base}/${exchange}/ohlc/${symbol}/${interval}?limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json(); // OHLC[]
}
```

WebSocket (aggregated liquidations; TypeScript)
```ts
const ws = new WebSocket("ws://localhost:8000/ws/all/liquidations?min_value_usd=50000");
ws.onmessage = (ev) => {
  const data = JSON.parse(ev.data);
  // data.type === "liquidation"
  console.log(data.exchange, data.symbol, data.value);
};
```

WebSocket (per‑exchange OHLC; TypeScript)
```ts
const ws = new WebSocket("ws://localhost:8000/ws/binance/BTCUSDT/ohlc?interval=1m");
ws.onmessage = (ev) => {
  const candle = JSON.parse(ev.data); // OHLC
  // candle.is_closed indicates closed vs updating
};
```


## Notes
- Hyperliquid expects coin symbols (BTC), not pairs (BTCUSDT); backend auto‑maps for aggregated REST/WS when possible.
- For aggregated large trades and liquidations, you can further filter per connection using the query params shown above.


