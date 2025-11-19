"""
Configuration Management Module

This module handles loading, validating, and providing access to application configuration
from environment variables (.env file).

Uses Pydantic Settings for automatic validation and type conversion.

Key Features:
- Loads configuration from .env file
- Validates all required settings
- Provides type-safe access to configuration values
- Converts comma-separated strings to lists (symbols, intervals)
- Handles optional settings with sensible defaults

Usage:
    from core.config import settings

    # Access configuration values
    print(settings.binance_base_url)
    print(settings.supported_symbols)  # Returns a list of strings
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class Settings(BaseSettings):
    """
    Application Settings

    This class defines all configuration parameters for the application.
    Values are automatically loaded from environment variables or .env file.

    Attributes:
        binance_base_url: Base URL for Binance Futures API
        binance_api_key: API key (optional, not needed for public endpoints)
        binance_secret_key: Secret key (optional, not needed for public endpoints)
        supported_symbols: List of trading pairs to support (e.g., ["BTCUSDT", "ETHUSDT"])
        supported_intervals: List of candlestick intervals (e.g., ["1m", "5m", "1h"])
        app_host: Host address for FastAPI server
        app_port: Port number for FastAPI server
        environment: Current environment (development, production)
        debug: Enable debug mode with verbose logging
        max_requests_per_second: Rate limit for API requests
        request_timeout: Timeout for HTTP requests in seconds
        ws_reconnect_delay: Delay between WebSocket reconnection attempts
        ws_max_reconnect_attempts: Maximum number of reconnection attempts
        redis_host: Redis server host (optional)
        redis_port: Redis server port
        redis_db: Redis database number
        cache_ttl: Cache time-to-live in seconds
        large_trade_threshold_usd: Minimum USD value for large trade detection
    """

    # ============================================
    # Binance API Configuration
    # ============================================

    binance_base_url: str = Field(
        default="https://fapi.binance.com",
        description="Binance Futures API base URL"
    )

    binance_api_key: str = Field(
        default="",
        description="Binance API key (optional for public endpoints)"
    )

    binance_secret_key: str = Field(
        default="",
        description="Binance secret key (optional for public endpoints)"
    )

    # ============================================
    # Supported Markets Configuration
    # ============================================

    supported_symbols: str = Field(
        default="BTCUSDT,ETHUSDT,SOLUSDT",
        description="Comma-separated list of trading pairs"
    )

    supported_intervals: str = Field(
        default="1m,5m,15m,1h,4h,1d",
        description="Comma-separated list of candlestick intervals"
    )

    # ============================================
    # Application Configuration
    # ============================================

    app_host: str = Field(
        default="0.0.0.0",
        description="FastAPI server host address"
    )

    app_port: int = Field(
        default=8000,
        description="FastAPI server port"
    )

    environment: str = Field(
        default="development",
        description="Application environment (development, production)"
    )

    debug: bool = Field(
        default=True,
        description="Enable debug mode"
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    # ============================================
    # Rate Limiting & Performance
    # ============================================

    max_requests_per_second: int = Field(
        default=10,
        description="Maximum API requests per second to avoid rate limits"
    )

    request_timeout: int = Field(
        default=30,
        description="HTTP request timeout in seconds"
    )

    ws_reconnect_delay: int = Field(
        default=5,
        description="Delay between WebSocket reconnection attempts (seconds)"
    )

    ws_max_reconnect_attempts: int = Field(
        default=10,
        description="Maximum WebSocket reconnection attempts"
    )

    # ============================================
    # Trading Configuration
    # ============================================

    large_trade_threshold_usd: int = Field(
        default=50_000,
        description="Minimum USD value for a trade to be considered 'large' ($100k default)"
    )

    # ============================================
    # CoinMarketCap API Configuration
    # ============================================

    coinmarketcap_api_key: str = Field(
        default="",
        description="CoinMarketCap API key (optional, for categories widget)"
    )

    # ============================================
    # CORS Configuration
    # ============================================

    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated list of allowed CORS origins"
    )

    # ============================================
    # Caching Configuration
    # ============================================

    redis_host: str = Field(
        default="",
        description="Redis server host (empty = use in-memory cache)"
    )

    redis_port: int = Field(
        default=6379,
        description="Redis server port"
    )

    redis_db: int = Field(
        default=0,
        description="Redis database number"
    )

    cache_ttl: int = Field(
        default=60,
        description="Cache TTL in seconds"
    )

    # ============================================
    # Pydantic Settings Configuration
    # ============================================

    model_config = SettingsConfigDict(
        # Look for .env file in the project root
        env_file=".env",
        # Ignore extra fields in .env that aren't defined here
        extra="ignore",
        # Case-insensitive environment variable matching
        case_sensitive=False
    )

    # ============================================
    # Custom Validators and Properties
    # ============================================

    @property
    def symbols_list(self) -> List[str]:
        """
        Convert comma-separated symbols string to a list.

        Returns:
            List of symbol strings (e.g., ["BTCUSDT", "ETHUSDT", "SOLUSDT"])

        Example:
            >>> settings.symbols_list
            ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        """
        return [s.strip().upper() for s in self.supported_symbols.split(",") if s.strip()]

    @property
    def intervals_list(self) -> List[str]:
        """
        Convert comma-separated intervals string to a list.

        Returns:
            List of interval strings (e.g., ["1m", "5m", "1h"])

        Example:
            >>> settings.intervals_list
            ['1m', '5m', '15m', '1h', '4h', '1d']
        """
        return [i.strip().lower() for i in self.supported_intervals.split(",") if i.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        """
        Convert comma-separated CORS origins string to a list.

        Returns:
            List of allowed origin URLs (e.g., ["http://localhost:3000", "https://myapp.com"])

        Example:
            >>> settings.cors_origins_list
            ['http://localhost:3000', 'http://localhost:5173']
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def use_redis(self) -> bool:
        """
        Check if Redis is configured.

        Returns:
            True if Redis host is set, False otherwise (use in-memory cache)
        """
        return bool(self.redis_host)

    def get_binance_headers(self) -> dict:
        """
        Get HTTP headers for Binance API requests.

        Returns:
            Dictionary of headers including API key if configured

        Note:
            Most public endpoints don't require authentication.
            This is used for future authenticated endpoints.
        """
        headers = {
            "Content-Type": "application/json",
        }

        # Add API key to headers if configured
        if self.binance_api_key:
            headers["X-MBX-APIKEY"] = self.binance_api_key

        return headers


