"""
Binance REST API Client

This module provides an async HTTP client for interacting with Binance Futures REST API.
It handles:
- HTTP requests with retry logic
- Rate limit handling (429, 418, 503 errors)
- Error handling and logging
- Data normalization to our schemas

API Documentation:
    https://binance-docs.github.io/apidocs/futures/en/

Rate Limits:
    - Weight-based system (each endpoint has a weight)
    - 2400 weight per minute limit
    - This client implements automatic retry with exponential backoff

Usage:
    async with BinanceAPIClient() as client:
        ohlc_data = await client.get_ohlc("BTCUSDT", "1h", limit=100)
        oi_data = await client.get_open_interest("BTCUSDT")
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional, Any
from core.logging import get_logger
from core.utils.time import to_utc_datetime
from core.schemas import OHLC, OpenInterest, FundingRate


class BinanceAPIClient:
    """
    Async HTTP client for Binance Futures REST API

    This client provides methods to fetch market data from Binance Futures (USD-M).
    All methods return normalized data using our Pydantic schemas.

    Attributes:
        BASE_URL: Binance Futures API base URL
        api_key: Optional API key for authenticated endpoints
        session: aiohttp ClientSession for HTTP requests
        logger: Logger instance for debugging

    Example:
        >>> async with BinanceAPIClient() as client:
        ...     ohlc = await client.get_ohlc("BTCUSDT", "1h", limit=100)
        ...     print(f"Fetched {len(ohlc)} candles")

    Notes:
        - Uses context manager for automatic session cleanup
        - Implements retry logic for rate limits
        - All timestamps converted to UTC datetime
        - No API key needed for public endpoints
    """

    BASE_URL = "https://fapi.binance.com"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Binance API client.

        Args:
            api_key: Optional Binance API key (not needed for public endpoints)
        """
        self.api_key = api_key
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
        self.logger.debug("BinanceAPIClient session created")
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
            self.logger.debug("BinanceAPIClient session closed")

    # ============================================
    # HTTP Request Handler with Retry Logic
    # ============================================

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Make GET request to Binance API with retry logic.

        This method handles:
        - Rate limiting (429, 418, 503 errors) with exponential backoff
        - Request timeouts
        - Error logging
        - Automatic retries (up to 3 attempts)

        Args:
            path: API endpoint path (e.g., "/fapi/v1/klines")
            params: Optional query parameters

        Returns:
            JSON response from API

        Raises:
            RuntimeError: If request fails after all retries

        Rate Limit Handling:
            - 429: Too many requests
            - 418: IP banned (temporary)
            - 503: Service unavailable

            Retry delay: 1.5s * (attempt + 1)
        """
        if not self.session:
            raise RuntimeError("Client session not initialized. Use 'async with' statement.")

        url = f"{self.BASE_URL}{path}"

        # Build headers
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key

        # Retry loop (max 3 attempts)
        for attempt in range(3):
            try:
                async with self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    # Success
                    if resp.status == 200:
                        data = await resp.json()
                        self.logger.debug(f"GET {path} - Success (attempt {attempt + 1})")
                        return data

                    # Rate limit errors - retry with backoff
                    elif resp.status in (429, 418, 503):
                        delay = 1.5 * (attempt + 1)
                        self.logger.warning(
                            f"Rate limited (HTTP {resp.status}) on {path}. "
                            f"Retrying in {delay:.1f}s... (attempt {attempt + 1}/3)"
                        )
                        await asyncio.sleep(delay)
                        continue

                    # Other errors - log and break
                    else:
                        text = await resp.text()
                        self.logger.error(f"HTTP {resp.status} on {path}: {text}")
                        break

            except asyncio.TimeoutError:
                self.logger.error(f"Timeout on {path} (attempt {attempt + 1}/3)")
                await asyncio.sleep(1.0 * (attempt + 1))

            except Exception as e:
                self.logger.error(f"Request failed on {path}: {e} (attempt {attempt + 1}/3)")
                await asyncio.sleep(1.0 * (attempt + 1))

        # All retries failed
        raise RuntimeError(f"Failed to fetch {url} after 3 attempts")

    # ============================================
    # API Methods
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
        Fetch historical OHLC (candlestick) data.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Candlestick interval (e.g., "1m", "5m", "1h", "1d")
            limit: Number of candles to fetch (max 1500, default 500)
            start_time: Optional start time in milliseconds since epoch
            end_time: Optional end time in milliseconds since epoch

        Returns:
            List of OHLC objects sorted by timestamp (oldest first)

        Raises:
            RuntimeError: If API request fails

        Binance Endpoint:
            GET /fapi/v1/klines

        Response Format:
            [
              [
                1499040000000,      // Open time
                "0.01634000",       // Open
                "0.80000000",       // High
                "0.01575800",       // Low
                "0.01577100",       // Close
                "148976.11427815",  // Volume
                1499644799999,      // Close time
                "2434.19055334",    // Quote asset volume
                308,                // Number of trades
                ...
              ]
            ]

        Example:
            >>> ohlc = await client.get_ohlc("BTCUSDT", "1h", limit=100)
            >>> print(f"Latest close: ${ohlc[-1].close:,.2f}")
            
            >>> # Fetch candles for a specific time range
            >>> start = 1704110400000  # Jan 1, 2024 12:00:00 UTC
            >>> end = 1704114000000     # Jan 1, 2024 13:00:00 UTC
            >>> ohlc = await client.get_ohlc("BTCUSDT", "1h", start_time=start, end_time=end)
        """
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, 1500)  # Binance max is 1500
        }

        # Add optional time range parameters
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        log_msg = f"Fetching OHLC: {symbol} {interval} (limit={limit}"
        if start_time:
            log_msg += f", startTime={start_time}"
        if end_time:
            log_msg += f", endTime={end_time}"
        log_msg += ")"
        self.logger.info(log_msg)

        data = await self._get("/fapi/v1/klines", params)

        # Normalize to OHLC schema
        ohlc_list = [
            OHLC(
                exchange="binance",
                symbol=symbol.upper(),
                interval=interval,
                timestamp=to_utc_datetime(item[0]),  # Open time in milliseconds
                open=float(item[1]),
                high=float(item[2]),
                low=float(item[3]),
                close=float(item[4]),
                volume=float(item[5]),
                quote_volume=float(item[7]),
                trades_count=int(item[8]),
                is_closed=True  # Historical candles are always closed
            )
            for item in data
        ]

        self.logger.info(f"Fetched {len(ohlc_list)} OHLC candles for {symbol}")
        return ohlc_list

    async def get_funding_info(self) -> List[Dict[str, Any]]:
        """
        Fetch funding rate info for all symbols.

        Returns info about funding rate caps and floors.

        Returns:
            List of funding info dictionaries

        Binance Endpoint:
            GET /fapi/v1/fundingInfo

        Response Format:
            [
              {
                "symbol": "BTCUSDT",
                "adjustedFundingRateCap": "0.02500000",
                "adjustedFundingRateFloor": "-0.02500000",
                "fundingIntervalHours": 8
              }
            ]

        Example:
            >>> info = await client.get_funding_info()
            >>> btc_info = [x for x in info if x["symbol"] == "BTCUSDT"][0]
            >>> print(f"Funding interval: {btc_info['fundingIntervalHours']}h")
        """
        self.logger.info("Fetching funding info")
        data = await self._get("/fapi/v1/fundingInfo")
        self.logger.info(f"Fetched funding info for {len(data)} symbols")
        return data

    async def get_funding_rate(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[FundingRate]:
        """
        Fetch historical funding rates for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            limit: Number of records to fetch (max 1000, default 100)

        Returns:
            List of FundingRate objects

        Binance Endpoint:
            GET /fapi/v1/fundingRate

        Response Format:
            [
              {
                "symbol": "BTCUSDT",
                "fundingRate": "0.00010000",
                "fundingTime": 1608307200000
              }
            ]

        Notes:
            - Funding occurs every 8 hours (00:00, 08:00, 16:00 UTC)
            - Positive rate: Longs pay shorts
            - Negative rate: Shorts pay longs

        Example:
            >>> rates = await client.get_funding_rate("BTCUSDT", limit=10)
            >>> latest = rates[-1]
            >>> print(f"Latest funding: {latest.funding_rate * 100:.4f}%")
        """
        params = {
            "symbol": symbol.upper(),
            "limit": min(limit, 1000)  # Binance max is 1000
        }

        self.logger.info(f"Fetching funding rate history: {symbol} (limit={limit})")

        data = await self._get("/fapi/v1/fundingRate", params)

        # Normalize to FundingRate schema
        funding_rates = [
            FundingRate(
                exchange="binance",
                symbol=item["symbol"],
                funding_rate=float(item["fundingRate"]),
                funding_time=to_utc_datetime(item["fundingTime"]),
                timestamp=to_utc_datetime(item["fundingTime"])
            )
            for item in data
        ]

        self.logger.info(f"Fetched {len(funding_rates)} funding rates for {symbol}")
        return funding_rates

    async def get_open_interest(self, symbol: str) -> OpenInterest:
        """
        Fetch current open interest for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            OpenInterest object with current snapshot

        Binance Endpoint:
            GET /fapi/v1/openInterest

        Response Format:
            {
              "symbol": "BTCUSDT",
              "openInterest": "10659.509",
              "time": 1589437530011
            }

        Example:
            >>> oi = await client.get_open_interest("BTCUSDT")
            >>> print(f"Open Interest: {oi.open_interest:,.2f} BTC")
        """
        params = {"symbol": symbol.upper()}

        self.logger.info(f"Fetching open interest: {symbol}")

        data = await self._get("/fapi/v1/openInterest", params)

        # Normalize to OpenInterest schema
        oi = OpenInterest(
            exchange="binance",
            symbol=data["symbol"],
            open_interest=float(data["openInterest"]),
            timestamp=to_utc_datetime(data["time"])
        )

        self.logger.info(f"Open interest for {symbol}: {oi.open_interest:,.2f}")
        return oi

    async def get_open_interest_hist(
        self,
        symbol: str,
        period: str = "5m",
        limit: int = 30
    ) -> List[OpenInterest]:
        """
        Fetch historical open interest data.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            period: Time period ("5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d")
            limit: Number of records to fetch (max 500, default 30)

        Returns:
            List of OpenInterest objects

        Binance Endpoint:
            GET /futures/data/openInterestHist

        Response Format:
            [
              {
                "symbol": "BTCUSDT",
                "sumOpenInterest": "10659.509",
                "sumOpenInterestValue": "532974500.23",
                "timestamp": 1589437530011
              }
            ]

        Example:
            >>> oi_hist = await client.get_open_interest_hist("BTCUSDT", "1h", limit=24)
            >>> print(f"Fetched {len(oi_hist)} hourly OI snapshots")
        """
        params = {
            "symbol": symbol.upper(),
            "period": period,
            "limit": min(limit, 500)  # Binance max is 500
        }

        self.logger.info(f"Fetching OI history: {symbol} {period} (limit={limit})")

        data = await self._get("/futures/data/openInterestHist", params)

        # Normalize to OpenInterest schema
        oi_list = [
            OpenInterest(
                exchange="binance",
                symbol=item["symbol"],
                open_interest=float(item["sumOpenInterest"]),
                open_interest_value=float(item["sumOpenInterestValue"]),
                timestamp=to_utc_datetime(item["timestamp"])
            )
            for item in data
        ]

        self.logger.info(f"Fetched {len(oi_list)} OI history records for {symbol}")
        return oi_list
