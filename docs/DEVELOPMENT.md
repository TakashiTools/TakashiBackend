# Development Guide

Guide for developers working on or extending the TAKASHI Multi-Exchange Market Data API.

---

## Getting Started

### Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Git**
- **Virtual environment tool** (venv, conda, etc.)
- **Code editor** (VS Code, PyCharm, etc.)

### Development Setup

1. **Clone the repository**
```bash
git clone https://github.com/TakashiTools/TakashiBackend.git
cd TakashiBackend
```

2. **Create virtual environment**
```bash
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

3. **Install dependencies (including dev tools)**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

5. **Run in development mode**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Architecture Overview

### Core Design Principles

1. **Interface Segregation** - All exchanges implement `ExchangeInterface`
2. **Dependency Inversion** - Depend on abstractions, not concretions
3. **Single Responsibility** - Each module has one clear purpose
4. **Open/Closed** - Open for extension, closed for modification
5. **Type Safety** - Full type hints and Pydantic validation

### Directory Structure

```
TakashiBackend/
├── app/                     # FastAPI application layer
│   └── main.py             # API routes and WebSocket endpoints
├── core/                    # Core business logic (exchange-agnostic)
│   ├── config.py           # Configuration management
│   ├── exchange_interface.py   # Abstract base class for exchanges
│   ├── exchange_manager.py # Exchange registry and lifecycle
│   ├── schemas.py          # Pydantic data models
│   ├── logging.py          # Logging configuration
│   └── utils/              # Utility functions
│       └── time.py         # Time conversion utilities
├── exchanges/               # Exchange-specific implementations
│   ├── binance/
│   │   ├── __init__.py     # BinanceExchange wrapper class
│   │   ├── api_client.py   # REST API client
│   │   └── ws_client.py    # WebSocket client
│   ├── bybit/
│   └── hyperliquid/
├── services/                # Background services
│   ├── event_bus.py        # Pub/sub event system
│   ├── all_liquidations.py # Multi-exchange liquidation aggregator
│   ├── all_large_trades.py # Multi-exchange trade aggregator
│   └── oi_vol_monitor.py   # OI/Volume spike detector
└── tests/                   # Test suite
    ├── unit/               # Unit tests
    └── integration/        # Integration tests
```

---

## Adding a New Exchange

### Step-by-Step Guide

#### 1. Create Exchange Directory

```bash
mkdir -p exchanges/newexchange
touch exchanges/newexchange/__init__.py
touch exchanges/newexchange/api_client.py
touch exchanges/newexchange/ws_client.py
```

#### 2. Implement REST API Client

`exchanges/newexchange/api_client.py`:

```python
"""
NewExchange REST API Client

Handles HTTP requests for historical and snapshot data.
"""

import aiohttp
import asyncio
from typing import List, Optional
from core.logging import get_logger
from core.utils.time import to_utc_datetime
from core.schemas import OHLC, OpenInterest, FundingRate


class NewExchangeAPIClient:
    """
    Async HTTP client for NewExchange REST API.
    
    All methods return normalized data using Pydantic schemas.
    """
    
    BASE_URL = "https://api.newexchange.com"
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _get(self, path: str, params: dict = None) -> dict:
        """Make GET request with retry logic."""
        if not self.session:
            raise RuntimeError("Client not initialized")
        
        url = f"{self.BASE_URL}{path}"
        
        # Implement retry logic with exponential backoff
        for attempt in range(3):
            try:
                async with self.session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status in (429, 503):
                        # Rate limit - retry with backoff
                        delay = 1.5 * (attempt + 1)
                        self.logger.warning(f"Rate limited, retrying in {delay}s")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        text = await resp.text()
                        self.logger.error(f"HTTP {resp.status}: {text}")
                        break
            except Exception as e:
                self.logger.error(f"Request failed: {e}")
                await asyncio.sleep(1.0 * (attempt + 1))
        
        raise RuntimeError(f"Failed to fetch {url} after 3 attempts")
    
    async def get_historical_ohlc(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[OHLC]:
        """
        Fetch historical OHLC data.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Timeframe (e.g., "1m", "5m", "1h")
            limit: Number of candles
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)
        
        Returns:
            List[OHLC]: Normalized candlestick data
        """
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit
        }
        
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        self.logger.info(f"Fetching OHLC: {symbol} {interval} (limit={limit})")
        data = await self._get("/api/v1/klines", params)
        
        # Normalize to OHLC schema
        ohlc_list = []
        for item in data:
            ohlc_list.append(
                OHLC(
                    exchange="newexchange",
                    symbol=symbol.upper(),
                    interval=interval,
                    timestamp=to_utc_datetime(item["timestamp"]),
                    open=float(item["open"]),
                    high=float(item["high"]),
                    low=float(item["low"]),
                    close=float(item["close"]),
                    volume=float(item["volume"]),
                    quote_volume=float(item.get("quoteVolume", 0)),
                    trades_count=int(item.get("trades", 0)),
                    is_closed=True  # Historical data is always closed
                )
            )
        
        self.logger.info(f"Fetched {len(ohlc_list)} candles for {symbol}")
        return ohlc_list
    
    async def get_open_interest(self, symbol: str) -> Optional[OpenInterest]:
        """Get current open interest for a symbol."""
        # Implement based on exchange API
        pass
    
    async def get_funding_rate(self, symbol: str, limit: int = 100) -> List[FundingRate]:
        """Get historical funding rates for a symbol."""
        # Implement based on exchange API
        pass
