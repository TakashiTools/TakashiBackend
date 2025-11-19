# TAKASHI Multi-Exchange Market Data API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-00C7B7?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![WebSocket](https://img.shields.io/badge/WebSocket-Enabled-green)](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> **Professional-grade cryptocurrency market data aggregation platform**  
> Unified REST and WebSocket API providing real-time and historical data from multiple exchanges.

---

## 🌟 Overview

TAKASHI is a high-performance, production-ready backend service that aggregates cryptocurrency market data from leading exchanges (Binance, Bybit, Hyperliquid) behind a single, normalized API interface. Built with FastAPI and modern async Python, it provides both REST endpoints for historical data and WebSocket streams for real-time updates.

### **Key Features**

- 🔄 **Unified Interface** - One API, multiple exchanges (easy to add more)
- ⚡ **High Performance** - Built on async Python with aiohttp and websockets
- 📊 **Normalized Data** - Consistent schemas across all exchanges using Pydantic v2
- 🔌 **Real-time Streaming** - WebSocket support for live market data
- 🛡️ **Type-Safe** - Full type hints and runtime validation
- 🔧 **Extensible** - Plugin architecture for adding new exchanges
- 📈 **Advanced Analytics** - OI/Volume spike detection with statistical analysis
- 🚀 **Production Ready** - Comprehensive error handling, logging, and testing

---

## 📊 Supported Exchanges & Features

| Exchange | OHLC | Open Interest | Funding Rate | Liquidations | Large Trades |
|----------|------|---------------|--------------|--------------|--------------|
| **Binance** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Bybit** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Hyperliquid** | ✅ | ✅ | ✅ | ❌ | ✅ |

---

## 🚀 Quick Start

### **Prerequisites**

- Python 3.11 or higher
- pip (Python package manager)

### **Installation**

```bash
# Clone the repository
git clone https://github.com/TakashiTools/TakashiBackend.git
cd TakashiBackend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### **Configuration**

Create a `.env` file in the project root:

```bash
# Copy the example environment file
cp env.example .env

# Edit .env and configure:
# - CORS_ORIGINS (add your frontend URL)
# - COINMARKETCAP_API_KEY (if using CoinMarketCap endpoints)
# - Other settings as needed
```

**Key configuration options:**

```env
# CORS Configuration - Add your frontend domain
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://yourdomain.com

# Application
LOG_LEVEL=INFO

# Supported Markets
SUPPORTED_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT
SUPPORTED_INTERVALS=1m,5m,15m,1h,4h,1d

# Trading Configuration
LARGE_TRADE_THRESHOLD_USD=100000

# Optional: CoinMarketCap API (for categories widget)
COINMARKETCAP_API_KEY=your_api_key_here
```

> **📝 Note:** See `env.example` for all available configuration options.

### **Run the Server**

```bash
# Development (with auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**API Documentation:** http://localhost:8000/docs

---

## 📚 API Documentation

### **REST Endpoints**

#### System
```http
GET /                    # API information
GET /health              # Health check all exchanges
GET /exchanges           # List exchanges and capabilities
GET /ws-catalog          # WebSocket documentation
```

#### Per-Exchange Market Data
```http
GET /{exchange}/ohlc/{symbol}/{interval}?limit=500
GET /{exchange}/oi/{symbol}
GET /{exchange}/oi-hist/{symbol}?period=1h&limit=100
GET /{exchange}/funding/{symbol}
GET /{exchange}/funding-hist/{symbol}?limit=100
```

#### Aggregated Data
```http
GET /multi/ohlc/{symbol}/{interval}         # All exchanges concurrently
GET /hyperliquid/predicted-funding?coin=BTC  # Cross-venue predictions
```

#### Proxy Endpoints (CORS-friendly)
```http
GET /binance/tickers/24hr                    # Binance 24h ticker data
GET /binance/mark-prices                     # Mark price/funding data
GET /binance/klines/{symbol}/{interval}      # Raw klines
GET /coinmarketcap/categories                # CMC categories
GET /coinmarketcap/category?id={id}          # CMC category details
```

### **WebSocket Streams**

#### Per-Exchange Streams
```
ws://{host}/ws/{exchange}/{symbol}/ohlc?interval=1m
ws://{host}/ws/{exchange}/{symbol}/large_trades
ws://{host}/ws/{exchange}/{symbol}/liquidations
```

#### Aggregated Streams
```
ws://{host}/ws/all/liquidations?min_value_usd=50000
ws://{host}/ws/all/large_trades?min_value_usd=100000
ws://{host}/ws/oi-vol?timeframes=5m,15m,1h
```

