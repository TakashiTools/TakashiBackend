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
from typing import List, Optional
from contextlib import asynccontextmanager

from core.exchange_manager import ExchangeManager
from core.schemas import OHLC, OpenInterest, FundingRate
from core.logging import logger
from core.config import settings, validate_configuration


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
        logger.info("=== Started Successfully ===")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("=== Shutting Down ===")
    try:
        await manager.shutdown_all()
        logger.info("=== Shutdown Complete ===")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# ============================================
# FastAPI Application
# ============================================

app = FastAPI(
    title="ITA Multi-Exchange Market Data API",
    description=(
        "Unified REST and WebSocket API for cryptocurrency market data.\n\n"
        "**Supported Exchanges:** Binance Futures (USD-M), Hyperliquid\n\n"
        "## REST Endpoints\n"
        "- `GET /{exchange}/ohlc/{symbol}/{interval}` - Historical candlestick data\n"
        "- `GET /{exchange}/oi/{symbol}` - Current open interest\n"
        "- `GET /{exchange}/oi-hist/{symbol}` - Historical open interest\n"
        "- `GET /{exchange}/funding/{symbol}` - Current funding rate\n"
        "- `GET /{exchange}/funding-hist/{symbol}` - Historical funding rates\n"
        "- `GET /exchanges` - List supported exchanges\n"
        "- `GET /health` - Health check\n\n"
        "## WebSocket Streams\n"
        "Pattern: `ws://localhost:8000/ws/{exchange}/{symbol}/{stream}`\n\n"
        "**Available:**\n"
        "- `ohlc?interval=1m` - Live candlesticks\n"
        "- `large_trades` - Large trade events\n"
        "- `liquidations` - Liquidation events (Binance only)\n\n"
        "**Examples:**\n"
        "```\n"
        "ws://localhost:8000/ws/binance/BTCUSDT/ohlc?interval=1m\n"
        "ws://localhost:8000/ws/hyperliquid/BTC/large_trades\n"
        "```"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

manager = ExchangeManager()  # Global exchange manager


# ============================================
# System Endpoints
# ============================================

@app.get("/", tags=["System"])
async def root():
    """API information and available exchanges."""
    return {
        "name": "ITA Multi-Exchange Market Data API",
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

    Note: Only supported by exchanges with historical OI endpoints (e.g., Binance).

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
