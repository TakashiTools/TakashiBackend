#!/usr/bin/env python3
"""
Quick test to verify Hyperliquid symbol conversion is working
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exchanges.hyperliquid.api_client import HyperliquidAPIClient
from exchanges.hyperliquid.ws_client import HyperliquidWSClient


async def test_symbol_conversion():
    """Test that symbol conversion works correctly"""
    
    print("🧪 Testing Hyperliquid Symbol Conversion")
    print("=" * 50)
    
    # Test API client symbol conversion
    api_client = HyperliquidAPIClient()
    
    test_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BTC", "ETH"]
    
    print("\n📊 API Client Symbol Conversion:")
    for symbol in test_symbols:
        coin_symbol = api_client._extract_coin_symbol(symbol)
        print(f"  {symbol:10} -> {coin_symbol}")
    
    # Test WebSocket client symbol conversion
    ws_client = HyperliquidWSClient()
    
    print("\n🌐 WebSocket Client Symbol Conversion:")
    for symbol in test_symbols:
        coin_symbol = ws_client._extract_coin_symbol(symbol)
        print(f"  {symbol:10} -> {coin_symbol}")
    
    print("\n✅ Symbol conversion test completed!")


async def test_hyperliquid_api():
    """Test Hyperliquid API with correct symbols"""
    
    print("\n🔌 Testing Hyperliquid API with Correct Symbols")
    print("=" * 50)
    
    async with HyperliquidAPIClient() as client:
        
        # Test Open Interest
        print("\n📈 Testing Open Interest:")
        try:
            oi = await client.get_open_interest("BTCUSDT")
            if oi:
                print(f"  ✅ BTC Open Interest: {oi.open_interest:,.2f} BTC")
                print(f"  📊 Value: ${oi.open_interest_value:,.2f}")
            else:
                print("  ❌ No open interest data")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Test Funding Rate
        print("\n💰 Testing Funding Rate:")
        try:
            rates = await client.get_funding_rate("BTCUSDT", limit=5)
            if rates:
                print(f"  ✅ Found {len(rates)} funding rates")
                latest = rates[-1]
                print(f"  📊 Latest rate: {latest.funding_rate * 100:.6f}%")
                print(f"  🕐 Time: {latest.funding_time}")
            else:
                print("  ❌ No funding rate data")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Test Historical OHLC
        print("\n📊 Testing Historical OHLC:")
        try:
            from core.utils.time import current_utc_timestamp
            end_time = current_utc_timestamp(milliseconds=True)
            start_time = end_time - (60 * 60 * 1000)  # 1 hour ago
            
            ohlc = await client.get_historical_ohlc("BTCUSDT", "1m", start_time, end_time)
            if ohlc:
                print(f"  ✅ Found {len(ohlc)} candles")
                latest = ohlc[-1]
                print(f"  📊 Latest candle: O={latest.open} H={latest.high} L={latest.low} C={latest.close}")
                print(f"  📈 Volume: {latest.volume}")
            else:
                print("  ❌ No OHLC data")
        except Exception as e:
            print(f"  ❌ Error: {e}")


async def main():
    """Main test function"""
    
    print("🚀 Hyperliquid Integration Test")
    print("=" * 60)
    
    # Test symbol conversion
    await test_symbol_conversion()
    
    # Test API calls
    await test_hyperliquid_api()
    
    print("\n🎉 All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
