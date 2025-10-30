# Multi‑Exchange Market Data API

FastAPI backend providing normalized cryptocurrency market data via REST and WebSocket. Designed for multiple exchanges behind a single interface.

## Overview

The service offers historical endpoints (REST) and real‑time streams (WebSocket) for:
- OHLC/candlesticks
- Open interest (current and historical)
- Funding rates (current and historical)
- Liquidations and large trades (exchange‑dependent)

Current connectors: Binance Futures (USD‑M), Hyperliquid, Bybit.

## Features

- Unified REST and WebSocket API
- Modular exchange connectors implementing a common interface
- Async I/O with `asyncio`, `aiohttp`
- Pydantic v2 schemas for type‑safe normalization
- Automatic API docs (Swagger / ReDoc)
- Tested with pytest (unit and integration)

## Architecture

```
┌─────────────────────────────┐
│           FastAPI           │  REST + WebSocket
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│         Core Engine         │  exchange‑agnostic
│  - ExchangeManager          │
│  - ExchangeInterface        │
│  - Pydantic Schemas         │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│      Exchange Connectors    │  Binance / Hyperliquid / Bybit
│  (REST + WS clients)        │
└─────────────────────────────┘
```

## API

Selected endpoints (see `/docs` for the full list):

- System: `GET /`, `GET /health`, `GET /exchanges`
- OHLC: `GET /{exchange}/ohlc/{symbol}/{interval}`
- Open Interest (current): `GET /{exchange}/oi/{symbol}`
- Open Interest (history): `GET /{exchange}/oi-hist/{symbol}` (if supported)
- Funding (current): `GET /{exchange}/funding/{symbol}`
- Funding (history): `GET /{exchange}/funding-hist/{symbol}` (if supported)

WebSocket streams:

- `ws://{host}/ws/{exchange}/{symbol}/ohlc?interval=1m`
- `ws://{host}/ws/{exchange}/{symbol}/large_trades`
- `ws://{host}/ws/{exchange}/{symbol}/liquidations` (if supported)

## Configuration

Environment variables (via `.env` or platform variables):

- `BINANCE_BASE_URL` (default `https://fapi.binance.com`)
- `SUPPORTED_SYMBOLS` (e.g., `BTCUSDT,ETHUSDT,SOLUSDT`)
- `SUPPORTED_INTERVALS` (e.g., `1m,5m,15m,1h,4h,1d`)
- `LOG_LEVEL` (e.g., `INFO`)
- `LARGE_TRADE_THRESHOLD_USD` (default `100000`)
- `WS_RECONNECT_DELAY`, `WS_MAX_RECONNECT_ATTEMPTS`

## Running Locally

```
python -m venv venv
source venv/bin/activate             # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/docs` for interactive API docs.

## Deployment (Railway)

This repository includes a `Procfile` and a `Dockerfile`.

Option A — Procfile (recommended with Railway Nixpacks)
1. Connect the GitHub repository in Railway and deploy.
2. Railway injects `PORT`; the Procfile runs: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Configure variables in Railway as needed (see Configuration).

Option B — Dockerfile
1. Select Docker as the deployment method.
2. Ensure `PORT` is set by the platform; the image runs `uvicorn` binding to `$PORT`.

## Testing

```
pytest
pytest --cov=. --cov-report=html
```

## Project Structure (abridged)

```
app/                 FastAPI application
core/                Exchange‑agnostic core (schemas, interface, manager, config, logging)
exchanges/           Connectors: binance/, hyperliquid/, bybit/
tests/               Unit and integration tests
Procfile             Process definition for platforms like Railway
Dockerfile           Container build (optional)
requirements.txt     Python dependencies
```

## License

MIT License. See `LICENSE` for details.
