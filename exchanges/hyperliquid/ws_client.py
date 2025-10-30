"""
Hyperliquid WebSocket Client

This module provides async WebSocket streaming for Hyperliquid real-time data.
It handles:
- WebSocket connections with automatic reconnection
- Message parsing and validation
- Exponential backoff on failures
- Graceful shutdown
- Data normalization to our schemas

Supported Streams:
    - Candles: Live OHLC data with interval support
    - Trades: Real-time trade execution data

WebSocket Documentation:
    https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket

Usage:
    client = HyperliquidWSClient()
    async for ohlc in client.stream_ohlc("BTC", "1m"):
        print(f"Close: {ohlc.close}")
"""

import asyncio
import websockets
import json
from typing import AsyncGenerator, Optional
from core.logging import get_logger
from core.schemas import OHLC, LargeTrade
from core.utils.time import to_utc_datetime


class HyperliquidWSClient:
    """
    Async WebSocket client for Hyperliquid streams.

    This client provides low-level WebSocket connectivity with automatic
    reconnection and error handling. It yields normalized data using our
    Pydantic schemas.

    Attributes:
        BASE_URL: Hyperliquid WebSocket base URL
        logger: Logger instance
        max_reconnect_delay: Maximum delay between reconnection attempts (seconds)

    Example:
        >>> client = HyperliquidWSClient()
        >>> async for ohlc in client.stream_ohlc("BTC", "1m"):
        ...     print(f"New candle: {ohlc.close}")

    Notes:
        - Reconnects automatically with exponential backoff
        - Normalizes all data to standard schemas
        - Handles both live updates and backfill data
    """

    BASE_URL = "wss://api.hyperliquid.xyz/ws"

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
        self.logger.info(f"Subscribed to {subscription.get('type', 'unknown')} stream")
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
        Stream live OHLC (candlestick) data.

        This method connects to Hyperliquid's candle WebSocket stream and yields
        normalized OHLC objects as they arrive. It handles both:
        - Backfill data (recent historical candles)
        - Live updates (real-time candle formation)

        Args:
            symbol: Trading pair (e.g., "BTC", "ETH")
            interval: Candlestick interval (e.g., "1m", "5m", "1h", "1d")

        Yields:
            OHLC: Normalized candlestick data

        Reconnection Strategy:
            - Attempt 1: Wait 1 second
            - Attempt 2: Wait 2 seconds
            - Attempt 3: Wait 4 seconds
            - Attempt N: Wait min(2^(N-1), max_reconnect_delay) seconds

        Hyperliquid Message Format:
            {
              "channel": "candle",
              "data": {
                "t": 1720000000000,  // Open time
                "o": "50000.0",      // Open
                "h": "50500.0",      // High
                "l": "49500.0",      // Low
                "c": "50250.0",      // Close
                "v": "125.5",        // Volume
                "n": 1523,           // Number of trades
                "closed": true       // Is candle closed?
              }
            }

        Example:
            >>> async for candle in client.stream_ohlc("BTC", "1m"):
            ...     print(f"{candle.timestamp}: O={candle.open} C={candle.close}")
        """
        # Convert trading pair to coin symbol (BTCUSDT -> BTC)
        coin_symbol = self._extract_coin_symbol(symbol)
        
        subscription = {
            "method": "subscribe",
            "subscription": {
                "type": "candle",
                "coin": coin_symbol.upper(),
                "interval": interval
            }
        }

        self.logger.info(f"Subscribing to Hyperliquid OHLC: {symbol} -> {coin_symbol} {interval}")

        while True:
            try:
                ws = await self._connect_and_subscribe(subscription)

                # Listen for messages
                async for message in ws:
                    try:
                        data = json.loads(message)

                        # Skip non-data messages (e.g., subscription confirmations)
                        if "channel" not in data or data.get("channel") != "candle":
                            self.logger.debug(f"Skipping non-candle message: {data}")
                            continue

                        candle_data = data.get("data")
                        if not candle_data:
                            continue

                        # Normalize to OHLC schema
                        yield OHLC(
                            exchange="hyperliquid",
                            symbol=symbol.upper(),  # Keep original symbol for consistency
                            interval=interval,
                            timestamp=to_utc_datetime(candle_data["t"]),
                            open=float(candle_data["o"]),
                            high=float(candle_data["h"]),
                            low=float(candle_data["l"]),
                            close=float(candle_data["c"]),
                            volume=float(candle_data["v"]),
                            quote_volume=float(candle_data["v"]) * float(candle_data["c"]),  # Estimate
                            trades_count=int(candle_data.get("n", 0)),
                            is_closed=candle_data.get("closed", False)
                        )

                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse JSON: {message[:100]}... Error: {e}")
                        continue
                    except KeyError as e:
                        self.logger.error(f"Missing field in candle data: {e}. Data: {data}")
                        continue
                    except Exception as e:
                        self.logger.error(f"Error processing candle: {e}")
                        continue

            except websockets.exceptions.WebSocketException as e:
                self.logger.error(f"WebSocket error: {e}")
            except asyncio.CancelledError:
                self.logger.info("OHLC stream cancelled")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in OHLC stream: {e}")

            # Reconnect logic with exponential backoff
            self._reconnect_attempt += 1
            delay = min(2 ** (self._reconnect_attempt - 1), self.max_reconnect_delay)
            self.logger.warning(
                f"Reconnecting to OHLC stream in {delay}s... (attempt {self._reconnect_attempt})"
            )
            await asyncio.sleep(delay)

    # ============================================
    # Trades Stream
    # ============================================

    async def stream_trades(
        self,
        symbol: str
    ) -> AsyncGenerator[LargeTrade, None]:
        """
        Stream real-time trade execution data.

        This method connects to Hyperliquid's trade WebSocket stream and yields
        normalized LargeTrade objects for all executed trades.

        Args:
            symbol: Trading pair (e.g., "BTC", "ETH")

        Yields:
            LargeTrade: Normalized trade data

        Hyperliquid Message Format:
            {
              "channel": "trades",
              "data": [
                {
                  "coin": "BTC",
                  "side": "B",          // "B" for buy, "A" for sell (ask)
                  "px": "50000.0",      // Price
                  "sz": "2.5",          // Size
                  "time": 1720000000000,
                  "tid": 123456789
                }
              ]
            }

        Notes:
            - side "B" = buy (taker bought from maker's sell order)
            - side "A" = sell/ask (taker sold to maker's buy order)
            - For is_buyer_maker: "B" means buyer is taker (maker was selling)

        Example:
            >>> async for trade in client.stream_trades("BTC"):
            ...     print(f"Trade: {trade.side} {trade.quantity} @ {trade.price}")
        """
        # Convert trading pair to coin symbol (BTCUSDT -> BTC)
        coin_symbol = self._extract_coin_symbol(symbol)
        
        subscription = {
            "method": "subscribe",
            "subscription": {
                "type": "trades",
                "coin": coin_symbol.upper()
            }
        }

        self.logger.info(f"Subscribing to Hyperliquid trades: {symbol} -> {coin_symbol}")

        while True:
            try:
                ws = await self._connect_and_subscribe(subscription)

                # Listen for messages
                async for message in ws:
                    try:
                        data = json.loads(message)

                        # Skip non-data messages (e.g., subscription confirmations)
                        if "channel" not in data or data.get("channel") != "trades":
                            self.logger.debug(f"Skipping non-trade message: {data}")
                            continue

                        trades_data = data.get("data", [])
                        if not trades_data:
                            continue

                        # Process each trade in the batch
                        for trade in trades_data:
                            # Determine side
                            # "B" = buy (buyer is taker), "A" = sell/ask (seller is taker)
                            raw_side = trade.get("side", "")
                            side = "buy" if raw_side == "B" else "sell"
                            is_buyer_maker = raw_side == "A"  # If sell, buyer was maker

                            price = float(trade["px"])
                            quantity = float(trade["sz"])

                            yield LargeTrade(
                                exchange="hyperliquid",
                                symbol=symbol.upper(),
                                side=side,
                                price=price,
                                quantity=quantity,
                                value=price * quantity,
                                is_buyer_maker=is_buyer_maker,
                                timestamp=to_utc_datetime(trade["time"])
                            )

                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse JSON: {message[:100]}... Error: {e}")
                        continue
                    except KeyError as e:
                        self.logger.error(f"Missing field in trade data: {e}. Data: {data}")
                        continue
                    except Exception as e:
                        self.logger.error(f"Error processing trade: {e}")
                        continue

            except websockets.exceptions.WebSocketException as e:
                self.logger.error(f"WebSocket error: {e}")
            except asyncio.CancelledError:
                self.logger.info("Trades stream cancelled")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in trades stream: {e}")

            # Reconnect logic with exponential backoff
            self._reconnect_attempt += 1
            delay = min(2 ** (self._reconnect_attempt - 1), self.max_reconnect_delay)
            self.logger.warning(
                f"Reconnecting to trades stream in {delay}s... (attempt {self._reconnect_attempt})"
            )
            await asyncio.sleep(delay)

    # ============================================
    # Helper Methods
    # ============================================

    def _extract_coin_symbol(self, symbol: str) -> str:
        """
        Extract coin symbol from trading pair for Hyperliquid API.
        
        Hyperliquid uses single coin symbols (BTC, ETH) instead of trading pairs (BTCUSDT, ETHUSDT).
        This method converts trading pairs to the appropriate coin symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT", "ETHUSDT", "BTC", "ETH")
            
        Returns:
            Coin symbol for Hyperliquid API (e.g., "BTC", "ETH")
            
        Examples:
            >>> client._extract_coin_symbol("BTCUSDT")
            "BTC"
            >>> client._extract_coin_symbol("ETHUSDT") 
            "ETH"
            >>> client._extract_coin_symbol("BTC")
            "BTC"
        """
        symbol = symbol.upper()
        
        # Common trading pairs to coin mapping
        pair_to_coin = {
            "BTCUSDT": "BTC",
            "ETHUSDT": "ETH", 
            "SOLUSDT": "SOL",
            "AVAXUSDT": "AVAX",
            "MATICUSDT": "MATIC",
            "DOGEUSDT": "DOGE",
            "ADAUSDT": "ADA",
            "DOTUSDT": "DOT",
            "LINKUSDT": "LINK",
            "UNIUSDT": "UNI",
            "ATOMUSDT": "ATOM",
            "NEARUSDT": "NEAR",
            "FTMUSDT": "FTM",
            "ALGOUSDT": "ALGO",
            "ICPUSDT": "ICP",
            "VETUSDT": "VET",
            "FILUSDT": "FIL",
            "TRXUSDT": "TRX",
            "ETCUSDT": "ETC",
            "XLMUSDT": "XLM",
            "BCHUSDT": "BCH",
            "LTCUSDT": "LTC",
            "XRPUSDT": "XRP",
            "BNBUSDT": "BNB",
            "SHIBUSDT": "SHIB",
            "APEUSDT": "APE",
            "SANDUSDT": "SAND",
            "MANAUSDT": "MANA",
            "AXSUSDT": "AXS",
            "CRVUSDT": "CRV",
            "COMPUSDT": "COMP",
            "MKRUSDT": "MKR",
            "SNXUSDT": "SNX",
            "YFIUSDT": "YFI",
            "SUSHIUSDT": "SUSHI",
            "1INCHUSDT": "1INCH",
            "AAVEUSDT": "AAVE",
            "GRTUSDT": "GRT",
            "BATUSDT": "BAT",
            "ZRXUSDT": "ZRX",
            "ENJUSDT": "ENJ",
            "CHZUSDT": "CHZ",
            "HOTUSDT": "HOT",
            "ZILUSDT": "ZIL",
            "IOTAUSDT": "IOTA",
            "ONTUSDT": "ONT",
            "QTUMUSDT": "QTUM",
            "NEOUSDT": "NEO",
            "WAVESUSDT": "WAVES",
            "OMGUSDT": "OMG",
            "ZECUSDT": "ZEC",
            "DASHUSDT": "DASH",
            "XMRUSDT": "XMR",
            "EOSUSDT": "EOS",
            "IOSTUSDT": "IOST",
            "NANOUSDT": "NANO",
            "DGBUSDT": "DGB",
            "RVNUSDT": "RVN",
            "SCUSDT": "SC",
            "STORJUSDT": "STORJ",
            "KNCUSDT": "KNC",
            "REPUSDT": "REP",
            "LSKUSDT": "LSK",
            "ARDRUSDT": "ARDR",
            "ARKUSDT": "ARK",
            "STRATUSDT": "STRAT",
            "FUNUSDT": "FUN",
            "REQUSDT": "REQ",
            "XEMUSDT": "XEM",
            "ICXUSDT": "ICX",
            "VENUSDT": "VEN",
            "POWRUSDT": "POWR",
            "LENDUSDT": "LEND",
            "ADXUSDT": "ADX",
            "BNTUSDT": "BNT",
            "CMTUSDT": "CMT",
            "DNTUSDT": "DNT",
            "GTOUSDT": "GTO",
            "ICNUSDT": "ICN",
            "MCOUSDT": "MCO",
            "WTCUSDT": "WTC",
            "LRCUSDT": "LRC",
            "TNTUSDT": "TNT",
            "FUELUSDT": "FUEL",
            "BCPTUSDT": "BCPT",
            "NEBLUSDT": "NEBL",
            "GASUSDT": "GAS",
            "NAVUSDT": "NAV",
            "TRIGUSDT": "TRIG",
            "APPCUSDT": "APPC",
            "VIBUSDT": "VIB",
            "RLCUSDT": "RLC",
            "INSUSDT": "INS",
            "PIVXUSDT": "PIVX",
            "CHATUSDT": "CHAT",
            "STEEMUSDT": "STEEM",
            "VIAUSDT": "VIA",
            "BLZUSDT": "BLZ",
            "AEUSDT": "AE",
            "RPXUSDT": "RPX",
            "NCASHUSDT": "NCASH",
            "POAUSDT": "POA",
            "STXUSDT": "STX",
            "QKCUSDT": "QKC"
        }
        
        # Check if it's a known trading pair
        if symbol in pair_to_coin:
            return pair_to_coin[symbol]
        
        # If it's already a single coin symbol, return as-is
        # Common single coin symbols
        single_coins = {
            "BTC", "ETH", "SOL", "AVAX", "MATIC", "DOGE", "ADA", "DOT", "LINK", 
            "UNI", "ATOM", "NEAR", "FTM", "ALGO", "ICP", "VET", "FIL", "TRX", 
            "ETC", "XLM", "BCH", "LTC", "XRP", "BNB", "SHIB", "APE", "SAND", 
            "MANA", "AXS", "CRV", "COMP", "MKR", "SNX", "YFI", "SUSHI", "1INCH", 
            "AAVE", "GRT", "BAT", "ZRX", "ENJ", "CHZ", "HOT", "ZIL", "IOTA", 
            "ONT", "QTUM", "NEO", "WAVES", "OMG", "ZEC", "DASH", "XMR", "EOS", 
            "IOST", "NANO", "DGB", "RVN", "SC", "STORJ", "KNC", "REP", "LSK", 
            "ARDR", "ARK", "STRAT", "FUN", "REQ", "XEM", "ICX", "VEN", "POWR", 
            "LEND", "ADX", "BNT", "CMT", "DNT", "GTO", "ICN", "MCO", "WTC", 
            "LRC", "TNT", "FUEL", "BCPT", "NEBL", "GAS", "NAV", "TRIG", "APPC", 
            "VIB", "RLC", "INS", "PIVX", "CHAT", "STEEM", "VIA", "BLZ", "AE", 
            "RPX", "NCASH", "POA", "STX", "QKC"
        }
        
        if symbol in single_coins:
            return symbol
        
        # If we can't determine the coin, try to extract from common patterns
        # Remove common suffixes
        for suffix in ["USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP"]:
            if symbol.endswith(suffix):
                coin = symbol[:-len(suffix)]
                if coin in single_coins:
                    return coin
        
        # Default fallback - return the symbol as-is and let the API handle it
        self.logger.warning(f"Unknown symbol format: {symbol}, using as-is")
        return symbol


# ============================================
# Convenience Stream Builders
# ============================================

def create_candle_stream(symbol: str, interval: str) -> HyperliquidWSClient:
    """
    Create a WebSocket client configured for candle streaming.

    Args:
        symbol: Trading pair (e.g., "BTC", "ETH")
        interval: Candle interval (e.g., "1m", "5m", "1h", "1d")

    Returns:
        HyperliquidWSClient instance

    Example:
        >>> client = create_candle_stream("BTC", "1m")
        >>> async for candle in client.stream_ohlc("BTC", "1m"):
        ...     print(candle.close)
    """
    return HyperliquidWSClient()


def create_trade_stream(symbol: str) -> HyperliquidWSClient:
    """
    Create a WebSocket client configured for trade streaming.

    Args:
        symbol: Trading pair (e.g., "BTC", "ETH")

    Returns:
        HyperliquidWSClient instance

    Example:
        >>> client = create_trade_stream("BTC")
        >>> async for trade in client.stream_trades("BTC"):
        ...     print(f"{trade.side}: {trade.quantity}")
    """
    return HyperliquidWSClient()
