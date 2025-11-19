# Changelog

All notable changes to TAKASHI Multi-Exchange Market Data API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned Features
- Additional exchange connectors (OKX, Kraken, etc.)
- Data caching layer with Redis
- Historical data storage with TimescaleDB
- Rate limiting per client
- API key authentication
- Advanced filtering and aggregation
- Data export functionality

---

## [1.0.0] - 2025-01-XX

### Added
- **Multi-Exchange Support**: Binance, Bybit, and Hyperliquid connectors
- **REST API Endpoints**:
  - System endpoints (health, exchanges, info)
  - Per-exchange OHLC/candlestick data
  - Open interest (current and historical)
  - Funding rates (current and historical)
  - Aggregated multi-exchange OHLC endpoint
  - Hyperliquid predicted funding endpoint
  - Binance proxy endpoints (tickers, mark prices, klines)
  - CoinMarketCap proxy endpoints (categories)
- **WebSocket Streams**:
  - Per-exchange OHLC streaming
  - Per-exchange large trades streaming
  - Per-exchange liquidations streaming
  - Aggregated multi-exchange liquidations
  - Aggregated multi-exchange large trades
  - Binance OI/Volume spike alerts
- **Background Services**:
  - Multi-exchange liquidation aggregator
  - Multi-exchange large trade aggregator
  - Binance OI/Volume anomaly detector (z-score based)
- **Core Architecture**:
  - Abstract ExchangeInterface for consistency
  - ExchangeManager for centralized orchestration
  - Pydantic v2 schemas for data normalization
  - Event bus for pub/sub messaging
  - Async I/O throughout (aiohttp, websockets)
- **Developer Experience**:
  - Comprehensive test suite (unit + integration)
  - Auto-generated API documentation (Swagger/ReDoc)
  - Type hints throughout codebase
  - Structured logging
  - Configuration via environment variables
- **Deployment**:
  - Dockerfile for containerization
  - Procfile for Railway deployment
  - Railway.toml configuration
  - Health check endpoints

### Features

#### Exchange Connectors

**Binance Futures (USD-M)**
- Full feature support: OHLC, OI, Funding, Liquidations, Large Trades
- Historical OI data support
- Rate limit handling with exponential backoff
- WebSocket auto-reconnection

**Bybit Linear Contracts**
- Full feature support: OHLC, OI, Funding, Liquidations, Large Trades
- V5 API integration
- Multi-batch WebSocket subscriptions
- Interval format conversion

**Hyperliquid**
- OHLC, OI, Funding, Large Trades support
- Predicted funding across venues (HlPerp, BinPerp, BybitPerp)
- Coin symbol format (BTC vs BTCUSDT)
- Auto-mapping for aggregated endpoints
- Note: No liquidation data available

#### Advanced Analytics

**OI/Volume Spike Detection**
- Statistical anomaly detection using z-scores
- Multiple timeframes (5m, 15m, 1h)
- Configurable thresholds per timeframe
- Tracks top 80 Binance symbols
- Real-time WebSocket alerts

**Large Trade Detection**
- Configurable USD threshold (default: $100,000)
- Multi-exchange aggregation
- Buyer/maker analysis for trade aggression
- Real-time WebSocket streaming

**Liquidation Tracking**
- Multi-exchange aggregation (Binance, OKX, Bybit)
- USD value filtering per connection
- Side detection (long vs short liquidations)
- Real-time WebSocket streaming

### Technical Details

**Dependencies**
- FastAPI 0.110+ (web framework)
- Uvicorn 0.27+ (ASGI server)
- aiohttp 3.9+ (async HTTP client)
- websockets 12.0+ (WebSocket client)
- Pydantic 2.6+ (data validation)
- pytest 8.0+ (testing)

**Performance**
- Fully asynchronous architecture
- Connection pooling for REST APIs
- WebSocket connection reuse
- Minimal latency for real-time data
- Handles thousands of concurrent connections

**Reliability**
- Automatic retry with exponential backoff
- WebSocket auto-reconnection
- Comprehensive error handling
- Health check endpoints
- Structured logging

### Documentation
- Complete README with quick start
- API reference documentation
- Development guide with examples
- Architecture documentation
- Contributing guidelines
- Testing documentation

---

## Release Notes Template

### [X.Y.Z] - YYYY-MM-DD

#### Added
- New features

#### Changed
- Changes to existing features

#### Deprecated
- Features to be removed in future versions

#### Removed
- Removed features

#### Fixed
- Bug fixes

#### Security
- Security updates

---

## Version History

### Version 1.0.0 (Initial Release)
- Complete multi-exchange market data aggregation platform
- Production-ready with comprehensive testing
- Full documentation and deployment guides
- Professional-grade code quality

---

## Links

- [Repository](https://github.com/TakashiTools/TakashiBackend)
- [Issues](https://github.com/TakashiTools/TakashiBackend/issues)
- [Pull Requests](https://github.com/TakashiTools/TakashiBackend/pulls)
- [Releases](https://github.com/TakashiTools/TakashiBackend/releases)

---

## Notes

### Semantic Versioning

- **Major version (X.0.0)**: Incompatible API changes
- **Minor version (0.X.0)**: Backward-compatible functionality
- **Patch version (0.0.X)**: Backward-compatible bug fixes

### Release Schedule

- Major releases: As needed for breaking changes
- Minor releases: Monthly feature releases
- Patch releases: As needed for bug fixes

