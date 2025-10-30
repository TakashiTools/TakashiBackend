"""
Unit Tests for Exchange Interface and Manager

These tests verify that:
- ExchangeInterface is properly defined as an abstract class
- Dummy implementations can inherit and implement the interface
- ExchangeManager correctly manages exchange instances
- Exchange capabilities are properly declared
- Lifecycle methods work as expected

Run with:
    pytest tests/unit/test_exchange_interface.py -v
"""

import pytest
from typing import List, AsyncGenerator
from core.exchange_interface import ExchangeInterface
from core.exchange_manager import ExchangeManager
from core.schemas import OHLC, OpenInterest, FundingRate, Liquidation, LargeTrade
from exchanges.binance import BinanceExchange


# ============================================
# Dummy Exchange for Testing
# ============================================

class DummyExchange(ExchangeInterface):
    """
    Minimal implementation of ExchangeInterface for testing purposes.

    This dummy exchange implements all required methods with minimal logic,
    allowing us to test the interface contract without actual API calls.
    """

    name = "dummy"
    capabilities = {
        "ohlc": True,
        "funding_rate": False,  # Intentionally not supported
        "open_interest": True,
        "liquidations": False,  # Intentionally not supported
        "large_trades": True
    }

    async def get_ohlc(self, symbol: str, interval: str, limit: int = 500) -> List[OHLC]:
        """Return empty list (stub)"""
        return []

    async def get_open_interest(self, symbol: str) -> OpenInterest:
        """Raise NotImplementedError (stub)"""
        raise NotImplementedError("Dummy exchange doesn't implement open interest")

    async def get_funding_rate(self, symbol: str) -> FundingRate:
        """Raise NotImplementedError (not supported)"""
        raise NotImplementedError("Dummy exchange doesn't support funding rates")

    async def stream_ohlc(self, symbol: str, interval: str) -> AsyncGenerator[OHLC, None]:
        """Empty generator (stub)"""
        if False:
            yield

    async def stream_liquidations(self, symbol: str) -> AsyncGenerator[Liquidation, None]:
        """Empty generator (not supported)"""
        if False:
            yield

    async def stream_large_trades(self, symbol: str) -> AsyncGenerator[LargeTrade, None]:
        """Empty generator (stub)"""
        if False:
            yield


# ============================================
# Tests for ExchangeInterface
# ============================================

class TestExchangeInterface:
    """Test the ExchangeInterface abstract class"""

    def test_cannot_instantiate_abstract_interface(self):
        """Verify that ExchangeInterface cannot be instantiated directly"""
        with pytest.raises(TypeError):
            # Should raise TypeError because it's abstract
            exchange = ExchangeInterface()

    def test_dummy_exchange_has_required_attributes(self):
        """Verify that exchange implementations have required attributes"""
        exchange = DummyExchange()
        assert hasattr(exchange, "name")
        assert hasattr(exchange, "capabilities")
        assert isinstance(exchange.name, str)
        assert isinstance(exchange.capabilities, dict)

    def test_dummy_exchange_implements_all_methods(self):
        """Verify that exchange has all required methods"""
        exchange = DummyExchange()

        # REST methods
        assert hasattr(exchange, "get_ohlc")
        assert hasattr(exchange, "get_open_interest")
        assert hasattr(exchange, "get_funding_rate")

        # WebSocket methods
        assert hasattr(exchange, "stream_ohlc")
        assert hasattr(exchange, "stream_liquidations")
        assert hasattr(exchange, "stream_large_trades")

        # Lifecycle methods
        assert hasattr(exchange, "initialize")
        assert hasattr(exchange, "shutdown")
        assert hasattr(exchange, "health_check")

    def test_supports_method_returns_correct_values(self):
        """Verify that supports() method checks capabilities correctly"""
        exchange = DummyExchange()

        assert exchange.supports("ohlc") is True
        assert exchange.supports("funding_rate") is False
        assert exchange.supports("open_interest") is True
        assert exchange.supports("liquidations") is False
        assert exchange.supports("large_trades") is True

        # Non-existent feature should return False
        assert exchange.supports("nonexistent_feature") is False

    @pytest.mark.asyncio
    async def test_get_ohlc_is_callable(self):
        """Verify that get_ohlc can be called and returns expected type"""
        exchange = DummyExchange()
        result = await exchange.get_ohlc("BTCUSDT", "1h", limit=100)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_unsupported_method_raises_not_implemented(self):
        """Verify that unsupported methods raise NotImplementedError"""
        exchange = DummyExchange()

        with pytest.raises(NotImplementedError):
            await exchange.get_funding_rate("BTCUSDT")

    @pytest.mark.asyncio
    async def test_health_check_default_returns_true(self):
        """Verify that default health_check returns True"""
        exchange = DummyExchange()
        is_healthy = await exchange.health_check()
        assert is_healthy is True


