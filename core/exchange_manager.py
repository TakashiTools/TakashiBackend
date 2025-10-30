"""
Exchange Manager — Central Registry for Exchange Connectors

This module provides a centralized manager for all exchange connectors.
The ExchangeManager acts as a registry and factory for exchange instances.

Design Benefits:
    - Single source of truth for available exchanges
    - Lazy loading of exchanges (initialize on first use)
    - Easy to add new exchanges without modifying API routes
    - Centralized lifecycle management (initialize/shutdown)
    - Type-safe access to exchanges

Architecture Pattern:
    This is a Registry/Factory pattern where:
    - ExchangeManager maintains a registry of exchange instances
    - API routes request exchanges by name
    - Manager returns the appropriate exchange instance
    - All exchanges conform to ExchangeInterface

Example Usage:
    # In app/main.py (FastAPI app)
    manager = ExchangeManager()
    await manager.initialize_all()

    @app.get("/{exchange}/ohlc/{symbol}/{interval}")
    async def get_ohlc(exchange: str, symbol: str, interval: str):
        ex = manager.get_exchange(exchange)  # Returns BinanceExchange, BybitExchange, etc.
        data = await ex.get_ohlc(symbol, interval)
        return data

    # Adding a new exchange is trivial:
    # 1. Create new exchange class (e.g., BybitExchange)
    # 2. Register it in ExchangeManager.__init__
    # That's it! No changes to API routes needed.
"""

from typing import Dict, List, Optional
from core.exchange_interface import ExchangeInterface
from core.logging import logger


