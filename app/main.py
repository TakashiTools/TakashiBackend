"""
FastAPI Application - Multi-Exchange Market Data API

Provides unified REST and WebSocket access to cryptocurrency market data.

Supported Exchanges:
    - Binance Futures (USD-M)
    - Hyperliquid

Features:
    - OHLC/Candlestick data (historical + live streaming)
    - Open Interest (current + historical)
    - Funding Rates (current + historical)
    - Large trades and liquidations (exchange-dependent)

Usage:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Docs:
    - Swagger: http://localhost:8000/docs
    - ReDoc: http://localhost:8000/redoc
"""

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from contextlib import asynccontextmanager
import asyncio
import httpx

from core.exchange_manager import ExchangeManager
from core.schemas import OHLC, OpenInterest, FundingRate
from core.schemas import PredictedFunding
from core.logging import logger
from core.config import settings, validate_configuration
from core.utils.time import to_utc_datetime
from exchanges.binance.ws_client import create_kline_stream
from services.event_bus import bus
from services.all_liquidations import get_all_liquidations_service
from services.oi_vol_monitor import get_oi_vol_monitor
from services.all_large_trades import get_all_large_trades_service


# ============================================
# Lifespan Management
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    # Startup
    logger.info("=== Application Starting ===")
    try:
        validate_configuration()
        await manager.initialize_all()
        # Start background services
        try:
            # All-exchange liquidations aggregator
            await get_all_liquidations_service(min_value_usd=50_000.0).start()
            # Binance OI/Volume monitor
            await get_oi_vol_monitor().start()
            # All-exchange large trades aggregator
            await get_all_large_trades_service().start()
        except Exception as svc_err:
            logger.error(f"Background services failed to start: {svc_err}")
        logger.info("=== Started Successfully ===")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("=== Shutting Down ===")
    try:
        # Stop background services
        try:
            await get_all_liquidations_service().stop()
        except Exception as svc_stop_err:
            logger.error(f"Error stopping AllLiquidationsService: {svc_stop_err}")
        try:
            await get_oi_vol_monitor().stop()
        except Exception as svc_stop_err:
            logger.error(f"Error stopping OIVolMonitor: {svc_stop_err}")
        try:
            await get_all_large_trades_service().stop()
        except Exception as svc_stop_err:
            logger.error(f"Error stopping AllLargeTradesService: {svc_stop_err}")
        await manager.shutdown_all()
        logger.info("=== Shutdown Complete ===")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# ============================================
# FastAPI Application
# ============================================

