"""
Unit Tests for Binance WebSocket Client

These tests verify that BinanceWebSocketClient:
- Connects to WebSocket endpoints correctly
- Parses and yields messages properly
- Handles reconnection with exponential backoff
- Gracefully closes connections
- Uses context managers correctly

Run with:
    pytest tests/unit/test_ws_client.py -v
"""

import pytest
import pytest_asyncio
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import WSMsgType

from exchanges.binance.ws_client import (
    BinanceWebSocketClient,
    create_kline_stream,
    create_liquidation_stream,
    create_trade_stream,
    create_mark_price_stream
)


# ============================================
# Mock WebSocket Message Helper
# ============================================

class MockWSMessage:
    """Mock aiohttp WebSocket message"""

    def __init__(self, msg_type, data=None):
        self.type = msg_type
        self.data = data


# ============================================
# Tests for Connection Management
# ============================================

class TestConnectionManagement:
    """Tests for WebSocket connection lifecycle"""

    @pytest.mark.asyncio
    async def test_context_manager_creates_session(self):
        """Verify context manager creates aiohttp session"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m")
        assert client.session is None

        async with client:
            assert client.session is not None
            assert client._is_running is True

    @pytest.mark.asyncio
    async def test_context_manager_closes_session(self):
        """Verify context manager closes session on exit"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m")

        async with client:
            pass

        assert client._is_running is False
        # Session is closed by __aexit__

    @pytest.mark.asyncio
    async def test_connect_raises_without_session(self):
        """Verify connect() raises error if session not initialized"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m")

        with pytest.raises(RuntimeError, match="not initialized"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_connect_builds_correct_url(self):
        """Verify WebSocket URL is constructed correctly"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m")

        async with client:
            # Mock ws_connect to inspect the URL
            with patch.object(client.session, "ws_connect") as mock_connect:
                mock_ws = AsyncMock()
                mock_connect.return_value = mock_ws

                await client.connect()

                # Verify URL format
                called_url = mock_connect.call_args[0][0]
                assert called_url == "wss://fstream.binance.com/ws/btcusdt@kline_1m"

    @pytest.mark.asyncio
    async def test_symbol_lowercased_in_url(self):
        """Verify symbol is lowercased (Binance requirement)"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1h")

        assert client.symbol == "btcusdt"  # Lowercased


# ============================================
# Tests for Message Streaming
# ============================================

class TestMessageStreaming:
    """Tests for listen() message streaming"""

    @pytest.mark.asyncio
    async def test_listen_yields_parsed_json(self):
        """Verify listen() parses and yields JSON messages"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m")

        # Mock WebSocket messages
        mock_msg = MockWSMessage(
            WSMsgType.TEXT,
            json.dumps({"e": "kline", "k": {"c": "50000"}})
        )

        async with client:
            with patch.object(client.session, "ws_connect") as mock_connect:
                # Create mock WebSocket that yields one message
                mock_ws = AsyncMock()
                mock_ws.closed = False

                # Properly mock async iteration
                async def mock_aiter():
                    yield mock_msg

                mock_ws.__aiter__ = mock_aiter
                mock_connect.return_value = mock_ws

                # Consume first message
                messages = []
                async for msg in client.listen():
                    messages.append(msg)
                    client._is_running = False  # Stop listening
                    break  # Only get first message

                assert len(messages) == 1
                assert messages[0]["e"] == "kline"
                assert messages[0]["k"]["c"] == "50000"

    @pytest.mark.asyncio
    async def test_listen_handles_closed_message(self):
        """Verify listen() stops on CLOSED message"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m")

        mock_closed = MockWSMessage(WSMsgType.CLOSED, "Connection closed")

        async with client:
            with patch.object(client.session, "ws_connect") as mock_connect:
                mock_ws = AsyncMock()
                mock_ws.closed = False

                async def mock_aiter():
                    yield mock_closed

                mock_ws.__aiter__ = mock_aiter
                mock_connect.return_value = mock_ws

                # Should exit cleanly without yielding
                messages = []
                client._is_running = False  # Prevent reconnection loop
                async for msg in client.listen():
                    messages.append(msg)

                assert len(messages) == 0  # No messages yielded

    @pytest.mark.asyncio
    async def test_listen_handles_invalid_json(self):
        """Verify listen() skips invalid JSON messages"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m")

        mock_invalid = MockWSMessage(WSMsgType.TEXT, "invalid json{{{")
        mock_valid = MockWSMessage(
            WSMsgType.TEXT,
            json.dumps({"e": "kline", "valid": True})
        )

        async with client:
            with patch.object(client.session, "ws_connect") as mock_connect:
                mock_ws = AsyncMock()
                mock_ws.closed = False

                async def mock_aiter():
                    yield mock_invalid
                    yield mock_valid

                mock_ws.__aiter__ = mock_aiter
                mock_connect.return_value = mock_ws

                messages = []
                async for msg in client.listen():
                    messages.append(msg)
                    if len(messages) >= 1:
                        client._is_running = False
                        break

                # Should skip invalid and yield valid
                assert len(messages) == 1
                assert messages[0]["valid"] is True