# ============================================
# Global Settings Instance
# ============================================

# Create a single instance of settings to be imported throughout the application
# This ensures configuration is loaded once and reused
settings = Settings()


# ============================================
# Configuration Validation
# ============================================

def validate_configuration() -> None:
    """
    Validate critical configuration settings on application startup.

    Raises:
        ValueError: If required configuration is missing or invalid

    This function is called during application initialization to ensure
    the configuration is valid before starting the server.
    """
    # Import logger here to avoid circular import
    # (logging.py imports config.py, so we can't import at module level)
    from core.logging import logger

    # Validate symbols exist
    if not settings.symbols_list:
        raise ValueError("SUPPORTED_SYMBOLS must contain at least one symbol")

    # Validate symbols are uppercase
    for symbol in settings.symbols_list:
        if not symbol.isupper():
            raise ValueError(
                f"Symbol '{symbol}' must be uppercase. "
                f"Please update SUPPORTED_SYMBOLS in .env"
            )

    # Validate intervals
    valid_intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
    for interval in settings.intervals_list:
        if interval not in valid_intervals:
            raise ValueError(
                f"Invalid interval: '{interval}'. "
                f"Must be one of: {', '.join(valid_intervals)}"
            )

    # Validate port number
    if not (1 <= settings.app_port <= 65535):
        raise ValueError(f"Invalid port number: {settings.app_port}. Must be between 1 and 65535")

    # Validate log level
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if settings.log_level.upper() not in valid_log_levels:
        raise ValueError(
            f"Invalid LOG_LEVEL: '{settings.log_level}'. "
            f"Must be one of: {', '.join(valid_log_levels)}"
        )

    # Log successful validation
    logger.info("Configuration validated successfully")
    logger.info(f"Tracking symbols: {', '.join(settings.symbols_list)}")
    logger.info(f"Using intervals: {', '.join(settings.intervals_list)}")
    logger.info(f"Binance API: {settings.binance_base_url}")
    logger.info(f"Server: {settings.app_host}:{settings.app_port}")
    logger.info(f"Log level: {settings.log_level.upper()}")
    logger.info(f"Cache: {'Redis' if settings.use_redis else 'In-Memory'}")
