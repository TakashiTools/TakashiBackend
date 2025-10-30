"""
Manual Test Script for Bybit Exchange Connector

This script tests the Bybit exchange connector directly (not through API endpoints).
It verifies both REST API and WebSocket functionality.

Usage:
    # Test REST API endpoints
    python test_bybit.py rest

    # Test WebSocket streams
    python test_bybit.py ws

    # Test everything
    python test_bybit.py all

Requirements:
    - Internet connection (connects to live Bybit API)
    - No API key needed (public endpoints only)
"""

import asyncio
import sys
from datetime import datetime, timezone
from core.utils.time import current_utc_timestamp


# ============================================
# REST API Tests
# ============================================

async def test_rest_api():
    """Test Bybit REST API endpoints"""
    from exchanges.bybit.api_client import BybitAPIClient

    print("=" * 60)
    print("TESTING BYBIT REST API")
    print("=" * 60)
    print()

    async with BybitAPIClient() as client:

        # Test 1: Get Server Time (Health Check)
        print("🕐 Test 1: Get Server Time")
        print("-" * 60)
        try:
            server_time = await client.get_server_time()
            if server_time:
                print(f"✓ Success!")
                print(f"  Server Time: {datetime.fromtimestamp(server_time/1000, tz=timezone.utc)}")
            else:
                print("✗ Failed: No data returned")
        except Exception as e:
            print(f"✗ Error: {e}")
        print()

        # Test 2: Get Historical OHLC
        print("📈 Test 2: Get Historical OHLC for BTCUSDT (1h interval)")
        print("-" * 60)
        try:
            ohlc_data = await client.get_historical_ohlc("BTCUSDT", "1h", limit=5)
            if ohlc_data:
                print(f"✓ Success! Fetched {len(ohlc_data)} candles")
                # Show last 3 candles
                for i, candle in enumerate(ohlc_data[-3:], 1):
                    print(f"  Candle {i}:")
                    print(f"    Time: {candle.timestamp}")
                    print(f"    O: ${candle.open:,.2f}  H: ${candle.high:,.2f}")
                    print(f"    L: ${candle.low:,.2f}   C: ${candle.close:,.2f}")
                    print(f"    Volume: {candle.volume:.4f} BTC")
            else:
                print("✗ Failed: No data returned")
        except Exception as e:
            print(f"✗ Error: {e}")
        print()

        # Test 3: Get Open Interest
        print("📊 Test 3: Get Open Interest for BTCUSDT")
        print("-" * 60)
        try:
            oi = await client.get_open_interest("BTCUSDT")
            if oi:
                print(f"✓ Success!")
                print(f"  Exchange: {oi.exchange}")
                print(f"  Symbol: {oi.symbol}")
                print(f"  Open Interest: {oi.open_interest:,.2f} BTC")
                if oi.open_interest_value:
                    print(f"  OI Value: ${oi.open_interest_value:,.2f}")
                print(f"  Timestamp: {oi.timestamp}")
            else:
                print("✗ Failed: No data returned")
        except Exception as e:
            print(f"✗ Error: {e}")
        print()

        # Test 4: Get Funding Rate History
        print("💰 Test 4: Get Funding Rate History for BTCUSDT")
        print("-" * 60)
        try:
            rates = await client.get_funding_rate("BTCUSDT", limit=3)
            if rates:
                print(f"✓ Success! Fetched {len(rates)} funding rates")
                for i, rate in enumerate(rates[-3:], 1):
                    print(f"  Rate {i}:")
                    print(f"    Funding Rate: {rate.funding_rate * 100:.4f}%")
                    print(f"    Time: {rate.funding_time}")
            else:
                print("✗ Failed: No data returned")
        except Exception as e:
            print(f"✗ Error: {e}")
        print()

    print("=" * 60)
    print("REST API TESTS COMPLETED")
    print("=" * 60)
    print()


# ============================================
# WebSocket Tests
# ============================================

async def test_websocket_ohlc():
    """Test Bybit WebSocket OHLC stream"""
    from exchanges.bybit.ws_client import BybitWSClient

    print("=" * 60)
    print("TESTING BYBIT WEBSOCKET - OHLC STREAM")
    print("=" * 60)
    print()

    print("📊 Subscribing to BTCUSDT 1m candles...")
    print("   Waiting for 5 candle updates...")
    print("-" * 60)

    client = BybitWSClient()

    try:
        count = 0
        async for candle in client.stream_ohlc("BTCUSDT", "1m"):
            count += 1
            print(f"\n✓ Candle Update {count}:")
            print(f"  Time: {candle.timestamp}")
            print(f"  Open: ${candle.open:,.2f}")
            print(f"  High: ${candle.high:,.2f}")
            print(f"  Low: ${candle.low:,.2f}")
            print(f"  Close: ${candle.close:,.2f}")
            print(f"  Volume: {candle.volume:.4f} BTC")
            print(f"  Closed: {candle.is_closed}")

            if count >= 5:
                print("\n✓ Received 5 updates, stopping...")
                break

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")

    print()
    print("=" * 60)
    print("OHLC STREAM TEST COMPLETED")
    print("=" * 60)
    print()