# ============================================
# Tests for BinanceExchange
# ============================================

class TestBinanceExchange:
    """Test the BinanceExchange implementation"""

    def test_binance_exchange_has_correct_name(self):
        """Verify Binance exchange has correct identifier"""
        exchange = BinanceExchange()
        assert exchange.name == "binance"

    def test_binance_exchange_capabilities_all_true(self):
        """Verify Binance supports all features"""
        exchange = BinanceExchange()
        assert exchange.capabilities["ohlc"] is True
        assert exchange.capabilities["funding_rate"] is True
        assert exchange.capabilities["open_interest"] is True
        assert exchange.capabilities["liquidations"] is True
        assert exchange.capabilities["large_trades"] is True

    def test_binance_exchange_has_urls_configured(self):
        """Verify Binance exchange has API URLs set"""
        exchange = BinanceExchange()
        assert exchange.base_url is not None
        assert "binance" in exchange.base_url.lower()
        assert exchange.ws_url is not None
        assert exchange.ws_url.startswith("wss://")

    @pytest.mark.asyncio
    async def test_binance_initialize_runs_without_error(self):
        """Verify Binance initialization doesn't raise errors"""
        exchange = BinanceExchange()
        await exchange.initialize()
        # Should complete without raising exceptions

    @pytest.mark.asyncio
    async def test_binance_shutdown_runs_without_error(self):
        """Verify Binance shutdown doesn't raise errors"""
        exchange = BinanceExchange()
        await exchange.shutdown()
        # Should complete without raising exceptions

    @pytest.mark.asyncio
    async def test_binance_health_check_returns_boolean(self):
        """Verify health check returns a boolean"""
        exchange = BinanceExchange()
        result = await exchange.health_check()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_binance_get_ohlc_returns_list(self):
        """Verify get_ohlc returns a list (even if empty stub)"""
        exchange = BinanceExchange()
        result = await exchange.get_ohlc("BTCUSDT", "1h", limit=100)
        assert isinstance(result, list)

    def test_binance_implements_exchange_interface(self):
        """Verify BinanceExchange is a subclass of ExchangeInterface"""
        exchange = BinanceExchange()
        assert isinstance(exchange, ExchangeInterface)


# ============================================
# Tests for ExchangeManager
# ============================================

