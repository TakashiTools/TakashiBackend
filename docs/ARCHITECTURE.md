# Architecture Documentation

**TAKASHI Multi-Exchange Market Data API - System Architecture**

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Application                    │
│                 (REST + WebSocket Layer)                 │
└────────────────────────┬────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
    ┌─────────▼─────────┐  ┌───────▼────────┐
    │  ExchangeManager   │  │   Event Bus    │
    │    (Registry)      │  │  (Pub/Sub)     │
    └─────────┬─────────┘  └───────┬────────┘
              │                     │
    ┌─────────▼─────────┐          │
    │ExchangeInterface  │          │
    │  (Abstract Base)  │          │
    └─────────┬─────────┘          │
              │                     │
     ┌────────┼────────┐           │
     │        │        │           │
┌────▼───┐┌──▼───┐┌───▼────┐     │
│Binance ││Bybit ││Hyper-  │     │
│Exchange││Exch. ││liquid  │     │
└────┬───┘└──┬───┘└───┬────┘     │
     │       │        │           │
┌────▼───────▼────────▼───────┐  │
│    Exchange Connectors       │  │
│  (API + WebSocket Clients)   │  │
└──────────────────────────────┘  │
                                   │
                     ┌─────────────▼────────────┐
                     │  Background Services     │
                     │  - Liquidation Aggregator│
                     │  - Trade Aggregator      │
                     │  - OI/Vol Monitor        │
                     └──────────────────────────┘
```

---

## Core Components

### 1. FastAPI Application Layer (`app/main.py`)

**Responsibilities:**
- HTTP request handling
- WebSocket connection management
- Route definitions
- Request validation
- Response serialization

**Key Features:**
- Automatic API documentation (Swagger/ReDoc)
- CORS middleware for frontend access
- Lifespan management (startup/shutdown)
- Error handling and logging

**Endpoints:**
- System: `/`, `/health`, `/exchanges`
- Market Data: `/{exchange}/ohlc/{symbol}/{interval}`
- Aggregated: `/multi/ohlc/{symbol}/{interval}`
- WebSocket: `/ws/{exchange}/{symbol}/{stream}`

---

### 2. Exchange Manager (`core/exchange_manager.py`)

**Pattern:** Registry + Factory

**Responsibilities:**
- Maintains registry of all exchange instances
- Provides centralized access to exchanges
- Handles lifecycle (initialization/shutdown)
- Conducts health checks
- Manages capabilities

**Key Methods:**
```python
manager.get_exchange(name) → ExchangeInterface
manager.initialize_all() → None
manager.shutdown_all() → None
manager.health_check_all() → Dict[str, bool]
```

**Benefits:**
- Single source of truth for exchanges
- Easy to add new exchanges
- Centralized lifecycle management
- Type-safe exchange access

---

### 3. Exchange Interface (`core/exchange_interface.py`)

**Pattern:** Abstract Base Class + Strategy

**Contract Definition:**
```python
class ExchangeInterface(ABC):
    name: str
    capabilities: Dict[str, bool]
    
    # REST Methods
    async def get_ohlc(...) → List[OHLC]
    async def get_open_interest(...) → OpenInterest
    async def get_funding_rate(...) → FundingRate
    
    # WebSocket Methods
    async def stream_ohlc(...) → AsyncGenerator[OHLC]
    async def stream_liquidations(...) → AsyncGenerator[Liquidation]
    async def stream_large_trades(...) → AsyncGenerator[LargeTrade]
    
    # Lifecycle
    async def initialize() → None
    async def shutdown() → None
    async def health_check() → bool
```

**Benefits:**
- Enforces consistency across exchanges
- Enables polymorphism
- Supports capability-based feature detection
- Simplifies testing with mocks

---

### 4. Data Schemas (`core/schemas.py`)

**Pattern:** Data Transfer Objects (DTO) with Validation

**Key Models:**
```python
BaseMarketModel  # Common fields: exchange, symbol, timestamp
├── OHLC        # Candlestick data
├── OpenInterest # Futures OI data
├── FundingRate  # Perpetual funding rates
├── Liquidation  # Forced liquidation events
└── LargeTrade   # Significant trades
```

**Features:**
- Pydantic v2 for validation
- Type-safe field definitions
- Automatic serialization
- Field validators
- JSON schema generation

**Benefits:**
- Normalized data across exchanges
- Runtime validation
- Type hints for IDE support
- Easy serialization for API responses

---

### 5. Exchange Connectors

**Structure per Exchange:**
```
exchanges/{exchange_name}/
├── __init__.py          # {Exchange}Exchange wrapper class
├── api_client.py        # REST API client (aiohttp)
└── ws_client.py         # WebSocket client (websockets)
```

#### API Client Pattern

**Responsibilities:**
- HTTP requests with retry logic
- Rate limit handling
- Data parsing and normalization
- Connection pooling

**Example:**
```python
class BinanceAPIClient:
    async def get_ohlc(...):
        # 1. Build request
        # 2. Make HTTP call
        # 3. Parse response
        # 4. Normalize to OHLC schema
        # 5. Return List[OHLC]