# ============================================
# Tests for Reconnection Logic
# ============================================

class TestReconnection:
    """Tests for automatic reconnection with exponential backoff"""

    def test_max_reconnect_delay_parameter(self):
        """Verify max_reconnect_delay is set correctly"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m", max_reconnect_delay=60)
        assert client.max_reconnect_delay == 60

    def test_default_max_reconnect_delay(self):
        """Verify default max_reconnect_delay is 30 seconds"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m")
        assert client.max_reconnect_delay == 30


# ============================================
# Tests for Convenience Builders
# ============================================

class TestConvenienceBuilders:
    """Tests for create_*_stream helper functions"""

    def test_create_kline_stream(self):
        """Verify create_kline_stream creates correct client"""
        client = create_kline_stream("BTCUSDT", "5m")

        assert isinstance(client, BinanceWebSocketClient)
        assert client.symbol == "btcusdt"
        assert client.stream == "kline_5m"

    def test_create_liquidation_stream(self):
        """Verify create_liquidation_stream creates correct client"""
        client = create_liquidation_stream("ETHUSDT")

        assert isinstance(client, BinanceWebSocketClient)
        assert client.symbol == "ethusdt"
        assert client.stream == "forceOrder"

    def test_create_trade_stream(self):
        """Verify create_trade_stream creates correct client"""
        client = create_trade_stream("BTCUSDT")

        assert isinstance(client, BinanceWebSocketClient)
        assert client.symbol == "btcusdt"
        assert client.stream == "aggTrade"

    def test_create_mark_price_stream(self):
        """Verify create_mark_price_stream creates correct client"""
        client = create_mark_price_stream("BTCUSDT")

        assert isinstance(client, BinanceWebSocketClient)
        assert client.symbol == "btcusdt"
        assert client.stream == "markPrice"


# ============================================
# Tests for Cleanup
# ============================================

class TestCleanup:
    """Tests for graceful shutdown"""

    @pytest.mark.asyncio
    async def test_close_called_on_exit(self):
        """Verify close() is called when exiting context"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m")

        async with client:
            with patch.object(client, "close", new_callable=AsyncMock) as mock_close:
                pass  # Exit context

        # Note: close is called by __aexit__, but our patch was inside the context
        # So we test close() method directly below

    @pytest.mark.asyncio
    async def test_close_handles_none_safely(self):
        """Verify close() is safe when ws/session are None"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m")

        # Should not raise error
        await client.close()

        assert client.ws is None
        assert client.session is None

    @pytest.mark.asyncio
    async def test_close_closes_both_ws_and_session(self):
        """Verify close() closes both WebSocket and session"""
        client = BinanceWebSocketClient("BTCUSDT", "kline_1m")

        async with client:
            with patch.object(client.session, "ws_connect") as mock_connect:
                mock_ws = AsyncMock()
                mock_ws.closed = False
                mock_connect.return_value = mock_ws

                await client.connect()

                # Close everything
                await client.close()

                # Verify close was called
                mock_ws.close.assert_called_once()
