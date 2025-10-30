"""
Hyperliquid REST API Client

This module provides an async HTTP client for interacting with Hyperliquid REST API.
It handles:
- HTTP POST requests with retry logic
- Rate limit handling
- Error handling and logging
- Data normalization to our schemas

API Documentation:
    https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api

Rate Limits:
    - Hyperliquid has rate limits on their endpoints
    - This client implements automatic retry with exponential backoff

Usage:
    async with HyperliquidAPIClient() as client:
        ohlc_data = await client.get_historical_ohlc("BTC", "1m", start_time, end_time)
        oi_data = await client.get_open_interest("BTC")
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional, Any
from core.logging import get_logger
from core.utils.time import to_utc_datetime
from core.schemas import OHLC, OpenInterest, FundingRate


class HyperliquidAPIClient:
    """
    Async HTTP client for Hyperliquid REST API

    This client provides methods to fetch market data from Hyperliquid.
    All methods return normalized data using our Pydantic schemas.

    Attributes:
        BASE_URL: Hyperliquid API base URL
        session: aiohttp ClientSession for HTTP requests
        logger: Logger instance for debugging

    Example:
        >>> async with HyperliquidAPIClient() as client:
        ...     ohlc = await client.get_historical_ohlc("BTC", "1m", 1720000000000, 1720010000000)
        ...     print(f"Fetched {len(ohlc)} candles")

    Notes:
        - Uses context manager for automatic session cleanup
        - Implements retry logic for rate limits
        - All timestamps converted to UTC datetime
        - Uses POST requests with JSON payloads (Hyperliquid API standard)
    """

    BASE_URL = "https://api.hyperliquid.xyz/info"

    def __init__(self):
        """
        Initialize the Hyperliquid API client.
        """
        self.logger = get_logger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None

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
        self.logger.debug("HyperliquidAPIClient session created")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit async context - closes HTTP session.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        if self.session:
            await self.session.close()
            self.logger.debug("HyperliquidAPIClient session closed")

    # ============================================
    # HTTP Request Handler with Retry Logic
    # ============================================

    async def _post(self, payload: Dict[str, Any]) -> Any:
        """
        Make POST request to Hyperliquid API with retry logic.

        This method handles:
        - Rate limiting (429 errors) with exponential backoff
        - Request timeouts
        - Error logging
        - Automatic retries (up to 3 attempts)

        Args:
            payload: JSON payload for the POST request

        Returns:
            JSON response from API

        Raises:
            RuntimeError: If request fails after all retries

        Rate Limit Handling:
            - 429: Too many requests
            Retry delay: 1.5s * (attempt + 1)
        """
        if not self.session:
            raise RuntimeError("Client session not initialized. Use 'async with' statement.")

        url = self.BASE_URL

        # Build headers
        headers = {"Content-Type": "application/json"}

        # Retry loop (max 3 attempts)
        for attempt in range(3):
            try:
                async with self.session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    # Success
                    if resp.status == 200:
                        data = await resp.json()
                        self.logger.debug(f"POST {payload.get('type', 'unknown')} - Success (attempt {attempt + 1})")
                        return data

                    # Rate limit errors - retry with backoff
                    elif resp.status in (429, 503):
                        delay = 1.5 * (attempt + 1)
                        self.logger.warning(
                            f"Rate limited (HTTP {resp.status}) on {payload.get('type', 'unknown')}. "
                            f"Retrying in {delay:.1f}s... (attempt {attempt + 1}/3)"
                        )
                        await asyncio.sleep(delay)
                        continue

                    # Other errors - log and break
                    else:
                        text = await resp.text()
                        self.logger.error(f"HTTP {resp.status} on {payload.get('type', 'unknown')}: {text}")
                        break

            except asyncio.TimeoutError:
                self.logger.error(f"Timeout on {payload.get('type', 'unknown')} (attempt {attempt + 1}/3)")
                await asyncio.sleep(1.0 * (attempt + 1))

            except Exception as e:
                self.logger.error(f"Request failed on {payload.get('type', 'unknown')}: {e} (attempt {attempt + 1}/3)")
                await asyncio.sleep(1.0 * (attempt + 1))

        # All retries failed
        raise RuntimeError(f"Failed to fetch from {url} after 3 attempts")

    # ============================================
    # API Methods
    # ============================================

    async def get_open_interest(self, symbol: str) -> Optional[OpenInterest]:
        """
        Fetch current open interest for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT" -> "BTC", "ETHUSDT" -> "ETH")

        Returns:
            OpenInterest object with current snapshot, or None if not found

        Hyperliquid Endpoint:
            POST /info with {"type": "metaAndAssetCtxs"}

        Response Format:
            [
              {
                "universe": [...],
                "coins": [
                  {
                    "name": "BTC",
                    "openInterest": "123456.78",
                    "markPrice": "50000.0",
                    "timestamp": 1704110400000
                  }
                ]
              }
            ]

        Example:
            >>> oi = await client.get_open_interest("BTCUSDT")
            >>> print(f"Open Interest: {oi.open_interest:,.2f} BTC")
        """
        # Convert trading pair to coin symbol (BTCUSDT -> BTC)
        coin_symbol = self._extract_coin_symbol(symbol)
        
        payload = {"type": "metaAndAssetCtxs"}

        self.logger.info(f"Fetching open interest: {symbol} -> {coin_symbol}")

        try:
            data = await self._post(payload)

            # Parse response structure
            # Response is a list with 2 elements:
            # [0] = meta (universe, marginTables, etc.)
            # [1] = asset contexts (list of OI, funding, markPx, etc.)
            if not data or not isinstance(data, list) or len(data) < 2:
                self.logger.warning(f"Unexpected response format for OI: {data}")
                return None

            meta = data[0]
            asset_ctxs = data[1]

            if not isinstance(asset_ctxs, list):
                self.logger.warning(f"Asset contexts not a list: {type(asset_ctxs)}")
                return None

            coins = meta.get("universe", [])

            # Find the matching coin index
            for idx, coin_info in enumerate(coins):
                coin_name = coin_info.get("name", "").upper()
                if coin_name == coin_symbol.upper():
                    # Get the context data from the same index
                    if idx < len(asset_ctxs):
                        ctx = asset_ctxs[idx]
                        oi_value = float(ctx.get("openInterest", 0))
                        mark_price = float(ctx.get("markPx", 0))

                        # Use current time since assetCtxs doesn't include timestamp
                        from core.utils.time import current_utc_datetime

                        oi = OpenInterest(
                            exchange="hyperliquid",
                            symbol=symbol.upper(),  # Keep original symbol for consistency
                            open_interest=oi_value,
                            open_interest_value=oi_value * mark_price if mark_price > 0 else None,
                            timestamp=current_utc_datetime()
                        )

                        self.logger.info(f"Open interest for {symbol}: {oi.open_interest:,.2f}")
                        return oi

            self.logger.warning(f"No OI data found for {symbol} (coin: {coin_symbol})")
            return None

        except Exception as e:
            self.logger.error(f"Error fetching open interest for {symbol}: {e}")
            return None

    async def get_funding_rate(self, symbol: str, limit: int = 100) -> List[FundingRate]:
        """
        Fetch historical funding rates for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT" -> "BTC", "ETHUSDT" -> "ETH")
            limit: Number of records to return (default 100)

        Returns:
            List of FundingRate objects (up to limit, most recent last)

        Hyperliquid Endpoint:
            POST /info with {"type": "fundingHistory", "coin": "BTC"}

        Response Format:
            [
              {
                "coin": "BTC",
                "fundingRate": "0.0001",
                "premium": "0.00005",
                "time": 1704110400000
              }
            ]

        Notes:
            - Funding occurs every 8 hours on Hyperliquid
            - Positive rate: Longs pay shorts
            - Negative rate: Shorts pay longs

        Example:
            >>> rates = await client.get_funding_rate("BTCUSDT", limit=10)
            >>> latest = rates[-1]
            >>> print(f"Latest funding: {latest.funding_rate * 100:.4f}%")
        """
        # Convert trading pair to coin symbol (BTCUSDT -> BTC)
        coin_symbol = self._extract_coin_symbol(symbol)
        
        # Hyperliquid requires startTime parameter
        # Use a reasonable default (90 days ago) to get recent history
        from core.utils.time import current_utc_timestamp
        default_start_time = current_utc_timestamp(milliseconds=True) - (90 * 24 * 60 * 60 * 1000)

        payload = {
            "type": "fundingHistory",
            "coin": coin_symbol.upper(),
            "startTime": default_start_time
        }

        self.logger.info(f"Fetching funding rate history: {symbol} -> {coin_symbol} (limit={limit})")

        try:
            data = await self._post(payload)

            if not data:
                self.logger.warning(f"No funding history for {symbol}")
                return []

            # Take the most recent 'limit' entries
            funding_data = data[-limit:] if len(data) > limit else data

            # Normalize to FundingRate schema
            funding_rates = [
                FundingRate(
                    exchange="hyperliquid",
                    symbol=symbol.upper(),
                    funding_rate=float(item["fundingRate"]),
                    funding_time=to_utc_datetime(item["time"]),
                    timestamp=to_utc_datetime(item["time"]),
                    next_funding_rate=None,  # Not provided by this endpoint
                    next_funding_time=None   # Not provided by this endpoint
                )
                for item in funding_data
            ]

            self.logger.info(f"Fetched {len(funding_rates)} funding rates for {symbol}")
            return funding_rates

        except Exception as e:
            self.logger.error(f"Error fetching funding rate for {symbol}: {e}")
            return []

    async def get_predicted_funding(self) -> Dict[str, float]:
        """
        Fetch predicted next funding rates for all symbols.

        Returns:
            Dictionary mapping symbol to predicted funding rate (Hyperliquid only)

        Hyperliquid Endpoint:
            POST /info with {"type": "predictedFundings"}

        Response Format:
            [
              ["BTC", [
                ["BinPerp", {"fundingRate": "0.00015", ...}],
                ["HlPerp", {"fundingRate": "0.0001", ...}],
                ...
              ]],
              ...
            ]

        Example:
            >>> predicted = await client.get_predicted_funding()
            >>> print(f"BTC predicted: {predicted.get('BTC', 0) * 100:.4f}%")
        """
        payload = {"type": "predictedFundings"}

        self.logger.info("Fetching predicted funding rates")

        try:
            data = await self._post(payload)

            if not data:
                self.logger.warning("No predicted funding data")
                return {}

            # Parse nested structure: [[coin, [[exchange, data], ...]], ...]
            result = {}
            for item in data:
                if not isinstance(item, list) or len(item) < 2:
                    continue

                coin = item[0]
                exchanges_data = item[1]

                # Find Hyperliquid's prediction (HlPerp)
                for exchange_data in exchanges_data:
                    if not isinstance(exchange_data, list) or len(exchange_data) < 2:
                        continue

                    exchange_name = exchange_data[0]
                    if exchange_name == "HlPerp":
                        funding_info = exchange_data[1]
                        result[coin] = float(funding_info.get("fundingRate", 0))
                        break

            self.logger.info(f"Fetched predicted funding for {len(result)} symbols")
            return result

        except Exception as e:
            self.logger.error(f"Error fetching predicted funding: {e}")
            return {}

    async def get_historical_ohlc(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int
    ) -> List[OHLC]:
        """
        Fetch historical OHLC (candlestick) data.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT" -> "BTC", "ETHUSDT" -> "ETH")
            interval: Candlestick interval (e.g., "1m", "5m", "1h", "1d")
            start_time: Start time in milliseconds
            end_time: End time in milliseconds

        Returns:
            List of OHLC objects sorted by timestamp (oldest first)

        Raises:
            RuntimeError: If API request fails

        Hyperliquid Endpoint:
            POST /info with {"type": "candleSnapshot", "req": {...}}

        Request Format:
            {
              "type": "candleSnapshot",
              "req": {
                "coin": "BTC",
                "interval": "1m",
                "startTime": 1720000000000,
                "endTime": 1720010000000
              }
            }

        Response Format:
            [
              {
                "t": 1720000000000,  // Open time
                "o": "50000.0",      // Open
                "h": "50500.0",      // High
                "l": "49500.0",      // Low
                "c": "50250.0",      // Close
                "v": "125.5",        // Volume
                "n": 1523            // Number of trades
              }
            ]

        Notes:
            - Can fetch up to ~5000 candles per request
            - All timestamps in milliseconds

        Example:
            >>> ohlc = await client.get_historical_ohlc("BTCUSDT", "1h", 1720000000000, 1720086400000)
            >>> print(f"Latest close: ${ohlc[-1].close:,.2f}")
        """
        # Convert trading pair to coin symbol (BTCUSDT -> BTC)
        coin_symbol = self._extract_coin_symbol(symbol)
        
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": coin_symbol.upper(),
                "interval": interval,
                "startTime": start_time,
                "endTime": end_time
            }
        }

        self.logger.info(f"Fetching historical OHLC: {symbol} -> {coin_symbol} {interval} ({start_time} - {end_time})")

        try:
            data = await self._post(payload)

            if not data:
                self.logger.warning(f"No OHLC data for {symbol}")
                return []

            # Normalize to OHLC schema
            ohlc_list = [
                OHLC(
                    exchange="hyperliquid",
                    symbol=symbol.upper(),  # Keep original symbol for consistency
                    interval=interval,
                    timestamp=to_utc_datetime(item["t"]),
                    open=float(item["o"]),
                    high=float(item["h"]),
                    low=float(item["l"]),
                    close=float(item["c"]),
                    volume=float(item["v"]),
                    quote_volume=float(item.get("v", 0)) * float(item["c"]),  # Estimate quote volume
                    trades_count=int(item.get("n", 0)),
                    is_closed=True  # Historical candles are always closed
                )
                for item in data
            ]

            self.logger.info(f"Fetched {len(ohlc_list)} OHLC candles for {symbol}")
            return ohlc_list

        except Exception as e:
            self.logger.error(f"Error fetching historical OHLC for {symbol}: {e}")
            return []

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
            "ADAUSDT": "ADA",
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
            "MANAUSDT": "MANA",
            "BCPTUSDT": "BCPT",
            "BNBUSDT": "BNB",
            "NEBLUSDT": "NEBL",
            "GASUSDT": "GAS",
            "NAVUSDT": "NAV",
            "TRIGUSDT": "TRIG",
            "APPCUSDT": "APPC",
            "VIBUSDT": "VIB",
            "RLCUSDT": "RLC",
            "INSUSDT": "INS",
            "PIVXUSDT": "PIVX",
            "IOSTUSDT": "IOST",
            "CHATUSDT": "CHAT",
            "STEEMUSDT": "STEEM",
            "NANOUSDT": "NANO",
            "VIAUSDT": "VIA",
            "BLZUSDT": "BLZ",
            "AEUSDT": "AE",
            "RPXUSDT": "RPX",
            "NCASHUSDT": "NCASH",
            "POAUSDT": "POA",
            "ZILUSDT": "ZIL",
            "ONTUSDT": "ONT",
            "STXUSDT": "STX",
            "QKCUSDT": "QKC",
            "LSKUSDT": "LSK",
            "ADAUSDT": "ADA",
            "XLMUSDT": "XLM",
            "IOTAUSDT": "IOTA",
            "NEOUSDT": "NEO",
            "XRPUSDT": "XRP",
            "ETCUSDT": "ETC",
            "BCHUSDT": "BCH",
            "LTCUSDT": "LTC",
            "BTCUSDT": "BTC",
            "ETHUSDT": "ETH"
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