```

#### WebSocket Client Pattern

**Responsibilities:**
- WebSocket connection management
- Auto-reconnection with backoff
- Message parsing
- Data normalization
- Async generator streaming

**Example:**
```python
class BinanceWSClient:
    async def stream_ohlc(...) -> AsyncGenerator[OHLC]:
        while True:
            try:
                async with websockets.connect(url) as ws:
                    async for message in ws:
                        # Parse and yield OHLC
                        yield normalized_ohlc
            except Exception:
                # Reconnect with exponential backoff
```

---

### 6. Event Bus (`services/event_bus.py`)

**Pattern:** Publish-Subscribe (Pub/Sub)

**Architecture:**
```
┌──────────────┐      ┌──────────────┐
│  Publishers  │      │ Subscribers  │
│ (Services)   │      │ (WebSockets) │
└──────┬───────┘      └──────▲───────┘
       │                     │
       │   ┌─────────────────┘
       │   │
       ▼   │
    ┌──────▼──────┐
    │  Event Bus  │
    │ Topic-based │
    └─────────────┘
```

**Implementation:**
- Topic-based routing
- Async queues per subscriber
- Non-blocking publish
- Automatic cleanup on disconnect

**Topics:**
- `liquidation` - Multi-exchange liquidation events
- `large_trade` - Multi-exchange large trades
- `oi_spike` - OI/Volume anomaly alerts

**Benefits:**
- Decouples services from WebSocket handlers
- Scales to many subscribers
- No blocking on slow consumers

---

### 7. Background Services

#### All Liquidations Service (`services/all_liquidations.py`)

**Purpose:** Aggregate liquidations from multiple exchanges

**Sources:**
- Binance: `wss://fstream.binance.com/ws/!forceOrder@arr`
- OKX: `wss://ws.okx.com:8443/ws/v5/public`
- Bybit: `wss://stream.bybit.com/v5/public/linear`

**Process:**
1. Connect to multiple exchange WebSockets
2. Parse exchange-specific formats
3. Normalize to Liquidation schema
4. Filter by USD value threshold
5. Publish to event bus

#### All Large Trades Service (`services/all_large_trades.py`)

**Purpose:** Aggregate large trades from multiple exchanges

**Sources:**
- Binance: aggTrade streams
- Bybit: publicTrade streams
- Hyperliquid: trades streams

**Process:**
1. Subscribe to trade streams per symbol
2. Calculate trade value (price × quantity)
3. Filter by USD threshold
4. Normalize to LargeTrade schema
5. Publish to event bus

#### OI/Volume Monitor (`services/oi_vol_monitor.py`)

**Purpose:** Detect anomalies in OI and volume using statistics

**Algorithm:**
1. Fetch OI history and kline volume periodically
2. Maintain rolling window (100 data points)
3. Calculate z-scores: `z = (current - mean) / stdev`
4. Trigger alert when z > threshold
5. Publish spike events to event bus

**Thresholds:**
- 5m: z-score > 3.0
- 15m: z-score > 2.5
- 1h: z-score > 2.0

---

## Data Flow Examples

### Example 1: REST API - Fetch OHLC

```
┌──────────┐
│  Client  │
└────┬─────┘
     │ GET /binance/ohlc/BTCUSDT/1h?limit=100
     ▼
┌─────────────────┐
│ FastAPI Router  │
└────┬────────────┘
     │ manager.get_exchange("binance")
     ▼
┌─────────────────┐
│Exchange Manager │
└────┬────────────┘
     │ returns BinanceExchange instance
     ▼
┌─────────────────┐
│BinanceExchange  │
└────┬────────────┘
     │ await exchange.get_ohlc(...)
     ▼
┌─────────────────┐
│BinanceAPIClient │
└────┬────────────┘
     │ HTTP GET https://fapi.binance.com/fapi/v1/klines
     ▼
┌─────────────────┐
│  Binance API    │
└────┬────────────┘
     │ Returns: [[timestamp, open, high, low, close, volume, ...], ...]
     ▼
┌─────────────────┐
│BinanceAPIClient │
└────┬────────────┘
     │ Normalize to List[OHLC]
     ▼
┌─────────────────┐
│BinanceExchange  │
└────┬────────────┘
     │ Return List[OHLC]
     ▼
┌─────────────────┐
│ FastAPI Router  │
└────┬────────────┘
     │ Serialize to JSON
     ▼
┌──────────┐
│  Client  │ Receives: [{"exchange": "binance", "symbol": "BTCUSDT", ...}]
└──────────┘
```

