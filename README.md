# Binance Futures Market Data Backend

A modular, scalable backend system for fetching and streaming cryptocurrency market data from Binance Futures (USD-M), designed for easy expansion to multiple exchanges.

## Overview

A production-ready cryptocurrency market data backend with **real-time streaming** and **historical REST API** endpoints.

### ✨ Features

**REST API (Historical Data)**
- 📊 OHLC/Candlestick data with configurable intervals
- 📈 Open Interest tracking (current + historical)
- 💰 Funding Rates monitoring (current + historical)
- 🔍 8 REST endpoints with automatic Swagger documentation

**WebSocket Streaming (Real-Time Data)**
- 🕯️ Live candlestick/OHLC updates
- ⚡ Real-time liquidation events
- 🐋 Large trade detection (configurable threshold, default $100k)
- 🔄 Auto-reconnect with exponential backoff
- ✅ Schema validation for all messages

**Architecture & Code Quality**
- 🏗️ Modular connector architecture (easy to add new exchanges)
- ⚡ Async-first with `asyncio` and `aiohttp`
- 📝 Type-safe with Pydantic V2 schemas
- 🧪 Comprehensive unit tests (48+ tests)
- 📚 Fully documented with docstrings
- ⚙️ Environment-based configuration (no hardcoded values)

Built with a **connector-oriented architecture** where each exchange is a separate module implementing a common interface, making it trivial to add new exchanges (Bybit, OKX, etc.) without rewriting core logic.

## Architecture

```
┌─────────────────────────────┐
│          FastAPI            │   ← Unified REST + WebSocket API
│   /binance/ohlc/BTCUSDT     │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│        Core Engine          │   ← Exchange-agnostic logic
│ - ExchangeManager           │
│ - Pydantic Schemas          │
│ - ExchangeInterface         │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Exchange Connectors        │   ← Modular, plug-and-play
│  /exchanges/binance/        │
│    - api_client.py (REST)   │
│    - ws_client.py (WS)      │
│    - exchange.py            │
└─────────────────────────────┘
```

## Project Structure

```
itabackend/
│
├── app/                      # FastAPI application
│   ├── main.py              # REST + WebSocket routes, lifespan management
│   └── __init__.py
│
├── core/                     # Exchange-agnostic core
│   ├── schemas.py           # Pydantic models (OHLC, OI, Funding, Liquidation, LargeTrade)
│   ├── exchange_interface.py  # Abstract base class for all exchanges
│   ├── exchange_manager.py    # Central registry for multi-exchange support
│   ├── config.py            # Configuration management with Pydantic Settings
│   ├── logging.py           # Centralized logging with structlog
│   ├── utils/
│   │   ├── time.py          # Timestamp utilities for UTC normalization
│   │   └── __init__.py
│   └── __init__.py
│
├── exchanges/                # Exchange connectors (plug-and-play)
│   ├── binance/
│   │   ├── __init__.py      # BinanceExchange implementation
│   │   ├── api_client.py    # REST API client (OHLC, OI, Funding)
│   │   └── ws_client.py     # WebSocket client (streaming with auto-reconnect)
│   └── __init__.py
│
├── storage/                  # Future: Caching & persistence
│   └── __init__.py
│
├── tests/
│   ├── unit/                # Unit tests
│   │   ├── test_config.py
│   │   ├── test_exchange_interface.py
│   │   ├── test_binance_api_client.py
│   │   ├── test_ws_client.py
│   │   ├── test_ws_integration.py
│   │   └── __init__.py
│   ├── integration/         # Integration tests
│   │   └── __init__.py
│   └── __init__.py
│
├── .env                      # Environment configuration
├── .env.example              # Example configuration
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Installation

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Setup

1. **Clone or navigate to the project directory**

```bash
cd C:\Users\Giovanni\Desktop\itabackend
```

2. **Create a virtual environment**

```bash
python -m venv venv
```

3. **Activate the virtual environment**

Windows:
```bash
venv\Scripts\activate
```

macOS/Linux:
```bash
source venv/bin/activate
```

4. **Install dependencies**

```bash
pip install -r requirements.txt
```

5. **Configure environment variables**

The `.env` file is already created with default settings. Review and modify if needed:

```bash
# Edit .env file to customize settings
notepad .env   # Windows
nano .env      # macOS/Linux
```

## Configuration

Key configuration variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `BINANCE_BASE_URL` | Binance Futures API endpoint | `https://fapi.binance.com` |
| `SUPPORTED_SYMBOLS` | Trading pairs to track | `BTCUSDT,ETHUSDT,SOLUSDT` |
| `SUPPORTED_INTERVALS` | Candlestick timeframes | `1m,5m,15m,1h,4h,1d` |
| `APP_PORT` | FastAPI server port | `8000` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `DEBUG` | Enable debug mode | `true` |
| `LARGE_TRADE_THRESHOLD_USD` | Minimum USD value for large trades | `100000` |
| `WS_RECONNECT_DELAY` | WebSocket reconnection delay (seconds) | `5` |
| `WS_MAX_RECONNECT_ATTEMPTS` | Max WebSocket reconnection attempts | `10` |

