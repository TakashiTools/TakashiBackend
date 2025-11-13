"""
Binance Exchange Connector

This module implements the ExchangeInterface for Binance Futures (USD-M).

Binance is one of the largest cryptocurrency exchanges globally, offering:
- Comprehensive REST API for historical data
- High-performance WebSocket streams for real-time data
- Support for OHLC, open interest, funding rates, liquidations, and trades

API Documentation:
    https://binance-docs.github.io/apidocs/futures/en/

Endpoints Used:
    REST:
        - GET /fapi/v1/klines - Historical candlestick data
        - GET /fapi/v1/openInterest - Current open interest
        - GET /fapi/v1/premiumIndex - Funding rate information
        - GET /fapi/v1/fundingRate - Historical funding rates

    WebSocket:
        - wss://fstream.binance.com/ws - Real-time market data streams
        - Kline streams: <symbol>@kline_<interval>
        - Liquidation streams: <symbol>@forceOrder
        - Aggregate trade streams: <symbol>@aggTrade

Implementation Status:
    This is currently a STUB implementation. Methods return placeholder data
    or raise NotImplementedError. The actual implementation will be added in
    Phase 4 when we build the api_client.py and ws_client.py modules.

Future Structure:
    exchanges/binance/
    ├── __init__.py          # This file (BinanceExchange class)
    ├── api_client.py        # REST API client with aiohttp
    └── ws_client.py         # WebSocket streaming client
"""

from typing import List, AsyncGenerator, Optional
from core.exchange_interface import ExchangeInterface
from core.schemas import OHLC, OpenInterest, FundingRate, Liquidation, LargeTrade
from core.logging import logger
from core.utils.time import to_utc_datetime
from .api_client import BinanceAPIClient
from .ws_client import (
    BinanceWebSocketClient,
    create_kline_stream,
    create_liquidation_stream,
    create_trade_stream
)