class TestExchangeManager:
    """Test the ExchangeManager registry"""

    def test_manager_initializes_with_exchanges(self):
        """Verify manager creates exchange instances on initialization"""
        manager = ExchangeManager()
        assert len(manager.exchanges) > 0
        assert "binance" in manager.exchanges

    def test_manager_get_exchange_returns_correct_instance(self):
        """Verify get_exchange returns the requested exchange"""
        manager = ExchangeManager()
        binance = manager.get_exchange("binance")
        assert isinstance(binance, BinanceExchange)
        assert binance.name == "binance"

    def test_manager_get_exchange_case_insensitive(self):
        """Verify exchange name lookup is case-insensitive"""
        manager = ExchangeManager()
        binance1 = manager.get_exchange("binance")
        binance2 = manager.get_exchange("BINANCE")
        binance3 = manager.get_exchange("Binance")
        assert binance1 is binance2 is binance3  # Same instance

    def test_manager_get_exchange_raises_for_unknown(self):
        """Verify ValueError is raised for unsupported exchanges"""
        manager = ExchangeManager()
        with pytest.raises(ValueError, match="not supported"):
            manager.get_exchange("unknown_exchange")

    def test_manager_has_exchange_returns_correct_values(self):
        """Verify has_exchange correctly identifies supported exchanges"""
        manager = ExchangeManager()
        assert manager.has_exchange("binance") is True
        assert manager.has_exchange("BINANCE") is True  # Case-insensitive
        assert manager.has_exchange("unknown") is False

    def test_manager_list_exchanges_returns_list(self):
        """Verify list_exchanges returns all exchange names"""
        manager = ExchangeManager()
        exchanges = manager.list_exchanges()
        assert isinstance(exchanges, list)
        assert "binance" in exchanges
        assert len(exchanges) > 0

    def test_manager_length_equals_exchange_count(self):
        """Verify len() returns the number of registered exchanges"""
        manager = ExchangeManager()
        assert len(manager) == len(manager.exchanges)

    @pytest.mark.asyncio
    async def test_manager_initialize_all_runs_without_error(self):
        """Verify initialize_all calls initialize on all exchanges"""
        manager = ExchangeManager()
        await manager.initialize_all()
        # Should complete without raising exceptions

    @pytest.mark.asyncio
    async def test_manager_shutdown_all_runs_without_error(self):
        """Verify shutdown_all calls shutdown on all exchanges"""
        manager = ExchangeManager()
        await manager.shutdown_all()
        # Should complete without raising exceptions

    @pytest.mark.asyncio
    async def test_manager_initialize_specific_exchange(self):
        """Verify initialize_exchange initializes a specific exchange"""
        manager = ExchangeManager()
        await manager.initialize_exchange("binance")
        # Should complete without raising exceptions

    @pytest.mark.asyncio
    async def test_manager_shutdown_specific_exchange(self):
        """Verify shutdown_exchange shuts down a specific exchange"""
        manager = ExchangeManager()
        await manager.shutdown_exchange("binance")
        # Should complete without raising exceptions

    @pytest.mark.asyncio
    async def test_manager_health_check_all_returns_dict(self):
        """Verify health_check_all returns status for all exchanges"""
        manager = ExchangeManager()
        health = await manager.health_check_all()
        assert isinstance(health, dict)
        assert "binance" in health
        assert isinstance(health["binance"], bool)

    @pytest.mark.asyncio
    async def test_manager_health_check_specific_exchange(self):
        """Verify health_check_exchange returns boolean"""
        manager = ExchangeManager()
        is_healthy = await manager.health_check_exchange("binance")
        assert isinstance(is_healthy, bool)

    def test_manager_get_exchanges_with_feature(self):
        """Verify get_exchanges_with_feature filters correctly"""
        manager = ExchangeManager()

        # Binance supports OHLC
        ohlc_exchanges = manager.get_exchanges_with_feature("ohlc")
        assert "binance" in ohlc_exchanges

        # Test with a feature that might not be universally supported
        # (In this case, all Binance features are supported)
        liquidations = manager.get_exchanges_with_feature("liquidations")
        assert isinstance(liquidations, list)

    def test_manager_get_exchange_capabilities(self):
        """Verify get_exchange_capabilities returns capabilities dict"""
        manager = ExchangeManager()
        caps = manager.get_exchange_capabilities("binance")
        assert isinstance(caps, dict)
        assert "ohlc" in caps
        assert "funding_rate" in caps

    def test_manager_repr_includes_exchange_names(self):
        """Verify __repr__ shows exchange names"""
        manager = ExchangeManager()
        repr_str = repr(manager)
        assert "ExchangeManager" in repr_str
        assert "binance" in repr_str


# ============================================
# Integration Tests
# ============================================

class TestExchangeIntegration:
    """Integration tests for the exchange system"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test complete lifecycle: create, initialize, use, shutdown"""
        # Create manager
        manager = ExchangeManager()

        # Initialize all exchanges
        await manager.initialize_all()

        # Get an exchange
        exchange = manager.get_exchange("binance")

        # Use the exchange
        result = await exchange.get_ohlc("BTCUSDT", "1h", limit=10)
        assert isinstance(result, list)

        # Check health
        is_healthy = await exchange.health_check()
        assert isinstance(is_healthy, bool)

        # Shutdown all
        await manager.shutdown_all()

    def test_multiple_managers_create_separate_instances(self):
        """Verify creating multiple managers works independently"""
        manager1 = ExchangeManager()
        manager2 = ExchangeManager()

        # They should have their own exchange instances
        binance1 = manager1.get_exchange("binance")
        binance2 = manager2.get_exchange("binance")

        # Different instances (unless using singleton pattern)
        # Since we're not using singleton by default, they should be different
        assert binance1 is not binance2