### Example 2: WebSocket - Real-time OHLC

```
┌──────────┐
│  Client  │
└────┬─────┘
     │ WS connect: /ws/binance/BTCUSDT/ohlc?interval=1m
     ▼
┌─────────────────┐
│ FastAPI WS      │
└────┬────────────┘
     │ manager.get_exchange("binance")
     ▼
┌─────────────────┐
│BinanceExchange  │
└────┬────────────┘
     │ async for ohlc in exchange.stream_ohlc(...)
     ▼
┌─────────────────┐
│BinanceWSClient  │
└────┬────────────┘
     │ WS connect: wss://fstream.binance.com/ws/btcusdt@kline_1m
     │ [Persistent connection]
     ▼
┌─────────────────┐
│  Binance WS     │ Streams: {"e":"kline", "k":{...}}
└────┬────────────┘
     │ Continuous messages
     ▼
┌─────────────────┐
│BinanceWSClient  │
└────┬────────────┘
     │ Parse and normalize → yield OHLC
     ▼
┌─────────────────┐
│BinanceExchange  │
└────┬────────────┘
     │ yield OHLC
     ▼
┌─────────────────┐
│ FastAPI WS      │
└────┬────────────┘
     │ Send JSON to client
     ▼
┌──────────┐
│  Client  │ Receives: {"exchange": "binance", "close": 50000, ...}
└──────────┘
```

### Example 3: Aggregated Liquidations

```
┌──────────────────────────────────────────────┐
│         Background Services (on startup)      │
└────┬────────────────────────────┬────────────┘
     │                             │
     ▼                             ▼
┌─────────────┐            ┌─────────────┐
│Binance WS   │            │  OKX WS     │ [+ Bybit WS]
└─────┬───────┘            └─────┬───────┘
      │                          │
      │ Liquidation events       │ Liquidation events
      ▼                          ▼
┌────────────────────────────────────────┐
│   AllLiquidationsService               │
│   - Parse exchange format              │
│   - Normalize to Liquidation schema    │
│   - Filter by min USD value            │
└──────────────┬─────────────────────────┘
               │ bus.publish("liquidation", event)
               ▼
         ┌───────────┐
         │ Event Bus │
         │  Topic:   │
         │"liquidation"│
         └─────┬─────┘
               │
     ┌─────────┼─────────┐
     │         │         │
     ▼         ▼         ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│Client 1 │ │Client 2 │ │Client N │
│WS Conn  │ │WS Conn  │ │WS Conn  │
└─────────┘ └─────────┘ └─────────┘
  (Receives filtered liquidations based on min_value_usd)
```

---

## Design Patterns Used

### 1. Abstract Factory Pattern
- **Where:** `ExchangeInterface`
- **Purpose:** Define contract for exchange implementations
- **Benefit:** Consistent interface across all exchanges

### 2. Registry Pattern
- **Where:** `ExchangeManager`
- **Purpose:** Central registry of exchange instances
- **Benefit:** Single source of truth, easy access

### 3. Strategy Pattern
- **Where:** Exchange implementations
- **Purpose:** Different exchanges, same interface
- **Benefit:** Polymorphism, easy to swap exchanges

### 4. Observer Pattern
- **Where:** `EventBus`
- **Purpose:** Pub/sub messaging
- **Benefit:** Decoupled services

### 5. Adapter Pattern
- **Where:** Exchange connectors
- **Purpose:** Normalize exchange-specific data
- **Benefit:** Consistent data format

### 6. Singleton Pattern
- **Where:** Event bus, service instances
- **Purpose:** Single shared instance
- **Benefit:** Resource efficiency

### 7. Builder Pattern
- **Where:** WebSocket client factories
- **Purpose:** Construct configured clients
- **Benefit:** Clean initialization

---

## Async Architecture

### Concurrency Model

