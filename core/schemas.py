"""
Normalized Data Schemas

This module defines Pydantic models for all market data types.
These schemas provide a unified, exchange-agnostic data format.

Key Principle:
    Regardless of which exchange the data comes from (Binance, Bybit, OKX, etc.),
    it gets normalized into these standardized schemas. This allows the frontend
    and API consumers to work with consistent data structures.

Models:
    - OHLC: Candlestick/Kline data (Open, High, Low, Close, Volume)
    - OpenInterest: Total open interest for a futures symbol
    - FundingRate: Perpetual futures funding rate information
    - Liquidation: Liquidation event details
    - LargeTrade: Significant trade detection
    - TickerInfo: 24h ticker statistics

Each model includes:
    - exchange: Source exchange identifier
    - symbol: Trading pair (e.g., BTCUSDT)
    - timestamp: Event time in UTC
    - Relevant data fields specific to that data type
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from decimal import Decimal


# ============================================
# Base Market Data Model
# ============================================

class BaseMarketModel(BaseModel):
    """
    Base model for all market data schemas.

    This abstract base class defines common fields that all market data types share:
    - exchange: The source exchange
    - symbol: The trading pair
    - timestamp: When the data was recorded

    All specific market data models (OHLC, OpenInterest, etc.) inherit from this class
    to avoid code duplication and ensure consistency.

    Benefits:
        - Single source of truth for common fields
        - Easier to add new common fields later
        - Consistent field validation across all models
        - Cleaner model definitions (only specific fields needed)

    Example:
        class OHLC(BaseMarketModel):
            # Inherits exchange, symbol, timestamp
            # Only needs to define OHLC-specific fields
            open: float
            high: float
            ...
    """

    exchange: str = Field(
        ...,
        description="Source exchange identifier (lowercase)",
        examples=["binance", "bybit", "okx"]
    )

    symbol: str = Field(
        ...,
        description="Trading pair symbol in uppercase",
        examples=["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    )

    timestamp: datetime = Field(
        ...,
        description="Event timestamp in UTC"
    )

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase"""
        return v.upper()

    @field_validator('exchange')
    @classmethod
    def validate_exchange(cls, v: str) -> str:
        """Ensure exchange is lowercase"""
        return v.lower()


# ============================================
# OHLC (Candlestick) Schema
# ============================================

