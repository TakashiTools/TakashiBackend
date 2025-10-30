"""
Comprehensive Exchange Test Suite

This script tests all registered exchanges comprehensively:
- REST API endpoints (OHLC, Open Interest, Funding Rates)
- WebSocket streams (OHLC, Trades, Liquidations)
- Exchange Manager integration
- Health checks

Generates detailed test results in JSON format for analysis.

Usage:
    python test_all_exchanges.py
    python test_all_exchanges.py --output results.json
    python test_all_exchanges.py --exchanges binance,bybit
    python test_all_exchanges.py --skip-ws
"""

import asyncio
import json
import sys
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pathlib import Path

from core.exchange_manager import ExchangeManager
from core.logging import get_logger


class ExchangeTestSuite:
    """
    Comprehensive test suite for all registered exchanges.
    
    Tests:
    - REST API endpoints
    - WebSocket streams  
    - Exchange Manager integration
    - Health checks
    """
    
    def __init__(self, output_file: str = "test_results.json"):
        self.output_file = output_file
        self.logger = get_logger(__name__)
        self.results = {
            "test_run": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_exchanges": 0,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0
            },
            "exchanges": {}
        }
        
    async def run_all_tests(self, exchanges: Optional[List[str]] = None, skip_ws: bool = False):
        """
        Run comprehensive tests for all or specified exchanges.
        
        Args:
            exchanges: List of exchange names to test (None = all)
            skip_ws: Skip WebSocket tests
        """
        self.logger.info("🚀 Starting Comprehensive Exchange Test Suite")
        self.logger.info("=" * 80)
        
        manager = ExchangeManager()
        available_exchanges = manager.list_exchanges()
        
        if exchanges:
            test_exchanges = [ex for ex in exchanges if ex in available_exchanges]
            if not test_exchanges:
                self.logger.error(f"No valid exchanges found in: {exchanges}")
                return
        else:
            test_exchanges = available_exchanges
            
        self.results["test_run"]["total_exchanges"] = len(test_exchanges)
        
        print(f"\n📋 Testing {len(test_exchanges)} exchanges: {', '.join(test_exchanges)}")
        print("=" * 80)
        
        # Initialize all exchanges
        await manager.initialize_all()
        
        for exchange_name in test_exchanges:
            await self.test_exchange(manager, exchange_name, skip_ws)
            
        # Shutdown all exchanges
        await manager.shutdown_all()
        
        # Generate summary and save results
        self.generate_summary()
        self.save_results()
        
    async def test_exchange(self, manager: ExchangeManager, exchange_name: str, skip_ws: bool):
        """
        Test a single exchange comprehensively.
        
        Args:
            manager: ExchangeManager instance
            exchange_name: Name of exchange to test
            skip_ws: Skip WebSocket tests
        """
        self.logger.info(f"\n🔍 Testing {exchange_name.upper()} Exchange")
        self.logger.info("-" * 60)
        
        exchange_results = {
            "name": exchange_name,
            "capabilities": {},
            "health_check": {"status": "unknown", "error": None},
            "rest_api": {},
            "websocket": {},
            "summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0
            }
        }
        
        try:
            exchange = manager.get_exchange(exchange_name)
            exchange_results["capabilities"] = exchange.capabilities.copy()
            
            # Test 1: Health Check
            await self.test_health_check(exchange, exchange_results)
            
            # Test 2: REST API Endpoints
            await self.test_rest_endpoints(exchange, exchange_results)
            
            # Test 3: WebSocket Streams (if not skipped)
            if not skip_ws:
                await self.test_websocket_streams(exchange, exchange_results)
            else:
                exchange_results["websocket"]["skipped"] = "WebSocket tests disabled"
                exchange_results["summary"]["skipped"] += 1
                
        except Exception as e:
            self.logger.error(f"❌ Failed to test {exchange_name}: {e}")
            exchange_results["error"] = str(e)
            
        self.results["exchanges"][exchange_name] = exchange_results
        
    async def test_health_check(self, exchange, exchange_results: Dict):
        """Test exchange health check."""
        test_name = "health_check"
        self.logger.info(f"  🏥 Testing {test_name}...")
        
        try:
            is_healthy = await exchange.health_check()
            exchange_results["health_check"]["status"] = "healthy" if is_healthy else "unhealthy"
            exchange_results["summary"]["passed"] += 1
            self.logger.info(f"    ✅ {test_name}: {'Healthy' if is_healthy else 'Unhealthy'}")
        except Exception as e:
            exchange_results["health_check"]["status"] = "error"
            exchange_results["health_check"]["error"] = str(e)
            exchange_results["summary"]["failed"] += 1
            self.logger.error(f"    ❌ {test_name}: {e}")
        finally:
            exchange_results["summary"]["total_tests"] += 1
            
    async def test_rest_endpoints(self, exchange, exchange_results: Dict):
        """Test all REST API endpoints."""
        rest_tests = [
            ("get_ohlc", "OHLC Data"),
            ("get_open_interest", "Open Interest"),
            ("get_funding_rate", "Funding Rate")
        ]
        
        for method_name, display_name in rest_tests:
            if not exchange.supports(method_name.replace("get_", "")):
                exchange_results["rest_api"][method_name] = {"skipped": "Not supported"}
                exchange_results["summary"]["skipped"] += 1
                exchange_results["summary"]["total_tests"] += 1
                continue
                
            self.logger.info(f"  📊 Testing {display_name}...")
            
            try:
                if method_name == "get_ohlc":
                    result = await exchange.get_ohlc("BTCUSDT", "1h", limit=5)
                elif method_name == "get_open_interest":
                    result = await exchange.get_open_interest("BTCUSDT")
                elif method_name == "get_funding_rate":
                    result = await exchange.get_funding_rate("BTCUSDT")
                    
                if result:
                    if isinstance(result, list):
                        count = len(result)
                        exchange_results["rest_api"][method_name] = {
                            "status": "success",
                            "data_count": count,
                            "sample_data": result[0].dict() if result else None
                        }
                    else:
                        exchange_results["rest_api"][method_name] = {
                            "status": "success",
                            "data": result.dict()
                        }
                    exchange_results["summary"]["passed"] += 1
                    self.logger.info(f"    ✅ {display_name}: Success")
                else:
                    exchange_results["rest_api"][method_name] = {"status": "no_data"}
                    exchange_results["summary"]["failed"] += 1
                    self.logger.warning(f"    ⚠️  {display_name}: No data returned")
                    
            except Exception as e:
                exchange_results["rest_api"][method_name] = {
                    "status": "error",
                    "error": str(e)
                }
                exchange_results["summary"]["failed"] += 1
                self.logger.error(f"    ❌ {display_name}: {e}")
            finally:
                exchange_results["summary"]["total_tests"] += 1
                
    async def test_websocket_streams(self, exchange, exchange_results: Dict):
        """Test WebSocket streams with timeout."""
        ws_tests = [
            ("stream_ohlc", "OHLC Stream"),
            ("stream_large_trades", "Trades Stream"),
            ("stream_liquidations", "Liquidations Stream")
        ]
        
        for method_name, display_name in ws_tests:
            feature_name = method_name.replace("stream_", "")
            if not exchange.supports(feature_name):
                exchange_results["websocket"][method_name] = {"skipped": "Not supported"}
                exchange_results["summary"]["skipped"] += 1
                exchange_results["summary"]["total_tests"] += 1
                continue
                
            self.logger.info(f"  🌐 Testing {display_name}...")
            
            try:
                # Test WebSocket with timeout
                if method_name == "stream_ohlc":
                    stream = exchange.stream_ohlc("BTCUSDT", "1m")
                elif method_name == "stream_large_trades":
                    stream = exchange.stream_large_trades("BTCUSDT")
                elif method_name == "stream_liquidations":
                    stream = exchange.stream_liquidations("BTCUSDT")
                    
                # Wait for first message with timeout
                message_count = 0
                timeout_seconds = 10
                
                async def collect_messages():
                    nonlocal message_count
                    try:
                        async for message in stream:
                            message_count += 1
                            if message_count >= 3:  # Collect 3 messages then stop
                                break
                    except Exception as e:
                        raise e
                        
                try:
                    await asyncio.wait_for(collect_messages(), timeout=timeout_seconds)
                    exchange_results["websocket"][method_name] = {
                        "status": "success",
                        "messages_received": message_count,
                        "timeout_seconds": timeout_seconds
                    }
                    exchange_results["summary"]["passed"] += 1
                    self.logger.info(f"    ✅ {display_name}: {message_count} messages received")
                except asyncio.TimeoutError:
                    exchange_results["websocket"][method_name] = {
                        "status": "timeout",
                        "messages_received": message_count,
                        "timeout_seconds": timeout_seconds
                    }
                    exchange_results["summary"]["failed"] += 1
                    self.logger.warning(f"    ⏰ {display_name}: Timeout after {timeout_seconds}s")
                    
            except Exception as e:
                exchange_results["websocket"][method_name] = {
                    "status": "error",
                    "error": str(e)
                }
                exchange_results["summary"]["failed"] += 1
                self.logger.error(f"    ❌ {display_name}: {e}")
            finally:
                exchange_results["summary"]["total_tests"] += 1
                
    def generate_summary(self):
        """Generate test summary statistics."""
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        
        for exchange_name, exchange_data in self.results["exchanges"].items():
            summary = exchange_data.get("summary", {})
            total_tests += summary.get("total_tests", 0)
            passed_tests += summary.get("passed", 0)
            failed_tests += summary.get("failed", 0)
            skipped_tests += summary.get("skipped", 0)
            
        self.results["test_run"]["total_tests"] = total_tests
        self.results["test_run"]["passed_tests"] = passed_tests
        self.results["test_run"]["failed_tests"] = failed_tests
        self.results["test_run"]["skipped_tests"] = skipped_tests
        
        # Calculate success rate
        if total_tests > 0:
            success_rate = (passed_tests / total_tests) * 100
            self.results["test_run"]["success_rate"] = round(success_rate, 2)
        else:
            self.results["test_run"]["success_rate"] = 0
            
    def save_results(self):
        """Save test results to JSON file."""
        try:
            with open(self.output_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            self.logger.info(f"📄 Test results saved to: {self.output_file}")
        except Exception as e:
            self.logger.error(f"❌ Failed to save results: {e}")
            
    def print_summary(self):
        """Print test summary to console."""
        run_info = self.results["test_run"]
        
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        print(f"🕐 Test Run: {run_info['timestamp']}")
        print(f"🏢 Exchanges Tested: {run_info['total_exchanges']}")
        print(f"🧪 Total Tests: {run_info['total_tests']}")
        print(f"✅ Passed: {run_info['passed_tests']}")
        print(f"❌ Failed: {run_info['failed_tests']}")
        print(f"⏭️  Skipped: {run_info['skipped_tests']}")
        print(f"📈 Success Rate: {run_info['success_rate']}%")
        
        print("\n📋 Exchange Details:")
        print("-" * 80)
        
        for exchange_name, exchange_data in self.results["exchanges"].items():
            summary = exchange_data.get("summary", {})
            health = exchange_data.get("health_check", {}).get("status", "unknown")
            
            print(f"\n🔍 {exchange_name.upper()}:")
            print(f"  Health: {'✅' if health == 'healthy' else '❌'} {health}")
            print(f"  Tests: {summary.get('passed', 0)}✅ {summary.get('failed', 0)}❌ {summary.get('skipped', 0)}⏭️")
            
            # Show capabilities
            caps = exchange_data.get("capabilities", {})
            supported = [k for k, v in caps.items() if v]
            print(f"  Features: {', '.join(supported) if supported else 'None'}")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Comprehensive Exchange Test Suite")
    parser.add_argument(
        "--exchanges", 
        help="Comma-separated list of exchanges to test (default: all)",
        type=str
    )
    parser.add_argument(
        "--output", 
        help="Output file for test results (default: test_results.json)",
        default="test_results.json"
    )
    parser.add_argument(
        "--skip-ws", 
        help="Skip WebSocket tests",
        action="store_true"
    )
    parser.add_argument(
        "--verbose", 
        help="Enable verbose logging",
        action="store_true"
    )
    return parser.parse_args()


async def main():
    """Main test runner."""
    args = parse_arguments()
    
    # Parse exchanges list
    exchanges = None
    if args.exchanges:
        exchanges = [ex.strip() for ex in args.exchanges.split(",")]
        
    # Create test suite
    test_suite = ExchangeTestSuite(args.output)
    
    try:
        # Run tests
        await test_suite.run_all_tests(exchanges, args.skip_ws)
        
        # Print summary
        test_suite.print_summary()
        
        # Exit with appropriate code
        if test_suite.results["test_run"]["failed_tests"] > 0:
            sys.exit(1)  # Some tests failed
        else:
            sys.exit(0)  # All tests passed
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
