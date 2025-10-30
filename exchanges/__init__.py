"""
Exchange Connectors Package

This package contains individual exchange connector modules.
Each exchange (Binance, Bybit, OKX, etc.) has its own subfolder with:
- api_client.py: REST API logic
- ws_client.py: WebSocket streaming logic
- exchange.py: Main exchange class implementing ExchangeInterface

The modular design allows adding new exchanges without modifying existing code.
"""
