"""
Storage Package

Handles data persistence and caching strategies.

Current implementation:
- In-memory caching for latest market data snapshots

Future expansion:
- Redis integration for distributed caching
- TimescaleDB/PostgreSQL for historical data storage
- Database models and migrations

The modular design allows upgrading storage without breaking the core architecture.
"""