class BinanceExchange(ExchangeInterface):
    """
    Binance Futures Exchange Connector

    This class implements the ExchangeInterface for Binance Futures (USD-M).
    It provides both REST API methods for historical data and WebSocket methods
    for real-time streaming.

    Attributes:
        name: Exchange identifier ("binance")
        capabilities: Dictionary of supported features (all True for Binance)
        base_url: Binance Futures API base URL
        ws_url: Binance WebSocket stream URL

    Example:
        >>> exchange = BinanceExchange()
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
        - Timestamps are converted from milliseconds to UTC datetime
        - WebSocket reconnection is handled automatically
        - Rate limits are respected (configurable in settings)
    """

    # ============================================
    # Class Attributes
    # ============================================

    name = "binance"

    capabilities = {
        "ohlc": True,
        "funding_rate": True,
        "open_interest": True,
        "liquidations": True,
        "large_trades": True
    }

    # ============================================
    # Initialization
    # ============================================

    def __init__(self):
        """
        Initialize the Binance exchange connector.

        Sets up the API endpoints and prepares for connection.
        Actual network connections are established in initialize().
        """
        # Import settings here to avoid circular imports
        from core.config import settings

        # API endpoints
        self.base_url = settings.binance_base_url
        self.ws_url = "wss://fstream.binance.com/ws"

        # API client (will be created in initialize())
        self.client: BinanceAPIClient = None

        # WebSocket connections registry (will be populated as needed)
        self.ws_connections = {}

        logger.debug(f"BinanceExchange created (base_url={self.base_url})")

    async def initialize(self) -> None:
        """
        Initialize the Binance connector.

        Sets up:
            - BinanceAPIClient for REST API calls
            - aiohttp ClientSession (via API client)
            - Connection pooling

        This method is called by ExchangeManager.initialize_all()
        """
        logger.info("Initializing Binance exchange connector...")

        # Create and initialize API client
        self.client = BinanceAPIClient()
        await self.client.__aenter__()

        logger.info("✓ Binance exchange connector initialized")

    async def shutdown(self) -> None:
        """
        Shutdown the Binance connector gracefully.

        Closes:
            - BinanceAPIClient (aiohttp session)
            - All active WebSocket connections (via context managers)
            - Background tasks

        Notes:
            - WebSocket connections are managed via async context managers
            - When stream generators are closed, their context managers cleanup automatically
        """
        logger.info("Shutting down Binance exchange connector...")

        # Close API client
        if self.client:
            await self.client.__aexit__(None, None, None)

        logger.info("✓ Binance exchange connector shut down")

    async def health_check(self) -> bool:
        """
        Check if Binance API is accessible.

        Returns:
            bool: True if API is reachable, False otherwise

        Notes:
            - Makes a lightweight call to /fapi/v1/ping
            - Does not count against rate limits
        """
        logger.debug("Running Binance health check...")

        # TODO: Implement in Phase 4
        # try:
        #     async with self.session.get("/fapi/v1/ping") as response:
        #         return response.status == 200
        # except Exception as e:
        #     logger.error(f"Binance health check failed: {e}")
        #     return False

        # For now, assume healthy
        return True

    # ============================================
    # REST API Methods
    # ============================================

    async def get_ohlc(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        startTime: Optional[int] = None,
        endTime: Optional[int] = None
    ) -> List[OHLC]:
        """
        Fetch historical OHLC data from Binance.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Candlestick interval (e.g., "1m", "5m", "1h", "1d")
            limit: Number of candles to fetch (max 1500)
            startTime: Optional start time in milliseconds (Unix timestamp)
            endTime: Optional end time in milliseconds (Unix timestamp)

        Returns:
            List[OHLC]: List of candlestick data

        Binance Endpoint:
            GET /fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}&startTime={startTime}&endTime={endTime}

        Example:
            >>> ohlc = await exchange.get_ohlc("BTCUSDT", "1h", limit=100)
            >>> print(f"Latest close: ${ohlc[-1].close:,.2f}")
            
            >>> # Fetch historical data before a specific time
            >>> ohlc = await exchange.get_ohlc("BTCUSDT", "1m", limit=120, endTime=1699876800000)
        """
        return await self.client.get_ohlc(symbol, interval, limit, startTime, endTime)

    async def get_open_interest(self, symbol: str) -> OpenInterest:
        """
        Get current open interest for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            OpenInterest: Current open interest data

        Binance Endpoint:
            GET /fapi/v1/openInterest?symbol={symbol}

        Example:
            >>> oi = await exchange.get_open_interest("BTCUSDT")
            >>> print(f"OI: {oi.open_interest:,.2f} BTC")
        """
        return await self.client.get_open_interest(symbol)

    async def get_funding_rate(self, symbol: str) -> FundingRate:
        """
        Get current funding rate for a perpetual symbol.

        Args:
            symbol: Perpetual symbol (e.g., "BTCUSDT")

        Returns:
            FundingRate: Latest funding rate

        Binance Endpoint:
            GET /fapi/v1/fundingRate?symbol={symbol}&limit=1

        Example:
            >>> fr = await exchange.get_funding_rate("BTCUSDT")
            >>> print(f"Funding rate: {fr.funding_rate * 100:.4f}%")
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
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Candlestick interval (e.g., "1m", "5m", "1h")

        Yields:
            OHLC: Live candlestick updates

        Binance WebSocket Stream:
            wss://fstream.binance.com/ws/{lowercase(symbol)}@kline_{interval}

        Message Format:
            {
              "e": "kline",
              "E": 1608307200000,
              "s": "BTCUSDT",
              "k": {
                "t": 1608307200000,
                "T": 1608307259999,
                "s": "BTCUSDT",
                "i": "1m",
                "o": "48000.00",
                "c": "48100.00",
                "h": "48200.00",
                "l": "47900.00",
                "v": "100.5",
                "q": "4850000.00",
                "n": 500,
                "x": false  // Is the kline closed?
              }
            }

        Example:
            >>> async for candle in exchange.stream_ohlc("BTCUSDT", "1m"):
            ...     print(f"Close: ${candle.close:,.2f}")
        """
        logger.info(f"[Binance] Starting OHLC stream: {symbol} {interval}")

        async with create_kline_stream(symbol, interval) as ws_client:
            async for msg in ws_client.listen():
                # Validate message type
                if msg.get("e") != "kline":
                    logger.warning(f"Unexpected message type: {msg.get('e')}")
                    continue

                # Extract kline data
                k = msg.get("k", {})

                # Normalize to OHLC schema
                yield OHLC(
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

    async def stream_liquidations(self, symbol: str) -> AsyncGenerator[Liquidation, None]:
        """
        Stream liquidation events via WebSocket.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Yields:
            Liquidation: Liquidation events

        Binance WebSocket Stream:
            wss://fstream.binance.com/ws/{lowercase(symbol)}@forceOrder

        Message Format:
            {
              "e": "forceOrder",
              "E": 1568014460893,
              "o": {
                "s": "BTCUSDT",
                "S": "SELL",  // Side
                "o": "LIMIT",
                "q": "0.014",  // Quantity
                "p": "9910",   // Price
                "ap": "9910",  // Average price
                "X": "FILLED",
                "T": 1568014460893
              }
            }

        Example:
            >>> async for liq in exchange.stream_liquidations("BTCUSDT"):
            ...     print(f"Liquidation: {liq.side} {liq.quantity} @ ${liq.price}")
        """
        logger.info(f"[Binance] Starting liquidation stream: {symbol}")

        async with create_liquidation_stream(symbol) as ws_client:
            async for msg in ws_client.listen():
                # Validate message type
                if msg.get("e") != "forceOrder":
                    logger.warning(f"Unexpected message type: {msg.get('e')}")
                    continue

                # Extract order data
                o = msg.get("o", {})

                # Normalize to Liquidation schema
                yield Liquidation(
                    exchange="binance",
                    symbol=o.get("s", symbol.upper()),
                    side=o.get("S", "").lower(),  # "SELL" -> "sell", "BUY" -> "buy"
                    price=float(o.get("p", 0)),
                    quantity=float(o.get("q", 0)),
                    timestamp=to_utc_datetime(o.get("T"))
                )

    async def stream_large_trades(self, symbol: str) -> AsyncGenerator[LargeTrade, None]:
        """
        Stream large trades via WebSocket.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Yields:
            LargeTrade: Significant trade events

        Binance WebSocket Stream:
            wss://fstream.binance.com/ws/{lowercase(symbol)}@aggTrade

        Message Format:
            {
              "e": "aggTrade",
              "E": 1568014460893,
              "s": "BTCUSDT",
              "a": 26129,         // Aggregate trade ID
              "p": "9910.00",     // Price
              "q": "5.5",         // Quantity
              "f": 100,           // First trade ID
              "l": 105,           // Last trade ID
              "T": 1568014460893, // Timestamp
              "m": true           // Is buyer maker?
            }

        Notes:
            - Filters trades by minimum USD value threshold (configurable via LARGE_TRADE_THRESHOLD_USD)
            - Default threshold: $100,000 USD
            - buyer_maker=True means trade is a sell (buyer is passive)
            - buyer_maker=False means trade is a buy (seller is passive)

        Example:
            >>> async for trade in exchange.stream_large_trades("BTCUSDT"):
            ...     print(f"Large trade: {trade.side} {trade.quantity} @ ${trade.price}")
        """
        logger.info(f"[Binance] Starting large trade stream: {symbol}")

        # Get minimum trade value from configuration
        from core.config import settings
        min_trade_value_usd = settings.large_trade_threshold_usd

        async with create_trade_stream(symbol) as ws_client:
            async for msg in ws_client.listen():
                # Validate message type
                if msg.get("e") != "aggTrade":
                    logger.warning(f"Unexpected message type: {msg.get('e')}")
                    continue

                # Parse trade data
                price = float(msg.get("p", 0))
                quantity = float(msg.get("q", 0))
                value = price * quantity

                # Filter: only yield trades above threshold
                if value < min_trade_value_usd:
                    continue

                # Determine side (buyer_maker=True means sell order filled)
                is_buyer_maker = msg.get("m", False)
                side = "sell" if is_buyer_maker else "buy"

                # Normalize to LargeTrade schema
                yield LargeTrade(
                    exchange="binance",
                    symbol=msg.get("s", symbol.upper()),
                    side=side,
                    price=price,
                    quantity=quantity,
                    value=value,
                    is_buyer_maker=is_buyer_maker,
                    timestamp=to_utc_datetime(msg.get("T"))
                )

    # ============================================
    # Helper Methods (To Be Implemented)
    # ============================================

    # These will be moved to api_client.py in Phase 4

    # def _normalize_ohlc(self, raw_data: list) -> OHLC:
    #     """Convert Binance kline data to OHLC schema"""
    #     ...

    # def _normalize_open_interest(self, raw_data: dict) -> OpenInterest:
    #     """Convert Binance OI data to OpenInterest schema"""
    #     ...

    # def _normalize_funding_rate(self, raw_data: dict) -> FundingRate:
    #     """Convert Binance premium index to FundingRate schema"""
    #     ...

    # def _normalize_liquidation(self, raw_data: dict) -> Liquidation:
    #     """Convert Binance force order to Liquidation schema"""
    #     ...

    # def _normalize_trade(self, raw_data: dict) -> LargeTrade:
    #     """Convert Binance aggTrade to LargeTrade schema"""
    #     ...