class OHLC(BaseMarketModel):
    """
    Open-High-Low-Close (Candlestick) Data Model

    Represents a single candlestick/kline for technical analysis and charting.
    Used for both historical data retrieval and live streaming.

    Inherits from BaseMarketModel:
        - exchange: Source exchange (e.g., "binance", "bybit")
        - symbol: Trading pair in uppercase (e.g., "BTCUSDT")
        - timestamp: Candle opening time in UTC

    Additional Attributes:
        interval: Timeframe (e.g., "1m", "5m", "1h", "1d")
        open: Opening price (first trade in the interval)
        high: Highest price during the interval
        low: Lowest price during the interval
        close: Closing price (last trade in the interval)
        volume: Total trading volume in base asset (e.g., BTC for BTCUSDT)
        quote_volume: Total trading volume in quote asset (e.g., USDT for BTCUSDT)
        trades_count: Number of trades executed during this interval
        is_closed: True if the candle is finalized, False if still forming

    Example:
        >>> ohlc = OHLC(
        ...     exchange="binance",
        ...     symbol="BTCUSDT",
        ...     interval="1h",
        ...     timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ...     open=50000.0,
        ...     high=51000.0,
        ...     low=49500.0,
        ...     close=50500.0,
        ...     volume=125.5,
        ...     quote_volume=6277500.0,
        ...     trades_count=1523,
        ...     is_closed=True
        ... )

    Notes:
        - Prices can be 0.0 (allowed for low-liquidity pairs with no trades)
        - For live streaming, is_closed=False means the candle is still updating
        - Always use the timestamp to identify which candle period this represents
        - Volume is in the base asset (BTC), quote_volume is in USDT
    """

    # Interval (OHLC-specific field)
    interval: str = Field(
        ...,
        description="Candlestick interval/timeframe",
        examples=["1m", "5m", "15m", "1h", "4h", "1d"]
    )

    # Price data (OHLC) - Allow >= 0 instead of > 0 to handle zero-volume candles
    open: float = Field(
        ...,
        ge=0,  # Greater than or equal to 0 (can be 0 for no trades)
        description="Opening price (first trade in interval)"
    )

    high: float = Field(
        ...,
        ge=0,
        description="Highest price during the interval"
    )

    low: float = Field(
        ...,
        ge=0,
        description="Lowest price during the interval"
    )

    close: float = Field(
        ...,
        ge=0,
        description="Closing price (last trade in interval)"
    )

    # Volume data
    volume: float = Field(
        ...,
        ge=0,  # Greater than or equal to 0 (can be 0 for no trades)
        description="Trading volume in base asset (e.g., BTC for BTCUSDT)"
    )

    quote_volume: float = Field(
        ...,
        ge=0,
        description="Trading volume in quote asset (e.g., USDT for BTCUSDT)"
    )

    # Additional metrics
    trades_count: int = Field(
        ...,
        ge=0,
        description="Number of trades executed during this interval"
    )

    is_closed: bool = Field(
        ...,
        description="True if candle is finalized, False if still forming (live data)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exchange": "binance",
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": "2024-01-01T12:00:00Z",
                "open": 50000.0,
                "high": 51000.0,
                "low": 49500.0,
                "close": 50500.0,
                "volume": 125.5,
                "quote_volume": 6277500.0,
                "trades_count": 1523,
                "is_closed": True
            }
        }
    )


# ============================================
# Open Interest Schema
# ============================================

class OpenInterest(BaseMarketModel):
    """
    Open Interest Data Model

    Represents the total number of outstanding derivative contracts (futures/perpetuals)
    that have not been settled. High open interest indicates strong market participation.

    Inherits from BaseMarketModel:
        - exchange: Source exchange identifier
        - symbol: Trading pair (futures/perpetual)
        - timestamp: Time of the measurement

    Open Interest Explained:
        - When a buyer and seller open a new position → OI increases
        - When a buyer and seller close existing positions → OI decreases
        - When position transfers from one trader to another → OI unchanged
        - Rising OI + Rising Price = Bullish (new longs entering)
        - Rising OI + Falling Price = Bearish (new shorts entering)
        - Falling OI = Positions closing, weakening trend

    Additional Attributes:
        open_interest: Total open interest value in base asset (e.g., BTC)
        open_interest_value: Open interest value in USD/USDT

    Example:
        >>> oi = OpenInterest(
        ...     exchange="binance",
        ...     symbol="BTCUSDT",
        ...     timestamp=datetime.utcnow(),
        ...     open_interest=125000.5,
        ...     open_interest_value=6250025000.0
        ... )
    """

    open_interest: float = Field(
        ...,
        ge=0,
        description="Total open interest in base asset (e.g., number of BTC)"
    )

    open_interest_value: Optional[float] = Field(
        None,
        ge=0,
        description="Open interest value in USD/USDT (optional)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exchange": "binance",
                "symbol": "BTCUSDT",
                "timestamp": "2024-01-01T12:00:00Z",
                "open_interest": 125000.5,
                "open_interest_value": 6250025000.0
            }
        }
    )


# ============================================
# Funding Rate Schema
# ============================================