async def test_websocket_trades():
    """Test Bybit WebSocket trades stream"""
    from exchanges.bybit.ws_client import BybitWSClient

    print("=" * 60)
    print("TESTING BYBIT WEBSOCKET - TRADES STREAM")
    print("=" * 60)
    print()

    print("💹 Subscribing to BTCUSDT trades...")
    print("   Waiting for 10 trades...")
    print("-" * 60)

    client = BybitWSClient()

    try:
        count = 0
        async for trade in client.stream_trades("BTCUSDT"):
            count += 1
            print(f"\n✓ Trade {count}:")
            print(f"  Time: {trade.timestamp}")
            print(f"  Side: {trade.side.upper()}")
            print(f"  Price: ${trade.price:,.2f}")
            print(f"  Quantity: {trade.quantity:.4f} BTC")
            print(f"  Value: ${trade.value:,.2f}")
            print(f"  Buyer was maker: {trade.is_buyer_maker}")

            if count >= 10:
                print("\n✓ Received 10 trades, stopping...")
                break

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")

    print()
    print("=" * 60)
    print("TRADES STREAM TEST COMPLETED")
    print("=" * 60)
    print()


async def test_websocket_liquidations():
    """Test Bybit WebSocket liquidations stream"""
    from exchanges.bybit.ws_client import BybitWSClient

    print("=" * 60)
    print("TESTING BYBIT WEBSOCKET - LIQUIDATIONS STREAM")
    print("=" * 60)
    print()

    print("💥 Subscribing to BTCUSDT liquidations...")
    print("   Waiting for 5 liquidations...")
    print("-" * 60)

    client = BybitWSClient()

    try:
        count = 0
        async for liquidation in client.stream_liquidations("BTCUSDT"):
            count += 1
            print(f"\n✓ Liquidation {count}:")
            print(f"  Time: {liquidation.timestamp}")
            print(f"  Side: {liquidation.side.upper()}")
            print(f"  Price: ${liquidation.price:,.2f}")
            print(f"  Quantity: {liquidation.quantity:.4f} BTC")
            print(f"  Value: ${liquidation.value:,.2f}")

            if count >= 5:
                print("\n✓ Received 5 liquidations, stopping...")
                break

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")

    print()
    print("=" * 60)
    print("LIQUIDATIONS STREAM TEST COMPLETED")
    print("=" * 60)
    print()


async def test_websocket_all():
    """Test all WebSocket streams"""
    print("\n🚀 Testing all WebSocket streams...\n")

    print("1️⃣  Testing OHLC Stream")
    await test_websocket_ohlc()

    await asyncio.sleep(2)

    print("\n2️⃣  Testing Trades Stream")
    await test_websocket_trades()

    await asyncio.sleep(2)

    print("\n3️⃣  Testing Liquidations Stream")
    await test_websocket_liquidations()


# ============================================
# Exchange Interface Tests
# ============================================

async def test_exchange_interface():
    """Test the BybitExchange class (full integration)"""
    from exchanges.bybit import BybitExchange

    print("=" * 60)
    print("TESTING BYBIT EXCHANGE INTERFACE")
    print("=" * 60)
    print()

    exchange = BybitExchange()

    # Initialize
    print("🔧 Initializing exchange...")
    await exchange.initialize()
    print("✓ Exchange initialized\n")

    # Test capabilities
    print("📋 Exchange Capabilities:")
    print("-" * 60)
    for feature, supported in exchange.capabilities.items():
        status = "✓ Supported" if supported else "✗ Not supported"
        print(f"  {feature}: {status}")
    print()

    # Test health check
    print("🏥 Health Check:")
    print("-" * 60)
    is_healthy = await exchange.health_check()
    if is_healthy:
        print("  ✓ Bybit API is healthy")
    else:
        print("  ✗ Bybit API is not responding")
    print()

    # Test REST methods
    print("📊 Testing get_ohlc()...")
    print("-" * 60)
    try:
        ohlc = await exchange.get_ohlc("BTCUSDT", "1h", limit=5)
        if ohlc:
            print(f"  ✓ OHLC: {len(ohlc)} candles fetched")
            print(f"  Latest close: ${ohlc[-1].close:,.2f}")
        else:
            print("  ✗ No data")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    print()

    print("📊 Testing get_open_interest()...")
    print("-" * 60)
    try:
        oi = await exchange.get_open_interest("BTCUSDT")
        if oi:
            print(f"  ✓ OI: {oi.open_interest:,.2f} BTC")
        else:
            print("  ✗ No data")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    print()

    print("💰 Testing get_funding_rate()...")
    print("-" * 60)
    try:
        fr = await exchange.get_funding_rate("BTCUSDT")
        if fr:
            print(f"  ✓ Rate: {fr.funding_rate * 100:.4f}%")
        else:
            print("  ✗ No data")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    print()

    # Shutdown
    print("🔌 Shutting down exchange...")
    await exchange.shutdown()
    print("✓ Exchange shut down\n")

    print("=" * 60)
    print("EXCHANGE INTERFACE TEST COMPLETED")
    print("=" * 60)
    print()


