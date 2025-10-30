"""
Unified Logging Configuration

This module sets up a centralized logging system for the entire application.
All modules should import and use the logger from this module instead of
using print() statements.

Benefits:
    - Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Consistent formatting across all modules
    - Easy to redirect logs to files or external services
    - Can filter logs by module/component
    - Production-ready logging

Usage:
    from core.logging import logger

    logger.debug("Detailed debugging information")
    logger.info("General informational messages")
    logger.warning("Warning messages for potentially harmful situations")
    logger.error("Error messages for serious problems")
    logger.critical("Critical messages for very serious errors")

Log Levels (from most to least verbose):
    DEBUG    - Detailed diagnostic information (e.g., "Received response: {...}")
    INFO     - General informational messages (e.g., "Connected to Binance")
    WARNING  - Warnings about potential issues (e.g., "Rate limit approaching")
    ERROR    - Errors that don't crash the app (e.g., "Failed to fetch OHLC")
    CRITICAL - Severe errors that may crash (e.g., "Database connection lost")

Configuration:
    Log level is controlled by the LOG_LEVEL setting in .env file.
    If not set, defaults to INFO in production, DEBUG in development.
"""

import logging
import sys
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_format: Optional[str] = None,
    include_timestamp: bool = True,
    include_module: bool = True
) -> logging.Logger:
    """
    Configure and return the application logger.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom log format string (uses default if None)
        include_timestamp: Include timestamp in log messages
        include_module: Include module name in log messages

    Returns:
        logging.Logger: Configured logger instance

    Example:
        >>> logger = setup_logging(log_level="DEBUG")
        >>> logger.info("Application started")
        2024-01-01 12:00:00 [INFO] itabackend: Application started
    """
    # Build log format string
    if log_format is None:
        format_parts = []

        if include_timestamp:
            # Format: 2024-01-01 12:00:00
            format_parts.append("%(asctime)s")

        # Always include log level
        format_parts.append("[%(levelname)s]")

        if include_module:
            # Show which module/file logged the message
            format_parts.append("%(name)s")

        # The actual log message
        format_parts.append("%(message)s")

        log_format = " ".join(format_parts)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",  # Timestamp format
        stream=sys.stdout,  # Output to console
        force=True  # Override any existing configuration
    )

    # Create and return logger
    logger = logging.getLogger("itabackend")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    return logger


# ============================================
# Initialize Logger with Settings
# ============================================

# Try to load log level from settings, fallback to INFO
try:
    from core.config import settings
    log_level = settings.log_level if hasattr(settings, 'log_level') else "INFO"
except ImportError:
    # If settings not available yet (during initial import), use INFO
    log_level = "INFO"

# Create the global logger instance
logger = setup_logging(log_level=log_level)


# ============================================
# Convenience Functions
# ============================================

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module or component.

    This allows different parts of the application to have
    separate loggers that can be configured independently.

    Args:
        name: Name for the logger (typically __name__)

    Returns:
        logging.Logger: Logger instance for the specified name

    Example:
        # In binance/api_client.py:
        from core.logging import get_logger
        logger = get_logger(__name__)  # Creates "itabackend.exchanges.binance.api_client"

        logger.info("Fetching OHLC data")
        # Output: 2024-01-01 12:00:00 [INFO] itabackend.exchanges.binance.api_client: Fetching OHLC data
    """
    return logging.getLogger(f"itabackend.{name}")


def set_log_level(level: str) -> None:
    """
    Change the log level at runtime.

    Args:
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example:
        >>> from core.logging import set_log_level, logger
        >>> set_log_level("DEBUG")
        >>> logger.debug("This will now be visible")
    """
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.getLogger().setLevel(getattr(logging, level.upper(), logging.INFO))


# ============================================
# Log Helper Functions
# ============================================

def log_api_request(exchange: str, endpoint: str, params: dict = None) -> None:
    """
    Log an API request with consistent formatting.

    Args:
        exchange: Exchange name (e.g., "binance")
        endpoint: API endpoint being called
        params: Request parameters (optional)

    Example:
        >>> log_api_request("binance", "/fapi/v1/klines", {"symbol": "BTCUSDT", "interval": "1h"})
        [DEBUG] API Request: binance /fapi/v1/klines | Params: {'symbol': 'BTCUSDT', 'interval': '1h'}
    """
    if params:
        logger.debug(f"API Request: {exchange} {endpoint} | Params: {params}")
    else:
        logger.debug(f"API Request: {exchange} {endpoint}")


def log_api_response(exchange: str, endpoint: str, status: int, response_time: float = None) -> None:
    """
    Log an API response with status and timing information.

    Args:
        exchange: Exchange name
        endpoint: API endpoint
        status: HTTP status code
        response_time: Response time in seconds (optional)

    Example:
        >>> log_api_response("binance", "/fapi/v1/klines", 200, 0.342)
        [DEBUG] API Response: binance /fapi/v1/klines | Status: 200 | Time: 0.342s
    """
    time_str = f" | Time: {response_time:.3f}s" if response_time else ""
    logger.debug(f"API Response: {exchange} {endpoint} | Status: {status}{time_str}")


def log_websocket_event(exchange: str, event: str, symbol: str = None, details: str = None) -> None:
    """
    Log a WebSocket event with consistent formatting.

    Args:
        exchange: Exchange name
        event: Event type (e.g., "connected", "disconnected", "message", "error")
        symbol: Trading symbol (optional)
        details: Additional details (optional)

    Example:
        >>> log_websocket_event("binance", "connected", "BTCUSDT")
        [INFO] WebSocket: binance connected | Symbol: BTCUSDT

        >>> log_websocket_event("binance", "error", details="Connection timeout")
        [ERROR] WebSocket: binance error | Connection timeout
    """
    symbol_str = f" | Symbol: {symbol}" if symbol else ""
    details_str = f" | {details}" if details else ""

    level = logging.ERROR if event == "error" else logging.INFO
    logger.log(level, f"WebSocket: {exchange} {event}{symbol_str}{details_str}")


# ============================================
# Module Initialization
# ============================================

# Log that the logging system is initialized
logger.debug("Logging system initialized")
