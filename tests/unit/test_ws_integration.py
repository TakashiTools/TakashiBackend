"""
Integration Tests for WebSocket Streaming

These tests verify the end-to-end WebSocket streaming functionality:
- BinanceExchange stream methods normalize data correctly
- OHLC, Liquidation, and LargeTrade streams work properly
- Data flows from WebSocket client through BinanceExchange
- Pydantic schemas are validated correctly

Run with:
    pytest tests/unit/test_ws_integration.py -v
"""

import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from aiohttp import WSMsgType

from exchanges.binance import BinanceExchange
from core.schemas import OHLC, Liquidation, LargeTrade


# ============================================
# Mock WebSocket Message Helper
# ============================================

class MockWSMessage:
    """Mock aiohttp WebSocket message"""

    def __init__(self, msg_type, data=None):
        self.type = msg_type
        self.data = data


# ============================================
# Fixtures
# ============================================

@pytest_asyncio.fixture
async def binance_exchange():
    """Create and initialize BinanceExchange for testing"""
    exchange = BinanceExchange()
    await exchange.initialize()
    yield exchange
    await exchange.shutdown()


# ============================================
# Tests for OHLC Streaming
# ============================================

class TestOHLCStreaming:
    """Tests for stream_ohlc integration"""

    @pytest.mark.asyncio
    async def test_stream_ohlc_yields_normalized_data(self, binance_exchange):
        """Verify stream_ohlc normalizes Binance messages to OHLC schema"""

        # Mock Binance kline WebSocket message
        binance_kline_msg = {
            "e": "kline",
            "E": 1672531200000,
            "s": "BTCUSDT",
            "k": {
                "t": 1672531200000,  # Open time
                "T": 1672531259999,  # Close time
                "s": "BTCUSDT",
                "i": "1m",
                "o": "50000.00",
                "c": "50100.00",
                "h": "50200.00",
                "l": "49900.00",
                "v": "100.5",
                "q": "5025000.0",
                "n": 1523,
                "x": True  # Candle closed
            }
        }

        # Mock WebSocket client
        with patch("exchanges.binance.create_kline_stream") as mock_create:
            mock_ws_client = AsyncMock()

            # Mock listen() to yield one message
            async def mock_listen():
                yield binance_kline_msg

            mock_ws_client.listen = mock_listen
            mock_ws_client.__aenter__ = AsyncMock(return_value=mock_ws_client)
            mock_ws_client.__aexit__ = AsyncMock()

            mock_create.return_value = mock_ws_client

            # Stream OHLC data
            ohlc_list = []
            async for ohlc in binance_exchange.stream_ohlc("BTCUSDT", "1m"):
                ohlc_list.append(ohlc)
                break  # Get first message only

            # Verify normalization
            assert len(ohlc_list) == 1
            ohlc = ohlc_list[0]

            assert isinstance(ohlc, OHLC)
            assert ohlc.exchange == "binance"
            assert ohlc.symbol == "BTCUSDT"
            assert ohlc.interval == "1m"
            assert ohlc.open == 50000.0
            assert ohlc.high == 50200.0
            assert ohlc.low == 49900.0
            assert ohlc.close == 50100.0
            assert ohlc.volume == 100.5
            assert ohlc.quote_volume == 5025000.0
            assert ohlc.trades_count == 1523
            assert ohlc.is_closed is True
            assert isinstance(ohlc.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_stream_ohlc_skips_invalid_messages(self, binance_exchange):
        """Verify stream_ohlc skips non-kline messages"""

        invalid_msg = {"e": "trade", "s": "BTCUSDT"}  # Wrong event type
        valid_msg = {
            "e": "kline",
            "k": {
                "t": 1672531200000,
                "o": "50000",
                "h": "50000",
                "l": "50000",
                "c": "50000",
                "v": "1",
                "q": "50000",
                "n": 1,
                "x": False
            }
        }

        with patch("exchanges.binance.create_kline_stream") as mock_create:
            mock_ws_client = AsyncMock()

            async def mock_listen():
                yield invalid_msg
                yield valid_msg

            mock_ws_client.listen = mock_listen
            mock_ws_client.__aenter__ = AsyncMock(return_value=mock_ws_client)
            mock_ws_client.__aexit__ = AsyncMock()

            mock_create.return_value = mock_ws_client

            # Should skip invalid and yield valid
            ohlc_list = []
            async for ohlc in binance_exchange.stream_ohlc("BTCUSDT", "1m"):
                ohlc_list.append(ohlc)
                break

            assert len(ohlc_list) == 1
            assert ohlc_list[0].close == 50000.0


# ============================================
# Tests for Liquidation Streaming
# ============================================

class TestLiquidationStreaming:
    """Tests for stream_liquidations integration"""

    @pytest.mark.asyncio
    async def test_stream_liquidations_yields_normalized_data(self, binance_exchange):
        """Verify stream_liquidations normalizes Binance messages to Liquidation schema"""

        # Mock Binance liquidation message
        binance_liq_msg = {
            "e": "forceOrder",
            "E": 1672531200000,
            "o": {
                "s": "BTCUSDT",
                "S": "SELL",
                "o": "LIMIT",
                "q": "2.5",
                "p": "50000.00",
                "ap": "50000.00",
                "X": "FILLED",
                "T": 1672531200000
            }
        }

        with patch("exchanges.binance.create_liquidation_stream") as mock_create:
            mock_ws_client = AsyncMock()

            async def mock_listen():
                yield binance_liq_msg

            mock_ws_client.listen = mock_listen
            mock_ws_client.__aenter__ = AsyncMock(return_value=mock_ws_client)
            mock_ws_client.__aexit__ = AsyncMock()

            mock_create.return_value = mock_ws_client

            # Stream liquidation data
            liq_list = []
            async for liq in binance_exchange.stream_liquidations("BTCUSDT"):
                liq_list.append(liq)
                break

            # Verify normalization
            assert len(liq_list) == 1
            liq = liq_list[0]

            assert isinstance(liq, Liquidation)
            assert liq.exchange == "binance"
            assert liq.symbol == "BTCUSDT"
            assert liq.side == "sell"  # Lowercased
            assert liq.price == 50000.0
            assert liq.quantity == 2.5
            assert isinstance(liq.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_stream_liquidations_handles_buy_side(self, binance_exchange):
        """Verify liquidation side is normalized (BUY -> buy)"""

        binance_liq_msg = {
            "e": "forceOrder",
            "E": 1672531200000,
            "o": {
                "s": "BTCUSDT",
                "S": "BUY",  # Buy liquidation
                "q": "1.0",
                "p": "50000.00",
                "T": 1672531200000
            }
        }

        with patch("exchanges.binance.create_liquidation_stream") as mock_create:
            mock_ws_client = AsyncMock()

            async def mock_listen():
                yield binance_liq_msg

            mock_ws_client.listen = mock_listen
            mock_ws_client.__aenter__ = AsyncMock(return_value=mock_ws_client)
            mock_ws_client.__aexit__ = AsyncMock()

            mock_create.return_value = mock_ws_client

            liq_list = []
            async for liq in binance_exchange.stream_liquidations("BTCUSDT"):
                liq_list.append(liq)
                break

            assert liq_list[0].side == "buy"  # Lowercased


# ============================================
# Tests for Large Trade Streaming
# ============================================

class TestLargeTradeStreaming:
    """Tests for stream_large_trades integration"""

    @pytest.mark.asyncio
    async def test_stream_large_trades_yields_normalized_data(self, binance_exchange):
        """Verify stream_large_trades normalizes Binance messages to LargeTrade schema"""

        # Mock Binance aggTrade message (large trade: $5M)
        binance_trade_msg = {
            "e": "aggTrade",
            "E": 1672531200000,
            "s": "BTCUSDT",
            "a": 12345,
            "p": "50000.00",
            "q": "100.0",  # 100 BTC * $50k = $5M (above $100k threshold)
            "f": 100,
            "l": 105,
            "T": 1672531200000,
            "m": False  # Not buyer maker = buy
        }

        with patch("exchanges.binance.create_trade_stream") as mock_create:
            mock_ws_client = AsyncMock()

            async def mock_listen():
                yield binance_trade_msg

            mock_ws_client.listen = mock_listen
            mock_ws_client.__aenter__ = AsyncMock(return_value=mock_ws_client)
            mock_ws_client.__aexit__ = AsyncMock()

            mock_create.return_value = mock_ws_client

            # Stream trade data
            trade_list = []
            async for trade in binance_exchange.stream_large_trades("BTCUSDT"):
                trade_list.append(trade)
                break

            # Verify normalization
            assert len(trade_list) == 1
            trade = trade_list[0]

            assert isinstance(trade, LargeTrade)
            assert trade.exchange == "binance"
            assert trade.symbol == "BTCUSDT"
            assert trade.side == "buy"  # m=False means buy
            assert trade.price == 50000.0
            assert trade.quantity == 100.0
            assert trade.value == 5_000_000.0
            assert trade.is_buyer_maker is False
            assert isinstance(trade.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_stream_large_trades_filters_small_trades(self, binance_exchange):
        """Verify trades below $100k are filtered out"""

        # Small trade: $50k (below threshold)
        small_trade_msg = {
            "e": "aggTrade",
            "s": "BTCUSDT",
            "p": "50000.00",
            "q": "0.5",  # 0.5 BTC * $50k = $25k (below threshold)
            "T": 1672531200000,
            "m": False
        }

        # Large trade: $5M (above threshold)
        large_trade_msg = {
            "e": "aggTrade",
            "s": "BTCUSDT",
            "p": "50000.00",
            "q": "100.0",  # 100 BTC * $50k = $5M
            "T": 1672531200000,
            "m": False
        }

        with patch("exchanges.binance.create_trade_stream") as mock_create:
            mock_ws_client = AsyncMock()

            async def mock_listen():
                yield small_trade_msg  # Should be filtered
                yield large_trade_msg  # Should be yielded

            mock_ws_client.listen = mock_listen
            mock_ws_client.__aenter__ = AsyncMock(return_value=mock_ws_client)
            mock_ws_client.__aexit__ = AsyncMock()

            mock_create.return_value = mock_ws_client

            # Should only get large trade
            trade_list = []
            async for trade in binance_exchange.stream_large_trades("BTCUSDT"):
                trade_list.append(trade)
                break

            assert len(trade_list) == 1
            assert trade_list[0].value == 5_000_000.0

    @pytest.mark.asyncio
    async def test_stream_large_trades_determines_side_correctly(self, binance_exchange):
        """Verify side is determined from buyer_maker flag"""

        # Test sell trade (buyer_maker=True)
        sell_trade_msg = {
            "e": "aggTrade",
            "s": "BTCUSDT",
            "p": "50000.00",
            "q": "100.0",
            "T": 1672531200000,
            "m": True  # Buyer maker = sell
        }

        with patch("exchanges.binance.create_trade_stream") as mock_create:
            mock_ws_client = AsyncMock()

            async def mock_listen():
                yield sell_trade_msg

            mock_ws_client.listen = mock_listen
            mock_ws_client.__aenter__ = AsyncMock(return_value=mock_ws_client)
            mock_ws_client.__aexit__ = AsyncMock()

            mock_create.return_value = mock_ws_client

            trade_list = []
            async for trade in binance_exchange.stream_large_trades("BTCUSDT"):
                trade_list.append(trade)
                break

            assert trade_list[0].side == "sell"
            assert trade_list[0].is_buyer_maker is True


# ============================================
# Tests for Error Handling
# ============================================

class TestErrorHandling:
    """Tests for WebSocket error scenarios"""

    @pytest.mark.asyncio
    async def test_stream_handles_websocket_errors_gracefully(self, binance_exchange):
        """Verify streams handle WebSocket errors without crashing"""

        with patch("exchanges.binance.create_kline_stream") as mock_create:
            mock_ws_client = AsyncMock()

            async def mock_listen():
                # Simulate WebSocket error
                raise Exception("WebSocket connection lost")

            mock_ws_client.listen = mock_listen
            mock_ws_client.__aenter__ = AsyncMock(return_value=mock_ws_client)
            mock_ws_client.__aexit__ = AsyncMock()

            mock_create.return_value = mock_ws_client

            # Should raise exception from listen()
            with pytest.raises(Exception, match="WebSocket connection lost"):
                async for ohlc in binance_exchange.stream_ohlc("BTCUSDT", "1m"):
                    pass


# ============================================
# Tests for Symbol Normalization
# ============================================

class TestSymbolNormalization:
    """Tests for symbol case handling"""

    @pytest.mark.asyncio
    async def test_stream_normalizes_symbol_to_uppercase(self, binance_exchange):
        """Verify output symbol is uppercase in OHLC"""

        binance_msg = {
            "e": "kline",
            "k": {
                "t": 1672531200000,
                "o": "50000",
                "h": "50000",
                "l": "50000",
                "c": "50000",
                "v": "1",
                "q": "50000",
                "n": 1,
                "x": False
            }
        }

        with patch("exchanges.binance.create_kline_stream") as mock_create:
            mock_ws_client = AsyncMock()

            async def mock_listen():
                yield binance_msg

            mock_ws_client.listen = mock_listen
            mock_ws_client.__aenter__ = AsyncMock(return_value=mock_ws_client)
            mock_ws_client.__aexit__ = AsyncMock()

            mock_create.return_value = mock_ws_client

            # Pass lowercase symbol
            ohlc_list = []
            async for ohlc in binance_exchange.stream_ohlc("btcusdt", "1m"):
                ohlc_list.append(ohlc)
                break

            # Output should be uppercase
            assert ohlc_list[0].symbol == "BTCUSDT"