**Python asyncio** with:
- `aiohttp` for HTTP requests
- `websockets` for WebSocket connections
- `asyncio.gather()` for concurrent operations
- Connection pooling for efficiency

### Benefits

1. **High Concurrency:**
   - Handle thousands of connections
   - Non-blocking I/O
   - Efficient resource usage

2. **Performance:**
   - Minimal latency for real-time data
   - Concurrent exchange requests
   - Connection reuse

3. **Scalability:**
   - Horizontal scaling possible
   - Minimal memory per connection
   - CPU-efficient

---

## Error Handling & Reliability

### Retry Logic

**Exponential Backoff:**
```python
for attempt in range(3):
    try:
        return await fetch_data()
    except RateLimitError:
        delay = 1.5 * (attempt + 1)
        await asyncio.sleep(delay)
```

### WebSocket Reconnection

**Auto-reconnect:**
```python
while running:
    try:
        async with websockets.connect(url) as ws:
            async for message in ws:
                yield parse(message)
    except Exception:
        await asyncio.sleep(backoff_delay)
```

### Circuit Breaker (Future Enhancement)

- Open circuit after N failures
- Half-open after timeout
- Close when successful

---

## Scalability Considerations

### Current Architecture

**Single Instance:**
- Handles ~1000 concurrent WebSocket connections
- REST API: ~100 req/s
- Suitable for small-medium deployments

### Scaling Horizontally

**Multiple Instances + Load Balancer:**
```
           ┌──────────────┐
           │Load Balancer │
           └──────┬───────┘
         ┌────────┼────────┐
         │        │        │
    ┌────▼──┐ ┌──▼───┐ ┌──▼───┐
    │API 1  │ │API 2 │ │API 3 │
    └───────┘ └──────┘ └──────┘
```

**Considerations:**
- Sticky sessions for WebSockets
- Shared cache (Redis)
- Centralized logging

### Caching Layer (Future)

**Redis Integration:**
- Cache OHLC data (1-5 second TTL)
- Cache OI/funding (10-30 second TTL)
- Reduce exchange API calls

---

## Security Considerations

### Current

- No authentication (public API)
- CORS configured for frontend origins
- Rate limiting (via exchange retry logic)
- Input validation (Pydantic)
- No sensitive data exposed

### Future Enhancements

- API key authentication
- Rate limiting per client
- Request throttling
- IP whitelisting
- DDoS protection

---

## Monitoring & Observability

### Logging

**Structured Logging:**
- Exchange-specific loggers
- Log levels: DEBUG, INFO, WARNING, ERROR
- Contextual information

### Health Checks

**Endpoints:**
- `GET /health` - Overall health
- Per-exchange health via manager

### Metrics (Future)

**Prometheus Integration:**
- Request count
- Response time
- Error rate
- Active WebSocket connections
- Exchange API latency

---

## Future Architecture Enhancements

### 1. Data Persistence

**TimescaleDB:**
- Store historical OHLC
- Store OI/funding history
- Enable complex queries

### 2. Caching Layer

**Redis:**
- Cache recent data
- Reduce exchange API load
- Improve response time

### 3. Message Queue

**RabbitMQ/Kafka:**
- Decouple services further
- Better scalability
- Guaranteed delivery

### 4. API Gateway

**Kong/AWS API Gateway:**
- Authentication
- Rate limiting
- Request transformation
- Analytics

### 5. Microservices

**Split by Domain:**
- Market Data Service
- Analytics Service
- User Service
- Notification Service

---

## Related Documentation

- [API Reference](API_REFERENCE.md)
- [Development Guide](DEVELOPMENT.md)
- [Exchange Guide](EXCHANGE_GUIDE.md)
- [Contributing](../CONTRIBUTING.md)

---

## Design Decisions

### Why FastAPI?

- Modern async framework
- Automatic API documentation
- Type hints integration
- High performance
- WebSocket support

### Why Pydantic v2?

- Type-safe validation
- Better performance than v1
- JSON schema generation
- Easy serialization

### Why aiohttp over requests?

- Async/await support
- Non-blocking I/O
- Connection pooling
- WebSocket support

### Why websockets library?

- Simple async API
- Reliable reconnection
- Good documentation
- Production-tested

---

**Architecture is designed for:**
- **Extensibility** - Easy to add exchanges  
- **Maintainability** - Clear separation of concerns  
- **Scalability** - Async architecture scales well  
- **Reliability** - Retry logic and error handling  
- **Type Safety** - Full type hints and validation