```

#### 3. Implement WebSocket Client

`exchanges/newexchange/ws_client.py`:

```python
"""
NewExchange WebSocket Client

Handles real-time data streams.
"""

import asyncio
import json
import websockets
from typing import AsyncGenerator
from core.logging import get_logger
from core.utils.time import to_utc_datetime
from core.schemas import OHLC, Liquidation, LargeTrade


class NewExchangeWSClient:
    """
    Async WebSocket client for NewExchange.
    
    Provides async generators that yield normalized data.
    """
    
    BASE_URL = "wss://stream.newexchange.com/ws"
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    async def stream_ohlc(
        self,
        symbol: str,
        interval: str
    ) -> AsyncGenerator[OHLC, None]:
        """
        Stream live OHLC updates.
        
        Args:
            symbol: Trading pair
            interval: Timeframe
        
        Yields:
            OHLC: Live candlestick updates
        """
        url = f"{self.BASE_URL}"
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [f"{symbol.lower()}@kline_{interval}"]
        }
        
        while True:
            try:
                async with websockets.connect(url) as ws:
                    await ws.send(json.dumps(subscribe_msg))
                    self.logger.info(f"Subscribed to {symbol} kline_{interval}")
                    
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            
                            # Parse exchange-specific format
                            k = data.get("k", {})
                            
                            yield OHLC(
                                exchange="newexchange",
                                symbol=symbol.upper(),
                                interval=interval,
                                timestamp=to_utc_datetime(k["t"]),
                                open=float(k["o"]),
                                high=float(k["h"]),
                                low=float(k["l"]),
                                close=float(k["c"]),
                                volume=float(k["v"]),
                                quote_volume=float(k["q"]),
                                trades_count=int(k["n"]),
                                is_closed=bool(k["x"])
                            )
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            self.logger.error(f"Parse error: {e}")
                            continue
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)  # Reconnect after 5 seconds
    
    async def stream_trades(self, symbol: str) -> AsyncGenerator[LargeTrade, None]:
        """Stream trade events."""
        # Implement based on exchange WebSocket API
        pass
    
    async def stream_liquidations(self, symbol: str) -> AsyncGenerator[Liquidation, None]:
        """Stream liquidation events (if supported)."""
        # Implement if exchange provides liquidation data
        pass
```

#### 4. Create Exchange Wrapper

`exchanges/newexchange/__init__.py`:

```python
"""
NewExchange Connector

Implements ExchangeInterface for NewExchange.
"""

from typing import List, AsyncGenerator, Optional
from core.exchange_interface import ExchangeInterface
from core.schemas import OHLC, OpenInterest, FundingRate, Liquidation, LargeTrade
from core.logging import get_logger
from .api_client import NewExchangeAPIClient
from .ws_client import NewExchangeWSClient


