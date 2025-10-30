"""
Bybit REST API Client

This module provides an async HTTP client for interacting with Bybit REST API.
It handles:
- HTTP GET requests with retry logic
- Rate limit handling
- Error handling and logging
- Data normalization to our schemas

API Documentation:
    https://bybit-exchange.github.io/docs/v5/intro

Rate Limits:
    - Bybit has rate limits on their endpoints
    - This client implements automatic retry with exponential backoff

Usage:
    async with BybitAPIClient() as client:
        ohlc_data = await client.get_historical_ohlc("BTCUSDT", "1m", limit=100)
        oi_data = await client.get_open_interest("BTCUSDT")
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional, Any
from core.logging import get_logger
from core.utils.time import to_utc_datetime
from core.schemas import OHLC, OpenInterest, FundingRate


class BybitAPIClient:
    """
    Async HTTP client for Bybit REST API

    This client provides methods to fetch market data from Bybit.
    All methods return normalized data using our Pydantic schemas.

    Attributes:
        BASE_URL: Bybit API base URL
        session: aiohttp ClientSession for HTTP requests
        logger: Logger instance for debugging

    Example:
        >>> async with BybitAPIClient() as client:
        ...     ohlc = await client.get_historical_ohlc("BTCUSDT", "1m", limit=100)
        ...     print(f"Fetched {len(ohlc)} candles")

    Notes:
        - Uses context manager for automatic session cleanup
        - Implements retry logic for rate limits
        - All timestamps converted to UTC datetime
        - Uses GET requests with query parameters (Bybit API standard)
    """

    BASE_URL = "https://api.bybit.com/v5/market"

    def __init__(self):
        """
        Initialize the Bybit API client.
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
        self.logger.debug("BybitAPIClient session created")
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
            self.logger.debug("BybitAPIClient session closed")

    # ============================================
    # HTTP Request Handler with Retry Logic
    # ============================================

    async def _get(self, endpoint: str, params: Dict[str, Any] = None) -> Any:
        """
        Make GET request to Bybit API with retry logic.

        Args:
            endpoint: API endpoint (e.g., "/kline")
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            Exception: If all retry attempts fail
        """
        url = f"{self.BASE_URL}{endpoint}"
        params = params or {}

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check Bybit response format
                        if data.get("retCode") != 0:
                            error_msg = data.get("retMsg", "Unknown error")
                            raise Exception(f"Bybit API error: {error_msg}")
                        
                        return data.get("result", {})
                    else:
                        raise Exception(f"HTTP {response.status}: {await response.text()}")
                        
            except Exception as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Bybit API request failed after {max_retries} attempts: {e}")
                    raise
                
                # Exponential backoff
                wait_time = 2 ** attempt
                self.logger.warning(f"Bybit API request failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)

    # ============================================
    # Market Data Methods
    # ============================================

    async def get_server_time(self) -> Optional[int]:
        """
        Get Bybit server time for health checks.

        Returns:
            Server timestamp in milliseconds, or None if failed

        Bybit Endpoint:
            GET /v5/market/time
        """
        try:
            data = await self._get("/time")
            return int(data.get("timeSecond", 0)) * 1000  # Convert to milliseconds
        except Exception as e:
            self.logger.error(f"Failed to get Bybit server time: {e}")
            return None

    async def get_historical_ohlc(
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
            symbol: Trading symbol (e.g., "BTCUSDT")
            interval: Candlestick interval (e.g., "1m", "5m", "1h", "1d")
            limit: Number of candles to fetch (max 1000)
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)

        Returns:
            List[OHLC]: List of candlestick data

        Bybit Endpoint:
            GET /v5/market/kline

        Notes:
            - Bybit returns data sorted by timestamp (oldest first)
            - We reverse it to match our convention (newest first)
            - Symbol should be uppercase (BTCUSDT)
            - Bybit uses numeric intervals: 1,3,5,15,30,60,120,240,360,720,D,W,M
        """
        self.logger.info(f"Fetching historical OHLC: {symbol} {interval} (limit={limit})")

        # Convert interval format to Bybit format
        bybit_interval = self._convert_interval_to_bybit(interval)

        params = {
            "category": "linear",  # USDT perpetual contracts
            "symbol": symbol.upper(),
            "interval": bybit_interval,
            "limit": min(limit, 1000)  # Bybit max is 1000
        }

        if start_time:
            params["start"] = start_time
        if end_time:
            params["end"] = end_time

        try:
            data = await self._get("/kline", params)
            candles = []

            # Bybit returns list of arrays: [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]
            for candle_data in data.get("list", []):
                candles.append(
                    OHLC(
                        exchange="bybit",
                        symbol=symbol.upper(),
                        interval=interval,
                        timestamp=to_utc_datetime(int(candle_data[0])),  # startTime
                        open=float(candle_data[1]),  # openPrice
                        high=float(candle_data[2]),  # highPrice
                        low=float(candle_data[3]),   # lowPrice
                        close=float(candle_data[4]), # closePrice
                        volume=float(candle_data[5]), # volume (base asset)
                        quote_volume=float(candle_data[6]), # turnover (quote asset)
                        trades_count=0,  # Not provided by Bybit
                        is_closed=True   # Historical data is always closed
                    )
                )

            # Reverse to get newest first (our convention)
            candles.reverse()
            
            self.logger.info(f"Fetched {len(candles)} OHLC candles for {symbol}")
            return candles

        except Exception as e:
            self.logger.error(f"Failed to fetch OHLC data for {symbol}: {e}")
            return []

    async def get_open_interest(self, symbol: str) -> Optional[OpenInterest]:
        """
        Get current open interest for a symbol.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")

        Returns:
            OpenInterest: Current open interest data, or None if not found

        Bybit Endpoint:
            GET /v5/market/open-interest

        Notes:
            - Bybit requires intervalTime parameter
            - We use "1h" interval for current data
        """
        self.logger.info(f"Fetching open interest: {symbol}")

        params = {
            "category": "linear",
            "symbol": symbol.upper(),
            "intervalTime": "1h",
            "limit": 1
        }

        try:
            data = await self._get("/open-interest", params)
            oi_list = data.get("list", [])

            if not oi_list:
                self.logger.warning(f"No open interest data found for {symbol}")
                return None

            # Get the most recent OI data
            oi_data = oi_list[0]
            
            oi = OpenInterest(
                exchange="bybit",
                symbol=symbol.upper(),
                timestamp=to_utc_datetime(int(oi_data["timestamp"])),
                open_interest=float(oi_data["openInterest"]),
                open_interest_value=None  # Bybit doesn't provide USD value directly
            )

            self.logger.info(f"Open interest for {symbol}: {oi.open_interest:,.2f}")
            return oi

        except Exception as e:
            self.logger.error(f"Failed to fetch open interest for {symbol}: {e}")
            return None

    async def get_funding_rate(
        self,
        symbol: str,
        limit: int = 200
    ) -> List[FundingRate]:
        """
        Get historical funding rates for a symbol.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            limit: Number of funding rates to fetch (max 200)

        Returns:
            List[FundingRate]: List of funding rate data

        Bybit Endpoint:
            GET /v5/market/funding/history

        Notes:
            - Bybit funding rates are applied every 8 hours
            - Data is sorted by timestamp (newest first)
        """
        self.logger.info(f"Fetching funding rate history: {symbol} (limit={limit})")

        params = {
            "category": "linear",
            "symbol": symbol.upper(),
            "limit": min(limit, 200)  # Bybit max is 200
        }

        try:
            data = await self._get("/funding/history", params)
            funding_rates = []

            for fr_data in data.get("list", []):
                funding_rates.append(
                    FundingRate(
                        exchange="bybit",
                        symbol=symbol.upper(),
                        timestamp=to_utc_datetime(int(fr_data["fundingRateTimestamp"])),
                        funding_rate=float(fr_data["fundingRate"]),
                        funding_time=to_utc_datetime(int(fr_data["fundingRateTimestamp"])),
                        next_funding_rate=None,  # Not provided by Bybit
                        next_funding_time=None   # Not provided by Bybit
                    )
                )

            self.logger.info(f"Fetched {len(funding_rates)} funding rates for {symbol}")
            return funding_rates

        except Exception as e:
            self.logger.error(f"Failed to fetch funding rates for {symbol}: {e}")
            return []

    async def get_predicted_funding(self) -> Dict[str, float]:
        """
        Get predicted funding rates for all symbols.

        Returns:
            Dict[str, float]: Symbol -> predicted funding rate mapping

        Bybit Endpoint:
            GET /v5/market/tickers

        Notes:
            - This is a workaround since Bybit doesn't have a dedicated predicted funding endpoint
            - We fetch ticker data which includes some funding information
            - Returns empty dict if not available
        """
        self.logger.info("Fetching predicted funding rates")

        params = {
            "category": "linear"
        }

        try:
            data = await self._get("/tickers", params)
            predicted = {}

            for ticker in data.get("list", []):
                symbol = ticker.get("symbol")
                # Bybit doesn't provide predicted funding in tickers
                # This is a placeholder for future implementation
                if symbol:
                    predicted[symbol] = 0.0  # Default to 0%

            self.logger.info(f"Fetched predicted funding for {len(predicted)} symbols")
            return predicted

        except Exception as e:
            self.logger.error(f"Failed to fetch predicted funding: {e}")
            return {}

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
