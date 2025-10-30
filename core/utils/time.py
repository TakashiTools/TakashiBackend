"""
Time Utilities

This module provides utilities for handling timestamps from different exchanges.

Different exchanges return timestamps in different formats:
- Binance: milliseconds since epoch (e.g., 1704110400000)
- Some exchanges: seconds since epoch (e.g., 1704110400)
- We need: Python datetime objects in UTC

The utilities in this module normalize all timestamp formats into
consistent UTC datetime objects for use in our Pydantic schemas.
"""

from datetime import datetime, timezone
from typing import Union


def to_utc_datetime(timestamp: Union[int, float]) -> datetime:
    """
    Convert a timestamp (seconds or milliseconds) to UTC datetime.

    This function automatically detects whether the timestamp is in
    seconds or milliseconds and converts it to a timezone-aware
    datetime object in UTC.

    Detection Logic:
        - If timestamp > 1e12 (1 trillion): Assumed to be milliseconds
        - Otherwise: Assumed to be seconds

    Args:
        timestamp: Unix timestamp in seconds or milliseconds

    Returns:
        datetime: Timezone-aware datetime object in UTC

    Raises:
        ValueError: If timestamp is negative or invalid

    Examples:
        >>> # Millisecond timestamp (Binance format)
        >>> to_utc_datetime(1704110400000)
        datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)

        >>> # Second timestamp (some exchanges)
        >>> to_utc_datetime(1704110400)
        datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)

        >>> # Float timestamp (also supported)
        >>> to_utc_datetime(1704110400.5)
        datetime.datetime(2024, 1, 1, 12, 0, 0, 500000, tzinfo=datetime.timezone.utc)

    Notes:
        - All returned datetimes are timezone-aware (UTC)
        - The threshold 1e12 works because:
          * Seconds: ~1.7 billion (current time)
          * Milliseconds: ~1.7 trillion (current time)
        - This threshold will work until year 2286 (1e12 seconds = Sept 2286)
    """
    # Validate timestamp
    if timestamp < 0:
        raise ValueError(f"Timestamp cannot be negative: {timestamp}")

    # Convert milliseconds to seconds if needed
    # 1e12 = 1,000,000,000,000 (1 trillion)
    # Current time in seconds: ~1.7 billion
    # Current time in milliseconds: ~1.7 trillion
    if timestamp > 1e12:
        timestamp = timestamp / 1000.0

    # Convert to datetime with UTC timezone
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OSError, OverflowError, ValueError) as e:
        raise ValueError(f"Invalid timestamp: {timestamp}. Error: {e}")


def datetime_to_timestamp(dt: datetime, milliseconds: bool = False) -> int:
    """
    Convert a datetime object to Unix timestamp.

    Args:
        dt: Datetime object (can be naive or timezone-aware)
        milliseconds: If True, return milliseconds; if False, return seconds

    Returns:
        int: Unix timestamp in seconds or milliseconds

    Examples:
        >>> dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        >>> datetime_to_timestamp(dt)
        1704110400

        >>> datetime_to_timestamp(dt, milliseconds=True)
        1704110400000

    Notes:
        - If datetime is naive (no timezone), UTC is assumed
        - Result is always an integer (fractional seconds are truncated)
    """
    # If datetime is naive (no timezone), assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Get timestamp in seconds
    timestamp = int(dt.timestamp())

    # Convert to milliseconds if requested
    if milliseconds:
        timestamp *= 1000

    return timestamp


def current_utc_timestamp(milliseconds: bool = False) -> int:
    """
    Get current UTC timestamp.

    Args:
        milliseconds: If True, return milliseconds; if False, return seconds

    Returns:
        int: Current Unix timestamp

    Examples:
        >>> current_utc_timestamp()
        1704110400

        >>> current_utc_timestamp(milliseconds=True)
        1704110400000

    Notes:
        This is a convenience function equivalent to:
        datetime_to_timestamp(datetime.now(timezone.utc), milliseconds)
    """
    return datetime_to_timestamp(datetime.now(timezone.utc), milliseconds)


def current_utc_datetime() -> datetime:
    """
    Get current UTC datetime.

    Returns:
        datetime: Current time as timezone-aware datetime in UTC

    Example:
        >>> current_utc_datetime()
        datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

    Notes:
        This is a convenience function equivalent to:
        datetime.now(timezone.utc)
    """
    return datetime.now(timezone.utc)
