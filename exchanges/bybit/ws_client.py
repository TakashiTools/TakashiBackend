"""
Bybit WebSocket Client

This module provides async WebSocket streaming for Bybit real-time data.
It handles:
- WebSocket connections with automatic reconnection
- Message parsing and validation
- Exponential backoff on failures
- Graceful shutdown
- Data normalization to our schemas

Supported Streams:
    - Candles: Live OHLC data with interval support
    - Trades: Real-time trade execution data
    - Liquidations: Real-time liquidation events

WebSocket Documentation:
    https://bybit-exchange.github.io/docs/v5/ws/public

Usage:
    client = BybitWSClient()
    async for ohlc in client.stream_ohlc("BTCUSDT", "1m"):
        print(f"Close: {ohlc.close}")
"""

import asyncio
import websockets
import json
from typing import AsyncGenerator, Optional
from core.logging import get_logger
from core.schemas import OHLC, LargeTrade, Liquidation
from core.utils.time import to_utc_datetime


class BybitWSClient:
    """
    Async WebSocket client for Bybit streams.

    This client provides low-level WebSocket connectivity with automatic
    reconnection and error handling. It yields normalized data using our
    Pydantic schemas.

    Attributes:
        BASE_URL: Bybit WebSocket base URL
        logger: Logger instance
        max_reconnect_delay: Maximum delay between reconnection attempts (seconds)

    Example:
        >>> client = BybitWSClient()
        >>> async for ohlc in client.stream_ohlc("BTCUSDT", "1m"):
        ...     print(f"New candle: {ohlc.close}")

    Notes:
        - Reconnects automatically with exponential backoff
        - Normalizes all data to standard schemas
        - Handles both live updates and backfill data
        - Supports multiple product types (linear, inverse, spot)
    """

    BASE_URL = "wss://stream.bybit.com/v5/public/linear"

    def __init__(self, max_reconnect_delay: int = 30):
        """
        Initialize WebSocket client.

        Args:
            max_reconnect_delay: Max seconds to wait between reconnects (default: 30)
        """
        self.max_reconnect_delay = max_reconnect_delay
        self.logger = get_logger(__name__)
        self._reconnect_attempt = 0

    # ============================================
    # WebSocket Connection Helper
    # ============================================

    async def _connect_and_subscribe(
        self,
        subscription: dict
    ) -> websockets.WebSocketClientProtocol:
        """
        Connect to WebSocket and send subscription message.

        Args:
            subscription: Subscription payload (will be JSON encoded)

        Returns:
            WebSocket connection

        Raises:
            Exception: If connection or subscription fails
        """
        ws = await websockets.connect(self.BASE_URL)
        await ws.send(json.dumps(subscription))
        self.logger.info(f"Subscribed to {subscription.get('args', ['unknown'])[0] if subscription.get('args') else 'unknown'} stream")
        self._reconnect_attempt = 0
        return ws

    # ============================================
    # OHLC (Candles) Stream
    # ============================================

    async def stream_ohlc(
        self,
        symbol: str,
        interval: str
    ) -> AsyncGenerator[OHLC, None]:
        """
        Stream live OHLC updates from Bybit.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            interval: Candlestick interval (e.g., "1m", "5m", "1h")

        Yields:
            OHLC: Live candlestick updates

        Bybit WebSocket Format:
            Topic: kline.{interval}.{symbol}
            Example: kline.1.BTCUSDT, kline.5.BTCUSDT, kline.60.BTCUSDT

        Notes:
            - Reconnects automatically on connection loss
            - Yields both live updates (confirm=false) and completed candles (confirm=true)
            - Uses Bybit's exact kline data format from official documentation
        """
        # Convert interval to Bybit format
        bybit_interval = self._convert_interval_to_bybit(interval)
        topic = f"kline.{bybit_interval}.{symbol.upper()}"
        subscription = {
            "op": "subscribe",
            "args": [topic]
        }

        while True:
            try:
                ws = await self._connect_and_subscribe(subscription)
                
                async for message in ws:
                    try:
                        data = json.loads(message)
                        
                        # Debug logging for first few messages
                        if self._reconnect_attempt == 0:  # Only log on first connection
                            self.logger.debug(f"Received Bybit OHLC message: {data}")
                        
                        # Handle subscription confirmation
                        if data.get("op") == "subscribe":
                            self.logger.info(f"Subscription confirmed: {data}")
                            continue
                        
                        # Handle kline data
                        if data.get("topic") == topic and data.get("type") == "snapshot":
                            kline_list = data.get("data", [])
                            self.logger.debug(f"Received kline data: {len(kline_list)} candles")
                            
                            # Bybit sends kline data as a list of objects with exact format from docs
                            for kline_data in kline_list:
                                if isinstance(kline_data, dict):
                                    ohlc = OHLC(
                                        exchange="bybit",
                                        symbol=symbol.upper(),
                                        interval=interval,
                                        timestamp=to_utc_datetime(int(kline_data["start"])),  # start timestamp
                                        open=float(kline_data["open"]),  # open price
                                        high=float(kline_data["high"]),  # high price
                                        low=float(kline_data["low"]),   # low price
                                        close=float(kline_data["close"]), # close price
                                        volume=float(kline_data["volume"]), # volume
                                        quote_volume=float(kline_data["turnover"]), # turnover
                                        trades_count=0,  # Not provided by Bybit
                                        is_closed=kline_data.get("confirm", False)  # confirm field indicates if candle is closed
                                    )
                                    
                                    yield ohlc
                                else:
                                    self.logger.warning(f"Unexpected kline data format: {type(kline_data)}")
                        else:
                            # Log other message types for debugging
                            if data.get("topic") != topic:
                                self.logger.debug(f"Received message for different topic: {data.get('topic')}")
                                
                    except json.JSONDecodeError:
                        self.logger.warning("Received invalid JSON from Bybit WebSocket")
                        continue
                    except Exception as e:
                        self.logger.error(f"Error processing Bybit OHLC message: {e}")
                        continue

            except Exception as e:
                self.logger.error(f"Bybit OHLC WebSocket connection failed: {e}")
                
                # Exponential backoff reconnection
                wait_time = min(2 ** self._reconnect_attempt, self.max_reconnect_delay)
                self.logger.info(f"Reconnecting to Bybit OHLC stream in {wait_time}s...")
                await asyncio.sleep(wait_time)
                self._reconnect_attempt += 1

    # ============================================
    # Trades Stream
    # ============================================

    async def stream_trades(
        self,
        symbol: str
    ) -> AsyncGenerator[LargeTrade, None]:
        """
        Stream live trade updates from Bybit.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")

        Yields:
            LargeTrade: Live trade updates

        Bybit WebSocket Format:
            Topic: publicTrade.{symbol}
            Example: publicTrade.BTCUSDT

        Notes:
            - Streams ALL trades (no server-side filtering)
            - Client can filter by trade value if needed
            - Reconnects automatically on connection loss
        """
        topic = f"publicTrade.{symbol.upper()}"
        subscription = {
            "op": "subscribe",
            "args": [topic]
        }

        while True:
            try:
                ws = await self._connect_and_subscribe(subscription)
                
                async for message in ws:
                    try:
                        data = json.loads(message)
                        
                        # Handle subscription confirmation
                        if data.get("op") == "subscribe":
                            continue
                        
                        # Handle trade data
                        if data.get("topic") == topic and data.get("type") == "snapshot":
                            trades = data.get("data", [])
                            
                            for trade_data in trades:
                                if isinstance(trade_data, dict):
                                    trade = LargeTrade(
                                        exchange="bybit",
                                        symbol=symbol.upper(),
                                        timestamp=to_utc_datetime(int(trade_data["T"])),
                                        side=trade_data["S"].lower(),  # Buy/Sell -> buy/sell
                                        price=float(trade_data["p"]),
                                        quantity=float(trade_data["v"]),
                                        value=float(trade_data["p"]) * float(trade_data["v"]),
                                        is_buyer_maker=False  # Bybit doesn't provide this info
                                    )
                                    
                                    yield trade
                                
                    except json.JSONDecodeError:
                        self.logger.warning("Received invalid JSON from Bybit WebSocket")
                        continue
                    except Exception as e:
                        self.logger.error(f"Error processing Bybit trade message: {e}")
                        continue

            except Exception as e:
                self.logger.error(f"Bybit trades WebSocket connection failed: {e}")
                
                # Exponential backoff reconnection
                wait_time = min(2 ** self._reconnect_attempt, self.max_reconnect_delay)
                self.logger.info(f"Reconnecting to Bybit trades stream in {wait_time}s...")
                await asyncio.sleep(wait_time)
                self._reconnect_attempt += 1

    # ============================================
    # Liquidations Stream
    # ============================================

    async def stream_liquidations(
        self,
        symbol: str
    ) -> AsyncGenerator[Liquidation, None]:
        """
        Stream live liquidation events from Bybit.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")

        Yields:
            Liquidation: Live liquidation events

        Bybit WebSocket Format:
            Topic: allLiquidation.{symbol}
            Example: allLiquidation.BTCUSDT

        Notes:
            - Reconnects automatically on connection loss
            - side="sell" means long liquidation (bearish)
            - side="buy" means short liquidation (bullish)
        """
        topic = f"allLiquidation.{symbol.upper()}"
        subscription = {
            "op": "subscribe",
            "args": [topic]
        }

        while True:
            try:
                ws = await self._connect_and_subscribe(subscription)
                
                async for message in ws:
                    try:
                        data = json.loads(message)
                        
                        # Handle subscription confirmation
                        if data.get("op") == "subscribe":
                            continue
                        
                        # Handle liquidation data
                        if data.get("topic") == topic and data.get("type") == "snapshot":
                            liquidations = data.get("data", [])
                            
                            for liq_data in liquidations:
                                if isinstance(liq_data, dict):
                                    liquidation = Liquidation(
                                        exchange="bybit",
                                        symbol=symbol.upper(),
                                        timestamp=to_utc_datetime(int(liq_data["T"])),
                                        side=liq_data["S"].lower(),  # Buy/Sell -> buy/sell
                                        price=float(liq_data["p"]),
                                        quantity=float(liq_data["v"]),
                                        value=float(liq_data["p"]) * float(liq_data["v"])
                                    )
                                    
                                    yield liquidation
                                
                    except json.JSONDecodeError:
                        self.logger.warning("Received invalid JSON from Bybit WebSocket")
                        continue
                    except Exception as e:
                        self.logger.error(f"Error processing Bybit liquidation message: {e}")
                        continue

            except Exception as e:
                self.logger.error(f"Bybit liquidations WebSocket connection failed: {e}")
                
                # Exponential backoff reconnection
                wait_time = min(2 ** self._reconnect_attempt, self.max_reconnect_delay)
                self.logger.info(f"Reconnecting to Bybit liquidations stream in {wait_time}s...")
                await asyncio.sleep(wait_time)
                self._reconnect_attempt += 1

    # ============================================
    # Helper Methods
    # ============================================

    def _convert_interval_to_bybit(self, interval: str) -> str:
        """
        Convert standard interval format to Bybit format.

        Args:
            interval: Standard interval (e.g., "1m", "5m", "1h", "1d")

        Returns:
            str: Bybit interval format (e.g., "1", "5", "60", "D")

        Bybit supported intervals:
            1,3,5,15,30,60,120,240,360,720,D,W,M
        """
        if interval.endswith('m'):
            minutes = int(interval[:-1])
            if minutes in [1, 3, 5, 15, 30]:
                return str(minutes)
            else:
                self.logger.warning(f"Unsupported minute interval: {interval}, using 1m")
                return "1"
        elif interval.endswith('h'):
            hours = int(interval[:-1])
            if hours == 1:
                return "60"  # 1 hour = 60 minutes
            elif hours == 2:
                return "120"  # 2 hours = 120 minutes
            elif hours == 4:
                return "240"  # 4 hours = 240 minutes
            elif hours == 6:
                return "360"  # 6 hours = 360 minutes
            elif hours == 12:
                return "720"  # 12 hours = 720 minutes
            else:
                self.logger.warning(f"Unsupported hour interval: {interval}, using 1h")
                return "60"
        elif interval.endswith('d'):
            days = int(interval[:-1])
            if days == 1:
                return "D"  # Daily
            elif days == 7:
                return "W"  # Weekly
            elif days == 30:
                return "M"  # Monthly
            else:
                self.logger.warning(f"Unsupported day interval: {interval}, using 1d")
                return "D"
        else:
            self.logger.warning(f"Unknown interval format: {interval}, using 1m")
            return "1"
