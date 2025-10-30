"""
Binance WebSocket Client

This module provides async WebSocket streaming for Binance Futures real-time data.
It handles:
- WebSocket connections with automatic reconnection
- Message parsing and validation
- Exponential backoff on failures
- Graceful shutdown
- Data normalization to our schemas

Supported Streams:
    - Kline/Candlestick: {symbol}@kline_{interval}
    - Force Liquidations: {symbol}@forceOrder
    - Aggregate Trades: {symbol}@aggTrade
    - Mark Price: {symbol}@markPrice (funding updates)

WebSocket Documentation:
    https://binance-docs.github.io/apidocs/futures/en/#websocket-market-streams

Usage:
    async with BinanceWebSocketClient("BTCUSDT", "kline_1m") as client:
        async for message in client.listen():
            print(message)
"""

import aiohttp
import asyncio
import json
from typing import AsyncGenerator, Dict, Any, Optional
from core.logging import get_logger


class BinanceWebSocketClient:
    """
    Async WebSocket client for Binance Futures streams.

    This client provides low-level WebSocket connectivity with automatic
    reconnection and error handling. It yields raw JSON messages from
    Binance that need to be normalized by the caller.

    Attributes:
        BASE_URL: Binance Futures WebSocket base URL
        symbol: Trading pair (lowercase, e.g., "btcusdt")
        stream: Stream type (e.g., "kline_1m", "forceOrder")
        session: aiohttp ClientSession for WebSocket
        ws: Active WebSocket connection
        logger: Logger instance
        max_reconnect_delay: Maximum delay between reconnection attempts (seconds)

    Example:
        >>> async with BinanceWebSocketClient("BTCUSDT", "kline_1m") as client:
        ...     async for msg in client.listen():
        ...         print(f"Event: {msg['e']}")

    Notes:
        - Symbol is automatically lowercased (Binance requirement)
        - Reconnects automatically with exponential backoff
        - Use as async context manager for proper cleanup
    """

    BASE_URL = "wss://fstream.binance.com/ws"

    def __init__(
        self,
        symbol: str,
        stream: str,
        max_reconnect_delay: int = 30
    ):
        """
        Initialize WebSocket client.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            stream: Stream type (e.g., "kline_1m", "forceOrder", "aggTrade")
            max_reconnect_delay: Max seconds to wait between reconnects (default: 30)
        """
        self.symbol = symbol.lower()  # Binance requires lowercase
        self.stream = stream
        self.max_reconnect_delay = max_reconnect_delay

        # Connection state
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._is_running = False
        self._reconnect_attempt = 0

        self.logger = get_logger(__name__)

    # ============================================
    # Context Manager for Session Management
    # ============================================

    async def __aenter__(self):
        """
        Enter async context - creates HTTP session.

        Returns:
            Self for use in async with statement
        """
        self.session = aiohttp.ClientSession()
        self._is_running = True
        self.logger.debug(f"BinanceWebSocketClient session created for {self.symbol}@{self.stream}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit async context - closes WebSocket and session.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        self._is_running = False
        await self.close()
        self.logger.debug(f"BinanceWebSocketClient session closed for {self.symbol}@{self.stream}")

    # ============================================
    # WebSocket Connection Management
    # ============================================

    async def connect(self) -> None:
        """
        Establish WebSocket connection to Binance.

        Raises:
            RuntimeError: If session not initialized
            aiohttp.ClientError: If connection fails

        Notes:
            - Constructs URL from symbol and stream
            - Sets _reconnect_attempt to 0 on success
        """
        if not self.session:
            raise RuntimeError("Client session not initialized. Use 'async with' statement.")

        url = f"{self.BASE_URL}/{self.symbol}@{self.stream}"
        self.logger.info(f"Connecting to {url}")

        try:
            self.ws = await self.session.ws_connect(
                url,
                heartbeat=30,  # Send ping every 30 seconds
                timeout=aiohttp.ClientTimeout(total=10)
            )
            self._reconnect_attempt = 0
            self.logger.info(f"✓ Connected to {self.symbol}@{self.stream}")

        except Exception as e:
            self.logger.error(f"Failed to connect to {url}: {e}")
            raise

    async def close(self) -> None:
        """
        Close WebSocket connection and session gracefully.

        Notes:
            - Safe to call multiple times
            - Closes both WebSocket and HTTP session
        """
        if self.ws and not self.ws.closed:
            await self.ws.close()
            self.logger.debug(f"WebSocket closed for {self.symbol}@{self.stream}")

        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.debug(f"Session closed for {self.symbol}@{self.stream}")

    # ============================================
    # Message Streaming with Auto-Reconnect
    # ============================================

    async def listen(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Listen for WebSocket messages with automatic reconnection.

        This is the main streaming method. It handles:
        - Automatic reconnection on disconnect
        - Exponential backoff (1s → 2s → 4s → ... → max_reconnect_delay)
        - Message parsing and validation
        - Graceful shutdown

        Yields:
            Dict[str, Any]: Parsed JSON message from Binance

        Raises:
            RuntimeError: If session not initialized

        Reconnection Strategy:
            - Attempt 1: Wait 1 second
            - Attempt 2: Wait 2 seconds
            - Attempt 3: Wait 4 seconds
            - Attempt N: Wait min(2^(N-1), max_reconnect_delay) seconds

        Message Types:
            - WSMsgType.TEXT: JSON data (yielded)
            - WSMsgType.PING/PONG: Heartbeat (handled automatically)
            - WSMsgType.CLOSED: Connection closed (triggers reconnect)
            - WSMsgType.ERROR: Error (triggers reconnect)

        Example:
            >>> async for msg in client.listen():
            ...     if msg.get("e") == "kline":
            ...         print(f"New candle: {msg['k']['c']}")
        """
        while self._is_running:
            try:
                # Connect if not already connected
                if not self.ws or self.ws.closed:
                    await self.connect()

                # Listen for messages
                async for msg in self.ws:
                    # Text message - parse and yield JSON
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                            self.logger.debug(f"Received message: {data.get('e', 'unknown')}")
                            yield data

                        except json.JSONDecodeError as e:
                            self.logger.error(f"Failed to parse JSON: {msg.data[:100]}... Error: {e}")
                            continue

                    # Connection closed
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        self.logger.warning(f"WebSocket closed: {msg.data}")
                        break

                    # Error
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        self.logger.error(f"WebSocket error: {msg.data}")
                        break

                    # Ping/Pong (handled automatically by aiohttp)
                    else:
                        self.logger.debug(f"Received message type: {msg.type}")

            except asyncio.CancelledError:
                self.logger.info("WebSocket listener cancelled")
                break

            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")

            # Reconnect logic with exponential backoff
            if self._is_running:
                self._reconnect_attempt += 1
                delay = min(2 ** (self._reconnect_attempt - 1), self.max_reconnect_delay)
                self.logger.warning(
                    f"Reconnecting in {delay}s... (attempt {self._reconnect_attempt})"
                )
                await asyncio.sleep(delay)

        # Cleanup on exit
        self.logger.info(f"WebSocket listener stopped for {self.symbol}@{self.stream}")


# ============================================
# Convenience Stream Builders
# ============================================

def create_kline_stream(symbol: str, interval: str) -> BinanceWebSocketClient:
    """
    Create a WebSocket client for kline/candlestick streaming.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        interval: Kline interval (e.g., "1m", "5m", "1h", "1d")

    Returns:
        BinanceWebSocketClient configured for kline stream

    Example:
        >>> async with create_kline_stream("BTCUSDT", "1m") as client:
        ...     async for msg in client.listen():
        ...         print(msg["k"]["c"])  # Close price
    """
    return BinanceWebSocketClient(symbol, f"kline_{interval}")


def create_liquidation_stream(symbol: str) -> BinanceWebSocketClient:
    """
    Create a WebSocket client for liquidation event streaming.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")

    Returns:
        BinanceWebSocketClient configured for forceOrder stream

    Example:
        >>> async with create_liquidation_stream("BTCUSDT") as client:
        ...     async for msg in client.listen():
        ...         print(f"Liquidation: {msg['o']['q']} @ {msg['o']['p']}")
    """
    return BinanceWebSocketClient(symbol, "forceOrder")


def create_trade_stream(symbol: str) -> BinanceWebSocketClient:
    """
    Create a WebSocket client for aggregate trade streaming.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")

    Returns:
        BinanceWebSocketClient configured for aggTrade stream

    Example:
        >>> async with create_trade_stream("BTCUSDT") as client:
        ...     async for msg in client.listen():
        ...         print(f"Trade: {msg['q']} @ {msg['p']}")
    """
    return BinanceWebSocketClient(symbol, "aggTrade")


def create_mark_price_stream(symbol: str) -> BinanceWebSocketClient:
    """
    Create a WebSocket client for mark price and funding rate streaming.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")

    Returns:
        BinanceWebSocketClient configured for markPrice stream

    Notes:
        - Updates every 3 seconds
        - Includes next funding rate and time

    Example:
        >>> async with create_mark_price_stream("BTCUSDT") as client:
        ...     async for msg in client.listen():
        ...         print(f"Funding: {msg['r']} (next: {msg['T']})")
    """
    return BinanceWebSocketClient(symbol, "markPrice")
