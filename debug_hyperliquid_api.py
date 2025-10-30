"""
Debug script to see raw Hyperliquid API responses
"""

import asyncio
import aiohttp
import json


async def test_raw_api():
    """Test raw API responses to understand the structure"""

    BASE_URL = "https://api.hyperliquid.xyz/info"

    async with aiohttp.ClientSession() as session:

        # Test 1: Meta and Asset Contexts (for OI)
        print("=" * 60)
        print("TEST 1: metaAndAssetCtxs (Open Interest)")
        print("=" * 60)
        payload = {"type": "metaAndAssetCtxs"}
        async with session.post(BASE_URL, json=payload) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Response type: {type(data)}")
            print(f"Response length: {len(data) if isinstance(data, list) else 'N/A'}")

            print("\n--- Element [0] (Meta) ---")
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                print(f"Keys: {list(first.keys())}")

                # Check universe
                if "universe" in first:
                    print(f"\nUniverse length: {len(first['universe'])}")
                    print(f"First 3 universe items:")
                    for item in first['universe'][:3]:
                        print(f"  {item}")

            print("\n--- Element [1] (Asset Contexts) ---")
            if isinstance(data, list) and len(data) > 1:
                second = data[1]
                print(f"Type: {type(second)}")
                if isinstance(second, list):
                    print(f"Length: {len(second)}")
                    print(f"\nFirst 3 assetCtx items:")
                    for item in second[:3]:
                        print(f"  {json.dumps(item, indent=2)}")
                else:
                    print(f"Structure: {json.dumps(second, indent=2)[:500]}")
        print()

        # Test 2: Funding History (with startTime)
        print("=" * 60)
        print("TEST 2: fundingHistory (with startTime)")
        print("=" * 60)
        payload = {"type": "fundingHistory", "coin": "BTC", "startTime": 1700000000000}
        async with session.post(BASE_URL, json=payload) as resp:
            print(f"Status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                print(f"Response type: {type(data)}")
                print(f"Response length: {len(data) if isinstance(data, list) else 'N/A'}")
                if isinstance(data, list) and len(data) > 0:
                    print(f"\nLast 3 items (most recent):")
                    for item in data[-3:]:
                        print(f"  {json.dumps(item, indent=2)}")
            else:
                text = await resp.text()
                print(f"Error: {text}")
        print()

        # Test 3: Predicted Fundings
        print("=" * 60)
        print("TEST 3: predictedFundings")
        print("=" * 60)
        payload = {"type": "predictedFundings"}
        async with session.post(BASE_URL, json=payload) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Response type: {type(data)}")
            if isinstance(data, list):
                print(f"Response length: {len(data)}")
                if len(data) > 0:
                    print(f"\nFirst item (full structure):")
                    print(f"  Coin: {data[0][0]}")
                    print(f"  Exchanges data:")
                    for exchange_data in data[0][1]:
                        exchange_name = exchange_data[0]
                        funding_info = exchange_data[1]
                        print(f"    {exchange_name}: {json.dumps(funding_info, indent=6)}")

                    # Find BTC
                    print(f"\nBTC data:")
                    for item in data:
                        if item[0] == "BTC":
                            for ex_data in item[1]:
                                if ex_data[0] == "HlPerp":
                                    print(f"  Hyperliquid funding for BTC: {json.dumps(ex_data[1], indent=4)}")
            else:
                print(f"Response: {json.dumps(data, indent=2)}")
        print()


if __name__ == "__main__":
    asyncio.run(test_raw_api())
