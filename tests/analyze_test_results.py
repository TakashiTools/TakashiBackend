"""
Test Results Analyzer

Analyzes test results from the comprehensive exchange test suite.
Provides detailed insights and recommendations.

Usage:
    python analyze_test_results.py test_results.json
    python analyze_test_results.py test_results.json --detailed
"""

import json
import sys
import argparse
from datetime import datetime
from typing import Dict, Any


class TestResultsAnalyzer:
    """Analyzes test results and provides insights."""
    
    def __init__(self, results_file: str):
        self.results_file = results_file
        self.results = self.load_results()
        
    def load_results(self) -> Dict[str, Any]:
        """Load test results from JSON file."""
        try:
            with open(self.results_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Results file not found: {self.results_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in results file: {e}")
            sys.exit(1)
            
    def analyze(self, detailed: bool = False):
        """Analyze test results and provide insights."""
        print("🔍 TEST RESULTS ANALYSIS")
        print("=" * 80)
        
        # Overall statistics
        self.print_overall_stats()
        
        # Exchange-by-exchange analysis
        self.print_exchange_analysis(detailed)
        
        # Recommendations
        self.print_recommendations()
        
    def print_overall_stats(self):
        """Print overall test statistics."""
        run_info = self.results["test_run"]
        
        print(f"\n📊 OVERALL STATISTICS")
        print("-" * 40)
        print(f"🕐 Test Run: {run_info['timestamp']}")
        print(f"🏢 Exchanges: {run_info['total_exchanges']}")
        print(f"🧪 Total Tests: {run_info['total_tests']}")
        print(f"✅ Passed: {run_info['passed_tests']}")
        print(f"❌ Failed: {run_info['failed_tests']}")
        print(f"⏭️  Skipped: {run_info['skipped_tests']}")
        print(f"📈 Success Rate: {run_info['success_rate']}%")
        
        # Health status
        healthy_exchanges = 0
        for exchange_data in self.results["exchanges"].values():
            if exchange_data.get("health_check", {}).get("status") == "healthy":
                healthy_exchanges += 1
                
        print(f"🏥 Healthy Exchanges: {healthy_exchanges}/{run_info['total_exchanges']}")
        
    def print_exchange_analysis(self, detailed: bool):
        """Print detailed exchange analysis."""
        print(f"\n🔍 EXCHANGE ANALYSIS")
        print("-" * 40)
        
        for exchange_name, exchange_data in self.results["exchanges"].items():
            print(f"\n📈 {exchange_name.upper()}:")
            
            # Health status
            health = exchange_data.get("health_check", {})
            health_status = health.get("status", "unknown")
            health_icon = "✅" if health_status == "healthy" else "❌"
            print(f"  {health_icon} Health: {health_status}")
            if health.get("error"):
                print(f"    Error: {health['error']}")
                
            # Test summary
            summary = exchange_data.get("summary", {})
            total = summary.get("total_tests", 0)
            passed = summary.get("passed", 0)
            failed = summary.get("failed", 0)
            skipped = summary.get("skipped", 0)
            
            if total > 0:
                success_rate = (passed / total) * 100
                print(f"  📊 Tests: {passed}✅ {failed}❌ {skipped}⏭️ ({success_rate:.1f}% success)")
            else:
                print(f"  📊 Tests: No tests run")
                
            # Capabilities
            caps = exchange_data.get("capabilities", {})
            supported_features = [k for k, v in caps.items() if v]
            unsupported_features = [k for k, v in caps.items() if not v]
            
            print(f"  🎯 Supported: {', '.join(supported_features) if supported_features else 'None'}")
            if unsupported_features:
                print(f"  🚫 Unsupported: {', '.join(unsupported_features)}")
                
            # Detailed analysis
            if detailed:
                self.print_detailed_exchange_analysis(exchange_name, exchange_data)
                
    def print_detailed_exchange_analysis(self, exchange_name: str, exchange_data: Dict):
        """Print detailed analysis for a specific exchange."""
        print(f"    📋 DETAILED ANALYSIS:")
        
        # REST API analysis
        rest_api = exchange_data.get("rest_api", {})
        if rest_api:
            print(f"      🌐 REST API:")
            for endpoint, result in rest_api.items():
                if isinstance(result, dict):
                    status = result.get("status", "unknown")
                    if status == "success":
                        if "data_count" in result:
                            print(f"        ✅ {endpoint}: {result['data_count']} items")
                        else:
                            print(f"        ✅ {endpoint}: Success")
                    elif status == "error":
                        print(f"        ❌ {endpoint}: {result.get('error', 'Unknown error')}")
                    elif status == "no_data":
                        print(f"        ⚠️  {endpoint}: No data returned")
                    elif status == "skipped":
                        print(f"        ⏭️  {endpoint}: {result.get('skipped', 'Skipped')}")
                        
        # WebSocket analysis
        websocket = exchange_data.get("websocket", {})
        if websocket:
            print(f"      🔌 WebSocket:")
            for stream, result in websocket.items():
                if isinstance(result, dict):
                    status = result.get("status", "unknown")
                    if status == "success":
                        messages = result.get("messages_received", 0)
                        print(f"        ✅ {stream}: {messages} messages")
                    elif status == "timeout":
                        messages = result.get("messages_received", 0)
                        timeout = result.get("timeout_seconds", 0)
                        print(f"        ⏰ {stream}: Timeout after {timeout}s ({messages} messages)")
                    elif status == "error":
                        print(f"        ❌ {stream}: {result.get('error', 'Unknown error')}")
                    elif status == "skipped":
                        print(f"        ⏭️  {stream}: {result.get('skipped', 'Skipped')}")
                        
    def print_recommendations(self):
        """Print recommendations based on test results."""
        print(f"\n💡 RECOMMENDATIONS")
        print("-" * 40)
        
        recommendations = []
        
        # Check for failed tests
        failed_tests = self.results["test_run"]["failed_tests"]
        if failed_tests > 0:
            recommendations.append(f"🔧 Fix {failed_tests} failed tests")
            
        # Check for unhealthy exchanges
        unhealthy_exchanges = []
        for exchange_name, exchange_data in self.results["exchanges"].items():
            health = exchange_data.get("health_check", {}).get("status")
            if health != "healthy":
                unhealthy_exchanges.append(exchange_name)
                
        if unhealthy_exchanges:
            recommendations.append(f"🏥 Investigate unhealthy exchanges: {', '.join(unhealthy_exchanges)}")
            
        # Check for WebSocket timeouts
        timeout_exchanges = []
        for exchange_name, exchange_data in self.results["exchanges"].items():
            websocket = exchange_data.get("websocket", {})
            for stream, result in websocket.items():
                if isinstance(result, dict) and result.get("status") == "timeout":
                    timeout_exchanges.append(f"{exchange_name}.{stream}")
                    
        if timeout_exchanges:
            recommendations.append(f"⏰ Investigate WebSocket timeouts: {', '.join(timeout_exchanges)}")
            
        # Check for unsupported features
        feature_coverage = {}
        for exchange_name, exchange_data in self.results["exchanges"].items():
            caps = exchange_data.get("capabilities", {})
            for feature, supported in caps.items():
                if feature not in feature_coverage:
                    feature_coverage[feature] = {"supported": 0, "total": 0}
                feature_coverage[feature]["total"] += 1
                if supported:
                    feature_coverage[feature]["supported"] += 1
                    
        for feature, coverage in feature_coverage.items():
            if coverage["supported"] == 0:
                recommendations.append(f"🚫 No exchanges support {feature} - consider implementation")
            elif coverage["supported"] < coverage["total"]:
                missing = coverage["total"] - coverage["supported"]
                recommendations.append(f"📈 Improve {feature} support ({missing} exchanges missing)")
                
        if not recommendations:
            recommendations.append("🎉 All systems operational - no issues detected!")
            
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
            
    def export_summary(self, output_file: str = "test_summary.txt"):
        """Export a text summary of the analysis."""
        try:
            with open(output_file, 'w') as f:
                f.write("EXCHANGE TEST RESULTS SUMMARY\n")
                f.write("=" * 50 + "\n\n")
                
                run_info = self.results["test_run"]
                f.write(f"Test Run: {run_info['timestamp']}\n")
                f.write(f"Exchanges: {run_info['total_exchanges']}\n")
                f.write(f"Total Tests: {run_info['total_tests']}\n")
                f.write(f"Passed: {run_info['passed_tests']}\n")
                f.write(f"Failed: {run_info['failed_tests']}\n")
                f.write(f"Skipped: {run_info['skipped_tests']}\n")
                f.write(f"Success Rate: {run_info['success_rate']}%\n\n")
                
                f.write("EXCHANGE DETAILS:\n")
                f.write("-" * 30 + "\n")
                
                for exchange_name, exchange_data in self.results["exchanges"].items():
                    health = exchange_data.get("health_check", {}).get("status", "unknown")
                    summary = exchange_data.get("summary", {})
                    
                    f.write(f"\n{exchange_name.upper()}:\n")
                    f.write(f"  Health: {health}\n")
                    f.write(f"  Tests: {summary.get('passed', 0)}✅ {summary.get('failed', 0)}❌ {summary.get('skipped', 0)}⏭️\n")
                    
            print(f"\n📄 Summary exported to: {output_file}")
        except Exception as e:
            print(f"❌ Failed to export summary: {e}")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Analyze Exchange Test Results")
    parser.add_argument(
        "results_file",
        help="Path to test results JSON file"
    )
    parser.add_argument(
        "--detailed",
        help="Show detailed analysis",
        action="store_true"
    )
    parser.add_argument(
        "--export",
        help="Export summary to text file",
        action="store_true"
    )
    return parser.parse_args()


def main():
    """Main analyzer function."""
    args = parse_arguments()
    
    analyzer = TestResultsAnalyzer(args.results_file)
    analyzer.analyze(args.detailed)
    
    if args.export:
        analyzer.export_summary()


if __name__ == "__main__":
    main()