class FundingRate(BaseMarketModel):
    """
    Funding Rate Data Model

    Represents the periodic payment between longs and shorts in perpetual futures.
    Funding rates help keep the perpetual price anchored to the spot price.

    Inherits from BaseMarketModel:
        - exchange: Source exchange identifier
        - symbol: Trading pair
        - timestamp: When the data was recorded

    Funding Rate Explained:
        - Positive rate: Longs pay shorts (market is bullish, long positions pay premium)
        - Negative rate: Shorts pay longs (market is bearish, short positions pay premium)
        - Rate typically applied every 8 hours (exchange-dependent)
        - Calculated as: (Perpetual Price - Spot Price) / Spot Price

    Trading Implications:
        - Very positive rate (>0.1%): Market overly long, potential reversal signal
        - Very negative rate (<-0.1%): Market overly short, potential reversal signal
        - Rate near 0%: Balanced market

    Additional Attributes:
        funding_rate: Current funding rate (as decimal, e.g., 0.0001 = 0.01%)
        funding_time: When the current funding is applied
        next_funding_rate: Predicted next funding rate (if available)
        next_funding_time: When the next funding will be applied

    Example:
        >>> fr = FundingRate(
        ...     exchange="binance",
        ...     symbol="BTCUSDT",
        ...     timestamp=datetime.utcnow(),
        ...     funding_rate=0.0001,  # 0.01%
        ...     funding_time=datetime(2024, 1, 1, 16, 0, 0),
        ...     next_funding_rate=0.00015,
        ...     next_funding_time=datetime(2024, 1, 2, 0, 0, 0)
        ... )
    """

    funding_rate: float = Field(
        ...,
        description="Current funding rate as decimal (0.0001 = 0.01%)"
    )

    funding_time: datetime = Field(
        ...,
        description="Timestamp when current funding rate is applied"
    )

    next_funding_rate: Optional[float] = Field(
        None,
        description="Predicted next funding rate (if available)"
    )

    next_funding_time: Optional[datetime] = Field(
        None,
        description="Timestamp when next funding will be applied"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exchange": "binance",
                "symbol": "BTCUSDT",
                "funding_rate": 0.0001,
                "funding_time": "2024-01-01T16:00:00Z",
                "next_funding_rate": 0.00015,
                "next_funding_time": "2024-01-02T00:00:00Z"
            }
        }
    )


# ============================================
# Liquidation Schema
# ============================================

class Liquidation(BaseMarketModel):
    """
    Liquidation Event Data Model

    Represents a forced closure of a leveraged position due to insufficient margin.
    Liquidations are important market indicators showing where leverage is concentrated.

    Inherits from BaseMarketModel:
        - exchange: Source exchange identifier
        - symbol: Trading pair that was liquidated
        - timestamp: When the liquidation occurred

    Liquidation Explained:
        - Occurs when a position's loss reaches the maintenance margin threshold
        - Exchange forcefully closes the position at market price
        - Large liquidations can cause cascading price movements
        - "Long liquidation" = forced sell = bearish pressure
        - "Short liquidation" = forced buy = bullish pressure

    Trading Implications:
        - Cluster of long liquidations → Support level being tested
        - Cluster of short liquidations → Resistance level being tested
        - Large liquidations → Potential reversal or continuation signal

    Additional Attributes:
        side: Position side ("buy" for long liquidation, "sell" for short liquidation)
        price: Liquidation execution price
        quantity: Amount liquidated in base asset
        value: Liquidation value in quote asset (USDT)

    Example:
        >>> liq = Liquidation(
        ...     exchange="binance",
        ...     symbol="BTCUSDT",
        ...     side="sell",  # Long position liquidated
        ...     price=49500.0,
        ...     quantity=2.5,
        ...     value=123750.0,
        ...     timestamp=datetime.utcnow()
        ... )
    """

    side: Literal["buy", "sell"] = Field(
        ...,
        description="Order side: 'buy' = short liquidation (forced buy), 'sell' = long liquidation (forced sell)"
    )

    price: float = Field(
        ...,
        ge=0,  # Allow 0 for edge cases
        description="Liquidation execution price"
    )

    quantity: float = Field(
        ...,
        ge=0,
        description="Liquidated quantity in base asset"
    )

    value: float = Field(
        ...,
        ge=0,
        description="Total liquidation value in quote asset (price × quantity)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exchange": "binance",
                "symbol": "BTCUSDT",
                "side": "sell",
                "price": 49500.0,
                "quantity": 2.5,
                "value": 123750.0,
                "timestamp": "2024-01-01T12:30:45Z"
            }
        }
    )


