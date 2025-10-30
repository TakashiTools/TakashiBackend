"""
Core Package

Contains the exchange-agnostic core logic including:
- ExchangeInterface: Abstract base class defining the contract for all exchanges
- ExchangeManager: Central coordinator that manages multiple exchange connectors
- Schemas: Pydantic models for normalized data structures (OHLC, OI, Funding, etc.)

This layer ensures all exchanges follow the same interface, making the system modular and scalable.
"""
