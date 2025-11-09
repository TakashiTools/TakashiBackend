"""
Bybit Exchange Connector

This module implements the ExchangeInterface for Bybit.

Bybit is a major cryptocurrency derivatives exchange offering:
- Comprehensive REST API for historical data
- WebSocket streams for real-time data
- Support for OHLC, open interest, funding rates, trades, and liquidations
- Multiple product types: spot, linear (USDT), inverse contracts

API Documentation:
    https://bybit-exchange.github.io/docs/v5/intro

Endpoints Used:
    REST (GET requests to https://api.bybit.com/v5/market):
        - /kline - Historical candlestick data
        - /funding/history - Historical funding rates
        - /open-interest - Open interest data
        - /tickers - Market tickers

    WebSocket (wss://stream.bybit.com/v5/public/linear):
        - kline streams: kline.{interval}.{symbol}
        - trade streams: publicTrade.{symbol}
        - liquidation streams: allLiquidation.{symbol}

Limitations:
    - Different WebSocket URLs for different product types
    - Symbol format varies by product type (BTCUSDT vs BTCUSD)
    - Rate limits apply to both REST and WebSocket

Structure:
    exchanges/bybit/
    ├── __init__.py          # This file (BybitExchange class)
    ├── api_client.py        # REST API client with aiohttp
    └── ws_client.py         # WebSocket streaming client
"""

from typing import List, AsyncGenerator, Optional
from core.exchange_interface import ExchangeInterface
from core.schemas import OHLC, OpenInterest, FundingRate, Liquidation, LargeTrade
from core.logging import logger, get_logger
from core.utils.time import to_utc_datetime, current_utc_timestamp
from .api_client import BybitAPIClient
from .ws_client import BybitWSClient


