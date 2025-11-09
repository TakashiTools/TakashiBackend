"""
Exchange Interface — Abstract Contract for All Exchanges

This module defines the abstract base class that all exchange connectors must implement.
By enforcing a consistent interface, we ensure:
- All exchanges expose the same methods
- Easy to add new exchanges without modifying core logic
- Type-safe interactions with exchange connectors
- Graceful handling of unsupported features

Design Philosophy:
    "Program to an interface, not an implementation"

    The API routes and core logic work with ExchangeInterface, not specific
    exchange implementations. This allows us to swap or add exchanges without
    changing the rest of the system.

Example:
    class BinanceExchange(ExchangeInterface):
        name = "binance"

        async def get_ohlc(self, symbol, interval, limit=500):
            # Binance-specific implementation
            ...

    class BybitExchange(ExchangeInterface):
        name = "bybit"

        async def get_ohlc(self, symbol, interval, limit=500):
            # Bybit-specific implementation
            ...

    # In API routes, we can use either exchange the same way:
    exchange = manager.get_exchange("binance")  # or "bybit"
    data = await exchange.get_ohlc("BTCUSDT", "1h")

Capabilities System:
    Each exchange declares which features it supports via the `capabilities` dict.
    This allows graceful degradation when an exchange doesn't support a feature.

    Example:
        capabilities = {
            "ohlc": True,
            "funding_rate": True,
            "open_interest": True,
            "liquidations": False,  # Not supported by this exchange
            "large_trades": True
        }
"""

from abc import ABC, abstractmethod
from typing import List, AsyncGenerator, Dict
from core.schemas import OHLC, OpenInterest, FundingRate, Liquidation, LargeTrade