app = FastAPI(
    title="TAKASHI Multi-Exchange Market Data API",
    description=(
        "Unified REST and WebSocket API for cryptocurrency market data.\n\n"
        "**Supported Exchanges:** Binance Futures (USD-M), Hyperliquid\n\n"
        "## REST Endpoints\n"
        "- `GET /{exchange}/ohlc/{symbol}/{interval}` - Historical candlestick data\n"
        "- `GET /{exchange}/oi/{symbol}` - Current open interest\n"
        "- `GET /{exchange}/oi-hist/{symbol}` - Historical open interest (Binance only)\n"
        "- `GET /{exchange}/funding/{symbol}` - Current funding rate\n"
        "- `GET /{exchange}/funding-hist/{symbol}` - Historical funding rates\n"
        "- `GET /hyperliquid/predicted-funding` - Predicted funding across venues (optional ?coin=BTC)\n"
        "- `GET /multi/ohlc/{symbol}/{interval}` - OHLC from all exchanges\n"
        "- `GET /exchanges` - List supported exchanges\n"
        "- `GET /health` - Health check\n"
        "- `GET /coinmarketcap/categories` - CoinMarketCap categories proxy\n"
        "- `GET /coinmarketcap/category` - CoinMarketCap category details proxy\n"
        "- `GET /binance/tickers/24hr` - Binance 24h ticker data (all symbols)\n"
        "- `GET /binance/mark-prices` - Binance mark price/funding data (all symbols)\n"
        "- `GET /binance/klines/{symbol}/{interval}` - Binance klines (raw format)\n\n"
        "## WebSocket Streams\n"
        "\n"
        "**A) Per‑exchange streams (symbol‑scoped)**\n"
        "\n"
        "Pattern: `ws://{host}/ws/{exchange}/{symbol}/{stream}`\n"
        "- Streams:\n"
        "  - `ohlc` (requires query `interval`, e.g., `?interval=1m|5m|1h`)\n"
        "  - `large_trades`\n"
        "  - `liquidations` (only on exchanges that support it)\n"
        "- Examples:\n"
        "  - `ws://localhost:8000/ws/binance/BTCUSDT/ohlc?interval=1m`\n"
        "  - `ws://localhost:8000/ws/hyperliquid/BTC/large_trades`\n"
        "\n"
        "**B) Aggregated / derived streams (not symbol‑scoped)**\n"
        "- Aggregated liquidations (multi‑exchange firehose):\n"
        "  - `ws://{host}/ws/all/liquidations?min_value_usd=50000` (Binance, OKX, Bybit)\n"
        "  - Query: `min_value_usd` filters events by USD value per connection\n"
        "- OI / Volume spike alerts (Binance‑wide):\n"
        "  - `ws://{host}/ws/oi-vol?timeframes=5m,15m,1h`\n"
        "  - Query: `timeframes` selects which TFs the client receives (comma‑separated)\n"
        "- Aggregated large trades (multi‑exchange, thresholded):\n"
        "  - `ws://{host}/ws/all/large_trades?min_value_usd=100000`\n"
        "- Examples:\n"
        "  - `ws://localhost:8000/ws/all/liquidations?min_value_usd=50000`\n"
        "  - `ws://localhost:8000/ws/oi-vol?timeframes=5m,15m`\n"
        "  - `ws://localhost:8000/ws/all/large_trades?min_value_usd=100000`\n"
        "\n"
        "All WebSocket messages are JSON objects using our Pydantic schemas.\n"
        "Clients should handle reconnects on disconnect."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS (allow your frontend origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://takash-psi.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

manager = ExchangeManager()  # Global exchange manager


# ============================================
# System Endpoints
# ============================================

@app.get("/", tags=["System"])
async def root():
    """API information and available exchanges."""
    return {
        "name": "TAKASHI Multi-Exchange Market Data API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "exchanges": manager.list_exchanges()
    }


@app.get("/health", tags=["System"])
async def health_check():
    """Health check - tests connectivity to all exchanges."""
    health = await manager.health_check_all()
    return {
        "status": "healthy" if all(health.values()) else "degraded",
        "exchanges": health
    }


@app.get("/exchanges", tags=["System"])
async def list_exchanges():
    """List all supported exchanges and their capabilities."""
    return {
        "exchanges": [
            {
                "name": name,
                "capabilities": manager.get_exchange_capabilities(name)
            }
            for name in manager.list_exchanges()
        ]
    }

@app.get("/ws-catalog", tags=["System"])
async def ws_catalog():
    """
    List available WebSocket endpoints and patterns.

    Note: WebSocket routes are not part of the OpenAPI/Swagger spec,
    so they don't appear as operations under /docs. This endpoint
    documents them for clients.
    """
    return {
        "per_exchange_pattern": "ws://{host}/ws/{exchange}/{symbol}/{stream}",
        "streams": {
            "ohlc": "Live candlesticks (requires ?interval=1m|5m|...)",
            "large_trades": "Large trade events",
            "liquidations": "Liquidation events (exchange-dependent)"
        },
        "aggregated": [
            {
                "path": "/ws/all/liquidations",
                "query": {"min_value_usd": "Minimum USD value filter (e.g., 50000)"},
                "description": "Aggregated liquidations from Binance/OKX/Bybit"
            },
            {
                "path": "/ws/all/large_trades",
                "query": {"min_value_usd": "Minimum USD value filter (e.g., 100000)"},
                "description": "Aggregated large trades from Binance/Bybit/Hyperliquid"
            },
            {
                "path": "/ws/oi-vol",
                "query": {"timeframes": "Comma-separated TFs (e.g., 5m,15m,1h)"},
                "description": "Binance OI/Volume spike alerts"
            },
            {
                "path": "/ws/binance/multi/ohlc",
                "query": {"interval": "Candle interval (1m, 5m, 15m, 1h, etc.)"},
                "description": "Multi-symbol OHLC stream (subscribe via JSON messages: {action: 'subscribe', symbols: [...]})",
                "note": "Allows subscribing to multiple symbols over single connection to reduce browser connection limits"
            }
        ],
        "examples": [
            "ws://localhost:8000/ws/binance/BTCUSDT/ohlc?interval=1m",
            "ws://localhost:8000/ws/hyperliquid/BTC/large_trades",
            "ws://localhost:8000/ws/all/liquidations?min_value_usd=50000",
            "ws://localhost:8000/ws/oi-vol?timeframes=5m,15m",
            "ws://localhost:8000/ws/all/large_trades?min_value_usd=100000",
            "ws://localhost:8000/ws/binance/multi/ohlc?interval=15m"
        ]
    }


# ============================================
# Aggregated Market Data Endpoints
# NOTE: must be defined BEFORE generic '/{exchange}/...' routes
#       to avoid being captured by the dynamic path.
# ============================================

def _to_hyperliquid_coin(symbol: str) -> str:
    sym = symbol.upper()
    for suffix in ["USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP"]:
        if sym.endswith(suffix):
            return sym[: -len(suffix)]
    return sym


@app.get("/multi/ohlc/{symbol}/{interval}", tags=["Market Data"])
async def get_multi_ohlc(
    symbol: str,
    interval: str,
    limit: int = Query(default=200, ge=1, le=1000, description="Number of candles per exchange")
):
    """
    Get historical OHLC for the same market across all exchanges concurrently.

    Notes:
        - Binance, Bybit expect pair symbols (e.g., BTCUSDT)
        - Hyperliquid expects coin symbols (e.g., BTC) - mapped automatically
        - Returns a dict: { exchangeName: List[OHLC] }
    """
    exchanges = ["binance", "bybit", "hyperliquid"]
    tasks = {}

    for name in exchanges:
        if not manager.has_exchange(name):
            continue
        ex = manager.get_exchange(name)
        if not ex.supports("ohlc"):
            continue

        sym = symbol
        if name == "hyperliquid":
            sym = _to_hyperliquid_coin(symbol)

        tasks[name] = asyncio.create_task(ex.get_ohlc(sym, interval, limit))

    results = {}
    for name, task in tasks.items():
        try:
            results[name] = await task
        except Exception as e:
            logger.error(f"Multi OHLC error for {name}/{symbol}/{interval}: {e}")
            results[name] = []

    return results

@app.get("/hyperliquid/predicted-funding", response_model=List[PredictedFunding], tags=["Market Data"])
async def get_hl_predicted_funding(coin: Optional[str] = Query(default=None, description="Coin filter (e.g., BTC)")):
    """
    Predicted funding rates across venues (HlPerp, BinPerp, BybitPerp) from Hyperliquid.

    Optional query param ?coin=BTC to filter a single coin.
    """
    try:
        ex = manager.get_exchange("hyperliquid")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        data = await ex.get_predicted_funding(coin)
        return data
    except Exception as e:
        logger.error(f"Predicted funding (Hyperliquid) error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch predicted funding")


# ============================================
# Market Data Endpoints
# ============================================

@app.get("/{exchange}/ohlc/{symbol}/{interval}", response_model=List[OHLC], tags=["Market Data"])
async def get_ohlc(
    exchange: str,
    symbol: str,
    interval: str,
    limit: int = Query(default=500, ge=1, le=1500, description="Number of candles")
):
    """
    Get historical OHLC/candlestick data.

    Examples:
        GET /binance/ohlc/BTCUSDT/1h?limit=100
        GET /hyperliquid/ohlc/BTC/1m?limit=50
    """
    try:
        ex = manager.get_exchange(exchange)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not ex.supports("ohlc"):
        raise HTTPException(status_code=404, detail=f"{exchange} does not support OHLC")

    try:
        return await ex.get_ohlc(symbol, interval, limit)
    except Exception as e:
        logger.error(f"OHLC error {exchange}/{symbol}/{interval}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch OHLC: {str(e)}")


@app.get("/{exchange}/oi/{symbol}", response_model=OpenInterest, tags=["Market Data"])
async def get_open_interest(exchange: str, symbol: str):
    """
    Get current open interest.

    Examples:
        GET /binance/oi/BTCUSDT
        GET /hyperliquid/oi/BTC
    """
    try:
        ex = manager.get_exchange(exchange)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not ex.supports("open_interest"):
        raise HTTPException(status_code=404, detail=f"{exchange} does not support OI")

    try:
        return await ex.get_open_interest(symbol)
    except Exception as e:
        logger.error(f"OI error {exchange}/{symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch OI: {str(e)}")


@app.get("/{exchange}/oi-hist/{symbol}", response_model=List[OpenInterest], tags=["Market Data"])
async def get_open_interest_hist(
    exchange: str,
    symbol: str,
    period: str = Query(default="5m", description="5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d"),
    limit: int = Query(default=30, ge=1, le=500, description="Number of records")
):
    """
    Get historical open interest data.

    Note: Only Binance supports historical open interest.

    Example:
        GET /binance/oi-hist/BTCUSDT?period=1h&limit=24
    """
    try:
        ex = manager.get_exchange(exchange)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        return await ex.client.get_open_interest_hist(symbol, period, limit)
    except AttributeError:
        raise HTTPException(status_code=404, detail=f"{exchange} doesn't support OI history")
    except Exception as e:
        logger.error(f"OI history error {exchange}/{symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch OI history: {str(e)}")


@app.get("/{exchange}/funding/{symbol}", response_model=FundingRate, tags=["Market Data"])
async def get_funding_rate(exchange: str, symbol: str):
    """
    Get current funding rate.

    Examples:
        GET /binance/funding/BTCUSDT
        GET /hyperliquid/funding/BTC
    """
    try:
        ex = manager.get_exchange(exchange)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not ex.supports("funding_rate"):
        raise HTTPException(status_code=404, detail=f"{exchange} doesn't support funding rates")

    try:
        data = await ex.get_funding_rate(symbol)
        if data is None:
            raise HTTPException(status_code=404, detail="No funding rate data")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Funding rate error {exchange}/{symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch funding rate: {str(e)}")


@app.get("/{exchange}/funding-hist/{symbol}", response_model=List[FundingRate], tags=["Market Data"])
async def get_funding_rate_hist(
    exchange: str,
    symbol: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Number of records")
):
    """
    Get historical funding rates.

    Examples:
        GET /binance/funding-hist/BTCUSDT?limit=50
        GET /hyperliquid/funding-hist/BTC?limit=100
    """
    try:
        ex = manager.get_exchange(exchange)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        return await ex.client.get_funding_rate(symbol, limit)
    except AttributeError:
        raise HTTPException(status_code=404, detail=f"{exchange} doesn't support funding history")
    except Exception as e:
        logger.error(f"Funding history error {exchange}/{symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch funding history: {str(e)}")


# ============================================
# Binance Proxy Endpoints (Raw Format)
# ============================================

BINANCE_API_BASE = "https://fapi.binance.com/fapi/v1"


@app.get("/binance/tickers/24hr", tags=["Binance Proxy"])
async def get_binance_tickers_24hr():
    """
    Proxy endpoint for Binance 24h ticker data (all symbols).
    
    Returns raw Binance ticker format for frontend compatibility.
    This endpoint bypasses CORS restrictions and provides centralized rate limiting.
    
    Example:
        GET /binance/tickers/24hr
    
    Returns: Array of ticker objects in Binance format
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BINANCE_API_BASE}/ticker/24hr",
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()  # Return raw Binance format
    except httpx.HTTPStatusError as e:
        # Forward Binance API errors
        error_detail = e.response.json() if e.response.headers.get("content-type") == "application/json" else e.response.text
        logger.error(f"Binance tickers API error: {e.response.status_code} - {error_detail}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=error_detail
        )
    except httpx.RequestError as e:
        logger.error(f"Binance API connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to Binance API: {str(e)}"
        )


@app.get("/binance/mark-prices", tags=["Binance Proxy"])
async def get_binance_mark_prices():
    """
    Proxy endpoint for Binance mark price and funding rate data (all symbols).
    
    Returns raw Binance mark price format for frontend compatibility.
    This endpoint returns mark price info for all symbols (no symbol parameter = all).
    
    Example:
        GET /binance/mark-prices
    
    Returns: Array of mark price objects in Binance format
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BINANCE_API_BASE}/premiumIndex",
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()  # Return raw Binance format
    except httpx.HTTPStatusError as e:
        # Forward Binance API errors
        error_detail = e.response.json() if e.response.headers.get("content-type") == "application/json" else e.response.text
        logger.error(f"Binance mark prices API error: {e.response.status_code} - {error_detail}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=error_detail
        )
    except httpx.RequestError as e:
        logger.error(f"Binance API connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to Binance API: {str(e)}"
        )


@app.get("/binance/klines/{symbol}/{interval}", tags=["Binance Proxy"])
async def get_binance_klines_raw(
    symbol: str,
    interval: str,
    limit: int = Query(500, ge=1, le=1500, description="Number of klines to return")
):
    """
    Proxy endpoint for Binance klines (raw format).
    
    Returns raw Binance klines array format for frontend compatibility.
    This is a proxy endpoint that returns the exact Binance format.
    
    Note: For normalized OHLC data, use /binance/ohlc/{symbol}/{interval} instead.
    
    Example:
        GET /binance/klines/BTCUSDT/5m?limit=12
    
    Returns: Array of kline arrays in Binance format [[openTime, open, high, low, close, volume, ...], ...]
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BINANCE_API_BASE}/klines",
                params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()  # Return raw Binance format
    except httpx.HTTPStatusError as e:
        # Forward Binance API errors
        error_detail = e.response.json() if e.response.headers.get("content-type") == "application/json" else e.response.text
        logger.error(f"Binance klines API error: {e.response.status_code} - {error_detail}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=error_detail
        )
    except httpx.RequestError as e:
        logger.error(f"Binance API connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to Binance API: {str(e)}"
        )


# ============================================
# CoinMarketCap Proxy Endpoints
# ============================================

CMC_BASE_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency"


@app.get("/coinmarketcap/categories", tags=["External APIs"])
async def get_cmc_categories(
    start: int = Query(1, ge=1, description="Offset start (1-based index)"),
    limit: int = Query(100, ge=1, le=5000, description="Number of results to return")
):
    """
    Proxy endpoint for CoinMarketCap Categories API.
    
    Returns information about all coin categories available on CoinMarketCap.
    This endpoint bypasses CORS restrictions and securely handles the API key.
    
    Example:
        GET /coinmarketcap/categories?start=1&limit=100
    """
    if not settings.coinmarketcap_api_key:
        raise HTTPException(
            status_code=500,
            detail="CoinMarketCap API key not configured"
        )
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CMC_BASE_URL}/categories",
                params={"start": start, "limit": limit},
                headers={"X-CMC_PRO_API_KEY": settings.coinmarketcap_api_key},
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        # Forward CoinMarketCap API errors
        error_detail = e.response.json() if e.response.headers.get("content-type") == "application/json" else e.response.text
        raise HTTPException(
            status_code=e.response.status_code,
            detail=error_detail
        )
    except httpx.RequestError as e:
        logger.error(f"CoinMarketCap API connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to CoinMarketCap API: {str(e)}"
        )


@app.get("/coinmarketcap/category", tags=["External APIs"])
async def get_cmc_category(
    id: str = Query(..., description="Category ID (required)"),
    start: int = Query(1, ge=1, description="Offset start (1-based index)"),
    limit: int = Query(100, ge=1, le=1000, description="Number of coins to return")
):
    """
    Proxy endpoint for CoinMarketCap Category API.
    
    Returns detailed information about a single coin category including tokens.
    This endpoint bypasses CORS restrictions and securely handles the API key.
    
    Example:
        GET /coinmarketcap/category?id=605e2ce9d41eae1066535f7c&limit=100
    """
    if not settings.coinmarketcap_api_key:
        raise HTTPException(
            status_code=500,
            detail="CoinMarketCap API key not configured"
        )
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CMC_BASE_URL}/category",
                params={"id": id, "start": start, "limit": limit},
                headers={"X-CMC_PRO_API_KEY": settings.coinmarketcap_api_key},
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        # Forward CoinMarketCap API errors
        error_detail = e.response.json() if e.response.headers.get("content-type") == "application/json" else e.response.text
        raise HTTPException(
            status_code=e.response.status_code,
            detail=error_detail
        )
    except httpx.RequestError as e:
        logger.error(f"CoinMarketCap API connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to CoinMarketCap API: {str(e)}"
        )


# ============================================
# WebSocket Endpoints
# ============================================

@app.websocket("/ws/{exchange}/{symbol}/{stream}")
async def websocket_stream(
    websocket: WebSocket,
    exchange: str,
    symbol: str,
    stream: str,
    interval: str = Query(default="1m", description="Interval for OHLC (e.g., 1m, 5m, 1h)")
):
    """
    WebSocket streaming for real-time market data.

    Streams:
        - ohlc: Live candlesticks (requires ?interval=1m param)
        - liquidations: Liquidation events (exchange-dependent)
        - large_trades: Large trades

    Examples:
        ws://localhost:8000/ws/binance/BTCUSDT/ohlc?interval=1m
        ws://localhost:8000/ws/hyperliquid/BTC/large_trades
        ws://localhost:8000/ws/binance/ETHUSDT/liquidations

    All messages are JSON-serialized Pydantic models.
    Client should handle reconnection on disconnect.
    """
    await websocket.accept()
    logger.info(f"WS connected: {exchange}/{symbol}/{stream}")

    try:
        try:
            ex = manager.get_exchange(exchange)
        except ValueError as e:
            await websocket.close(code=1008, reason=str(e))
            return

        stream_methods = {
            "ohlc": lambda: ex.stream_ohlc(symbol, interval),
            "liquidations": lambda: ex.stream_liquidations(symbol),
            "large_trades": lambda: ex.stream_large_trades(symbol)
        }

        if stream not in stream_methods:
            await websocket.close(code=1008, reason=f"Invalid stream: {stream}")
            return

        if not ex.supports(stream.replace("_", "")):  # "large_trades" -> "largetrades"
            capability = {"ohlc": "ohlc", "liquidations": "liquidations", "large_trades": "large_trades"}[stream]
            if not ex.supports(capability):
                await websocket.close(code=1008, reason=f"{exchange} doesn't support {stream}")
                return

        logger.info(f"Starting {stream} for {exchange}/{symbol}")

        async for event in stream_methods[stream]():
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except Exception as e:
                logger.error(f"Send error: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"WS disconnected: {exchange}/{symbol}/{stream}")
    except Exception as e:
        logger.error(f"WS error {exchange}/{symbol}/{stream}: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass
    finally:
        logger.info(f"WS ended: {exchange}/{symbol}/{stream}")


# ============================================
# New WebSocket Endpoints (Aggregated Services)
# ============================================

@app.websocket("/ws/all/liquidations")
async def websocket_all_liquidations(
    websocket: WebSocket,
    min_value_usd: float = Query(default=5_000.0, description="Minimum USD value to forward to client")
):
    """
    Aggregated liquidation stream across multiple exchanges (Binance, OKX, Hyperliquid).

    Example:
        ws://localhost:8000/ws/all/liquidations?min_value_usd=50000
    """
    await websocket.accept()
    logger.info("WS connected: all/liquidations")
    queue = await bus.subscribe("liquidation")
    try:
        while True:
            try:
                event = await queue.get()
                # Per-connection filtering by USD value
                if float(event.get("value", 0)) < float(min_value_usd):
                    continue
                await websocket.send_json(event)
            except Exception as e:
                logger.error(f"[WS all/liquidations] send error: {e}")
                break
    except WebSocketDisconnect:
        logger.info("WS disconnected: all/liquidations")
    except Exception as e:
        logger.error(f"WS error all/liquidations: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass
    finally:
        await bus.unsubscribe("liquidation", queue)
        logger.info("WS ended: all/liquidations")


@app.websocket("/ws/oi-vol")
async def websocket_oi_vol(
    websocket: WebSocket,
    timeframes: str = Query(default="5m,15m,1h", description="Comma-separated TFs to include (5m,15m,1h)")
):
    """
    Binance OI/Volume spike alerts (z-score based).

    Example:
        ws://localhost:8000/ws/oi-vol?timeframes=5m,15m
    """
    await websocket.accept()
    logger.info("WS connected: oi-vol")
    allowed = {tf.strip() for tf in timeframes.split(",") if tf.strip()}
    queue = await bus.subscribe("oi_spike")
    try:
        while True:
            try:
                event = await queue.get()
                if event.get("timeframe") not in allowed:
                    continue
                await websocket.send_json(event)
            except Exception as e:
                logger.error(f"[WS oi-vol] send error: {e}")
                break
    except WebSocketDisconnect:
        logger.info("WS disconnected: oi-vol")
    except Exception as e:
        logger.error(f"WS error oi-vol: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass
    finally:
        await bus.unsubscribe("oi_spike", queue)
        logger.info("WS ended: oi-vol")

@app.websocket("/ws/all/large_trades")
async def websocket_all_large_trades(
    websocket: WebSocket,
    min_value_usd: float = Query(default=100_000.0, description="Minimum USD value to forward to client")
):
    """
    Aggregated large trades across Binance, Bybit, Hyperliquid.
    """
    await websocket.accept()
    logger.info("WS connected: all/large_trades")
    queue = await bus.subscribe("large_trade")
    try:
        while True:
            try:
                event = await queue.get()
                if float(event.get("value", 0)) < float(min_value_usd):
                    continue
                await websocket.send_json(event)
            except Exception as e:
                logger.error(f"[WS all/large_trades] send error: {e}")
                break
    except WebSocketDisconnect:
        logger.info("WS disconnected: all/large_trades")
    except Exception as e:
        logger.error(f"WS error all/large_trades: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass
    finally:
        await bus.unsubscribe("large_trade", queue)
        logger.info("WS ended: all/large_trades")


# ============================================
# Multi-Symbol OHLC WebSocket Endpoint
# ============================================

@app.websocket("/ws/binance/multi/ohlc")
async def websocket_multi_symbol_ohlc(
    websocket: WebSocket,
    interval: str = Query(..., description="Candle interval (1m, 5m, 15m, 1h, etc.)")
):
    """
    Aggregate OHLC stream for multiple symbols over single WebSocket connection.
    
    This endpoint allows subscribing to multiple symbols and receiving OHLC updates
    for all of them over a single WebSocket connection, reducing browser connection limits.
    
    Connection Flow:
    1. Client connects: ws://host/ws/binance/multi/ohlc?interval=15m
    2. Client sends subscription: {"action": "subscribe", "symbols": ["BTCUSDT", "ETHUSDT", ...]}
    3. Server streams OHLC updates for all subscribed symbols
    
    Client can dynamically add/remove symbols:
    - {"action": "subscribe", "symbols": ["ADAUSDT"]}
    - {"action": "unsubscribe", "symbols": ["BTCUSDT"]}
    
    Example:
        ws://localhost:8000/ws/binance/multi/ohlc?interval=15m
    """
    await websocket.accept()
    logger.info(f"WS connected: binance/multi/ohlc (interval={interval})")
    
    subscribed_symbols: set[str] = set()
    binance_connections: dict[str, asyncio.Task] = {}  # symbol -> task
    _is_running = True
    
    async def send_error(message: str, code: str, symbol: Optional[str] = None):
        """Send error message to client."""
        error_msg = {"type": "error", "message": message, "code": code}
        if symbol:
            error_msg["symbol"] = symbol
        try:
            await websocket.send_json(error_msg)
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    
    async def forward_symbol_updates(symbol: str, interval: str):
        """Forward OHLC updates from Binance for a single symbol."""
        try:
            async with create_kline_stream(symbol, interval) as ws_client:
                async for msg in ws_client.listen():
                    if not _is_running:
                        break
                    
                    # Validate message type
                    if msg.get("e") != "kline":
                        continue
                    
                    # Extract kline data
                    k = msg.get("k", {})
                    
                    # Normalize to OHLC schema
                    ohlc = OHLC(
                        exchange="binance",
                        symbol=symbol.upper(),
                        interval=interval,
                        timestamp=to_utc_datetime(k.get("t")),
                        open=float(k.get("o", 0)),
                        high=float(k.get("h", 0)),
                        low=float(k.get("l", 0)),
                        close=float(k.get("c", 0)),
                        volume=float(k.get("v", 0)),
                        quote_volume=float(k.get("q", 0)),
                        trades_count=int(k.get("n", 0)),
                        is_closed=bool(k.get("x", False))
                    )
                    
                    # Forward to client
                    try:
                        await websocket.send_json(ohlc.model_dump(mode="json"))
                    except Exception as e:
                        logger.error(f"Failed to send OHLC update for {symbol}: {e}")
                        break
                        
        except asyncio.CancelledError:
            logger.info(f"Symbol forwarder cancelled: {symbol}")
        except Exception as e:
            logger.error(f"Error forwarding updates for {symbol}: {e}")
            if _is_running:
                await send_error(f"Failed to subscribe to {symbol}", "SUBSCRIPTION_FAILED", symbol)
        finally:
            # Clean up connection
            if symbol in binance_connections:
                del binance_connections[symbol]
            subscribed_symbols.discard(symbol)
    
    async def handle_client_messages():
        """Handle incoming messages from client (subscribe/unsubscribe)."""
        try:
            while _is_running:
                try:
                    # Wait for message with timeout
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=300.0)
                    
                    action = data.get("action")
                    symbols = data.get("symbols", [])
                    
                    if action == "subscribe":
                        # Validate symbol count
                        new_count = len(subscribed_symbols) + len(symbols)
                        if new_count > settings.max_symbols_per_connection:
                            await send_error(
                                f"Too many symbols requested (max {settings.max_symbols_per_connection})",
                                "RATE_LIMIT"
                            )
                            continue
                        
                        # Subscribe to each symbol
                        for symbol in symbols:
                            symbol_upper = symbol.upper()
                            
                            # Validate symbol format (basic check)
                            if not symbol_upper.endswith("USDT"):
                                await send_error(f"Invalid symbol format: {symbol}", "INVALID_SYMBOL", symbol)
                                continue
                            
                            # Skip if already subscribed
                            if symbol_upper in subscribed_symbols:
                                continue
                            
                            # Start forwarding task for this symbol
                            task = asyncio.create_task(
                                forward_symbol_updates(symbol_upper, interval),
                                name=f"ohlc_{symbol_upper}"
                            )
                            binance_connections[symbol_upper] = task
                            subscribed_symbols.add(symbol_upper)
                            logger.info(f"Subscribed to {symbol_upper} (total: {len(subscribed_symbols)})")
                    
                    elif action == "unsubscribe":
                        # Unsubscribe from symbols
                        for symbol in symbols:
                            symbol_upper = symbol.upper()
                            
                            if symbol_upper in subscribed_symbols:
                                # Cancel the forwarding task
                                if symbol_upper in binance_connections:
                                    task = binance_connections[symbol_upper]
                                    task.cancel()
                                    try:
                                        await task
                                    except asyncio.CancelledError:
                                        pass
                                
                                subscribed_symbols.discard(symbol_upper)
                                logger.info(f"Unsubscribed from {symbol_upper} (remaining: {len(subscribed_symbols)})")
                    
                    else:
                        await send_error(f"Invalid action: {action}", "INVALID_ACTION")
                
                except asyncio.TimeoutError:
                    # No message received for 5 minutes - close connection
                    logger.info("No activity for 5 minutes, closing connection")
                    break
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error handling client message: {e}")
                    await send_error("Internal server error", "INTERNAL_ERROR")
                    break
        
        except WebSocketDisconnect:
            logger.info("Client disconnected from multi-symbol OHLC")
        finally:
            _is_running = False
    
    try:
        # Wait for initial subscription (with timeout)
        try:
            initial_data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)
            
            if initial_data.get("action") == "subscribe":
                symbols = initial_data.get("symbols", [])
                
                # Validate symbol count
                if len(symbols) > settings.max_symbols_per_connection:
                    await send_error(
                        f"Too many symbols requested (max {settings.max_symbols_per_connection})",
                        "RATE_LIMIT"
                    )
                    await websocket.close(code=1008, reason="Too many symbols")
                    return
                
                # Subscribe to all symbols
                for symbol in symbols:
                    symbol_upper = symbol.upper()
                    
                    # Validate symbol format
                    if not symbol_upper.endswith("USDT"):
                        await send_error(f"Invalid symbol format: {symbol}", "INVALID_SYMBOL", symbol)
                        continue
                    
                    # Start forwarding task
                    task = asyncio.create_task(
                        forward_symbol_updates(symbol_upper, interval),
                        name=f"ohlc_{symbol_upper}"
                    )
                    binance_connections[symbol_upper] = task
                    subscribed_symbols.add(symbol_upper)
                    logger.info(f"Initial subscription: {symbol_upper} (total: {len(subscribed_symbols)})")
            else:
                await send_error("First message must be a subscribe action", "INVALID_ACTION")
                await websocket.close(code=1008, reason="Invalid initial message")
                return
        
        except asyncio.TimeoutError:
            await send_error("No subscription received within 60 seconds", "TIMEOUT")
            await websocket.close(code=1008, reason="No subscription")
            return
        
        # Start message handler for subsequent subscribe/unsubscribe messages
        await handle_client_messages()
        
    except WebSocketDisconnect:
        logger.info("WS disconnected: binance/multi/ohlc")
    except Exception as e:
        logger.error(f"WS error binance/multi/ohlc: {e}")
    finally:
        # Cleanup: cancel all symbol forwarding tasks
        _is_running = False
        for symbol, task in binance_connections.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"WS ended: binance/multi/ohlc (subscribed to {len(subscribed_symbols)} symbols)")


# ============================================
# Error Handlers
# ============================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    return JSONResponse(status_code=404, content={"detail": "Not found", "path": str(request.url)})


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors."""
    logger.error(f"Internal error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