class BybitExchange(ExchangeInterface):
    """
    Bybit Exchange Connector

    This class implements the ExchangeInterface for Bybit.
    It provides both REST API methods for historical data and WebSocket methods
    for real-time streaming.

    Attributes:
        name: Exchange identifier ("bybit")
        capabilities: Dictionary of supported features
        base_url: Bybit API base URL
        ws_url: Bybit WebSocket stream URL

    Example:
        >>> exchange = BybitExchange()
        >>> await exchange.initialize()
        >>>
        >>> # Fetch historical OHLC
        >>> ohlc = await exchange.get_ohlc("BTCUSDT", "1h", limit=100)
        >>>
        >>> # Stream live candlesticks
        >>> async for candle in exchange.stream_ohlc("BTCUSDT", "1m"):
        ...     print(f"Price: {candle.close}")
        >>>
        >>> await exchange.shutdown()

    Notes:
        - All data is normalized to our standard schemas
        - Timestamps are converted to UTC datetime
        - WebSocket reconnection is handled automatically
        - Supports all major features: OHLC, funding, OI, trades, liquidations
    """

    # ============================================
    # Class Attributes
    # ============================================

    name = "bybit"

    capabilities = {
        "ohlc": True,
        "funding_rate": True,
        "open_interest": True,
        "liquidations": True,  # Supported by Bybit
        "large_trades": True
    }

    # ============================================
    # Initialization
    # ============================================

    def __init__(self):
        """
        Initialize the Bybit exchange connector.

        Sets up the API endpoints and prepares for connection.
        Actual network connections are established in initialize().
        """
        # API endpoints
        self.base_url = "https://api.bybit.com/v5/market"
        self.ws_url = "wss://stream.bybit.com/v5/public/linear"

        # API client (will be created in initialize())
        self.client: Optional[BybitAPIClient] = None

        # Logger
        self.logger = get_logger(__name__)

        self.logger.debug(f"BybitExchange created (base_url={self.base_url})")

    async def initialize(self) -> None:
        """
        Initialize the Bybit connector.

        Sets up:
            - BybitAPIClient for REST API calls
            - aiohttp ClientSession (via API client)
            - Connection pooling

        This method is called by ExchangeManager.initialize_all()
        """
        self.logger.info("Initializing Bybit exchange connector...")

        # Create and initialize API client
        self.client = BybitAPIClient()
        await self.client.__aenter__()

        self.logger.info("✓ Bybit exchange connector initialized")

    async def shutdown(self) -> None:
        """
        Shutdown the Bybit connector gracefully.

        Closes:
            - BybitAPIClient (aiohttp session)
            - All active WebSocket connections
            - Background tasks

        Notes:
            - WebSocket connections are managed via async generators
            - When stream generators are closed, cleanup happens automatically
        """
        self.logger.info("Shutting down Bybit exchange connector...")

        # Close API client
        if self.client:
            await self.client.__aexit__(None, None, None)

        self.logger.info("✓ Bybit exchange connector shut down")

    async def health_check(self) -> bool:
        """
        Check if Bybit API is accessible.

        Returns:
            bool: True if API is reachable, False otherwise

        Notes:
            - Makes a lightweight call to fetch server time
            - Minimal data transfer for health check
        """
        self.logger.debug("Running Bybit health check...")

        try:
            if self.client:
                # Try to fetch server time (lightweight endpoint)
                result = await self.client.get_server_time()
                return result is not None
            return False
        except Exception as e:
            self.logger.error(f"Bybit health check failed: {e}")
            return False

    # ============================================
    # REST API Methods
    # ============================================

    async def get_ohlc(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[OHLC]:
        """
        Fetch historical OHLC data from Bybit.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT")
            interval: Candlestick interval (e.g., "1m", "5m", "1h", "1d")
            limit: Number of candles to fetch (max 1000)
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)

        Returns:
            List[OHLC]: List of candlestick data

        Bybit Endpoint:
            GET /v5/market/kline

        Notes:
            - If start_time/end_time not provided, fetches most recent candles
            - Symbol should be pair format (BTCUSDT) for linear contracts
            - Data is sorted by timestamp (oldest first)

        Example:
            >>> ohlc = await exchange.get_ohlc("BTCUSDT", "1h", limit=100)
            >>> print(f"Latest close: ${ohlc[-1].close:,.2f}")
        """
        return await self.client.get_historical_ohlc(symbol, interval, limit, start_time, end_time)

    async def get_open_interest(self, symbol: str) -> Optional[OpenInterest]:
        """
        Get current open interest for a symbol.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT")

        Returns:
            OpenInterest: Current open interest data, or None if not found

        Bybit Endpoint:
            GET /v5/market/open-interest

        Example:
            >>> oi = await exchange.get_open_interest("BTCUSDT")
            >>> if oi:
            ...     print(f"OI: {oi.open_interest:,.2f} BTC")
        """
        return await self.client.get_open_interest(symbol)

    async def get_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """
        Get current funding rate for a perpetual symbol.

        Args:
            symbol: Perpetual symbol (e.g., "BTCUSDT", "ETHUSDT")

        Returns:
            FundingRate: Latest funding rate, or None if not found

        Bybit Endpoint:
            GET /v5/market/funding/history

        Example:
            >>> fr = await exchange.get_funding_rate("BTCUSDT")
            >>> if fr:
            ...     print(f"Funding rate: {fr.funding_rate * 100:.4f}%")
        """
        # Get latest funding rate (limit=1 returns most recent)
        funding_rates = await self.client.get_funding_rate(symbol, limit=1)
        return funding_rates[0] if funding_rates else None

    # ============================================
    # WebSocket Streaming Methods
    # ============================================

    async def stream_ohlc(
        self,
        symbol: str,
        interval: str
    ) -> AsyncGenerator[OHLC, None]:
        """
        Stream live OHLC updates via WebSocket.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT")
            interval: Candlestick interval (e.g., "1m", "5m", "1h")

        Yields:
            OHLC: Live candlestick updates

        Bybit WebSocket:
            wss://stream.bybit.com/v5/public/linear
            Subscribe: {"op": "subscribe", "args": ["kline.1.BTCUSDT"]}

        Example:
            >>> async for candle in exchange.stream_ohlc("BTCUSDT", "1m"):
            ...     print(f"Close: ${candle.close:,.2f}")
        """
        self.logger.info(f"[Bybit] Starting OHLC stream: {symbol} {interval}")

        ws_client = BybitWSClient()
        async for ohlc in ws_client.stream_ohlc(symbol, interval):
            yield ohlc

    async def stream_liquidations(self, symbol: str) -> AsyncGenerator[Liquidation, None]:
        """
        Stream liquidation events via WebSocket.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT")

        Yields:
            Liquidation: Live liquidation events

        Bybit WebSocket:
            wss://stream.bybit.com/v5/public/linear
            Subscribe: {"op": "subscribe", "args": ["allLiquidation.BTCUSDT"]}

        Example:
            >>> async for liq in exchange.stream_liquidations("BTCUSDT"):
            ...     print(f"{liq.side} liquidation: {liq.quantity} @ {liq.price}")
        """
        self.logger.info(f"[Bybit] Starting liquidation stream: {symbol}")

        ws_client = BybitWSClient()
        async for liquidation in ws_client.stream_liquidations(symbol):
            yield liquidation

    async def stream_large_trades(self, symbol: str) -> AsyncGenerator[LargeTrade, None]:
        """
        Stream large trades via WebSocket.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT")

        Yields:
            LargeTrade: Significant trade events

        Bybit WebSocket:
            wss://stream.bybit.com/v5/public/linear
            Subscribe: {"op": "subscribe", "args": ["publicTrade.BTCUSDT"]}

        Notes:
            - Streams ALL trades (no server-side filtering by size)
            - Consider filtering by value threshold on client side if needed

        Example:
            >>> async for trade in exchange.stream_large_trades("BTCUSDT"):
            ...     if trade.value > 100000:  # $100k+ trades
            ...         print(f"Large trade: {trade.side} ${trade.value:,.0f}")
        """
        self.logger.info(f"[Bybit] Starting trade stream: {symbol}")

        # Use the same global threshold as Binance for consistency
        from core.config import settings
        min_trade_value_usd = settings.large_trade_threshold_usd

        ws_client = BybitWSClient()
        async for trade in ws_client.stream_trades(symbol):
            # Filter: only yield trades above threshold
            try:
                if float(trade.value) < float(min_trade_value_usd):
                    continue
            except Exception:
                # If value not parsable, be conservative and skip
                continue
            yield trade

    # ============================================
    # Helper Methods
    # ============================================

    def _interval_to_milliseconds(self, interval: str) -> int:
        """
        Convert interval string to milliseconds.

        Args:
            interval: Interval string (e.g., "1m", "5m", "1h", "1d")

        Returns:
            int: Interval in milliseconds

        Example:
            >>> self._interval_to_milliseconds("1m")
            60000
            >>> self._interval_to_milliseconds("1h")
            3600000
        """
        unit = interval[-1]
        value = int(interval[:-1])

        if unit == 'm':
            return value * 60 * 1000
        elif unit == 'h':
            return value * 60 * 60 * 1000
        elif unit == 'd':
            return value * 24 * 60 * 60 * 1000
        else:
            self.logger.warning(f"Unknown interval unit: {unit}, defaulting to 1 minute")
            return 60 * 1000