**📖 Full API Reference:** [docs/API_REFERENCE.md](docs/API_REFERENCE.md)

---

## 🏗️ Architecture

```
┌─────────────────────────────┐
│      FastAPI Application     │  REST + WebSocket endpoints
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│     ExchangeManager          │  Registry/Factory pattern
│  (Central orchestration)     │  
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│    ExchangeInterface         │  Abstract base class
│  (Contract all must follow)  │  Capabilities system
└──────────────┬───────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────────┐
│Binance │ │ Bybit  │ │Hyperliquid │
│Exchange│ │Exchange│ │  Exchange  │
└────────┘ └────────┘ └────────────┘
```

### **Design Patterns**

- **Abstract Factory** - `ExchangeInterface` defines contract
- **Registry** - `ExchangeManager` maintains exchange instances
- **Strategy** - Different exchanges, same interface
- **Observer** - Event bus for pub/sub messaging
- **Adapter** - Normalize exchange-specific data to common schemas

**📖 Architecture Deep Dive:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/unit/test_binance_api_client.py

# Run integration tests only
pytest tests/integration/
```

**Test Coverage:** 
- Unit tests for API clients, schemas, config
- Integration tests for exchange connectivity
- WebSocket stream validation

---

## 📦 Project Structure

```
TakashiBackend/
├── app/
│   └── main.py              # FastAPI application
├── core/
│   ├── config.py            # Configuration management
│   ├── exchange_interface.py   # Abstract base class
│   ├── exchange_manager.py  # Exchange registry
│   ├── schemas.py           # Pydantic data models
│   └── logging.py           # Logging configuration
├── exchanges/
│   ├── binance/             # Binance connector
│   ├── bybit/               # Bybit connector
│   └── hyperliquid/         # Hyperliquid connector
├── services/
│   ├── event_bus.py         # Pub/sub event system
│   ├── all_liquidations.py  # Multi-exchange liquidation aggregator
│   ├── all_large_trades.py  # Multi-exchange trade aggregator
│   └── oi_vol_monitor.py    # OI/Volume spike detector
├── tests/
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── docs/                    # Documentation
├── requirements.txt         # Python dependencies
├── Dockerfile              # Container build
└── Procfile                # Deployment config
```

---

## 🚢 Deployment

### **Railway (Recommended)**

1. Connect GitHub repository to Railway
2. Set environment variables in Railway dashboard
3. Deploy automatically on push to main

Railway will detect `Procfile` and run:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### **Docker**

```bash
# Build image
docker build -t takashi-backend .

# Run container
docker run -p 8000:8000 --env-file .env takashi-backend
```

### **Manual Deployment**

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export PORT=8000
export LOG_LEVEL=INFO

# Run with gunicorn + uvicorn workers
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

**📖 Deployment Guide:** [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### **Adding a New Exchange**

Adding a new exchange is straightforward:

1. Create folder: `exchanges/{exchange_name}/`
2. Implement `api_client.py` (REST API)
3. Implement `ws_client.py` (WebSocket)
4. Create wrapper class implementing `ExchangeInterface`
5. Register in `ExchangeManager`

**📖 Developer Guide:** [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

---

## 📋 Requirements

### **Python Dependencies**

- **FastAPI** 0.110+ - Modern async web framework
- **Uvicorn** 0.27+ - ASGI server
- **aiohttp** 3.9+ - Async HTTP client
- **websockets** 12.0+ - WebSocket client
- **Pydantic** 2.6+ - Data validation
- **pytest** 8.0+ - Testing framework

See [requirements.txt](requirements.txt) for full list.

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🔗 Links

- **Documentation:** [docs/](docs/)
- **API Reference:** [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- **Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)

---

## 📧 Support

For questions, issues, or feature requests:

- **Issues:** [GitHub Issues](https://github.com/TakashiTools/TakashiBackend/issues)
- **Discussions:** [GitHub Discussions](https://github.com/TakashiTools/TakashiBackend/discussions)

---

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation using Python type annotations
- [aiohttp](https://docs.aiohttp.org/) - Async HTTP client/server
- [websockets](https://websockets.readthedocs.io/) - WebSocket implementation

Exchange APIs:
- [Binance Futures](https://binance-docs.github.io/apidocs/futures/en/)
- [Bybit](https://bybit-exchange.github.io/docs/v5/intro)
- [Hyperliquid](https://hyperliquid.gitbook.io/hyperliquid-docs/)

---

<div align="center">

**⭐ Star this repository if you find it useful!**

Made with ❤️ for the crypto trading community

</div>