## Usage

### Running the Server

```bash
# Start the FastAPI development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: `http://localhost:8000`

### API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### API Endpoints

**REST** (Historical Data)
- System: `/`, `/health`, `/exchanges`
- OHLC: `/binance/ohlc/{symbol}/{interval}`
- Open Interest: `/binance/oi/{symbol}`, `/binance/oi-hist/{symbol}`
- Funding: `/binance/funding/{symbol}`, `/binance/funding-hist/{symbol}`

**WebSocket** (Real-Time Streams)
- Live OHLC: `ws://localhost:8000/ws/binance/BTCUSDT/ohlc?interval=1m`
- Liquidations: `ws://localhost:8000/ws/binance/BTCUSDT/liquidations`
- Large Trades: `ws://localhost:8000/ws/binance/BTCUSDT/large_trades`

## Development Principles

1. **Async-first**: All I/O operations use `asyncio` for high concurrency
2. **Modular**: Each exchange is independent, implements `ExchangeInterface`
3. **Normalized data**: Exchange-specific responses → unified Pydantic schemas
4. **Type-safe**: Full type hints + Pydantic validation
5. **Testable**: Comprehensive unit and integration tests

## Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# Run only unit tests
pytest tests/unit/

# Run only integration tests (makes real API calls)
pytest tests/integration/
```

## Roadmap

### Phase 1: Foundation & Core Infrastructure ✅ **COMPLETED**
- [x] Project structure and folder setup
- [x] Core configuration system with Pydantic Settings
- [x] Pydantic data schemas (OHLC, OpenInterest, FundingRate, Liquidation, LargeTrade)
- [x] Logging infrastructure with structlog
- [x] Time utilities for timestamp normalization (UTC)
- [x] Unit tests for configuration
- [x] Requirements and virtual environment setup
- [x] `.env` configuration with validation

### Phase 2: Exchange Interface & Manager ✅ **COMPLETED**
- [x] ExchangeInterface abstract base class
- [x] ExchangeManager for multi-exchange registry
- [x] BinanceExchange stub implementation
- [x] Unit tests for interface and manager (33 tests passing)
- [x] Capability detection system
- [x] Health check infrastructure

### Phase 3: Binance REST API ✅ **COMPLETED**
- [x] BinanceAPIClient with aiohttp
- [x] OHLC/candlestick data fetching (`get_ohlc`)
- [x] Current open interest (`get_open_interest`)
- [x] Historical open interest (`get_open_interest_hist`)
- [x] Current funding rate (`get_funding_rate`)
- [x] Historical funding rates (API method)
- [x] Funding rate info endpoint
- [x] Retry logic with exponential backoff (429, 418, 503 errors)
- [x] Data normalization to Pydantic schemas
- [x] FastAPI REST endpoints (8 endpoints)
- [x] Unit tests for API client (15 tests passing)
- [x] Automatic API documentation (Swagger UI + ReDoc)

### Phase 4: WebSocket Real-Time Streaming ✅ **COMPLETED**
- [x] WebSocket client infrastructure with auto-reconnect
- [x] Exponential backoff reconnection (1s → 2s → 4s → max 30s)
- [x] Live OHLC/candlestick streaming (`stream_ohlc`)
- [x] Real-time liquidation events (`stream_liquidations`)
- [x] Large trade detection with configurable threshold (`stream_large_trades`)
- [x] FastAPI WebSocket endpoint (`/ws/{exchange}/{symbol}/{stream}`)
- [x] Message parsing and schema validation
- [x] Graceful connection handling and cleanup
- [x] Unit tests for WebSocket client
- [x] Integration tests for streaming

### Phase 5: Additional Exchanges (Future)
- [ ] Bybit connector
- [ ] OKX connector
- [ ] Multi-exchange data aggregation
- [ ] Cross-exchange arbitrage detection

### Phase 6: Persistence & Scaling (Future)
- [ ] In-memory caching layer
- [ ] Redis caching integration
- [ ] TimescaleDB for historical data storage
- [ ] Database migration system (Alembic)
- [ ] Performance optimization and profiling
- [ ] Rate limiting and request pooling
- [ ] Horizontal scaling with load balancer

## Contributing

This is a learning project. Code is heavily commented to explain:
- **What** each component does
- **Why** design decisions were made
- **How** components interact

## License

MIT License - See LICENSE file for details

## Resources

- [Binance Futures API Documentation](https://binance-docs.github.io/apidocs/futures/en/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

**Status**: Core Features Complete ✅ | Ready for Production Testing 🚀
**Last Updated**: 2025-10-27
**Phases Completed**: 1, 2, 3, 4 (Foundation → REST API → WebSocket Streaming)