class NewExchangeExchange(ExchangeInterface):
    """
    NewExchange connector implementing the ExchangeInterface.
    
    Capabilities:
        - OHLC: Yes
        - Open Interest: Yes
        - Funding Rate: Yes
        - Liquidations: No (not supported)
        - Large Trades: Yes
    """
    
    name = "newexchange"
    
    capabilities = {
        "ohlc": True,
        "funding_rate": True,
        "open_interest": True,
        "liquidations": False,  # Not supported by this exchange
        "large_trades": True
    }
    
    def __init__(self):
        self.base_url = "https://api.newexchange.com"
        self.ws_url = "wss://stream.newexchange.com/ws"
        self.client: Optional[NewExchangeAPIClient] = None
        self.logger = get_logger(__name__)
    
    async def initialize(self) -> None:
        """Initialize the exchange connector."""
        self.logger.info("Initializing NewExchange connector...")
        self.client = NewExchangeAPIClient()
        await self.client.__aenter__()
        self.logger.info("✓ NewExchange connector initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the exchange connector."""
        self.logger.info("Shutting down NewExchange connector...")
        if self.client:
            await self.client.__aexit__(None, None, None)
        self.logger.info("✓ NewExchange connector shut down")
    
    async def health_check(self) -> bool:
        """Check if exchange API is accessible."""
        try:
            # Make a lightweight API call
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    # Implement required interface methods
    
    async def get_ohlc(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[OHLC]:
        """Get historical OHLC data."""
        return await self.client.get_historical_ohlc(
            symbol, interval, limit, start_time, end_time
        )
    
    async def get_open_interest(self, symbol: str) -> Optional[OpenInterest]:
        """Get current open interest."""
        return await self.client.get_open_interest(symbol)
    
    async def get_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """Get current funding rate."""
        rates = await self.client.get_funding_rate(symbol, limit=1)
        return rates[0] if rates else None
    
    async def stream_ohlc(
        self,
        symbol: str,
        interval: str
    ) -> AsyncGenerator[OHLC, None]:
        """Stream live OHLC updates."""
        ws_client = NewExchangeWSClient()
        async for ohlc in ws_client.stream_ohlc(symbol, interval):
            yield ohlc
    
    async def stream_liquidations(
        self,
        symbol: str
    ) -> AsyncGenerator[Liquidation, None]:
        """Stream liquidation events."""
        # Not supported by this exchange
        raise NotImplementedError("NewExchange does not provide liquidation data")
    
    async def stream_large_trades(
        self,
        symbol: str
    ) -> AsyncGenerator[LargeTrade, None]:
        """Stream large trades."""
        from core.config import settings
        min_value = settings.large_trade_threshold_usd
        
        ws_client = NewExchangeWSClient()
        async for trade in ws_client.stream_trades(symbol):
            # Filter by threshold
            if trade.value >= min_value:
                yield trade
```

#### 5. Register Exchange in Manager

Edit `core/exchange_manager.py`:

```python
from exchanges.newexchange import NewExchangeExchange

class ExchangeManager:
    def __init__(self):
        # ... existing code ...
        from exchanges.newexchange import NewExchangeExchange
        
        self.exchanges: Dict[str, ExchangeInterface] = {
            "binance": BinanceExchange(),
            "bybit": BybitExchange(),
            "hyperliquid": HyperliquidExchange(),
            "newexchange": NewExchangeExchange(),  # Add new exchange
        }
```

#### 6. Add Tests

Create `tests/unit/test_newexchange_api_client.py`:

```python
"""
Tests for NewExchange API client.
"""

import pytest
from exchanges.newexchange.api_client import NewExchangeAPIClient


@pytest.mark.asyncio
async def test_get_historical_ohlc():
    """Test fetching historical OHLC data."""
    async with NewExchangeAPIClient() as client:
        ohlc = await client.get_historical_ohlc("BTCUSDT", "1h", limit=5)
        
        assert len(ohlc) > 0
        assert ohlc[0].exchange == "newexchange"
        assert ohlc[0].symbol == "BTCUSDT"
        assert ohlc[0].is_closed is True


@pytest.mark.asyncio
async def test_get_open_interest():
    """Test fetching open interest."""
    async with NewExchangeAPIClient() as client:
        oi = await client.get_open_interest("BTCUSDT")
        
        assert oi is not None
        assert oi.exchange == "newexchange"
        assert oi.open_interest >= 0
```

#### 7. Test Your Implementation

```bash
# Run unit tests
pytest tests/unit/test_newexchange_api_client.py -v

# Test API endpoint
curl "http://localhost:8000/newexchange/ohlc/BTCUSDT/1h?limit=5"

# Test WebSocket
wscat -c "ws://localhost:8000/ws/newexchange/BTCUSDT/ohlc?interval=1m"
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html --cov-report=term

# Run specific test file
pytest tests/unit/test_binance_api_client.py -v

# Run tests matching pattern
pytest -k "test_ohlc" -v

# Run integration tests only
pytest tests/integration/ -v

# Run with detailed output
pytest -vv --tb=short
```

### Writing Tests

**Unit Test Example:**
```python
import pytest
from core.schemas import OHLC
from datetime import datetime


def test_ohlc_validation():
    """Test OHLC schema validation."""
    ohlc = OHLC(
        exchange="binance",
        symbol="BTCUSDT",
        interval="1h",
        timestamp=datetime.utcnow(),
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
        volume=100.0,
        quote_volume=5000000.0,
        trades_count=1000,
        is_closed=True
    )
    
    assert ohlc.exchange == "binance"
    assert ohlc.symbol == "BTCUSDT"
    assert ohlc.high >= ohlc.low
```

**Async Test Example:**
```python
@pytest.mark.asyncio
async def test_exchange_health_check():
    """Test exchange health check."""
    from core.exchange_manager import ExchangeManager
    
    manager = ExchangeManager()
    await manager.initialize_all()
    
    health = await manager.health_check_all()
    
    assert isinstance(health, dict)
    assert "binance" in health
    assert health["binance"] is True
    
    await manager.shutdown_all()
```

---

## Code Style

### Python Style Guide

We follow **PEP 8** with some modifications:

- **Line length:** 120 characters (not 79)
- **Formatter:** black
- **Linter:** ruff
- **Type checker:** mypy

### Format Code

```bash
# Format with black
black .

# Check with ruff
ruff check .

# Type check with mypy
mypy core/ exchanges/ services/
```

### Pre-commit Hooks (Optional)

```bash
# Install pre-commit
pip install pre-commit

# Set up hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

---

## Documentation Standards

### Docstrings

Use Google-style docstrings:

```python
async def get_ohlc(
    self,
    symbol: str,
    interval: str,
    limit: int = 500
) -> List[OHLC]:
    """
    Fetch historical OHLC data.
    
    This method retrieves candlestick data from the exchange API
    and normalizes it to our OHLC schema.
    
    Args:
        symbol: Trading pair in uppercase (e.g., "BTCUSDT")
        interval: Timeframe (e.g., "1m", "5m", "1h", "1d")
        limit: Number of candles to fetch (default: 500, max: 1500)
    
    Returns:
        List[OHLC]: List of candlestick data sorted by timestamp
    
    Raises:
        ValueError: If symbol or interval is invalid
        RuntimeError: If API request fails after retries
    
    Example:
        >>> ohlc = await client.get_ohlc("BTCUSDT", "1h", limit=100)
        >>> print(f"Fetched {len(ohlc)} candles")
    """
    pass
```

### Type Hints

Always use type hints:

```python
from typing import List, Optional, Dict, Any

async def fetch_data(
    symbol: str,
    limit: int = 500,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Fetch data with type hints."""
    pass
```

---

## Debugging

### Enable Debug Logging

```env
# .env file
LOG_LEVEL=DEBUG
```

### VS Code Launch Configuration

`.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: FastAPI",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "app.main:app",
                "--reload",
                "--host",
                "0.0.0.0",
                "--port",
                "8000"
            ],
            "jinja": true,
            "justMyCode": false
        }
    ]
}
```

### Common Issues

**Issue: Import errors**
```bash
# Solution: Ensure virtual environment is activated
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

**Issue: WebSocket connection fails**
```python
# Solution: Check if exchange connector is initialized
await manager.initialize_all()
```

**Issue: Rate limit errors**
```python
# Solution: Increase retry delay in API client
await asyncio.sleep(3.0)  # Wait longer between retries
```

---

## Performance Optimization

### Async Best Practices

1. **Use asyncio.gather() for concurrent requests**
```python
results = await asyncio.gather(
    exchange1.get_ohlc("BTCUSDT", "1h"),
    exchange2.get_ohlc("BTCUSDT", "1h"),
    exchange3.get_ohlc("BTCUSDT", "1h")
)
```

2. **Connection pooling**
```python
# Use single session for multiple requests
async with aiohttp.ClientSession() as session:
    # Reuse session for all requests
    pass
```

3. **Avoid blocking calls**
```python
# Bad: Blocking I/O
data = requests.get(url)

# Good: Async I/O
async with session.get(url) as resp:
    data = await resp.json()
```

---

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [aiohttp Documentation](https://docs.aiohttp.org/)
- [Python Async/Await](https://docs.python.org/3/library/asyncio.html)

---

## Need Help?

- **Architecture questions:** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **API usage:** See [API_REFERENCE.md](API_REFERENCE.md)
- **Issues:** [GitHub Issues](https://github.com/TakashiTools/TakashiBackend/issues)

