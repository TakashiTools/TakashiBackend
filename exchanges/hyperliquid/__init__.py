"""
Hyperliquid Exchange Connector

This module implements the ExchangeInterface for Hyperliquid.

Hyperliquid is a decentralized perpetual futures exchange offering:
- Comprehensive REST API for historical data
- WebSocket streams for real-time data
- Support for OHLC, open interest, funding rates, and trades
- No liquidation stream available

API Documentation:
    https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api

Endpoints Used:
    REST (POST to https://api.hyperliquid.xyz/info):
        - {"type": "candleSnapshot"} - Historical candlestick data
        - {"type": "metaAndAssetCtxs"} - Open interest and market context
        - {"type": "fundingHistory"} - Historical funding rates
        - {"type": "predictedFundings"} - Predicted next funding

    WebSocket (wss://api.hyperliquid.xyz/ws):
        - Candle streams: {"type": "candle", "coin": "BTC", "interval": "1m"}
        - Trade streams: {"type": "trades", "coin": "BTC"}

Limitations:
    - Liquidation data: Not available
    - Symbol format: Uses coin symbols (BTC, ETH) not pairs (BTCUSDT)
    - Historical OHLC: Limited to ~5000 candles per request

Structure:
    exchanges/hyperliquid/
    ├── __init__.py          # This file (HyperliquidExchange class)
    ├── api_client.py        # REST API client with aiohttp
    └── ws_client.py         # WebSocket streaming client
"""

from typing import List, AsyncGenerator, Optional
from core.exchange_interface import ExchangeInterface
from core.schemas import OHLC, OpenInterest, FundingRate, Liquidation, LargeTrade
from core.logging import logger, get_logger
from core.utils.time import to_utc_datetime, current_utc_timestamp
from .api_client import HyperliquidAPIClient
from .ws_client import HyperliquidWSClient, create_candle_stream, create_trade_stream


