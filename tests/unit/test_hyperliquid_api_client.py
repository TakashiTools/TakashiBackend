"""
Unit Tests for Hyperliquid API Client

These tests verify that the HyperliquidAPIClient:
- Correctly formats API requests (POST with JSON payloads)
- Normalizes Hyperliquid responses to our schemas
- Handles errors and retries appropriately
- Works with mocked HTTP responses

Run with:
    pytest tests/unit/test_hyperliquid_api_client.py -v
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from exchanges.hyperliquid.api_client import HyperliquidAPIClient
from core.schemas import OHLC, OpenInterest, FundingRate


# ============================================
# Fixtures
# ============================================

@pytest_asyncio.fixture
async def api_client():
    """Create a HyperliquidAPIClient instance for testing"""
    async with HyperliquidAPIClient() as client:
        yield client


# ============================================
# Tests for OHLC/Candlestick Data
# ============================================

class TestGetHistoricalOHLC:
    """Tests for get_historical_ohlc method"""

    @pytest.mark.asyncio
    async def test_get_historical_ohlc_returns_list_of_ohlc(self, api_client, monkeypatch):
        """Verify get_historical_ohlc returns normalized OHLC objects"""
        # Mock Hyperliquid API response
        mock_response = [
            {
                "t": 1720000000000,  # Timestamp
                "o": "50000.0",      # Open
                "h": "50500.0",      # High
                "l": "49500.0",      # Low
                "c": "50250.0",      # Close
                "v": "125.5",        # Volume
                "n": 1523            # Number of trades
            }
        ]

        async def mock_post(payload):
            return mock_response

        monkeypatch.setattr(api_client, "_post", mock_post)

        # Call the method
        result = await api_client.get_historical_ohlc("BTC", "1m", 1720000000000, 1720001000000)

        # Assertions
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], OHLC)
        assert result[0].exchange == "hyperliquid"
        assert result[0].symbol == "BTC"
        assert result[0].interval == "1m"
        assert result[0].open == 50000.0
        assert result[0].high == 50500.0
        assert result[0].low == 49500.0
        assert result[0].close == 50250.0
        assert result[0].volume == 125.5
        assert result[0].trades_count == 1523
        assert result[0].is_closed is True

    @pytest.mark.asyncio
    async def test_get_historical_ohlc_normalizes_symbol_to_uppercase(self, api_client, monkeypatch):
        """Verify symbol is normalized to uppercase"""
        called_payload = {}

        async def mock_post(payload):
            nonlocal called_payload
            called_payload = payload
            return []

        monkeypatch.setattr(api_client, "_post", mock_post)

        await api_client.get_historical_ohlc("btc", "1h", 1720000000000, 1720001000000)

        assert called_payload["req"]["coin"] == "BTC"

    @pytest.mark.asyncio
    async def test_get_historical_ohlc_handles_empty_response(self, api_client, monkeypatch):
        """Verify empty response is handled gracefully"""
        async def mock_post(payload):
            return []

        monkeypatch.setattr(api_client, "_post", mock_post)

        result = await api_client.get_historical_ohlc("BTC", "1h", 1720000000000, 1720001000000)

        assert isinstance(result, list)
        assert len(result) == 0


# ============================================
# Tests for Open Interest
# ============================================

class TestGetOpenInterest:
    """Tests for get_open_interest method"""

    @pytest.mark.asyncio
    async def test_get_open_interest_returns_normalized_oi(self, api_client, monkeypatch):
        """Verify get_open_interest returns normalized OpenInterest object"""
        mock_response = [
            {
                "universe": [
                    {"name": "BTC"},
                    {"name": "ETH"}
                ],
                "assetCtxs": [
                    {
                        "openInterest": "12345.678",
                        "markPx": "50000.0",
                        "timestamp": 1720000000000
                    },
                    {
                        "openInterest": "5000.0",
                        "markPx": "3000.0",
                        "timestamp": 1720000000000
                    }
                ]
            }
        ]

        async def mock_post(payload):
            return mock_response

        monkeypatch.setattr(api_client, "_post", mock_post)

        result = await api_client.get_open_interest("BTC")

        assert isinstance(result, OpenInterest)
        assert result.exchange == "hyperliquid"
        assert result.symbol == "BTC"
        assert result.open_interest == 12345.678
        assert result.open_interest_value == 12345.678 * 50000.0
        assert isinstance(result.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_get_open_interest_handles_symbol_not_found(self, api_client, monkeypatch):
        """Verify get_open_interest returns None for unknown symbol"""
        mock_response = [
            {
                "universe": [{"name": "BTC"}],
                "assetCtxs": [
                    {
                        "openInterest": "12345.678",
                        "markPx": "50000.0",
                        "timestamp": 1720000000000
                    }
                ]
            }
        ]

        async def mock_post(payload):
            return mock_response

        monkeypatch.setattr(api_client, "_post", mock_post)

        result = await api_client.get_open_interest("UNKNOWN")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_open_interest_normalizes_symbol(self, api_client, monkeypatch):
        """Verify symbol is normalized to uppercase"""
        called_payload = {}

        async def mock_post(payload):
            nonlocal called_payload
            called_payload = payload
            return [{"universe": [], "assetCtxs": []}]

        monkeypatch.setattr(api_client, "_post", mock_post)

        await api_client.get_open_interest("btc")

        # The payload should have type but not symbol (metaAndAssetCtxs fetches all)
        assert called_payload["type"] == "metaAndAssetCtxs"


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
                "coin": "BTC",
                "fundingRate": "0.0001",
                "premium": "0.00005",
                "time": 1720000000000
            },
            {
                "coin": "BTC",
                "fundingRate": "0.00015",
                "premium": "0.00007",
                "time": 1720028800000
            }
        ]

        async def mock_post(payload):
            return mock_response

        monkeypatch.setattr(api_client, "_post", mock_post)

        result = await api_client.get_funding_rate("BTC", limit=2)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(fr, FundingRate) for fr in result)
        assert result[0].symbol == "BTC"
        assert result[0].funding_rate == 0.0001
        assert result[1].funding_rate == 0.00015

    @pytest.mark.asyncio
    async def test_get_funding_rate_respects_limit(self, api_client, monkeypatch):
        """Verify limit parameter truncates results"""
        mock_response = [
            {"coin": "BTC", "fundingRate": "0.0001", "time": 1720000000000},
            {"coin": "BTC", "fundingRate": "0.0002", "time": 1720001000000},
            {"coin": "BTC", "fundingRate": "0.0003", "time": 1720002000000},
            {"coin": "BTC", "fundingRate": "0.0004", "time": 1720003000000},
            {"coin": "BTC", "fundingRate": "0.0005", "time": 1720004000000},
        ]

        async def mock_post(payload):
            return mock_response

        monkeypatch.setattr(api_client, "_post", mock_post)

        result = await api_client.get_funding_rate("BTC", limit=2)

        # Should return only the last 2 entries
        assert len(result) == 2
        assert result[0].funding_rate == 0.0004
        assert result[1].funding_rate == 0.0005

    @pytest.mark.asyncio
    async def test_get_funding_rate_handles_empty_response(self, api_client, monkeypatch):
        """Verify empty response is handled gracefully"""
        async def mock_post(payload):
            return []

        monkeypatch.setattr(api_client, "_post", mock_post)

        result = await api_client.get_funding_rate("BTC")

        assert isinstance(result, list)
        assert len(result) == 0


# ============================================
# Tests for Predicted Funding
# ============================================

class TestGetPredictedFunding:
    """Tests for get_predicted_funding method"""

    @pytest.mark.asyncio
    async def test_get_predicted_funding_returns_dict(self, api_client, monkeypatch):
        """Verify get_predicted_funding returns dict of predictions"""
        mock_response = [
            {"coin": "BTC", "fundingRate": "0.00015"},
            {"coin": "ETH", "fundingRate": "0.0002"}
        ]

        async def mock_post(payload):
            return mock_response

        monkeypatch.setattr(api_client, "_post", mock_post)

        result = await api_client.get_predicted_funding()

        assert isinstance(result, dict)
        assert "BTC" in result
        assert "ETH" in result
        assert result["BTC"] == 0.00015
        assert result["ETH"] == 0.0002

    @pytest.mark.asyncio
    async def test_get_predicted_funding_handles_empty_response(self, api_client, monkeypatch):
        """Verify empty response is handled gracefully"""
        async def mock_post(payload):
            return []

        monkeypatch.setattr(api_client, "_post", mock_post)

        result = await api_client.get_predicted_funding()

        assert isinstance(result, dict)
        assert len(result) == 0


# ============================================
# Tests for Context Manager
# ============================================

class TestContextManager:
    """Tests for async context manager functionality"""

    @pytest.mark.asyncio
    async def test_context_manager_creates_session(self):
        """Verify context manager creates aiohttp session"""
        client = HyperliquidAPIClient()
        assert client.session is None

        async with client as c:
            assert c.session is not None

    @pytest.mark.asyncio
    async def test_context_manager_raises_if_not_used(self):
        """Verify _post raises error if session not initialized"""
        client = HyperliquidAPIClient()

        with pytest.raises(RuntimeError, match="not initialized"):
            await client._post({"type": "test"})


# ============================================
# Tests for Error Handling
# ============================================

class TestErrorHandling:
    """Tests for error handling and retry logic"""

    @pytest.mark.asyncio
    async def test_post_retries_on_rate_limit(self, api_client, monkeypatch):
        """Verify _post retries on rate limit (429)"""
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

        def mock_post(url, json=None, headers=None, timeout=None):
            nonlocal call_count
            call_count += 1

            # Return rate limit error on first 2 calls, success on 3rd
            if call_count < 3:
                return MockResponse(429)  # Rate limited
            else:
                return MockResponse(200, {"success": True})  # Success

        # Patch the session.post method
        api_client.session.post = mock_post

        result = await api_client._post({"type": "test"})

        assert call_count == 3  # Should retry 2 times before success
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_post_fails_after_max_retries(self, api_client, monkeypatch):
        """Verify _post raises error after max retries"""

        class MockResponse:
            def __init__(self):
                self.status = 429

            async def text(self):
                return "Rate limit exceeded"

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        def mock_post(url, json=None, headers=None, timeout=None):
            # Always return rate limit error
            return MockResponse()

        api_client.session.post = mock_post

        with pytest.raises(RuntimeError, match="Failed to fetch"):
            await api_client._post({"type": "test"})

    @pytest.mark.asyncio
    async def test_get_open_interest_handles_exception(self, api_client, monkeypatch):
        """Verify get_open_interest handles exceptions gracefully"""
        async def mock_post(payload):
            raise Exception("Network error")

        monkeypatch.setattr(api_client, "_post", mock_post)

        result = await api_client.get_open_interest("BTC")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_funding_rate_handles_exception(self, api_client, monkeypatch):
        """Verify get_funding_rate handles exceptions gracefully"""
        async def mock_post(payload):
            raise Exception("Network error")

        monkeypatch.setattr(api_client, "_post", mock_post)

        result = await api_client.get_funding_rate("BTC")

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_historical_ohlc_handles_exception(self, api_client, monkeypatch):
        """Verify get_historical_ohlc handles exceptions gracefully"""
        async def mock_post(payload):
            raise Exception("Network error")

        monkeypatch.setattr(api_client, "_post", mock_post)

        result = await api_client.get_historical_ohlc("BTC", "1m", 1720000000000, 1720001000000)

        assert isinstance(result, list)
        assert len(result) == 0