class ExchangeManager:
    """
    Central Manager for Exchange Connectors

    This class maintains a registry of all available exchange connectors and
    provides methods to retrieve, initialize, and manage them.

    Attributes:
        exchanges: Dictionary mapping exchange names to exchange instances
                  Example: {"binance": BinanceExchange(), "bybit": BybitExchange()}

    Example:
        >>> manager = ExchangeManager()
        >>> await manager.initialize_all()
        >>>
        >>> # Get an exchange
        >>> binance = manager.get_exchange("binance")
        >>> ohlc = await binance.get_ohlc("BTCUSDT", "1h")
        >>>
        >>> # List available exchanges
        >>> print(manager.list_exchanges())
        ['binance', 'bybit', 'okx']
        >>>
        >>> # Shutdown all exchanges
        >>> await manager.shutdown_all()
    """

    def __init__(self):
        """
        Initialize the Exchange Manager and register all exchanges.

        This constructor creates instances of all available exchange connectors
        and stores them in the registry.

        Note:
            Exchange instances are created but not initialized here.
            Call initialize_all() or initialize_exchange() to set up connections.
        """
        # Import here to avoid circular imports
        # Each exchange module imports from core, so we can't import at module level
        from exchanges.binance import BinanceExchange
        from exchanges.hyperliquid import HyperliquidExchange
        from exchanges.bybit import BybitExchange

        # Registry of exchange instances
        self.exchanges: Dict[str, ExchangeInterface] = {
            "binance": BinanceExchange(),
            "hyperliquid": HyperliquidExchange(),
            "bybit": BybitExchange(),
            # Future exchanges will be added here:
            # "okx": OKXExchange(),
            # "kraken": KrakenExchange(),
        }

        logger.info(f"ExchangeManager initialized with {len(self.exchanges)} exchange(s): {', '.join(self.exchanges.keys())}")

    # ============================================
    # Exchange Retrieval Methods
    # ============================================

    def get_exchange(self, name: str) -> ExchangeInterface:
        """
        Get an exchange connector by name.

        Args:
            name: Exchange name in lowercase (e.g., "binance", "bybit")

        Returns:
            ExchangeInterface: The requested exchange instance

        Raises:
            ValueError: If the exchange is not supported

        Example:
            >>> exchange = manager.get_exchange("binance")
            >>> ohlc = await exchange.get_ohlc("BTCUSDT", "1h")
        """
        # Normalize to lowercase
        name = name.lower()

        if name not in self.exchanges:
            available = ", ".join(self.exchanges.keys())
            logger.error(f"Exchange '{name}' not found. Available: {available}")
            raise ValueError(
                f"Exchange '{name}' is not supported. "
                f"Available exchanges: {available}"
            )

        logger.debug(f"Retrieved exchange: {name}")
        return self.exchanges[name]

    def has_exchange(self, name: str) -> bool:
        """
        Check if an exchange is supported.

        Args:
            name: Exchange name (case-insensitive)

        Returns:
            bool: True if exchange is supported, False otherwise

        Example:
            >>> if manager.has_exchange("binance"):
            ...     exchange = manager.get_exchange("binance")
        """
        return name.lower() in self.exchanges

    def list_exchanges(self) -> List[str]:
        """
        Get a list of all supported exchange names.

        Returns:
            List[str]: List of exchange names

        Example:
            >>> exchanges = manager.list_exchanges()
            >>> print(f"Supported: {', '.join(exchanges)}")
            Supported: binance, bybit, okx
        """
        return list(self.exchanges.keys())

    # ============================================
    # Lifecycle Management
    # ============================================

    async def initialize_all(self) -> None:
        """
        Initialize all registered exchanges.

        This method calls the initialize() method on each exchange, allowing
        them to set up connections, sessions, and resources.

        Raises:
            Exception: If any exchange fails to initialize

        Example:
            >>> manager = ExchangeManager()
            >>> await manager.initialize_all()
            >>> # All exchanges are now ready to use
        """
        logger.info("Initializing all exchanges...")

        for name, exchange in self.exchanges.items():
            try:
                logger.debug(f"Initializing {name}...")
                await exchange.initialize()
                logger.info(f"✓ {name.capitalize()} initialized successfully")
            except Exception as e:
                logger.error(f"✗ Failed to initialize {name}: {e}")
                # Continue initializing other exchanges even if one fails
                # You could also raise here if you want fail-fast behavior

        logger.info("All exchanges initialized")

    async def initialize_exchange(self, name: str) -> None:
        """
        Initialize a specific exchange.

        Args:
            name: Exchange name to initialize

        Raises:
            ValueError: If exchange is not found
            Exception: If initialization fails

        Example:
            >>> await manager.initialize_exchange("binance")
        """
        exchange = self.get_exchange(name)
        logger.info(f"Initializing {name}...")
        await exchange.initialize()
        logger.info(f"{name.capitalize()} initialized successfully")

    async def shutdown_all(self) -> None:
        """
        Shutdown all exchanges gracefully.

        This method calls the shutdown() method on each exchange, allowing
        them to close connections and release resources.

        This should be called when the application is shutting down.

        Example:
            >>> # In FastAPI lifespan or shutdown event
            >>> @app.on_event("shutdown")
            >>> async def shutdown():
            ...     await manager.shutdown_all()
        """
        logger.info("Shutting down all exchanges...")

        for name, exchange in self.exchanges.items():
            try:
                logger.debug(f"Shutting down {name}...")
                await exchange.shutdown()
                logger.info(f"✓ {name.capitalize()} shut down successfully")
            except Exception as e:
                logger.error(f"✗ Error shutting down {name}: {e}")
                # Continue shutting down other exchanges

        logger.info("All exchanges shut down")

    async def shutdown_exchange(self, name: str) -> None:
        """
        Shutdown a specific exchange.

        Args:
            name: Exchange name to shutdown

        Raises:
            ValueError: If exchange is not found

        Example:
            >>> await manager.shutdown_exchange("binance")
        """
        exchange = self.get_exchange(name)
        logger.info(f"Shutting down {name}...")
        await exchange.shutdown()
        logger.info(f"{name.capitalize()} shut down successfully")

    # ============================================
    # Health Check Methods
    # ============================================

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Check health status of all exchanges.

        Returns:
            Dict[str, bool]: Dictionary mapping exchange names to health status
                            True = healthy, False = unreachable

        Example:
            >>> health = await manager.health_check_all()
            >>> for exchange, is_healthy in health.items():
            ...     status = "✓ OK" if is_healthy else "✗ Down"
            ...     print(f"{exchange}: {status}")
            binance: ✓ OK
            bybit: ✓ OK
        """
        logger.debug("Running health check on all exchanges...")

        health_status = {}
        for name, exchange in self.exchanges.items():
            try:
                is_healthy = await exchange.health_check()
                health_status[name] = is_healthy
                status = "healthy" if is_healthy else "unhealthy"
                logger.debug(f"{name}: {status}")
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                health_status[name] = False

        return health_status

    async def health_check_exchange(self, name: str) -> bool:
        """
        Check health status of a specific exchange.

        Args:
            name: Exchange name to check

        Returns:
            bool: True if exchange is healthy, False otherwise

        Raises:
            ValueError: If exchange is not found

        Example:
            >>> if await manager.health_check_exchange("binance"):
            ...     print("Binance is operational")
        """
        exchange = self.get_exchange(name)
        return await exchange.health_check()

    # ============================================
    # Capability Queries
    # ============================================

    def get_exchanges_with_feature(self, feature: str) -> List[str]:
        """
        Get list of exchanges that support a specific feature.

        Args:
            feature: Feature name (e.g., "liquidations", "funding_rate")

        Returns:
            List[str]: List of exchange names supporting the feature

        Example:
            >>> # Find which exchanges support liquidation streams
            >>> exchanges = manager.get_exchanges_with_feature("liquidations")
            >>> print(f"Liquidations supported by: {', '.join(exchanges)}")
            Liquidations supported by: binance, bybit
        """
        supporting_exchanges = [
            name for name, exchange in self.exchanges.items()
            if exchange.supports(feature)
        ]

        logger.debug(f"Feature '{feature}' supported by: {', '.join(supporting_exchanges) or 'none'}")
        return supporting_exchanges

    def get_exchange_capabilities(self, name: str) -> Dict[str, bool]:
        """
        Get the capabilities of a specific exchange.

        Args:
            name: Exchange name

        Returns:
            Dict[str, bool]: Dictionary of features and their support status

        Raises:
            ValueError: If exchange is not found

        Example:
            >>> caps = manager.get_exchange_capabilities("binance")
            >>> print(caps)
            {'ohlc': True, 'funding_rate': True, 'liquidations': True, ...}
        """
        exchange = self.get_exchange(name)
        return exchange.capabilities.copy()

    # ============================================
    # Utility Methods
    # ============================================

    def __repr__(self) -> str:
        """String representation of the manager."""
        return f"<ExchangeManager(exchanges={list(self.exchanges.keys())})>"

    def __len__(self) -> int:
        """Number of registered exchanges."""
        return len(self.exchanges)


# ============================================
# Global Manager Instance (Optional)
# ============================================

# You can create a singleton instance for use throughout the application
# This is optional; you may prefer to create the manager in main.py instead
_manager: Optional[ExchangeManager] = None


def get_manager() -> ExchangeManager:
    """
    Get the global ExchangeManager instance (singleton pattern).

    Returns:
        ExchangeManager: The global manager instance

    Example:
        >>> from core.exchange_manager import get_manager
        >>> manager = get_manager()
        >>> binance = manager.get_exchange("binance")

    Notes:
        - This creates a singleton instance on first call
        - Subsequent calls return the same instance
        - Alternative: Create manager in main.py and pass it around
    """
    global _manager
    if _manager is None:
        _manager = ExchangeManager()
        logger.debug("Created global ExchangeManager instance")
    return _manager