class HyperliquidExchange(ExchangeInterface):
    """
    Hyperliquid Exchange Connector

    This class implements the ExchangeInterface for Hyperliquid.
    It provides both REST API methods for historical data and WebSocket methods
    for real-time streaming.

    Attributes:
        name: Exchange identifier ("hyperliquid")
        capabilities: Dictionary of supported features
        base_url: Hyperliquid API base URL
        ws_url: Hyperliquid WebSocket stream URL

    Example:
        >>> exchange = HyperliquidExchange()
        >>> await exchange.initialize()
        >>>
        >>> # Fetch historical OHLC
        >>> now = current_utc_timestamp(milliseconds=True)
        >>> start = now - (60 * 60 * 1000)  # 1 hour ago
        >>> ohlc = await exchange.get_ohlc("BTC", "1m", start_time=start, end_time=now)
        >>>
        >>> # Stream live candlesticks
        >>> async for candle in exchange.stream_ohlc("BTC", "1m"):
        ...     print(f"Price: {candle.close}")
        >>>
        >>> await exchange.shutdown()

    Notes:
        - All data is normalized to our standard schemas
        - Timestamps are converted to UTC datetime
        - WebSocket reconnection is handled automatically
        - Liquidations are not supported by Hyperliquid
    """

    # ============================================
    # Class Attributes
    # ============================================

    name = "hyperliquid"

    capabilities = {
        "ohlc": True,
        "funding_rate": True,
        "open_interest": True,
        "liquidations": False,  # Not supported by Hyperliquid
        "large_trades": True
    }

    # ============================================
    # Initialization
    # ============================================

    def __init__(self):
        """
        Initialize the Hyperliquid exchange connector.

        Sets up the API endpoints and prepares for connection.
        Actual network connections are established in initialize().
        """
        # API endpoints
        self.base_url = "https://api.hyperliquid.xyz/info"
        self.ws_url = "wss://api.hyperliquid.xyz/ws"

        # API client (will be created in initialize())
        self.client: Optional[HyperliquidAPIClient] = None

        # Logger
        self.logger = get_logger(__name__)

        self.logger.debug(f"HyperliquidExchange created (base_url={self.base_url})")

    async def initialize(self) -> None:
        """
        Initialize the Hyperliquid connector.

        Sets up:
            - HyperliquidAPIClient for REST API calls
            - aiohttp ClientSession (via API client)
            - Connection pooling

        This method is called by ExchangeManager.initialize_all()
        """
        self.logger.info("Initializing Hyperliquid exchange connector...")

        # Create and initialize API client
        self.client = HyperliquidAPIClient()
        await self.client.__aenter__()

        self.logger.info("✓ Hyperliquid exchange connector initialized")

    async def shutdown(self) -> None:
        """
        Shutdown the Hyperliquid connector gracefully.

        Closes:
            - HyperliquidAPIClient (aiohttp session)
            - All active WebSocket connections
            - Background tasks

        Notes:
            - WebSocket connections are managed via async generators
            - When stream generators are closed, cleanup happens automatically
        """
        self.logger.info("Shutting down Hyperliquid exchange connector...")

        # Close API client
        if self.client:
            await self.client.__aexit__(None, None, None)

        self.logger.info("✓ Hyperliquid exchange connector shut down")

    async def health_check(self) -> bool:
        """
        Check if Hyperliquid API is accessible.

        Returns:
            bool: True if API is reachable, False otherwise

        Notes:
            - Makes a lightweight call to fetch predicted funding
            - Minimal data transfer for health check
        """
        self.logger.debug("Running Hyperliquid health check...")

        try:
            if self.client:
                # Try to fetch predicted funding (lightweight endpoint)
                result = await self.client.get_predicted_funding()
                return len(result) > 0
            return False
        except Exception as e:
            self.logger.error(f"Hyperliquid health check failed: {e}")
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
        Fetch historical OHLC data from Hyperliquid.

        Args:
            symbol: Trading symbol (e.g., "BTC", "ETH")
            interval: Candlestick interval (e.g., "1m", "5m", "1h", "1d")
            limit: Number of candles to fetch (max ~5000)
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)

        Returns:
            List[OHLC]: List of candlestick data

        Hyperliquid Endpoint:
            POST /info with {"type": "candleSnapshot", "req": {...}}

        Notes:
            - If start_time/end_time not provided, fetches most recent candles
            - Symbol should be coin name (BTC, ETH) not pair (BTCUSDT)

        Example:
            >>> ohlc = await exchange.get_ohlc("BTC", "1h", limit=100)
            >>> print(f"Latest close: ${ohlc[-1].close:,.2f}")
        """
        # If no time range specified, fetch recent candles
        if start_time is None or end_time is None:
            end_time = current_utc_timestamp(milliseconds=True)
            # Calculate start time based on interval and limit
            interval_ms = self._interval_to_milliseconds(interval)
            start_time = end_time - (interval_ms * limit)

        return await self.client.get_historical_ohlc(symbol, interval, start_time, end_time)

    async def get_open_interest(self, symbol: str) -> Optional[OpenInterest]:
        """
        Get current open interest for a symbol.

        Args:
            symbol: Trading symbol (e.g., "BTC", "ETH")

        Returns:
            OpenInterest: Current open interest data, or None if not found

        Hyperliquid Endpoint:
            POST /info with {"type": "metaAndAssetCtxs"}

        Example:
            >>> oi = await exchange.get_open_interest("BTC")
            >>> if oi:
            ...     print(f"OI: {oi.open_interest:,.2f} BTC")
        """
        return await self.client.get_open_interest(symbol)

    async def get_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """
        Get current funding rate for a perpetual symbol.

        Args:
            symbol: Perpetual symbol (e.g., "BTC", "ETH")

        Returns:
            FundingRate: Latest funding rate, or None if not found

        Hyperliquid Endpoint:
            POST /info with {"type": "fundingHistory", "coin": "BTC"}

        Example:
            >>> fr = await exchange.get_funding_rate("BTC")
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
            symbol: Trading symbol (e.g., "BTC", "ETH")
            interval: Candlestick interval (e.g., "1m", "5m", "1h")

        Yields:
            OHLC: Live candlestick updates

        Hyperliquid WebSocket:
            wss://api.hyperliquid.xyz/ws
            Subscribe: {"method": "subscribe", "subscription": {"type": "candle", "coin": "BTC", "interval": "1m"}}

        Example:
            >>> async for candle in exchange.stream_ohlc("BTC", "1m"):
            ...     print(f"Close: ${candle.close:,.2f}")
        """
        self.logger.info(f"[Hyperliquid] Starting OHLC stream: {symbol} {interval}")

        ws_client = HyperliquidWSClient()
        async for ohlc in ws_client.stream_ohlc(symbol, interval):
            yield ohlc

    async def stream_liquidations(self, symbol: str) -> AsyncGenerator[Liquidation, None]:
        """
        Stream liquidation events via WebSocket.

        Args:
            symbol: Trading symbol (e.g., "BTC", "ETH")

        Yields:
            Liquidation: Never yields (not supported by Hyperliquid)

        Raises:
            NotImplementedError: Hyperliquid does not provide liquidation data

        Notes:
            - Hyperliquid does not expose public liquidation events
            - This method is required by ExchangeInterface but always raises
        """
        self.logger.warning(f"[Hyperliquid] Liquidation streams are not supported")
        raise NotImplementedError("Hyperliquid does not provide liquidation data")

    async def stream_large_trades(self, symbol: str) -> AsyncGenerator[LargeTrade, None]:
        """
        Stream large trades via WebSocket.

        Args:
            symbol: Trading symbol (e.g., "BTC", "ETH")

        Yields:
            LargeTrade: Significant trade events

        Hyperliquid WebSocket:
            wss://api.hyperliquid.xyz/ws
            Subscribe: {"method": "subscribe", "subscription": {"type": "trades", "coin": "BTC"}}

        Notes:
            - Streams ALL trades (no server-side filtering by size)
            - Consider filtering by value threshold on client side if needed

        Example:
            >>> async for trade in exchange.stream_large_trades("BTC"):
            ...     if trade.value > 100000:  # $100k+ trades
            ...         print(f"Large trade: {trade.side} ${trade.value:,.0f}")
        """
        self.logger.info(f"[Hyperliquid] Starting trade stream: {symbol}")

        ws_client = HyperliquidWSClient()
        async for trade in ws_client.stream_trades(symbol):
            # Optionally filter by minimum trade value
            # For now, yield all trades (caller can filter)
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