class ExchangeInterface(ABC):
    """
    Abstract Base Class for Exchange Connectors

    All exchange implementations (Binance, Bybit, OKX, etc.) must inherit from this
    class and implement all abstract methods. This ensures a consistent interface
    across all exchanges.

    Class Attributes:
        name: Unique identifier for the exchange (lowercase, e.g., "binance", "bybit")
        capabilities: Dictionary indicating which features this exchange supports

    Abstract Methods (MUST be implemented by all exchanges):
        - get_ohlc: Fetch historical candlestick data
        - get_open_interest: Get current open interest
        - get_funding_rate: Get current and next funding rate
        - stream_ohlc: Stream live candlestick updates
        - stream_liquidations: Stream liquidation events
        - stream_large_trades: Stream significant trades

    Optional Methods (can be overridden):
        - initialize: Setup connections, sessions, etc.
        - shutdown: Cleanup connections
        - health_check: Verify exchange API is accessible

    Example Implementation:
        >>> class BinanceExchange(ExchangeInterface):
        ...     name = "binance"
        ...     capabilities = {
        ...         "ohlc": True,
        ...         "funding_rate": True,
        ...         "open_interest": True,
        ...         "liquidations": True,
        ...         "large_trades": True
        ...     }
        ...
        ...     async def get_ohlc(self, symbol, interval, limit=500):
        ...         # Implementation here
        ...         return [OHLC(...), OHLC(...), ...]
    """

    # ============================================
    # Class Attributes (must be set by subclasses)
    # ============================================

    name: str
    """Unique exchange identifier (lowercase). Example: "binance", "bybit", "okx" """

    capabilities: Dict[str, bool] = {
        "ohlc": False,
        "funding_rate": False,
        "open_interest": False,
        "liquidations": False,
        "large_trades": False
    }
    """Dictionary indicating which features this exchange supports"""

    # ============================================
    # REST API Methods (Historical/Snapshot Data)
    # ============================================

    @abstractmethod
    async def get_ohlc(
        self,
        symbol: str,
        interval: str,
        limit: int = 500
    ) -> List[OHLC]:
        """
        Fetch historical OHLC (candlestick) data from the exchange.

        This method retrieves historical candlestick data for technical analysis
        and charting. The data is normalized into our OHLC schema.

        Args:
            symbol: Trading pair symbol in uppercase (e.g., "BTCUSDT", "ETHUSDT")
            interval: Candlestick interval (e.g., "1m", "5m", "1h", "1d")
                     Must be one of the intervals supported by the exchange
            limit: Number of candlesticks to fetch (default: 500, max varies by exchange)
                   Most recent candles are returned (newest first or oldest first
                   depending on exchange, but should be normalized to newest first)

        Returns:
            List[OHLC]: List of OHLC objects sorted by timestamp (newest first)
                       Empty list if symbol/interval not found or no data available

        Raises:
            NotImplementedError: If this exchange doesn't support OHLC data
            ValueError: If symbol or interval is invalid
            Exception: For network errors, API errors, or rate limits

        Example:
            >>> exchange = BinanceExchange()
            >>> ohlc_data = await exchange.get_ohlc("BTCUSDT", "1h", limit=100)
            >>> print(f"Fetched {len(ohlc_data)} candles")
            >>> print(f"Latest close: {ohlc_data[0].close}")

        Notes:
            - Data should be normalized to our OHLC schema
            - Timestamps must be UTC datetime objects
            - Handle exchange-specific quirks (ms vs seconds, field names, etc.)
            - Consider caching recent data to avoid rate limits
        """
        ...

    @abstractmethod
    async def get_open_interest(self, symbol: str) -> OpenInterest:
        """
        Get current open interest for a futures/perpetual symbol.

        Open Interest represents the total number of outstanding derivative contracts
        that have not been settled. It's a key metric for futures market analysis.

        Args:
            symbol: Trading pair symbol in uppercase (e.g., "BTCUSDT")
                   Must be a futures or perpetual contract symbol

        Returns:
            OpenInterest: Current open interest data with normalized schema

        Raises:
            NotImplementedError: If exchange doesn't support open interest
            ValueError: If symbol is invalid or not a futures contract
            Exception: For API errors or network issues

        Example:
            >>> oi = await exchange.get_open_interest("BTCUSDT")
            >>> print(f"Open Interest: {oi.open_interest} BTC")
            >>> print(f"OI Value: ${oi.open_interest_value:,.2f}")

        Notes:
            - Only applicable to futures/perpetual markets
            - Some exchanges update OI every minute, others less frequently
            - Value in USD/USDT is optional but recommended
        """
        ...

    @abstractmethod
    async def get_funding_rate(self, symbol: str) -> FundingRate:
        """
        Get current and next funding rate for a perpetual futures symbol.

        Funding rates are periodic payments between long and short positions in
        perpetual futures markets. They help keep the perpetual price anchored
        to the spot price.

        Args:
            symbol: Perpetual futures symbol in uppercase (e.g., "BTCUSDT")

        Returns:
            FundingRate: Current funding rate with next funding rate prediction

        Raises:
            NotImplementedError: If exchange doesn't support funding rates
            ValueError: If symbol is invalid or not a perpetual contract
            Exception: For API errors or network issues

        Example:
            >>> fr = await exchange.get_funding_rate("BTCUSDT")
            >>> print(f"Current rate: {fr.funding_rate * 100:.4f}%")

        Notes:
            - Only applicable to perpetual (not dated) futures
            - Positive rate: Longs pay shorts
            - Negative rate: Shorts pay longs
            - Funding typically happens every 8 hours (exchange-specific)
        """
        ...

    # ============================================
    # WebSocket Streaming Methods (Live Data)
    # ============================================

    @abstractmethod
    async def stream_ohlc(
        self,
        symbol: str,
        interval: str
    ) -> AsyncGenerator[OHLC, None]:
        """
        Stream live OHLC (candlestick) updates via WebSocket.

        This method establishes a WebSocket connection and yields OHLC updates
        as they occur. Each update represents the current state of the active
        candle (is_closed=False) or a newly completed candle (is_closed=True).

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            interval: Candlestick interval (e.g., "1m", "5m", "1h")

        Yields:
            OHLC: Live candlestick updates with normalized schema
                 - is_closed=False: Candle is still forming (updates continuously)
                 - is_closed=True: Candle just completed (final values)

        Raises:
            NotImplementedError: If exchange doesn't support live OHLC streaming
            Exception: For WebSocket connection errors

        Example:
            >>> async for candle in exchange.stream_ohlc("BTCUSDT", "1m"):
            ...     if candle.is_closed:
            ...         print(f"Candle closed: {candle.close}")
            ...     else:
            ...         print(f"Current price: {candle.close}")

        Notes:
            - This is an infinite async generator (streams until interrupted)
            - Handle WebSocket reconnection internally
            - Normalize exchange-specific WebSocket message format
            - Consider implementing heartbeat/ping-pong for connection health
        """
        ...

    @abstractmethod
    async def stream_liquidations(self, symbol: str) -> AsyncGenerator[Liquidation, None]:
        """
        Stream liquidation events via WebSocket.

        Liquidations occur when leveraged positions are forcefully closed due to
        insufficient margin. Tracking liquidations helps identify market stress
        and potential reversal points.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")

        Yields:
            Liquidation: Live liquidation events with normalized schema

        Raises:
            NotImplementedError: If exchange doesn't support liquidation streams
            Exception: For WebSocket errors

        Example:
            >>> async for liq in exchange.stream_liquidations("BTCUSDT"):
            ...     print(f"{liq.side} liquidation: {liq.quantity} @ {liq.price}")

        Notes:
            - Not all exchanges provide public liquidation streams
            - side="sell" means a long position was liquidated (bearish)
            - side="buy" means a short position was liquidated (bullish)
            - Large liquidations can cause cascading price movements
        """
        ...

    @abstractmethod
    async def stream_large_trades(self, symbol: str) -> AsyncGenerator[LargeTrade, None]:
        """
        Stream significant trades (whale trades) via WebSocket.

        This method filters and streams trades that exceed a certain threshold,
        indicating potential institutional or whale activity.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")

        Yields:
            LargeTrade: Significant trade events with normalized schema

        Raises:
            NotImplementedError: If exchange doesn't support trade streaming
            Exception: For WebSocket errors

        Example:
            >>> async for trade in exchange.stream_large_trades("BTCUSDT"):
            ...     if trade.value > 1_000_000:  # $1M+ trades
            ...         print(f"Whale {trade.side}: ${trade.value:,.0f}")

        Notes:
            - "Large" threshold is implementation-specific (can be configurable)
            - is_buyer_maker=False (taker) indicates more aggressive orders
            - Consider using aggTrade streams for reduced noise
        """
        ...

    # ============================================
    # Optional Lifecycle Methods
    # ============================================

    async def initialize(self) -> None:
        """
        Initialize the exchange connector.

        This method is called when the exchange is first loaded. Use it to:
        - Set up aiohttp ClientSession for REST requests
        - Validate API credentials (if required)
        - Fetch exchange info (symbol list, intervals, etc.)
        - Establish persistent connections

        Raises:
            Exception: If initialization fails

        Example:
            >>> await exchange.initialize()
            >>> print(f"{exchange.name} initialized successfully")

        Notes:
            - This is optional; default implementation does nothing
            - Called automatically by ExchangeManager
            - Should be idempotent (safe to call multiple times)
        """
        pass

    async def shutdown(self) -> None:
        """
        Shutdown the exchange connector and cleanup resources.

        This method is called when the application is shutting down. Use it to:
        - Close aiohttp sessions
        - Close WebSocket connections
        - Cancel background tasks
        - Release resources

        Example:
            >>> await exchange.shutdown()
            >>> print(f"{exchange.name} shut down gracefully")

        Notes:
            - This is optional; default implementation does nothing
            - Called automatically by ExchangeManager during shutdown
            - Should handle errors gracefully (don't raise exceptions)
        """
        pass

    async def health_check(self) -> bool:
        """
        Check if the exchange API is accessible and healthy.

        Returns:
            bool: True if exchange is accessible, False otherwise

        Example:
            >>> is_healthy = await exchange.health_check()
            >>> if not is_healthy:
            ...     print(f"{exchange.name} is unreachable!")

        Notes:
            - This is optional; default implementation returns True
            - Should make a lightweight API call (e.g., ping, server time)
            - Don't raise exceptions; return False on errors
        """
        return True

    # ============================================
    # Helper Methods
    # ============================================

    def supports(self, feature: str) -> bool:
        """
        Check if this exchange supports a specific feature.

        Args:
            feature: Feature name (e.g., "ohlc", "funding_rate", "liquidations")

        Returns:
            bool: True if feature is supported, False otherwise

        Example:
            >>> if exchange.supports("liquidations"):
            ...     async for liq in exchange.stream_liquidations("BTCUSDT"):
            ...         print(liq)
            ... else:
            ...     print("Liquidations not supported")
        """
        return self.capabilities.get(feature, False)

    def __repr__(self) -> str:
        """String representation of the exchange."""
        return f"<{self.__class__.__name__}(name='{self.name}')>"