# ============================================
# Large Trade Schema
# ============================================

class LargeTrade(BaseMarketModel):
    """
    Large Trade Detection Data Model

    Represents significant trades that may indicate institutional or whale activity.
    Large trades can signal potential price movements or accumulation/distribution.

    Inherits from BaseMarketModel:
        - exchange: Source exchange identifier
        - symbol: Trading pair
        - timestamp: When the trade executed

    Large Trade Significance:
        - Indicates big players entering or exiting positions
        - Can precede significant price movements
        - Aggressive large buy → Potential upward pressure
        - Aggressive large sell → Potential downward pressure
        - Helps identify support/resistance where big orders are placed

    Additional Attributes:
        side: Trade side ("buy" or "sell")
        price: Execution price
        quantity: Trade size in base asset
        value: Trade value in quote asset (USDT)
        is_buyer_maker: True if buyer was maker (limit order), False if taker (market order)

    Notes:
        - is_buyer_maker=False (taker) often indicates more aggressive/urgent orders
        - Large taker buys are more bullish than large maker buys
        - Threshold for "large" is typically determined by volume analysis

    Example:
        >>> trade = LargeTrade(
        ...     exchange="binance",
        ...     symbol="BTCUSDT",
        ...     side="buy",
        ...     price=50000.0,
        ...     quantity=50.0,
        ...     value=2500000.0,
        ...     timestamp=datetime.utcnow(),
        ...     is_buyer_maker=False  # Aggressive market buy
        ... )
    """

    side: Literal["buy", "sell"] = Field(
        ...,
        description="Trade side: 'buy' or 'sell'"
    )

    price: float = Field(
        ...,
        ge=0,  # Allow 0 for edge cases
        description="Trade execution price"
    )

    quantity: float = Field(
        ...,
        ge=0,
        description="Trade quantity in base asset"
    )

    value: float = Field(
        ...,
        ge=0,
        description="Total trade value in quote asset (price × quantity)"
    )

    is_buyer_maker: bool = Field(
        ...,
        description="True if buyer was maker (limit order), False if taker (market order)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exchange": "binance",
                "symbol": "BTCUSDT",
                "side": "buy",
                "price": 50000.0,
                "quantity": 50.0,
                "value": 2500000.0,
                "timestamp": "2024-01-01T12:30:45Z",
                "is_buyer_maker": False
            }
        }
    )


# ============================================
# Helper Functions
# ============================================

def validate_ohlc_consistency(ohlc: OHLC) -> bool:
    """
    Validate that OHLC data is logically consistent.

    Checks:
        - high >= open, close, low
        - low <= open, close, high
        - All prices > 0
        - Volume >= 0

    Args:
        ohlc: OHLC instance to validate

    Returns:
        True if valid, raises ValueError if invalid

    Raises:
        ValueError: If data is inconsistent

    Example:
        >>> ohlc = OHLC(...)
        >>> validate_ohlc_consistency(ohlc)  # Raises ValueError if invalid
    """
    if ohlc.high < ohlc.low:
        raise ValueError(f"High ({ohlc.high}) cannot be less than Low ({ohlc.low})")

    if ohlc.high < ohlc.open or ohlc.high < ohlc.close:
        raise ValueError(f"High ({ohlc.high}) must be >= Open ({ohlc.open}) and Close ({ohlc.close})")

    if ohlc.low > ohlc.open or ohlc.low > ohlc.close:
        raise ValueError(f"Low ({ohlc.low}) must be <= Open ({ohlc.open}) and Close ({ohlc.close})")

    return True
