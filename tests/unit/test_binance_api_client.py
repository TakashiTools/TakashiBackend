"""
Unit Tests for Binance API Client

These tests verify that the BinanceAPIClient:
- Correctly formats API requests
- Normalizes Binance responses to our schemas
- Handles errors and retries appropriately
- Works with mocked HTTP responses

Run with:
    pytest tests/unit/test_binance_api_client.py -v
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from exchanges.binance.api_client import BinanceAPIClient
from core.schemas import OHLC, OpenInterest, FundingRate


# ============================================
# Fixtures
# ============================================

@pytest_asyncio.fixture
async def api_client():
    """Create a BinanceAPIClient instance for testing"""
    async with BinanceAPIClient() as client:
        yield client


# ============================================
# Tests for OHLC/Candlestick Data
# ============================================

class TestGetOHLC:
    """Tests for get_ohlc method"""

    @pytest.mark.asyncio
    async def test_get_ohlc_returns_list_of_ohlc(self, api_client, monkeypatch):
        """Verify get_ohlc returns normalized OHLC objects"""
        # Mock Binance API response
        mock_response = [
            [
                1609459200000,  # Open time
                "29000.00",     # Open
                "29500.00",     # High
                "28500.00",     # Low
                "29200.00",     # Close
                "1000.5",       # Volume
                1609462799999,  # Close time
                "29150000.0",   # Quote volume
                1523,           # Number of trades
                "500.25",       # Taker buy base
                "14575000.0",   # Taker buy quote
                "0"             # Ignore
            ]
        ]

        async def mock_get(path, params=None):
            return mock_response

        monkeypatch.setattr(api_client, "_get", mock_get)

        # Call the method
        result = await api_client.get_ohlc("BTCUSDT", "1h", limit=1)

        # Assertions
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], OHLC)
        assert result[0].exchange == "binance"
        assert result[0].symbol == "BTCUSDT"
        assert result[0].interval == "1h"
        assert result[0].open == 29000.0
        assert result[0].high == 29500.0
        assert result[0].low == 28500.0
        assert result[0].close == 29200.0
        assert result[0].volume == 1000.5
        assert result[0].quote_volume == 29150000.0
        assert result[0].trades_count == 1523
        assert result[0].is_closed is True

    @pytest.mark.asyncio
    async def test_get_ohlc_normalizes_symbol_to_uppercase(self, api_client, monkeypatch):
        """Verify symbol is normalized to uppercase"""
        called_params = {}

        async def mock_get(path, params=None):
            nonlocal called_params
            called_params = params
            return []

        monkeypatch.setattr(api_client, "_get", mock_get)

        await api_client.get_ohlc("btcusdt", "1h")

        assert called_params["symbol"] == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_get_ohlc_respects_limit_parameter(self, api_client, monkeypatch):
        """Verify limit parameter is passed correctly"""
        called_params = {}

        async def mock_get(path, params=None):
            nonlocal called_params
            called_params = params
            return []

        monkeypatch.setattr(api_client, "_get", mock_get)

        await api_client.get_ohlc("BTCUSDT", "1h", limit=100)

        assert called_params["limit"] == 100

    @pytest.mark.asyncio
    async def test_get_ohlc_caps_limit_at_1500(self, api_client, monkeypatch):
        """Verify limit is capped at Binance maximum (1500)"""
        called_params = {}

        async def mock_get(path, params=None):
            nonlocal called_params
            called_params = params
            return []

        monkeypatch.setattr(api_client, "_get", mock_get)

        await api_client.get_ohlc("BTCUSDT", "1h", limit=2000)

        assert called_params["limit"] == 1500


# ============================================
# Tests for Open Interest
# ============================================

class TestGetOpenInterest:
    """Tests for get_open_interest method"""

    @pytest.mark.asyncio
    async def test_get_open_interest_returns_normalized_oi(self, api_client, monkeypatch):
        """Verify get_open_interest returns normalized OpenInterest object"""
        mock_response = {
            "symbol": "BTCUSDT",
            "openInterest": "12345.678",
            "time": 1609459200000
        }

        async def mock_get(path, params=None):
            return mock_response

        monkeypatch.setattr(api_client, "_get", mock_get)

        result = await api_client.get_open_interest("BTCUSDT")

        assert isinstance(result, OpenInterest)
        assert result.exchange == "binance"
        assert result.symbol == "BTCUSDT"
        assert result.open_interest == 12345.678
        assert isinstance(result.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_get_open_interest_normalizes_symbol(self, api_client, monkeypatch):
        """Verify symbol is normalized to uppercase"""
        called_params = {}

        async def mock_get(path, params=None):
            nonlocal called_params
            called_params = params
            return {"symbol": "BTCUSDT", "openInterest": "1000", "time": 1609459200000}

        monkeypatch.setattr(api_client, "_get", mock_get)

        await api_client.get_open_interest("btcusdt")

        assert called_params["symbol"] == "BTCUSDT"


# ============================================
# Tests for Open Interest History
# ============================================

class TestGetOpenInterestHist:
    """Tests for get_open_interest_hist method"""

    @pytest.mark.asyncio
    async def test_get_open_interest_hist_returns_list(self, api_client, monkeypatch):
        """Verify get_open_interest_hist returns list of OpenInterest objects"""
        mock_response = [
            {
                "symbol": "BTCUSDT",
                "sumOpenInterest": "10000.5",
                "sumOpenInterestValue": "500000000.0",
                "timestamp": 1609459200000
            },
            {
                "symbol": "BTCUSDT",
                "sumOpenInterest": "10500.5",
                "sumOpenInterestValue": "525000000.0",
                "timestamp": 1609462800000
            }
        ]

        async def mock_get(path, params=None):
            return mock_response

        monkeypatch.setattr(api_client, "_get", mock_get)

        result = await api_client.get_open_interest_hist("BTCUSDT", period="5m", limit=2)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(oi, OpenInterest) for oi in result)
        assert result[0].open_interest == 10000.5
        assert result[0].open_interest_value == 500000000.0
        assert result[1].open_interest == 10500.5

    @pytest.mark.asyncio
    async def test_get_open_interest_hist_caps_limit_at_500(self, api_client, monkeypatch):
        """Verify limit is capped at Binance maximum (500)"""
        called_params = {}

        async def mock_get(path, params=None):
            nonlocal called_params
            called_params = params
            return []

        monkeypatch.setattr(api_client, "_get", mock_get)

        await api_client.get_open_interest_hist("BTCUSDT", limit=1000)

        assert called_params["limit"] == 500


# ============================================
# Tests for Funding Rate
# ============================================

class TestGetFundingRate:
    """Tests for get_funding_rate method"""

    @pytest.mark.asyncio
    async def test_get_funding_rate_returns_list_of_funding_rates(self, api_client, monkeypatch):
        """Verify get_funding_rate returns list of FundingRate objects"""
        mock_response = [
            {
                "symbol": "BTCUSDT",
                "fundingRate": "0.0001",
                "fundingTime": 1609459200000
            },
            {
                "symbol": "BTCUSDT",
                "fundingRate": "0.00015",
                "fundingTime": 1609488000000
            }
        ]

        async def mock_get(path, params=None):
            return mock_response

        monkeypatch.setattr(api_client, "_get", mock_get)

        result = await api_client.get_funding_rate("BTCUSDT", limit=2)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(fr, FundingRate) for fr in result)
        assert result[0].symbol == "BTCUSDT"
        assert result[0].funding_rate == 0.0001
        assert result[1].funding_rate == 0.00015

    @pytest.mark.asyncio
    async def test_get_funding_rate_caps_limit_at_1000(self, api_client, monkeypatch):
        """Verify limit is capped at Binance maximum (1000)"""
        called_params = {}

        async def mock_get(path, params=None):
            nonlocal called_params
            called_params = params
            return []

        monkeypatch.setattr(api_client, "_get", mock_get)

        await api_client.get_funding_rate("BTCUSDT", limit=2000)

        assert called_params["limit"] == 1000


# ============================================
# Tests for Funding Info
# ============================================

class TestGetFundingInfo:
    """Tests for get_funding_info method"""

    @pytest.mark.asyncio
    async def test_get_funding_info_returns_list(self, api_client, monkeypatch):
        """Verify get_funding_info returns list of dicts"""
        mock_response = [
            {
                "symbol": "BTCUSDT",
                "adjustedFundingRateCap": "0.025",
                "adjustedFundingRateFloor": "-0.025",
                "fundingIntervalHours": 8
            }
        ]

        async def mock_get(path, params=None):
            return mock_response

        monkeypatch.setattr(api_client, "_get", mock_get)

        result = await api_client.get_funding_info()

        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0]["symbol"] == "BTCUSDT"


# ============================================
# Tests for Context Manager
# ============================================

class TestContextManager:
    """Tests for async context manager functionality"""

    @pytest.mark.asyncio
    async def test_context_manager_creates_session(self):
        """Verify context manager creates aiohttp session"""
        client = BinanceAPIClient()
        assert client.session is None

        async with client as c:
            assert c.session is not None

        # Session should be closed after exit
        # (We can't easily test this without checking session state)

    @pytest.mark.asyncio
    async def test_context_manager_raises_if_not_used(self):
        """Verify _get raises error if session not initialized"""
        client = BinanceAPIClient()

        with pytest.raises(RuntimeError, match="not initialized"):
            await client._get("/test")


# ============================================
# Tests for Error Handling
# ============================================

class TestErrorHandling:
    """Tests for error handling and retry logic"""

    @pytest.mark.asyncio
    async def test_get_retries_on_rate_limit(self, api_client, monkeypatch):
        """Verify _get retries on rate limit (429)"""
        call_count = 0

        class MockResponse:
            def __init__(self, status, json_data=None):
                self.status = status
                self._json_data = json_data

            async def json(self):
                return self._json_data

            async def text(self):
                return "Rate limit exceeded"

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        def mock_get(url, params=None, headers=None, timeout=None):
            nonlocal call_count
            call_count += 1

            # Return rate limit error on first 2 calls, success on 3rd
            if call_count < 3:
                return MockResponse(429)  # Rate limited
            else:
                return MockResponse(200, {"success": True})  # Success

        # Patch the session.get method
        api_client.session.get = mock_get

        result = await api_client._get("/test")

        assert call_count == 3  # Should retry 2 times before success
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_get_fails_after_max_retries(self, api_client, monkeypatch):
        """Verify _get raises error after max retries"""

        class MockResponse:
            def __init__(self):
                self.status = 429

            async def text(self):
                return "Rate limit exceeded"

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        def mock_get(url, params=None, headers=None, timeout=None):
            # Always return rate limit error
            return MockResponse()

        api_client.session.get = mock_get

        with pytest.raises(RuntimeError, match="Failed to fetch"):
            await api_client._get("/test")