async def test_exchange_manager():
    """Test accessing Bybit through ExchangeManager"""
    from core.exchange_manager import ExchangeManager

    print("=" * 60)
    print("TESTING EXCHANGE MANAGER INTEGRATION")
    print("=" * 60)
    print()

    manager = ExchangeManager()

    print("📋 Available Exchanges:")
    print("-" * 60)
    exchanges = manager.list_exchanges()
    for ex in exchanges:
        print(f"  • {ex}")
    print()

    print("🔍 Getting Bybit exchange...")
    print("-" * 60)
    try:
        bybit = manager.get_exchange("bybit")
        print(f"  ✓ Got exchange: {bybit.name}")
        print(f"  ✓ Capabilities: {bybit.capabilities}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    print()

    print("🏥 Health check all exchanges...")
    print("-" * 60)
    await manager.initialize_all()
    health = await manager.health_check_all()
    for ex, is_healthy in health.items():
        status = "✓ Healthy" if is_healthy else "✗ Unhealthy"
        print(f"  {ex}: {status}")
    await manager.shutdown_all()
    print()

    print("=" * 60)
    print("EXCHANGE MANAGER TEST COMPLETED")
    print("=" * 60)
    print()


# ============================================
# Main Entry Point
# ============================================

async def run_all_tests():
    """Run all tests"""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║           BYBIT EXCHANGE CONNECTOR TEST SUITE             ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()

    # Test 1: REST API
    await test_rest_api()
    await asyncio.sleep(1)

    # Test 2: Exchange Interface
    await test_exchange_interface()
    await asyncio.sleep(1)

    # Test 3: Exchange Manager
    await test_exchange_manager()
    await asyncio.sleep(1)

    # Test 4: WebSocket (only one stream to avoid too long test)
    print("\n🌐 WebSocket Stream Test")
    print("   (Testing only OHLC stream - use 'ws' mode for full WS tests)")
    print()
    await test_websocket_ohlc()

    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                  ALL TESTS COMPLETED                      ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()


def print_usage():
    """Print usage instructions"""
    print()
    print("Usage: python test_bybit.py [mode]")
    print()
    print("Modes:")
    print("  rest       - Test REST API endpoints only")
    print("  ws         - Test WebSocket streams only")
    print("  ws-ohlc    - Test WebSocket OHLC stream only")
    print("  ws-trades  - Test WebSocket trades stream only")
    print("  ws-liq     - Test WebSocket liquidations stream only")
    print("  interface  - Test Exchange Interface")
    print("  manager    - Test Exchange Manager integration")
    print("  all        - Run all tests (default)")
    print()
    print("Examples:")
    print("  python test_bybit.py rest")
    print("  python test_bybit.py ws-ohlc")
    print("  python test_bybit.py all")
    print()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "help" or mode == "-h" or mode == "--help":
        print_usage()
        sys.exit(0)

    try:
        if mode == "rest":
            asyncio.run(test_rest_api())
        elif mode == "ws":
            asyncio.run(test_websocket_all())
        elif mode == "ws-ohlc":
            asyncio.run(test_websocket_ohlc())
        elif mode == "ws-trades":
            asyncio.run(test_websocket_trades())
        elif mode == "ws-liq":
            asyncio.run(test_websocket_liquidations())
        elif mode == "interface":
            asyncio.run(test_exchange_interface())
        elif mode == "manager":
            asyncio.run(test_exchange_manager())
        elif mode == "all":
            asyncio.run(run_all_tests())
        else:
            print(f"❌ Unknown mode: {mode}")
            print_usage()
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
